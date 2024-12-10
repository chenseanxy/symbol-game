import threading
import socket
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional, Callable
from . import messages
from .messages import Identity, BaseMessage, message_types

_logger = logging.getLogger(__name__)

class Connection:
    '''Handles communication between two nodes'''
    def __init__(self, sock: socket.socket, *, me: Identity, transport: Identity):
        self.socket = sock
        self.me = me
        self.transport = transport
        self.other: Optional[Identity] = None
        
        self.terminating = threading.Event()
        self.lock = threading.Lock()
        self.thread_pool = ThreadPoolExecutor(
            max_workers=1, 
            thread_name_prefix=f"connection_{transport.ip}_{transport.port}"
        )
        self.receive_thread = threading.Thread(
            target=self.message_loop, name=f"incoming_{transport.ip}_{transport.port}")
        self.message_handlers: Dict[str, Callable] = {}

    def set_message_handler(self, message_type: str, handler: Callable):
        """Register a message handler"""
        _logger.info(f"Registering handler for message type: {message_type}")
        self.message_handlers[message_type] = handler

    def start(self):
        """Start the connection and message handling"""
        # Do initial handshake
        self.send(messages.Hello(identity=self.me))
        self.other = messages.Hello(**self.receive()).identity
        
        # Start message handling loop
        self.receive_thread.start()

    def message_loop(self):
        """Main message handling loop with improved error handling"""
        while not self.terminating.is_set():
            try:
                msg = self.receive()
                if msg is None:
                    continue
                
                # Unmarshall message
                method = BaseMessage(**msg).method
                if method not in message_types:
                    _logger.error(f"Invalid message type: {method}")
                    continue
                msg_type = message_types[method]
                msg = msg_type(**msg)

                # Dispatch message to handler
                if method in self.message_handlers:
                    handler = self.message_handlers[method]
                    handler(self, msg)
                else:
                    _logger.warning(f"No handler for message type: {method}")
                    
            except ConnectionError:
                _logger.error("Connection lost")
                break
            except Exception as e:
                _logger.exception(f"Error in message loop: {type(e).__name__}: {e}")
                if self.terminating.is_set():
                    break

    def receive(self, timeout=5):
        """Receive and parse a message with better error handling"""
        try:
            data = self.socket.recv(1024)
            if not data:
                if not self.terminating.is_set():
                    _logger.warning("Connection closed by peer")
                    raise ConnectionError("Connection closed by peer")
                return None
            
            try:
                message = json.loads(data.decode())
                _logger.info(f"Successfully received message: {message}")
                return message

            except json.JSONDecodeError as e:
                _logger.error(f"Failed to decode message: {data!r}")
                raise
                
        except socket.error as e:
            if not self.terminating.is_set():
                _logger.error(f"Socket error while receiving: {e}")
                raise
            return None

    def send(self, message: BaseMessage):
        """Send a message"""
        if isinstance(message, BaseMessage):
            message = message.model_dump()
            
        _logger.info(f"Sending: {message}")
        self.socket.send(json.dumps(message).encode())

    def stop(self):
        """Stop the connection"""
        _logger.info(f"Stopping connection to {self.other}")
        self.terminating.set()
        self.socket.shutdown(socket.SHUT_RDWR)
        self.socket.close()
        self.thread_pool.shutdown(cancel_futures=True)

class ConnectionStore:
    '''Manages all active connections'''
    def __init__(self):
        self.connections: Dict[Identity, Connection] = {}
        self.lock = threading.Lock()
    
    def add(self, conn: Connection):
        with self.lock:
            if conn.other in self.connections:
                # Likely a reconnection
                prev = self.connections.pop(conn.other)
                conn.message_handlers = prev.message_handlers
                prev.stop()
            self.connections[conn.other] = conn
    
    def remove(self, ident: Identity):
        with self.lock:
            self.connections.pop(ident)
    
    def get(self, ident: Identity) -> Optional[Connection]:
        with self.lock:
            return self.connections.get(ident)
    
    @staticmethod
    def connect(other: Identity, me: Identity) -> Connection:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(other.addr)
        conn = Connection(sock, me=me, transport=other)
        conn.start()
        return conn

    def stop_all(self):
        for conn in self.connections.values():
            conn.stop()

class Server:
    '''Handles incoming connections'''
    def __init__(self, ident: Identity, connection_store: ConnectionStore):
        self.ident = ident
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind(self.ident.addr)
        self.thread = threading.Thread(target=self._listen, name="server")
        self.terminating = threading.Event()
        self.connection_store = connection_store
        self.on_connect = None
    
    def set_on_connect(self, on_connect: Callable):
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

    def _listen(self):
        while not self.terminating.is_set():
            try:
                conn, addr = self.sock.accept()
                if self.terminating.is_set():
                    break
                    
                ident = Identity(ip=addr[0], port=addr[1])
                connection = Connection(conn, me=self.ident, transport=ident)
                connection.start()

                if self.on_connect:
                    self.on_connect(connection)
                    
            except Exception as e:
                _logger.error(f"Error in server loop: {e}")
                if self.terminating.is_set():
                    break