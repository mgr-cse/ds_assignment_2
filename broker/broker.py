from flask import Flask
from flask import request
from flask_sqlalchemy import SQLAlchemy

import threading
import time
import socket
import requests

broker_manager_address = '172.17.0.2:5000'
heartbeat_time = 2
app_kill_event = False

username = 'mattie'
password = 'password'
database = 'psqlqueue'
db_port = '5432'

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = f"postgresql://{username}:{password}@localhost:{db_port}/{database}"

# queue database structures
db = SQLAlchemy(app)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    topic_id = db.Column(db.Integer, nullable=False)
    partition_id = db.Column(db.Integer, nullable=False)
    message_content = db.Column(db.String(255))
    
    # producer sends some info to uniquely identify the message
    producer_client = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    random_string = db.Column(db.String(257), nullable=False)

# debugging functions
def print_thread_id():
    print('Request handled by worker thread:', threading.get_native_id())

def return_message(status:str, message=None):
    content = dict()
    content['status'] = status
    if message is not None:
        content['message'] = message
    return content

# functions for handelling each endpoint
@app.route('/store_message', methods=['POST'])
def topic_register_request():
    print_thread_id()
    content_type = request.headers.get('Content-Type')
    if content_type != 'application/json':
        return return_message('failure', 'Content-Type not supported')

    # parse content
    topic_id = None
    partition_id = None
    message_content = None
    producer_client = None
    timestamp = None
    random_string = None
    try:
        receive = request.json
        topic_id = receive['topic_name']
        partition_id = receive['partition_id']
        message_content = receive['message_content']
        producer_client = receive['producer_client']
        timestamp = receive['timestamp']
        random_string = receive['random_string']
    except:
        return return_message('failure', 'Error While Parsing json')
    
    # database
    try:
        # check if the message was already written
        message = Message.query.filter_by(producer_client=producer_client, timestamp=timestamp, random_string=random_string).first()
        if message is not None:
            return return_message('sucess')

        # write the messaage
        message = Message(
                topic_id=topic_id,
                partition_id=partition_id,
                message_content=message_content,
                producer_client=producer_client,
                timestamp=timestamp,
                random_string = random_string
            )

        # write ahead
        db.session.add(message)
        db.flush()
        
        # commit transaction
        db.session.commit()
        return return_message('success')
    except:
        return return_message('failure', 'Error while querying/comitting to database')

@app.route('/retreive_messages', methods=['GET'])
def topic_get_request():
    print_thread_id()
    min_id = None
    try:
        min_id = request.args.get('min_id')
        min_id = int(min_id)
    except:
        return return_message('failure', 'Error while parsing request')
    
    try:
        messages = Message.query.filter(Message.id > min_id).order_by(Message.id)
        message_list = []
        for m in messages:
            message_list.append(
                (
                    m.topic_id,
                    m.partition_id,
                    m.message_content,
                    m.producer_client,
                    m.timestamp,
                    m.random_string
                )
            )
        max_id = 0
        if len(messages) > 0:
            max_id = messages[-1].id
        return {
            "status": 'success',
            "max_id": max_id,
            "messages": message_list
        }
    except:
        return return_message('Failure','Error while querying/commiting database')

# heartbeat function
def heartbeat(beat_time):
    while True:
        if app_kill_event:
            return
        print('heart beat <3')
        # get self ip
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()

        # send ip to broker_manager
        res = requests.post('http://' + broker_manager_address + '/broker/heartbeat', json={"ip": ip, "port": 5000})
        time.sleep(beat_time)

if __name__ == "__main__":
    thread = None
    with app.app_context():
        db.create_all()
        # launch heartbeats
        thread = threading.Thread(target=heartbeat, args=(heartbeat_time,))
        thread.start()

    # launch request handler
    app.run(host='0.0.0.0',debug=False, threaded=True, processes=1)
    app_kill_event = True
    thread.join()