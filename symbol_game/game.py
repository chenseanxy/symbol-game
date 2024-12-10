import random
import time
import logging
from functools import partial
from typing import List, Dict, Optional
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

    @property
    def can_host(self) -> bool:
        return self.host is None or self.host == self.me
    
    @property
    def is_host(self) -> bool:
        return self.host is not None and self.host == self.me

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

                self.prompt()
            except Exception as e:
                _logger.exception(f"Error processing command: {type(e).__name__}: {e}")

    def prompt(self):
        '''Show command prompt beginning'''
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
                
                # Host-specific incoming messages
                conn.set_message_handler('choose_symbol', self.on_choose_symbol)

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
        
        # Setup message handlers as client
        conn.set_message_handler('validate_symbol', self.on_validate_symbol)
        conn.set_message_handler('start_game', self.on_start_game)

        # Setup message handlers for the game phase
        conn.set_message_handler('propose_move', self.on_propose_move)
        conn.set_message_handler('commit_move', self.on_commit_move)
        conn.set_message_handler('validate_move', self.on_validate_move)

        self.prompt()

    def command_join(self, ip: str, port: int):
        """Join another player's game session."""
        if not self.phase == "lobby":
            print(f"Cannot join game in the {self.phase} phase")
            return
        if self.is_host:
            print("You are already hosting a game, start the game with 'start'")
            return

        conn = self.connections.connect(Identity(ip=ip, port=port), self.me)
        
        # Set up message handlers as client
        conn.set_message_handler('validate_symbol', self.on_validate_symbol)
        conn.set_message_handler('start_game', self.on_start_game)

        # Setup message handlers for the game phase
        conn.set_message_handler('propose_move', self.on_propose_move)
        conn.set_message_handler('commit_move', self.on_commit_move)
        conn.set_message_handler('validate_move', self.on_validate_move)
        
        print(f"Connected to {conn.other}")
        self.connections.add(conn)
        self.host = conn.other

    def command_symbol(self, symbol: str):
        """Handle symbol selection request."""
        if self.phase != "lobby":
            print("Can only choose symbol in lobby phase")
            return
        
        if not self.host:
            print("Wait for players to join, or join a game, then choose symbols")
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
        host_conn = self.connections.get(self.host)
        
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
        self.prompt()

    # this is getting messy but who am I to judge kek
    def on_propose_move(self, conn: Connection, msg: messages.ProposeMove):
        """ handles move proposition by players"""
        _logger.info(f"Received move proposal from {conn.other}: location {msg.location}")

        row, col = msg.location

        # validates move
        valid = (0 <= row < self.board_size and 
                0 <= col < self.board_size and 
                self.board[row][col] is None)

        _logger.info(f"Move validation result: coordinates valid={valid}, "
                f"row={row}, col={col}, board_size={self.board_size}")

        # checks for win/tie if move would be valid
        game_result = None
        winning_player = None

        if valid:
            # temporarily applies move to check for win condition
            symbol = self.symbols[conn.other]
            self.board[row][col] = symbol
            _logger.info(f"Checking win condition for symbol {symbol}")

            if self.check_win(row, col, symbol):
                game_result = "win"
                winning_player = self.player_ids[conn.other]
                _logger.info(f"Win detected for player {winning_player}")
            elif self.is_board_full():
                game_result = "tie"
                _logger.info("Tie detected - board is full")

            # undoes temporary move
            self.board[row][col] = None
            _logger.info("Temporary move undone")

        response = messages.ValidateMove(
            is_valid=valid,
            game_result=game_result,
            winning_player=winning_player
        )
        _logger.info(f"Sending validation response: {response}")
        conn.send(response)


    def on_commit_move(self, conn: Connection, msg: messages.CommitMove):
        """move commitment - update board with the confirmed move."""
        _logger.info(f"Received move commitment from {conn.other}: "
            f"location={msg.location}, symbol={msg.symbol}, player_id={msg.player_id}")

        row, col = msg.location
        
        # Apply the move to our board
        self.board[row][col] = msg.symbol
        _logger.info(f"Applied move to board at ({row}, {col})")

        # Move to next turn
        self.current_turn = (self.current_turn + 1) % len(self.turn_order)
        _logger.info(f"Updated turn to {self.current_turn}")

        # Display updated game state
        self.display_board()

        # Announce next turn
        if self.is_my_turn():
            print("\nIt's your turn! Use 'move <row> <col>' to make a move.")
            self.prompt()
        else:
            next_player = next(p for p in self.players 
                            if self.player_ids[p] == self.turn_order[self.current_turn])
            print(f"\nIt's {next_player.name}'s turn!")



    def on_validate_move(self, conn: Connection, msg: messages.ValidateMove):
        """handles validation response for a proposed move."""
        _logger.info(f"Received move validation from {conn.other}: valid={msg.is_valid}, "
                    f"game_result={msg.game_result}, winning_player={msg.winning_player}")

        if not msg.is_valid:
            print(f"Move was rejected by {conn.other}")
            return

        if msg.game_result:
            if msg.game_result == "win":
                winner_name = next(p.name for p in self.players 
                                if self.player_ids[p] == msg.winning_player)
                print(f"This move would result in victory for {winner_name}!")
            else:
                print("This move would result in a tie!")

        _logger.info("Move validation accepted")
        return True

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
        for player in self.players:
            if self.player_ids[player] < self.player_ids[self.me]:
                if player not in self.connections.connections:
                    conn = self.connections.connect(player, self.me)

                    # Set up message handlers as client
                    conn.set_message_handler('validate_symbol', self.on_validate_symbol)
                    conn.set_message_handler('start_game', self.on_start_game)

                    # Setup message handlers for the game phase
                    conn.set_message_handler('propose_move', self.on_propose_move)
                    conn.set_message_handler('commit_move', self.on_commit_move)
                    conn.set_message_handler('validate_move', self.on_validate_move)
                    self.connections.add(conn)

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
        validations: Dict[str, messages.ValidateMove] = {}  # for all players' validations of the move

        _logger.info("Starting move process...")

        def on_validation(player, conn, response):
            _logger.info(f"Received validation response from {conn.other}: {response}")
            _logger.info(f"{player=} {conn.other=}")
            validations[player] = response

        print("Proposing move to other players...")
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                _logger.info(f"Sending move proposal to {player}: {move_msg=}")
                conn.set_message_handler(
                    'validate_move',
                    partial(on_validation, player)
                )
                validations[player] = None      # Mark as pending
                conn.send(move_msg)

        # Wait for all validations to come back, timeout after 10 seconds
        deadline = time.time() + 10
        while any(v is None for v in validations.values()):
            print("Waiting for validation responses...")
            if time.time() > deadline:
                print("Validation responses timed out")
                # TODO: handle
                return
            time.sleep(0.1)

        _logger.info(f"Validation check starting. All validations: {validations}")  # Before validation check
        all_valid = all(v.is_valid for v in validations.values())
        _logger.info(f"All moves valid: {all_valid}")  # After validation check

        if not all_valid:
            print("Move was rejected by other players!")
            # TODO: handle
            return

        _logger.info("Move validated, proceeding with commit")
        # make actual move here
        player_id = self.player_ids[self.me]
        symbol = self.symbols[self.me]
        self.board[row][col] = symbol
        _logger.info(f"Applied move locally: position=({row}, {col}), symbol={symbol}")

        # commit move to all players
        commit_msg = messages.CommitMove(
            location=[row, col],
            symbol=symbol,
            player_id=player_id
        )
        _logger.info("Sending commit message to all players")

        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                _logger.info(f"Sending commit to {player}")
                conn.send(commit_msg)
        
        print("Move successful! After your move, the board is: ")
        self.display_board()

        # check winning condition here

        # check for non-None game result
        game_result = next((v.game_result for v in validations.values() if v.game_result), None)

        # check for non-None winner
        if game_result:
            winner = next((v.winning_player for v in validations.values() if v.winning_player), None)

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

        # announce next player's turn
        next_player = next(p for p in self.players 
                        if self.player_ids[p] == self.turn_order[self.current_turn])
        print(f"\nIt's {next_player.name}'s turn!")
