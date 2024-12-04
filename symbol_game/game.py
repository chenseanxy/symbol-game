from typing import List
import logging

from . import messages
from .messages import Identity
from .connection import Connection, ConnectionStore, Server

_logger = logging.getLogger(__name__)


class Game:
    def __init__(self, me: Identity):
        self.me = me
        self.connections = ConnectionStore()
        self.server = Server(me, self.connections)

        self.phase = "lobby"    # lobby, game

        # All nodes can be hosts by default
        # drops to False if this node connects to another host
        self.can_host = True
        self.is_host = False
    
        self.players: List[Identity] = [me]

    def start(self):
        self.server.set_on_connect(self.on_connect)
        self.server.start()
        print(f"Hello, {self.me}!")
        print(f"Wait for other players to join, or join a game with the command 'join <ip> <port>'")

    def stop(self):
        _logger.info("Stopping game")
        self.server.stop()
        self.connections.stop_all()

    def run(self):
        while True:
            cmd = input().split()
            if cmd[0] == "join":
                ip, port = cmd[1], int(cmd[2])
                self.command_join(ip, port)
            elif cmd[0] == "start":
                self.command_start()
            elif cmd[0] == "players":
                self.command_players()
            elif cmd[0] == "exit":
                break
            else:
                print("Unknown command: ", cmd)

    def on_connect(self, conn: Connection):
        if self.can_host:
            print(conn.other, "has connected, start the game with 'start'")
            self.connections.add(conn)
            self.is_host = True
            self.players.append(conn.other)

    def command_join(self, ip: str, port: int):
        if not self.phase == "lobby":
            print(f"Cannot join game in the {self.phase} phase")
            return
        if self.is_host:
            print("You are already hosting a game, start the game with 'start'")
            return

        conn = self.connections.connect(Identity(ip=ip, port=port), self.me)
        print("Connected to", conn.other)
        self.connections.add(conn)
        self.can_host = False

        # in thread for host connection: wait for start_game message and start the game
        def wait_start_game():
            msg = messages.StartGame(**conn.receive())
            self.on_start_game(msg)
        conn.thread_pool.submit(wait_start_game)

    def command_players(self):
        if self.phase == "lobby" and not self.is_host:
            print("Only hosts can list players in the lobby")
            return
        for player in self.players:
            print("-", player)

    def command_start(self):
        if not self.phase == "lobby":
            print(f"Cannot start game in the {self.phase} phase")
            return
        if not self.is_host:
            print("You are not hosting the game")
            return
        if len(self.players) < 2:
            print("Need at least 2 players to start the game")
            return

        msg = messages.StartGame(players=self.players)
        for player in self.players:
            if player == self.me:
                continue
            conn = self.connections.get(player)
            conn.send(msg)
        self.on_start_game(msg)

    def on_start_game(self, msg: messages.StartGame):
        self.phase = "game"
        self.players = msg.players
        print("Game started with players:")
        for player in self.players:
            print("-", player)

