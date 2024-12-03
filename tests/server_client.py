'''
python tests/server_client.py s
python tests/server_client.py c
'''

import socket
import time
import sys

from symbol_game.connection import Connection, Identity

if sys.argv[1] == "s":
    # Server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('localhost', 12345))
    server.listen(1)
    print('Server started')
    conn, addr = server.accept()
    other = Identity(*addr, "client")
    print(f'Connection from {other}')
    connection = Connection(conn, other)
    connection.start()
    connection.send({"ping": "server"})
    time.sleep(1)
    print(connection.messages())
    print(connection.messages())
    connection.send({"ping": "server"})
    time.sleep(1)
    print(connection.messages())
    connection.stop()
else:
    # Client
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = Identity('localhost', 12345, "server")
    client.connect(server.addr)
    print(f'Connected to {server}')
    connection = Connection(client, server)
    connection.start()
    connection.send({"ping": "client"})
    time.sleep(1)
    print(connection.messages())
    print(connection.messages())
    connection.send({"ping": "client"})
    time.sleep(1)
    print(connection.messages())
    connection.stop()
