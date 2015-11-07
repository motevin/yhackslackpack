import pynder
import sys
import ConfigParser
import pika
import json
from pymongo import MongoClient

session = None
connection = pika.BlockingConnection(pika.ConnectionParameters(
        host='localhost'))
channel = connection.channel()

def get_likes_remaining(user):
    likes = str(session.likes_remaining)
    print likes
    send_message_and_await_response(user, likes)

#
# MESSAGE PASSING METHODS
#

def wait_for_response(queue):
    print "Waiting for response from slack " + queue
    channel.basic_consume(callback, queue=queue, no_ack=True, consumer_tag=queue)
    channel.start_consuming()

# This is what you do when you get back a response
def callback(ch, method, properties, body):
    print "Tinder Received %r" % (body,)
    parse(body)

def send_message_and_await_response(queue, message):
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "\nMessage: " + message
    wait_for_response(queue)

def send_message_and_exit(queue, message):
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "\nMessage: " + message
    connection.close()


##############################################

# Connects to mongo and returns a MongoClient
def connect_to_mongo():

    credentials = ConfigParser.ConfigParser()
    credentials.read("/Users/tevin/dev/yhackslackpack/credentials.ini")

    host = credentials.get("Mongo", "connection")
    user = credentials.get("Mongo", "user")
    password = credentials.get("Mongo", "password")
    db = credentials.get("Mongo", "database")
    connection_url = "mongodb://" + user + ":" + password + "@" + host + "/" + db + "?authSource=admin"

    client = MongoClient(connection_url)
    return client[db]

# Get session credentials for user in mongo
# If the user/required details do not exist in mongo, it queries the bot for them
def get_tinder_creds(user):
    db = connect_to_mongo()
    print user
    user_tinder_data = db.users.find_one({"name": user}, {"tinder": 1})
    print user_tinder_data
    if user_tinder_data:
        access_token = user_tinder_data['tinder']['access_token']
        fbid = user_tinder_data['tinder']['fbid']
        print access_token + "\n" + fbid
        return pynder.Session(fbid, access_token)
    else:
        quit()

def get_user_from_json(json_obj):
    return json.loads(json_obj)['user']

def get_message_from_json(json_obj):
    return json.loads(json_obj)['message']

def parse(user, message):
    print message
    if "likes" in message:
        get_likes_remaining(user)
    else:
        send_message_and_exit(user, message)
# Creates a global Tinder session for the specified user and executes the given query
def main(args):
    global session
    user = get_user_from_json(args)
    session = get_tinder_creds(user)

    message = get_user_from_json(args)
    parse(user, message)

if __name__ == '__main__':
    print "Starting Tinder"
    main(sys.argv)
