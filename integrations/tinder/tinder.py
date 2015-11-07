import pynder
import ConfigParser
from pymongo import MongoClient

session = None

# Connects to mongo and returns a MongoClient
def connect_to_mongo():

    credentials = ConfigParser.ConfigParser()
    credentials.read("../../credentials.ini")

    # client = MongoClient('mongodb://admin:yhackslackpack@104.236.11.224:27017/yhackslackpack?authSource=admin')
    host = credentials.get("Mongo", "connection")
    user = credentials.get("Mongo", "user")
    password = credentials.get("Mongo", "password")
    db = credentials.get("Mongo", "database")
    connection_url = "mongodb://" + user + ":" + password + "@" + host + "/" + db + "?authSource=admin"

    client = MongoClient(connection_url)
    return client[db]

# Get sesion credentials for user in mongo
# If the user/required details do not exist in mongo, it queries the bot for them
def get_tinder_creds(user):
    db = connect_to_mongo()
    user_tinder_data = db.users.find_one({"name": user}, {"tinder": 1})
    access_token = user_tinder_data['tinder']['access_token']
    fbid = user_tinder_data['tinder']['fbid']
    print access_token + "\n" + fbid
    return pynder.Session(fbid, access_token)

# Creates a global Tinder session for the specified user and executes the given query
def main(user):
    global session
    session = get_tinder_creds(user)
    users = session.nearby_users()
    for user in users[:5]:
        print user.like()

if __name__ == '__main__':
    main("U03FN2LLB")