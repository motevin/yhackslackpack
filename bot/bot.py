import time
import ConfigParser
import pika
import imp
import json
from threading import Thread
from slackclient import SlackClient

PROJECT_ROOT = "/Users/tevin/dev/yhackslackpack"
connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()
sc = None
slack_channel = None

def wait_for_response(queue):
    channel.queue_declare(queue=queue)
    print "Waiting for response from user " + queue
    channel.basic_consume(callback, queue=queue, no_ack=True, consumer_tag=queue)
    channel.start_consuming()

def callback(ch, method, properties, body):
    print "Bot Received %r" % (body,)
    sc.rtm_send_message(slack_channel, body)
    channel.stop_consuming()

#==========================
# COMMUNICATE WITH SERVICES
#=========================
# Sends messages to the service with the format
#
# {
#     "user":""
#     "message":""
# }
#
# It's up to the service to parse the message.
# Bot will wait for a response to post back to slack

def send_message_and_await_response(queue, message):
    print "Service already running"
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "\nMessage: " + message
    wait_for_response(queue)

def start_service_and_await_response(service, user, message):
    print "Starting service " + service
    service_obj = get_service_module(service)
    payload = {}
    payload['user'] = user
    payload['message'] = message
    t = Thread(target=service_obj.main, args=(json.dumps(payload),))
    t.start()
    wait_for_response(user)

def get_service_module(service):
    config = ConfigParser.ConfigParser()
    config.read(PROJECT_ROOT + "/modules.ini")
    service_path = PROJECT_ROOT + config.get('Modules', service)
    return imp.load_source('module.name', service_path)

# Process input from slack and either spin up the related service
# or send the message as part of an ongoing exchange
def process(user, message):
    global channel
    # If a queue exists for the user, send it on that queue
    try:
        channel.queue_declare(queue=user, passive=True)
        send_message_and_await_response(user, message)

    #Service is currently not running. We need to start it. Idk how to MQ
    except pika.exceptions.ChannelClosed:
        channel = connection.channel()
        service = "tinder" #assume the service name is the first thing in the message. Yes its janky. This is a fucking hackathon
        message.strip(service)
        print "Checking message: " + message
        start_service_and_await_response(service, user, message)

def run(apikey):
    global sc, slack_channel
    sc = SlackClient(apikey)
    if sc.rtm_connect():
        global generalID
        generalID = sc.server.channels.find('general').id
        while True:
            response = sc.rtm_read()
            if response != []:
                print response
                if 'type' in response[0] and response[0]['type'] == 'message':
                    # direct messages start with D
                    if (response[0]['channel'][0] == 'D' and response[0]['user'] != 'U0E2LB8C8'):
                        slack_channel = response[0]['channel']
                        t = Thread(target=process, args=(response[0]['user'],response[0]['text']))
                        t.start()
            time.sleep(1)
    else:
        print 'connection failed'


def main():
    config = ConfigParser.ConfigParser()
    config.read("/Users/tevin/dev/yhackslackpack/credentials.ini")
    token = config.get('Slack', 'apikey')
    run(token)


if __name__ == '__main__':
    main()