import time
import ConfigParser
from slackclient import SlackClient

def run(apikey):
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
                    if (response[0]['channel'][0] == 'D'):
                        sc.rtm_send_message(response[0]['channel'], 'yo')
            time.sleep(1)
    else:
        print 'connection failed'

def main():
    config = ConfigParser.ConfigParser()
    config.read('../../credentials.ini')
    token = config.get('Slack', 'apikey')
    run(token)

if __name__ == '__main__':
    main()