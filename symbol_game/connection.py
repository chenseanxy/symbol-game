'''
P2P connection between nodes
'''

import threading
import socket
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict

from .messages import Identity, BaseMessage, Hello

_logger = logging.getLogger(__name__)

class Connection:
    '''
    Connection object to another node
    Handles sending and receiving messages

    - Send: directly send through socket
    - Receive: blocks until receives one message
    '''

    def __init__(self, sock, *, me, transport):
        '''
        Adopt connection with another node
        Socket either created from making a connection, or accepted from listening
        '''
        self.socket: socket.socket = sock
        self.me: Identity = me
        self.transport: Identity = transport
        self.other: Identity = None
        self.terminating = threading.Event()
        self.lock = threading.Lock()
        self.thread_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="game")
    
    def start(self):
        # identify ourselves and counterparty
        self.send(Hello(identity=self.me))
        self.other = Hello(**self.receive()).identity
        pass
    
    def stop(self):
        _logger.info(f"Stopping connection to {self.other}", )
        self.terminating.set()
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        self.thread_pool.shutdown(cancel_futures=True)
        _logger.info(f"Connection to {self.other} stopped")

    def send(self, message):
        '''
        Send message to the other node
        '''
        if isinstance(message, BaseMessage):
            message = message.model_dump()
        _logger.info(f"Sending {message} to {self.other}")
        self.socket.send(json.dumps(message).encode())
    
    def receive(self):
        '''
        Receive message from the other node
        '''
        # Messages should not be larger than 1024
        # Otherwise: TODO: frag message handling
        msg = self.socket.recv(1024)
        marshalled = json.loads(msg.decode())
        _logger.info(f"Received {marshalled} from {self.other}")
        return marshalled


class ConnectionStore:
    '''
    Store of connections
    '''

    def __init__(self):
        self.connections: Dict[str, Connection] = {}
        self.lock = threading.Lock()
    
    def add(self, conn: Connection):
        with self.lock:
            self.connections[conn.other] = conn
    
    def remove(self, ident: Identity):
        with self.lock:
            self.connections.pop(ident)
    
    def get(self, ident: Identity):
        with self.lock:
            return self.connections.get(ident)
    
    @staticmethod
    def connect(other: Identity, me: Identity):
        '''
        Connect to a node
        '''
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(other.addr)
        conn = Connection(sock, me=me, transport=other)
        conn.start()
        return conn

    def stop_all(self):
        for conn in self.connections.values():
            conn.stop()


class Server:
    '''
    Server object to listen for incoming connections
    '''

    def __init__(self, ident: Identity, connection_store: ConnectionStore):
        self.ident = ident
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(self.ident.addr)
        self.thread = threading.Thread(target=self._listen, name="server")
        self.terminating = threading.Event()
        self.connection_store = connection_store
        self.on_connect = None
    
    def set_on_connect(self, on_connect):
        self.on_connect = on_connect

    def start(self):
        self.sock.listen(5)
        self.thread.start()
    
    def stop(self):
        _logger.info("Stopping server")
        self.terminating.set()
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(self.ident.addr)
        self.sock.close()
        self.thread.join()
        _logger.info("Server stopped")
    
    def _listen(self):
        while not self.terminating.is_set():
            conn, addr = self.sock.accept()
            if self.terminating.is_set():
                break
            ident = Identity(ip=addr[0], port=addr[1])
            connection = Connection(conn, me=self.ident, transport=ident)
            connection.start()

            if self.on_connect:
                self.on_connect(connection)
