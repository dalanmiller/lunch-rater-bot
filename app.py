from slackclient import SlackClient
import logging
import asyncio
import datetime
from functools import partial
import json
import requests
import rethinkdb as r
import os
from pprint import pprint


if 'SLACK_TOKEN' in os.environ:
    LUNCHTIME_GUY = sys.env['SLACK_TOKEN']
else:
    from secrets import LUNCHTIME_GUY

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
    datefmt='%m-%d %H:%M:%S'
    )

conn = r.connect("localhost", 28015)

try:
    r.db_create("asyncio").run(conn)
except:
    pass
try:
    r.db("asyncio").table_create("lunch").run(conn)
except:
    pass
try:
    r.db("asyncio").table_create("lunch").run(conn)
except:
    pass

conn.close()

r.set_loop_type('asyncio')
db = r.db("asyncio").table("lunch")
client = SlackClient(LUNCHTIME_GUY)
current_channel = "#random"

def thumbs(text):
    if " :thumbsup:" in text or " :+1:" in text:
        return True
    elif " :thumbsdown:" in text or ":-1:" in text:
        return True
    else:
        return False


async def get_present_users(client):

    res = await loop.run_in_executor(client.api_call("users.list", presence=True))
    user_list = json.loads(bytes.decode(res))['members']
    present_users = [user for user in user_list.items() if user['presence'] == 'active']

    return present_users

async def ask_present_users(client):

    # async for user in get_present_users():
    message = {
        "channel": current_channel,
        "text": 'Howdy <!here>, how did you like your lunch today? Give a :+1: or :-1: to @lunchtimeguy (v2) to vote!',
        "as_user": True,
        "icon_emoji": ":yum:"
    }

    await loop.run_in_executor(None, partial(client.api_call, "chat.postMessage", **message))

async def listen_for_responses(client):


    raw_users = await loop.run_in_executor(None, client.api_call, "users.list")
    logging.info(raw_users)
    user_list = json.loads(bytes.decode(raw_users))['members']

    user_map = {}
    for user in user_list:
        user_map[user['id']] = user['name']

    conn = await r.connect("localhost", 28015)
    todays_date = datetime.datetime.today().strftime("%Y-%m-%d")
    await db.insert({
        "id": todays_date,
        "score": 0
    }).run(conn)
    conn.close()

    already_voted = set()

    if client.rtm_connect():
        logging.info("Successful Slack RTM connection, entering subscribe loop")
        while True:
            events = await loop.run_in_executor(None, client.rtm_read)
            for event in events:
                if "type" in event:
                    if event["type"] == "message" and "text" in event:
                        if "score" in event["text"] and event['user'] != "U0L810UD6":
                            logging.info(event)

                            score = await db.get(todays_date)['score'].run(conn)
                            logging.info(score)

                            message = {
                                "channel": current_channel,
                                "text": 'The lunchtime score for today is {}'.format(score),
                                "as_user": True,
                                "icon_emoji": ":yum:"
                            }

                            await loop.run_in_executor(None, partial(client.api_call, "chat.postMessage", **message))

                        elif "<@U0L810UD6>" in event["text"] and event['user'] in already_voted:
                            logging.info(event)

                            name = user_map[event['user']]
                            message = {
                                "channel": current_channel,
                                "text": 'You\'ve already voted @{}, be quiet.'.format(name),
                                "as_user": True,
                                "icon_emoji": ":yum:"
                            }

                            await loop.run_in_executor(None, partial(client.api_call, "chat.postMessage", **message))

                        elif "<@U0L810UD6>" in event["text"] and thumbs(event["text"]):
                            logging.info(event)

                            update_doc = None
                            if ":+1:" in event["text"] or ":thumbsup:" in event["text"]:
                                update_doc = {
                                    "score": r.row["score"].add(1)
                                }
                            elif ":-1:" in event["text"] or ":thumbsdown:" in event["text"]:
                                update_doc = {
                                    "score": r.row["score"].sub(1)
                                }

                            if update_doc:
                                conn = await r.connect("localhost", 28015)
                                await db \
                                    .get(todays_date)\
                                    .update(update_doc)\
                                    .run(conn)
                            already_voted.add(event['user'])

            await asyncio.sleep(0.2)

loop = asyncio.get_event_loop()
# loop.create_task(ask_present_users(client))
loop.create_task(listen_for_responses(client))

try:
    loop.run_forever()
except (KeyboardInterrupt, SystemExit):
    logging.info("Pending tasks at exit: %s" % asyncio.Task.all_tasks(loop))
    loop.close()
