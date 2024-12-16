# author: Runjie
import logging
import random
import time

from . import messages

from .base import GameProtocol
from .messages import Identity

_logger = logging.getLogger(__name__)


class StartGameMixin(GameProtocol):
    def is_valid_to_start(self) -> bool:
        """Check if the game can be started."""
        if not self.phase == "lobby":
            print(f"Cannot start game in the {self.phase} phase")
            return False
        if not self.is_host:
            print("You are not hosting the game")
            return False
        if len(self.players) < 2:
            print("Need at least 2 players to start the game")
            return False
        if len(self.symbols) != len(self.players):
            print("Not all players have chosen symbols")
            return False
        return True

    def initialize_board(self, size: int):
        """Create an empty game board of the specified size."""
        self.board = [[None for _ in range(size)] for _ in range(size)]
        self.board_size = size

    def command_start(self):
        """Start the game with proper initialization (host only)."""
        if not self.is_valid_to_start():
            return

        # Assign IDs and generate turn order
        for i, player in enumerate(self.players, 1):
            self.player_ids[player] = i
        turn_order = list(self.player_ids.values())
        random.shuffle(turn_order)

        # Create player information for start message
        player_info = [
            {
                "id": self.player_ids[player],
                "name": player.name or f"Player{self.player_ids[player]}",
                "address": f"{player.ip}:{player.port}",
                "symbol": self.symbols[player]
            }
            for player in self.players
        ]

        # Create and send start game message
        msg = messages.StartGame(
            players=player_info,
            board_size=len(self.players) + 1,
            turn_order=turn_order,
            session_settings={}
        )

        # Send to all other players
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                conn.send(msg)

        # Start game locally
        self.on_start_game(None, msg)

    def on_start_game(self, conn, msg: messages.StartGame):
        """Handle game start message and initialize game state."""
        self.phase = "game"
        self.initialize_board(msg.board_size)

        # Process player information
        for player_info in msg.players:
            player_id = player_info["id"]
            addr = player_info["address"].split(":")
            player = Identity(ip=addr[0], port=int(addr[1]), name=player_info["name"])

            # Store both ID and symbol
            self.player_ids[player] = player_id
            self.symbols[player] = player_info["symbol"]

            # Make sure player is in players list
            if player not in self.players:
                self.players.append(player)


            """for player in self.players:
                if f"{player.ip}:{player.port}" == player_info["address"]:
                    self.player_ids[player] = player_id
                    break"""

        # Set up turn order
        self.turn_order = msg.turn_order
        self.current_turn = 0

        # Connect to clients that have their id smaller than us
        # ID, NOT TURN ORDER, this should not be randomized
        self.connect_to_players()

        # Wait for all other players to connect
        time.sleep(0.02)
        for player in self.players:
            if player != self.me and player not in self.connections.connections:
                print(f"Waiting for {player} to connect...")
                while player not in self.connections.connections:
                    time.sleep(0.01)

        # Display game start information
        print("\nGame started!")
        print("\nPlayers and their symbols:")
        for player_info in msg.players:
            print(f"- Player {player_info['id']}: {player_info['name']} ({player_info['symbol']})")
        
        print("\nTurn order:", " -> ".join(map(str, self.turn_order)))
        print(f"\nBoard size: {self.board_size}x{self.board_size}")
        self.display_board()

        if self.is_my_turn():
            print("\nIt's your turn! Use 'move <row> <col>' to make a move.")
            self.prompt()
