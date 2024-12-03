'''
P2P connection between nodes
'''

import threading
import socket
import json


class Identity:
    '''
    Identity of a node
    Contains IP address, port, and name
    '''

    def __init__(self, ip, port, name):
        self.ip = ip
        self.port = port
        self.name = name

    @property
    def addr(self):
        '''(ip, port) tuple'''
        return (self.ip, self.port)

    def __hash__(self):
        return hash((self.ip, self.port))
    
    def __eq__(self, other):
        return self.ip == other.ip and self.port == other.port
    
    def __str__(self):
        return f'{self.name} ({self.ip}:{self.port})'


class Connection:
    '''
    Connection object to another node
    Handles sending and receiving messages

    - Send: directly send through socket
    - Receive: buffers all received messages
        - on `Connection.messages()` call, returns all of them and clears the buffer
    '''

    def __init__(self, sock, ident):
        '''
        Adopt connection with another node
        Socket either created from making a connection, or accepted from listening
        '''
        self.socket: socket.socket = sock
        self.other: Identity = ident
        self.thread = threading.Thread(target=self._listen)
        self._messages = []
        self.terminating = threading.Event()
        self.lock = threading.Lock()
    
    def start(self):
        self.thread.start()
    
    def stop(self):
        self.socket.shutdown(socket.SHUT_WR)
        self.terminating.set()
        self.thread.join()

    def _listen(self):
        '''
        Listen for incoming messages, put them into messages list
        '''
        while not self.terminating.is_set():
            # Messages should not be larger than 1024
            # Otherwise: TODO: frag message handling
            message = self.socket.recv(1024)
            if not message:
                # TODO: handle connection closed
                continue
            json_message = json.loads(message.decode())
            with self.lock:
                self._messages.append(json_message)
            print(f'Received: {json_message}')

    def messages(self):
        '''
        Get unhandled messages from the buffer
        Once read, all messages are removed from buffer
        '''
        with self.lock:
            ret = self._messages
            self._messages = []
        return ret

    def send(self, message):
        '''
        Send message to the other node
        '''
        self.socket.send(json.dumps(message).encode())
