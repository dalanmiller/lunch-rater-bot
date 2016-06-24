FROM python:3.5.1-alpine

RUN mkdir -p /usr/app
VOLUME .:/usr/app

WORKDIR /usr/app
RUN pip install -r requirements.txt

CMD python app.py
