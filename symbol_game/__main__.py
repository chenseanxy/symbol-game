import argparse
import socket
import os
import tkinter as tk
from .messages import Identity
from .game import Game
from .gui import GUI
from .logging import init_logging

parser = argparse.ArgumentParser(prog="Symbols Game")
parser.add_argument("--address", type=str, help="your IP address", default=socket.gethostname())
parser.add_argument("--port", type=int, help="port to bind to", default=10080)
parser.add_argument("--name", type=str, help="your username", default=None)
parser.add_argument("--join", type=str, help="join a server", default=None)
parser.add_argument("--host", action="store_true", help="host a server", default=False)
parser.add_argument("--symbol", type=str, help="your symbol", default=None)
parser.add_argument("--gui", action="store_true", help="use the GUI", default=False)
parser.add_argument("--remote-logging", action="store_true", help="enable remote logging", default=False)
parser.add_argument("--reconnect", action="store_true", help="reconnect to existing game", default=False)

args = parser.parse_args()

username = args.name or input("Enter your username: ")
me = Identity(ip=args.address, port=args.port, name=username)

init_logging(me.ip, me.port, args.remote_logging or bool(os.getenv("REMOTE_LOGGING", False)))

game = Game(me)
try:
    game.start()
    if args.join:
        ip, port = args.join.split(":")
        game.command_join(ip, int(port))
    if args.host:
        game.host = game.me
    if args.symbol:
        game.command_symbol(args.symbol)
    if args.reconnect:
        game.command_resync_game_state()
    if args.gui:
        game.frontend = "gui"
        root = tk.Tk()
        game.gui = GUI(root, game)
        root.mainloop()
    else:
        game.run()
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    game.stop()
