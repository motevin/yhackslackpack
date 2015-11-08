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
tinder_user = None
user = None
#
# TINDERIZER
#
def get_likes_remaining(user):
    likes = str(session.likes_remaining)
    send_message_and_exit(user, likes)

def swipe(ch, method, properties, body):
    channel.stop_consuming()
    if body == "swipe":
        if tinder_user.like():
            send_message_and_exit(user, "YOU HAVE A MATCH!")
    elif body == "nah":
        tinder_user.dislike()
    else:
        send_message_and_exit(user, "Yeah should probably not be on Tinder at work")

def get_nearby_user(user):
    global tinder_user
    tinder_user = session.nearby_users()[0]
    name = tinder_user.name
    bio = tinder_user.bio
    first_photo = tinder_user.photos[0]
    response = "*Name* : " + name + "\n" + "*Bio* : " + bio + "\n" + "*Photo: * : " + first_photo
    send_message_and_await_response(user, response, swipe)
    get_nearby_user(user)

#
# MESSAGE PASSING METHODS
#

def wait_for_response(queue):
    print "Waiting for response from slack " + queue
    channel.basic_consume(callback, queue=queue, no_ack=True, consumer_tag=queue)
    channel.start_consuming()

def wait_for_response(queue, callback):
    print "Waiting for response from slack " + queue
    channel.basic_consume(callback, queue=queue, no_ack=True, consumer_tag=queue)
    channel.start_consuming()

# This is what you do when you get back a response
def callback(ch, method, properties, body):
    print "Tinder Received %r" % (body,)
    channel.stop_consuming()

def send_message_and_await_response(queue, message):
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "Message: " + message
    wait_for_response(queue)

def send_message_and_await_response(queue, message, callback):
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "Message: " + message
    wait_for_response(queue, callback)

def send_message_and_exit(queue, message):
    channel.queue_declare(queue=queue)
    channel.basic_publish(exchange='',routing_key=queue,body=message)
    print "Sending message to service for user " + queue
    print "\nMessage: " + message
    channel.queue_delete()
    connection.close()

##############################################

# Connects to mongo and returns a MongoClient
def connect_to_mongo():

    credentials = ConfigParser.ConfigParser()
    credentials.read("../credentials.ini")

    host = credentials.get("Mongo", "connection")
    user = credentials.get("Mongo", "user")
    password = credentials.get("Mongo", "password")
    db = credentials.get("Mongo", "database")
    connection_url = "mongodb://" + user + ":" + password + "@" + host + "/" + db + "?authSource=admin"

    client = MongoClient(connection_url)
    return client[db]

def write_auth_key(ch, method, properties, body):
    channel.stop_consuming()
    channel.queue_delete()
    print "Authenticating"
    credentials = body.split()
    fbid = credentials[0]
    authtoken = credentials[1]

    db = connect_to_mongo()
    authenticated =  db.users.update_one({'_id': user},
        {'$set': {
            'tinder': {
                'fbid': fbid,
                'access_token': authtoken,
                }
            },
        '$currentDate': {'lastModified': True}
        })
    if authenticated:
        send_message_and_exit(user, "Authentication received.")
    else:
        send_message_and_exit(user, "Authentication failed.")

def do_auth(user):
    response = "To find your facebook id, go to http://findmyfbid.com/ and follow the instructions.\n " \
               " To get your auth key, go to" \
               " https://www.facebook.com/dialog/oauth?client_id=464891386855067&redirect_uri=https://www.facebook.com/connect/login_success.html&scope=basic_info,email,public_profile,user_about_me,user_activities,user_birthday,user_education_history,user_friends,user_interests,user_likes,user_location,user_photos,user_relationship_details&response_type=token" \
               " and pick the auth token out of the URL you are redirected to. Respond with your fbid & auth token " \
               " i.e <fbid> <authtoken>"
    send_message_and_await_response(user, response, write_auth_key)

# Get session credentials for user in mongo
# If the user/required details do not exist in mongo, it queries the bot for them
def get_tinder_creds(user):
    db = connect_to_mongo()
    print user
    user_tinder_data = db.users.find_one({"_id": user}, {"tinder": 1})
    if user_tinder_data:
        access_token = user_tinder_data['tinder']['access_token']
        fbid = user_tinder_data['tinder']['fbid']
        return pynder.Session(fbid, access_token)
    else:
        do_auth(user)

def get_user_from_json(json_obj):
    return json.loads(json_obj)['user']

def get_message_from_json(json_obj):
    return json.loads(json_obj)['message']

def parse(user, message):
    if "likes" in message:
        get_likes_remaining(user)
    elif "nearby" in message:
        get_nearby_user(user)
    elif "auth" in message:
        write_auth_key(user)

# Creates a global Tinder session for the specified user and executes the given query
def main(args):
    global session
    global user
    user = get_user_from_json(args)
    try:
        session = get_tinder_creds(user)
        print("Succesfully connected to tinder")
    except pynder.errors.RequestError:
        do_auth(user)

    message = get_message_from_json(args)
    parse(user, message)

if __name__ == '__main__':
    print "Starting Tinder"
    main(sys.argv)
