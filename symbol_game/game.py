import random
from typing import List, Dict, Optional
import logging
from concurrent.futures import ThreadPoolExecutor

from . import messages
from .messages import Identity
from .connection import Connection, ConnectionStore, Server

_logger = logging.getLogger(__name__)

class Game:
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

        # Game phase and role management
        self.phase = "lobby"    # Current phase: "lobby" or "game"
        self.can_host = True    # Ability to become host (false when joining others)
        self.is_host = False    # Whether this node is the host

        # Player and symbol management
        self.players: List[Identity] = [me]  # List of all players
        self.symbols: Dict[Identity, str] = {}  # Maps players to their symbols
        self.player_ids: Dict[Identity, int] = {}  # Maps players to their numeric IDs
        self.pending_symbol = None  # Symbol waiting for validation

        # Game state
        self.board_size: int = 4  # Size of the game board
        self.board: List[List[Optional[str]]] = []  # The game board grid
        self.turn_order: List[int] = []  # Order of player IDs for turns
        self.current_turn: int = 0  # Index in turn_order

    def start(self):
        """Initialize the game server and begin accepting connections."""
        self.server.set_on_connect(self.on_connect)
        self.server.start()
        print(f"Hello, {self.me}!")
        print(f"Wait for other players to join, or join a game with the command 'join <ip> <port>'")
        if not self.is_host:
            print("Please choose a symbol with command 'symbol <X>'")

    def stop(self):
        """Clean up resources and close all connections."""
        _logger.info("Stopping game")
        self.server.stop()
        self.connections.stop_all()

    def initialize_board(self, size: int):
        """Create an empty game board of the specified size."""
        self.board = [[None for _ in range(size)] for _ in range(size)]
        self.board_size = size

    def is_my_turn(self) -> bool:
        """Check if it's this player's turn."""
        return self.turn_order[self.current_turn] == self.player_ids[self.me]

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
                cmd = input().split()
                if not cmd:
                    continue

                command = cmd[0]
                if command == "join":
                    if len(cmd) != 3:
                        print("Usage: join <ip> <port>")
                        continue
                    ip, port = cmd[1], int(cmd[2])
                    self.command_join(ip, port)
                elif command == "start":
                    self.command_start()
                elif command == "players":
                    self.command_players()
                elif command == "symbol":
                    if len(cmd) != 2:
                        print("Usage: symbol <symbol>")
                        continue
                    self.command_symbol(cmd[1])
                elif command == "move":
                    if len(cmd) != 3:
                        print("Usage: move <row> <col>")
                        continue
                    row, col = int(cmd[1]), int(cmd[2])
                    self.command_move(row, col)
                elif command == "board":
                    self.display_board()
                elif command == "exit":
                    break
                else:
                    print("Unknown command:", command)
                    print("Available commands: join, start, players, symbol, move, board, exit")
            
            except Exception as e:
                _logger.error(f"Error processing command: {e}")

    def on_connect(self, conn: Connection):
        """Handle new connection and set up message handlers."""
        if self.phase == 'lobby':
            if self.can_host:
                self.is_host = True
                _logger.info(f"Connected to {conn.other}")
                
                # Set up message handlers for all message types
                conn.set_message_handler('choose_symbol', self.on_choose_symbol)
                conn.set_message_handler('validate_symbol', self.on_validate_symbol)
                conn.set_message_handler('start_game', self.on_start_game)

                # new batch
                conn.set_message_handler('propose_move', self.on_propose_move)
                conn.set_message_handler('commit_move', self.on_commit_move)
                conn.set_message_handler('validate_move', self.on_validate_move)
                
                # Update game state and inform user
                self.connections.add(conn)
                self.players.append(conn.other)
                print(f"{conn.other} has connected, start the game with 'start'")
                print("Please choose a symbol with command 'symbol <X>'")
            else:
                print("Please choose a symbol with command 'symbol <X>'")
        else:
            _logger.info(f"Connected to {conn.other} during game phase")
            self.connections.add(conn)

    def command_join(self, ip: str, port: int):
        """Join another player's game session."""
        if not self.phase == "lobby":
            print(f"Cannot join game in the {self.phase} phase")
            return
        if self.is_host:
            print("You are already hosting a game, start the game with 'start'")
            return

        conn = self.connections.connect(Identity(ip=ip, port=port), self.me)
        
        # Set up message handlers
        conn.set_message_handler('choose_symbol', self.on_choose_symbol)
        conn.set_message_handler('validate_symbol', self.on_validate_symbol)
        conn.set_message_handler('start_game', self.on_start_game)

        conn.set_message_handler('propose_move', self.on_propose_move)
        conn.set_message_handler('commit_move', self.on_commit_move)
        conn.set_message_handler('validate_move', self.on_validate_move)
        
        print(f"Connected to {conn.other}")
        self.connections.add(conn)
        self.can_host = False
        print("Please choose a symbol with command 'symbol <X>'")

        def wait_start_game():
            msg = messages.StartGame(**conn.receive())
            self.thread_pool.submit(self.on_start_game, msg)
        conn.thread_pool.submit(wait_start_game)

    def command_symbol(self, symbol: str):
        """Handle symbol selection request."""
        if self.phase != "lobby":
            print("Can only choose symbol in lobby phase")
            return
            
        if self.is_host:
            if symbol not in self.symbols.values():
                self.symbols[self.me] = symbol
                _logger.info(f"Host chose symbol: {symbol}")
                print(f"Successfully chose symbol: {symbol}")
            else:
                _logger.info(f"Symbol already taken: {symbol}")
                print("This symbol is already taken")
            return

        # Store pending symbol and send validation request
        self.pending_symbol = symbol
        choice_msg = messages.ChooseSymbol(symbol=symbol)
        host_conn = next(iter(self.connections.connections.values()))
        
        print("Waiting for symbol validation from host...")
        _logger.info(f"Sending symbol choice to host: {symbol}")
        host_conn.send(choice_msg)

    def on_choose_symbol(self, conn: Connection, msg: messages.ChooseSymbol):
        """Handle incoming symbol choice request."""
        _logger.info(f"Received symbol choice request from {conn.other}: {msg.symbol}")
        
        is_valid = msg.symbol not in self.symbols.values()
        _logger.info(f"Symbol {msg.symbol} validation result: {is_valid}")
        
        response = messages.ValidateSymbol(is_valid=is_valid)
        _logger.info(f"Sending validation response to {conn.other}: {is_valid}")
        conn.send(response)
        
        if is_valid:
            _logger.info(f"Recording symbol {msg.symbol} for {conn.other}")
            self.symbols[conn.other] = msg.symbol

    def on_validate_symbol(self, conn: Connection, msg: messages.ValidateSymbol):
        """Handle symbol validation response."""
        _logger.info(f"Received symbol validation response: {msg.is_valid}")
        
        if msg.is_valid and self.pending_symbol:
            self.symbols[self.me] = self.pending_symbol
            print(f"\nSuccessfully chose symbol: {self.pending_symbol}")
        else:
            print("\nSymbol choice was invalid (already taken)")
        
        self.pending_symbol = None
        print("\nEnter command: ", end='', flush=True)


    # this is getting messy but who am I to judge kek
    def on_propose_move(self, conn: Connection, msg: messages.ProposeMove):
        return

    def on_commit_move(self, conn: Connection, msg: messages.CommitMove):
        return

    def on_validate_move(self, conn: Connection, msg: messages.ValidateMove):
        return

    def is_board_full(self) -> bool:
        '''checks if the board is completely filled.'''
        return all(cell is not None
                for row in self.board
                for cell in row)

    def check_win(self, row: int, col: int, symbol: str) -> bool:
        '''checks if the last move at (row, col) created a winning condition'''

        # checks row
        if all(self.board[row][c] == symbol for c in range(self.board_size)):
            return True

        # checks column
        if all(self.board[r][col] == symbol for r in range(self.board_size)):
            return True

        # checks diagonals if move was on them
        if row == col:
            if all(self.board[i][i] == symbol for i in range(self.board_size)):
                return True

        if row + col == self.board_size - 1:
            if all(self.board[i][self.board_size-1-i] == symbol 
                for i in range(self.board_size)):
                return True
            
        return False

    def command_players(self):
        """Display current player list with their symbols."""
        if self.phase == "lobby" and not self.is_host:
            print("Only hosts can list players in the lobby")
            return
            
        print("\nPlayers:")
        for player in self.players:
            symbol = self.symbols.get(player, "no symbol")
            print(f"- {player} ({symbol})")

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
            board_size=self.board_size,
            turn_order=turn_order,
            session_settings={}
        )

        # Send to all other players
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                conn.send(msg)

        # Start game locally
        self.on_start_game(msg)

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

    def on_start_game(self, msg: messages.StartGame):
        """Handle game start message and initialize game state."""
        self.phase = "game"
        self.initialize_board(msg.board_size)

        # Process player information
        for player_info in msg.players:
            player_id = player_info["id"]
            for player in self.players:
                if f"{player.ip}:{player.port}" == player_info["address"]:
                    self.player_ids[player] = player_id
                    break

        # Set up turn order
        self.turn_order = msg.turn_order
        self.current_turn = 0

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

    def command_move(self, row: int, col: int):
        ''' handles a move command from the current player'''

        # checks for turn
        if not self.is_my_turn():
            print("Wait your turn!")
            return

        # checks for bad coordinates
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            print(f"Invalid coordinates. Must be between 0 and {self.board_size-1}")
            return
        # checks for marks on board
        if self.board[row][col] is not None:
            print("That cell is already marked!")
            return

        move_msg = messages.ProposeMove(location=[row, col])
        validations = [] # for all players' validations of the move

        print("Proposing move to other players...")
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                conn.send(move_msg)

                # wait for validation
                response = messages.ValidateMove(**conn.receive())
                validations.append(response)

        if not all(v.is_valid for v in validations):
            print("Move was rejected by other players!")
            return

        # make actual move here
        player_id = self.player_ids[self.me]
        symbol = self.symbols[self.me]
        self.board[row][col] = symbol

        # commit move to all players
        commit_msg = messages.CommitMove(
            location=[row, col],
            symbol=symbol,
            player_id=player_id
        )

        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                conn.send(commit_msg)

        # check winning condition here

        # check for non-None game result
        game_result = next((v.game_result for v in validations if v.game_result), None)

        # check for non-None winner
        if game_result:
            winner = next((v.winning_player for v in validations if v.winning_player), None)

            # print endgame msg
            if winner:
                winner_name = next(p.name for p in self.players 
                                if self.player_ids[p] == winner)
                print(f"\nGame Over! {winner_name} wins!")
            else:
                print("\nGame Over! It's a tie!")
            return

        # move to next turn
        self.current_turn = (self.current_turn + 1) % len(self.turn_order)

        self.display_board()

        # announce next player's turn
        next_player = next(p for p in self.players 
                        if self.player_ids[p] == self.turn_order[self.current_turn])
        print(f"\nIt's {next_player.name}'s turn!")