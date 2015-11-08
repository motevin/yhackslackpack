import ConfigParser
import requests
import datetime
import pytz
from pymongo import MongoClient

access_token = ''
venmo_id = ''

# Connects to mongo and returns a MongoClient
def connect_to_mongo():

    credentials = ConfigParser.ConfigParser()
    credentials.read("../../credentials.ini")

    host = credentials.get("Mongo", "connection")
    user = credentials.get("Mongo", "user")
    password = credentials.get("Mongo", "password")
    db = credentials.get("Mongo", "database")
    connection_url = "mongodb://" + user + ":" + password + "@" + host + "/" + db + "?authSource=admin"

    client = MongoClient(connection_url)
    return client[db]

def send_to_bot():
    pass

def recieve_from_bot():
    pass

def update_database(user_id, db, access_token, expires_date, refresh_token):
    return db.users.update_one({'_id': user_id},
        {'$set': {
            'venmo': {
                'access_token': access_token,
                'expires_in': expires_date,
                'refresh_token': refresh_token
                }
            },
        '$currentDate': {'lastModified': True}
        })

def get_access_token(user_id):
    config = ConfigParser.ConfigParser()
    config.read('../../credentials.ini')
    db = connect_to_mongo()
    venmo_auth = db.users.find_one({'_id': user_id}, {'venmo': 1})
    if (venmo_auth == None):
        user_doc = db.users.find_one({'_id': user_id})
        if (user_doc == None):
            create_user_doc = db.users.insert_one({'_id': user_id})
        create_venmo_auth = update_database(user_id, db, '', '', '')
        auth_url = 'https://api.venmo.com/v1/oauth/authorize?client_id=' + config.get('Venmo', 'clientId') + '&scope=make_payments%20access_payment_history%20access_feed%20access_profile%20access_email%20access_phone%20access_balance%20access_friends&response_type=code'
        print auth_url
        # send_to_bot(auth_url)
        # receive_from_bot()
        code = 'd611f37a8869117be6a000778077baf1'
        post_data = {
            'client_id': config.get('Venmo', 'clientId'),
            'client_secret': config.get('Venmo', 'clientSecret'),
            'code': code
            }
        response = requests.post('https://api.venmo.com/v1/oauth/access_token', post_data)
        response_dict = response.json()
        access_token = response_dict['access_token']
        expires_in = response_dict['expires_in']
        expires_date = (datetime.datetime.utcnow().replace(tzinfo = pytz.utc) + datetime.timedelta(seconds=expires_in))
        refresh_token = response_dict['refresh_token']
        update_access_token = update_database(user_id, db, access_token, expires_date, refresh_token)
        return access_token
    else:
        expires_date = venmo_auth['venmo']['expires_in'].replace(tzinfo = pytz.utc)
        if (expires_date < datetime.datetime.utcnow().replace(tzinfo = pytz.utc)):
            post_data = {
                'client_id': config.get('Venmo', 'clientId'),
                'client_secret': config.get('Venmo', 'clientSecret'),
                'refresh_token': venmo_auth['venmo']['refresh_token']
                }
            response = requests.post('https://api.venmo.com/v1/oauth/access_token', post_data)
            response_dict = response.json()
            access_token = response_dict['access_token']
            expires_in = response_dict['expires_in']
            expires_date = (datetime.datetime.utcnow().replace(tzinfo = pytz.utc) + datetime.timedelta(seconds=expires_in))
            update_database(user_id, db, access_token, expires_date, response_dict['refresh_token'])
            return access_token
        return venmo_auth['venmo']['access_token']

def _get_venmo_id():
    global access_token
    response = requests.get('http://api.venmo.com/v1/me?access_token=' + access_token)
    response_dict = response.json()
    if ('error' in response_dict):
        venmo_error(response_dict['error'])
    global venmo_id
    venmo_id = response_dict['data']['user']['id']

def _get_pagination(initial, access_token):
    final_list = []
    while True:
        final_list += initial['data']
        if (not initial['pagination'] or initial['pagination']['next'] == None):
            break
        else:
            response = requests.get(initial['pagination']['next'] + '&access_token=' + access_token)
            response_dict = response.json()
            if ('error' in response_dict):
                venmo_error(response_dict['error'])
            initial = response_dict
    return final_list

def _find_friend(list, username):
    for friend in list:
        if (friend['username'].lower() == username.lower()):
            return friend['id']
    return None

def get_venmo_balance():
    global access_token
    response = requests.get('https://api.venmo.com/v1/me?access_token=' + access_token)
    response_dict = response.json()
    if ('error' in response_dict):
        venmo_error(response_dict['error'])
    return response_dict['data']['balance']

def venmo_payment(audience, which, amount, note, recipients):
    global access_token
    global venmo_id
    url = 'https://api.venmo.com/v1/payments'
    amount_str = str(amount)
    if (which == 'charge'):
        amount_str = '-' + amount_str
    friends_response = requests.get('https://api.venmo.com/v1/users/' + venmo_id + '/friends?access_token=' + access_token)
    friends_response_dict = friends_response.json()
    if ('error' in friends_response_dict):
        venmo_error(friends_response_dict['error'])
    full = _get_pagination(friends_response_dict, access_token)
    for r in recipients:
        post_data = {
            'access_token': access_token
            }
        if r.startswith('phone:'):
            id = r[6:]
            post_data['phone'] = id
        elif r.startswith('email:'):
            id = r[6:]
            post_data['email'] = id
        else:
            id = _find_friend(full, r)
            if (id == None):
                parse_error('You are not friends with ' + r)
                return
            post_data['user_id'] = id
        post_data['note'] = note
        post_data['amount'] = amount_str
        post_data['audience'] = audience
        response = requests.post(url, post_data)
        response_dict = response.json()
        if ('error' in response_dict):
            pass
            # send response_dict['error']['message']
        else:
            name = ''
            target = response_dict['data']['payment']['target']
            if (target['type'] == 'user'):
                name = target['user']['display_name']
            elif (target['type'] == 'phone'):
                name = target['phone']
            elif (target['type'] == 'email'):
                name = target['email']
            if (amount_str.startswith('-')):
                print 'Successfully charged ' + name + ' $' '{:0,.2f}'.format(response_dict['data']['payment']['amount']) + ' for ' + response_dict['data']['payment']['note'] + '. Audience is ' + audience
            else:
                print 'Successfully paid ' + name + ' $' '{:0,.2f}'.format(response_dict['data']['payment']['amount']) + ' for ' + response_dict['data']['payment']['note'] + '. Audience is ' + audience


def venmo_pending(which):
    global access_token
    global venmo_id
    message = ''
    url = 'https://api.venmo.com/v1/payments?access_token=' + access_token + '&status=pending'
    response = requests.get(url)
    response_dict = response.json()
    if ('error' in response_dict):
        venmo_error(response_dict['error'])
    full = _get_pagination(response_dict, access_token)
    for pending in response_dict['data']:
        if (which == 'to'):
            if (pending['actor']['id'] != venmo_id):
                message += pending['actor']['display_name'] + ' requests $' + '{:0,.2f}'.format(pending['amount']) + ' for ' + pending['note'] + ' | ID: ' + pending['id'] + '\n'
        elif (which == 'from'):
            if (pending['actor']['id'] == venmo_id):
                if (pending['target']['type'] == 'user'):
                    message += pending['target']['user']['display_name'] + ' owes you $' + '{:0,.2f}'.format(pending['amount']) + ' ' + pending['note'] + ' | ID: ' + pending['id'] + '\n'
    return message[0:-1]

def venmo_complete(which, number):
    global access_token
    url = 'https://api.venmo.com/v1/payments/' + str(number)
    action = ''
    if (which == 'accept'):
        action = 'approve'
    elif (which == 'reject'):
        action = 'deny'
    put_data = {
        'access_token': access_token,
        'action': action
        }
    response = requests.put(url, put_data)
    response_dict = response.json()
    if ('error' in response_dict):
        venmo_error(response_dict['error'])

def help():
    print ('Venmo help\n'
           'Commands:\n'
           'venmo balance\n'
           '    returns your Venmo balance\n'
           'venmo (audience) pay/charge amount for note to recipients\n'
           '    example: venmo public charge $10.00 for lunch to testuser phone:5555555555 email:example@example.com\n'
           '    audience (optional) = public OR friends OR private\n'
           '        defaults to friends if omitted\n'
           '    pay/charge = pay OR charge\n'
           '    amount = Venmo amount\n'
           '    note = Venmo message\n'
           '    recipients = list of recipients, can specify Venmo username, phone number prefixed with phone: or email prefixed with email:\n'
           'venmo pending (to OR from)\n'
           '    returns pending venmo charges, defaults to to\n'
           '    also returns ID for payment completion\n'
           'venmo complete accept/reject number\n'
           '    accept OR reject a payment with the given ID\n'
           'venmo help\n'
           '    this help message')


def venmo_error(dict):
    print dict['message']
    exit()

def parse_error(error_message):
    print error_message

def _find_last_str_in_list(list, str):
    index = -1
    for i in range(len(list)):
        if (list[i].lower() == str.lower()):
            index = i
    return index

def parse_message(message):
    split_message = message.split()
    if (len(split_message) == 1):
        help()
    elif (split_message[1].lower() == 'help'):
        help()
    elif (split_message[1].lower() == 'balance'):
        balance = get_venmo_balance()
        print balance
        # send to bot
    elif (split_message[1].lower() == 'pending'):
        if (len(split_message) == 2):
            venmo_pending('to')
        elif (len(split_message) == 3):
            which = split_message[2].lower()
            if (which == 'to' or which == 'from'):
                venmo_pending(which)
            else:
                parse_error('Valid pending commands\npending\npending to\npending from')
        else:
            parse_error('Valid pending commands\npending\npending to\npending from')
    elif (split_message[1].lower() == 'complete'):
        if (len(split_message) == 4):
            which = split_message[2].lower()
            if (which == 'accept' or which == 'reject'):
                number = -1
                try:
                    number = int(split_message[3])
                except:
                    parse_error('Payment completion number must be a number')
                    return
                venmo_complete(which, number)
            else:
                parse_error('Valid complete commands\nvenmo complete accept #\nvenmo complete reject #')
        else:
            parse_error('Valid complete commands\nvenmo complete accept #\nvenmo complete reject #')
    elif (len(split_message) <= 2):
        parse_error('Invalid payment string')
    elif (split_message[1].lower() == 'charge' or split_message[2].lower() == 'charge' or
          split_message[1].lower() == 'pay' or split_message[2].lower() == 'pay'):
        audience = 'friends'
        if (split_message[2].lower() == 'charge' or split_message[2].lower() == 'pay'):
            audience = split_message[1].lower()
            if (audience != 'public' and audience != 'friends' and audience != 'private'):
                parse_error('Valid payment sharing commands\npublic\nfriend\nprivate')
                return
            del split_message[1]
        which = split_message[1]
        if (len(split_message) <= 6):
            parse_error('Invalid payment string')
            return
        amount_str = split_message[2]
        amount = 0
        if (amount_str.startswith('$')):
            amount_str = amount_str[1:]
        try:
            amount = float(amount_str)
        except:
            parse_error('Invalid amount')
            return
        if (split_message[3].lower() != 'for'):
            parse_error('Invalid payment string')
            return
        to_index = _find_last_str_in_list(split_message, 'to')
        if (to_index < 5):
            parse_error('Could not find recipients')
            return
        note = ' '.join(split_message[4:to_index])
        recipients = split_message[to_index + 1:]
        venmo_payment(audience, which, amount, note, recipients)

def main(user_id):
    global access_token
    access_token = get_access_token(user_id)
    _get_venmo_id()
    parse_message('venmo')
    parse_message('venmo help')

if __name__ == '__main__':
    main('U03FNCQL3')