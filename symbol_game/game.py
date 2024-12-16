import logging
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from .base import GameProtocol
from .logic_lobby import LobbyMixin
from .logic_start_game import StartGameMixin
from .logic_turns import GameTurnsMixin
from .sync import SyncGameStateMixin

from .messages import Identity
from .connection import Connection, ConnectionStore, Server

_logger = logging.getLogger(__name__)


class Game(LobbyMixin, StartGameMixin, GameTurnsMixin, SyncGameStateMixin, GameProtocol):
    """
    Main game class that coordinates the multiplayer tic-tac-toe game.
    Handles both the lobby phase and the game phase, managing player connections,
    game state, and message passing between nodes.
    """
    def __init__(self, me: Identity):
        # Core networking components for P2P communication
        self.me = me
        self.connections = ConnectionStore()
        self.server = Server(me, self.connections)
        self.thread_pool = ThreadPoolExecutor(5, "game")

        self.frontend = "cli"   # Frontend type: "cli" or "gui"
        self.gui = None         # GUI frontend object

        # Game phase and role management
        self.phase = "lobby"    # Current phase: "lobby", "game", "end"
        self.host = None        # Identity of the host: None, self.me, or some other node

        # Player and symbol management
        self.players: List[Identity] = [me]         # List of all players
        self.symbols: Dict[Identity, str] = {}      # Maps players to their symbols
        self.player_ids: Dict[Identity, int] = {}   # Maps players to their numeric IDs
        self.pending_symbol = None                  # Symbol waiting for validation

        # Game state
        self.board_size: int = 4                    # Size of the game board
        self.board: List[List[Optional[str]]] = []  # The game board grid
        self.turn_order: List[int] = []             # Order of player IDs for turns
        self.current_turn: int = 0                  # Index in turn_order
        self.winner_id: Optional[int] = None        # Winning player ID
        self.winner: Optional[Identity] = None      # Winning player Identity

    def start(self):
        """Initialize the game server and begin accepting connections."""
        self.server.set_on_connect(self.on_connect)
        self.server.start()
        _logger.info(f"Starting game for {self.me}")
        print(f"Hello, {self.me}!")
        print(f"Wait for other players to join, or join a game with the command 'join <ip> <port>'")

    def stop(self):
        """Clean up resources and close all connections."""
        _logger.info("Stopping game")
        self.server.stop()
        self.connections.stop_all()

    def display_board(self):
        """Display the current state of the game board."""
        print("\nCurrent board:")
        for row in self.board:
            print("|", end=" ")
            for cell in row:
                print(cell if cell else "·", end=" | ")
            print("\n" + "-" * (self.board_size * 4 + 1))

    def run(self):
        """Main command loop handling user input and game commands."""
        while True:
            try:
                cmd = input()
                exit = self.run_command(cmd)
                if exit:
                    break
            except Exception as e:
                _logger.exception(f"Error processing command: {type(e).__name__}: {e}")

    def run_command(self, cmd):
        cmd = cmd.split()
        if not cmd:
            return
        command = cmd[0]
        if command == "join":
            if len(cmd) != 3:
                print("Usage: join <ip> <port>")
                return
            ip, port = cmd[1], int(cmd[2])
            self.command_join(ip, port)
        elif command == "start":
            self.command_start()
        elif command == "players":
            self.command_players()
        elif command == "symbol":
            if len(cmd) != 2:
                print("Usage: symbol <symbol>")
                return
            self.command_symbol(cmd[1])
        elif command == "move":
            if len(cmd) != 3:
                print("Usage: move <row> <col>")
                return
            row, col = int(cmd[1]), int(cmd[2])
            self.command_move(row, col)
        elif command == "board":
            self.display_board()
        elif command == "exit":
            return True
        elif command == "resync":
            self.command_resync_game_state()
        else:
            print("Unknown command:", command)
            print("Available commands: join, start, players, symbol, move, board, exit")
        self.prompt()

    def prompt(self):
        '''Dispatch update to frontend and give a new command prompt'''
        if self.frontend == "gui":
            self.gui.update_label()
            self.gui.update_board()
            self.gui.update_buttons()
            return

        if self.phase == "lobby":
            if self.me not in self.symbols:
                print("Choose a symbol with 'symbol <X>'")
            if self.is_host:
                print("Once everyone is ready, start the game with 'start'")
        print("> ", end="", flush=True)

    def on_connect(self, conn: Connection):
        """Handle new connection and set up message handlers."""
        if self.phase == 'lobby':
            if self.can_host:
                # Become host
                self.host = self.me
                _logger.info(f"{conn.other} has connected")
                
                # Update game state and inform user
                self.connections.add(conn)
                self.players.append(conn.other)
                print(f"{conn.other} has connected, start the game with 'start'")
            else:
                _logger.info(
                    f"Connected to {conn.other} when we're still in the lobby, "
                    "assuming that the game has started, we just haven't been notified yet"
                )
                self.connections.add(conn)
        else:
            _logger.info(f"Connected to {conn.other} during game phase")
            self.connections.add(conn)
        
        self.setup_handlers(conn)
        self.prompt()

    def setup_handlers(self, conn: Connection):
        conn.set_message_handler('choose_symbol', self.on_choose_symbol)
        conn.set_message_handler('validate_symbol', self.on_validate_symbol)
        conn.set_message_handler('start_game', self.on_start_game)
        conn.set_message_handler('propose_move', self.on_propose_move)
        conn.set_message_handler('commit_move', self.on_commit_move)
        conn.set_message_handler('request_game_state', self.on_request_game_state)
        return 
    
    def connect_to_players(self, reconnect = False):
        for player in self.players:
            if player == self.me:
                continue
            if not reconnect and self.player_ids[player] < self.player_ids[self.me]:
                continue
            if player not in self.connections.connections:
                conn = self.connections.connect(player, self.me)
                self.setup_handlers(conn)
                self.connections.add(conn)
