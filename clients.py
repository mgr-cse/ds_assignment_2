from typing import Dict
from typing import Tuple
import requests
import sys

class Consumer:
    def __init__(self, host_primary: str, port_primary: int, name: str = '') -> None:
        self.hostname: str = f'http://{host_primary}:{port_primary}/'
        self.current_replica = None

        self.ids : Dict[Tuple(str, int), int] = {}
        self.name: str = name
    
    def eprint(self, *args, **kwargs):
            print(self.name, *args, file=sys.stderr, **kwargs)

    def change_replica(self):
        # update list
        self.eprint('replica change init')
        
        # request
        res = None
        try:
            res = requests.get(self.hostname + 'replicas')
        except:
            self.eprint('can not communicate to primary for replicas')
            return
        
        # parse the request
        try:    
            if  not res.ok:
                self.eprint(f'invalid response code received: {res.status_code}')
                return
            response = res.json()
            
            if response['status'] != 'success':
                self.eprint(response)
                return
        
            for r in response['replicas']:
                ip = r['ip']
                port = r['port']
                host = f'http://{ip}:{port}/'
                if host != self.current_replica:
                    self.current_replica = host
                    return
        except:
            self.eprint('change replica: error while parsing response')
        return

    def register(self, topic: str, partition: int=-1) -> int:
        # self checks
        
        # already registered
        if (topic, partition) in self.ids:
            return -1

        # prepare request content 
        request_content = {"topic":topic}
        if partition != -1:
            request_content['partition_id'] = partition
            
        if self.current_replica is None:
            self.eprint('error: replica address not set')
            self.change_replica()
            return -1
        
        # request
        res = None
        try:
            res = requests.post(self.current_replica + 'consumer/register', json=request_content)
        except:
            self.eprint('Can not make a post request/received unparsable response')
            self.change_replica()
            return -1
        
        # parse the request
        try:
            if not res.ok:
                self.eprint('received unexpected response code', res.status_code)
                self.change_replica()
                return False
            
            response = res.json()
            if response['status'] == 'failure':
                self.eprint(response)
                return -1
            self.ids[(topic, partition)] = response['consumer_id']
            return response['consumer_id']
        except:
            self.eprint('error while parsing response')
            self.change_replica()
        
        return -1

        def register(self, topic: str, partition: int=-1) -> int:
        # self checks
        
        # already registered
        if (topic, partition) in self.ids:
            return -1

        # prepare request content 
        request_content = {"topic":topic}
        if partition != -1:
            request_content['partition_id'] = partition
            
        if self.current_replica is None:
            self.eprint('error: replica address not set')
            self.change_replica()
            return -1
        
        # request
        res = None
        try:
            res = requests.post(self.current_replica + 'consumer/register', json=request_content)
        except:
            self.eprint('Can not make a post request/received unparsable response')
            self.change_replica()
            return -1
        
        # parse the request
        try:
            if not res.ok:
                self.eprint('received unexpected response code', res.status_code)
                self.change_replica()
                return False
            
            response = res.json()
            if response['status'] == 'failure':
                self.eprint(response)
                return -1
            self.ids[(topic, partition)] = response['consumer_id']
            return response['consumer_id']
        except:
            self.eprint('error while parsing response')
            self.change_replica()
        
        return -1

    def dequeue(self, topic: str, partition: int=-1) -> bool|str:
        # self check failure
        if (topic,partition) not in self.ids:
            self.eprint('not registered for topic', topic)
            self.change_replica()
            return False
        
        # check replica availability
        if self.current_replica is None:
            self.eprint('error: replica address not set')
            self.change_replica()
            return False
        
        # make consume request
        cons_id = self.ids[(topic,partition)]
        res = None
        try:
            res = requests.get(self.current_replica + 'consumer/consume', params={"consumer_id": cons_id, "topic": topic})
        except:
            self.eprint('Can not make post request')
            self.change_replica()
            return False
        
        # parse request
        try:
            if not res.ok:
                self.eprint('received unexpected response code', res.status_code)
                self.change_replica()
                return False
                
            response = res.json()
            if response['status'] == 'success':
                return response['message'] 
            else: self.eprint(response['message'])
        except:
            self.eprint('Invalid response:', res.text)
            self.change_replica()

        return False


from typing import Dict
from typing import Tuple
import requests
import json
import traceback
import sys

class Producer:
    def __init__(self, host: str, port: int, name: str = '') -> None:
        self.hostname: str = 'http://' + host + ':' + str(port) + '/'
        self.ids : Dict[Tuple(str, int), int] = {}
        self.name: str = name

    def eprint(self, *args, **kwargs):
        print(self.name, *args, file=sys.stderr, **kwargs)

    def register(self, topic: str, partition: int=-1) -> int:
        # self check
        if (topic, partition) in self.ids:
            self.eprint('already registered for the topic', topic)
            return -1
        
        # prepare request
        request_content = {"topic":topic}
        if partition != -1:
            request_content['partition_id'] = partition
        
        # make request
        try:
            res = requests.post(self.hostname + 'producer/register', json=request_content)
        except:
            self.eprint('Error Can not make a post request')
            return -1
        
        # parse request
        try: 
            if not res.ok:
                self.eprint('received unexpected response code', res.status_code)
                return -1
            
            response = res.json()
            if response['status'] == 'success':
                self.ids[(topic, partition)] = response['producer_id']
                return response['producer_id']
            
            self.eprint(response)
        except:
            self.eprint('Invalid Response:', res.text) 
        return -1

    def enqueue(self, topic: str, message: str, timestamp: float, random_string: str, partition: int=-1) -> bool:
        # self check
        if (topic, partition) not in self.ids:
            self.eprint('not registered for the topic/partition!')
            return False
        
        # prepare request
        prod_id = self.ids[(topic, partition)]
        request_content = {
            "topic": topic,
            "producer_id": prod_id,
            "message": message,
            "prod_client": self.name,
            "timestamp": timestamp,
            "random_string": random_string
        }
        
        # make request
        try:
            res = requests.post(self.hostname + 'producer/produce', json=request_content)
        except:
            self.eprint('Can not make a post request')
            return False
        
        # parse request
        try:    
            if not res.ok:
                self.eprint('received unexpected response code', res.status_code)
                return False
                    
            response = res.json()
            if response['status'] == 'success':
                return True  
            self.eprint(response)
        except:
            self.eprint('Invalid response:', res.text)
        return False
