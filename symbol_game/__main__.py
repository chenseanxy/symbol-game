import argparse
from .messages import Identity
from .game import Game
from .logging import init_logging

parser = argparse.ArgumentParser(prog="Symbols Game")
parser.add_argument("--address", type=str, help="your IP address")
parser.add_argument("--port", type=int, help="port to bind to")
parser.add_argument("--name", type=str, help="your username", default=None)
parser.add_argument("--connect", type=str, help="connect to a server", default=None)

args = parser.parse_args()

username = args.name or input("Enter your username: ")
me = Identity(ip=args.address, port=args.port, name=username)

init_logging(f"{me.ip}-{me.port}")

game = Game(me)
try:
    game.start()
    if args.connect:
        ip, port = args.connect.split(":")
        game.command_join(ip, int(port))
    game.run()
finally:
    game.stop()
