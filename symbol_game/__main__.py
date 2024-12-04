import argparse
from .connection import Connection, ConnectionStore, Server
from .messages import Identity
from .game import Game
from . import messages

parser = argparse.ArgumentParser(prog="Symbols Game")
parser.add_argument("--address", type=str, help="your IP address")
parser.add_argument("--port", type=int, help="port to bind to")
parser.add_argument("--name", type=str, help="your username", default=None)

args = parser.parse_args()

username = args.name or input("Enter your username: ")
me = Identity(ip=args.address, port=args.port, name=username)

game = Game(me)
game.run()
