import ConfigParser
from pymongo import MongoClient

# Connects to mongo and returns a MongoClient
def connect_to_mongo():

    credentials = ConfigParser.ConfigParser()
    #TODO: fix this malarkey
    credentials.read("credentials.ini")

    host = credentials.get("Mongo", "connection")
    user = credentials.get("Mongo", "user")
    password = credentials.get("Mongo", "password")
    db = credentials.get("Mongo", "database")
    connection_url = "mongodb://" + user + ":" + password + "@" + host + "/" + db + "?authSource=admin"

    client = MongoClient(connection_url)
    return client


connection = None


def get_connection():
    global connection
    if not connection:
        connection = connect_to_mongo()  # possibly with configuration vars passed in
    return connection
