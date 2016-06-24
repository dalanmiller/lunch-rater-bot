from functools import partial
from pprint import pprint
from slackclient import SlackClient
from dateutil.parser import *
from datetime import *
import asyncio
import datetime
import json
import logging
import os
import requests
import arrow

if 'SLACK_TOKEN' in os.environ:
    LUNCHTIME_GUY = os.environ['SLACK_TOKEN']
else:
    from secrets import LUNCHTIME_GUY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M:%S'
    )

client = SlackClient(LUNCHTIME_GUY)
current_channel = "#random"

def thumbs(text):
    if " :thumbsup:" in text or " :+1:" in text:
        return True
    elif " :thumbsdown:" in text or ":-1:" in text:
        return True
    else:
        return False

async def lunchtime():
    r = await loop.run_in_executor(None, partial(requests.get, "https://zerocater.com/m/73DB/json"))
    lunch_json = json.loads(r.text)
    title = lunch_json['meals'][0]['meal_name']
    vendor = lunch_json['meals'][0]['vendor_name']
    arriving_text = lunch_json['meals'][0]['meal_time']
    arriving_datetime = parse(arriving_text)

    menu_items = []

    for x in lunch_json['meals'][0]['meal_items']:
    	out = u"_{}_\n{}".format(
    		x['name'],
    		x['description'].strip()
    	)
    	menu_items.append(out)

    menu_items = "\n\n".join(menu_items)

    lunch_text = r"""
%s | %s | arriving %s

%s

""" % (title, vendor, arrow.get(arriving_datetime).humanize(), menu_items)

    #Add the image if it exists
    if 'vendor_image' in lunch_json['meals'][0]:
    	lunch_text += "\n{}".format(lunch_json['meals'][0]['vendor_image'])

    return lunch_text




async def listen_for_lunchtime(client):
    if client.rtm_connect():
        logging.info("Successful Slack RTM connection, entering subscribe loop")
        while True:
            events = await loop.run_in_executor(None, client.rtm_read)
            for event in events:
                if 'type' in event and event["type"] == "message" and "text" in event and event['text'].lower() == 'lunchtime':
                    pprint(event)
                    lunch_text = await lunchtime()

                    message = {
                        "channel": event['channel'],
                        "text": lunch_text,
                        "as_user": True,
                        "icon_emoji": ":yum:"
                    }

                    await loop.run_in_executor(None, partial(client.api_call, "chat.postMessage", **message))


loop = asyncio.get_event_loop()
loop.create_task(listen_for_lunchtime(client))

try:
    loop.run_forever()
except (KeyboardInterrupt, SystemExit):
    logging.info("Pending tasks at exit: %s" % asyncio.Task.all_tasks(loop))
    loop.close()
