from typing import List, Dict
import logging
from concurrent.futures import ThreadPoolExecutor

from . import messages
from .messages import Identity
from .connection import Connection, ConnectionStore, Server

_logger = logging.getLogger(__name__)

class Game:
    """
    Main game class that manages the game state and coordinates between players.
    Handles both host and client roles in the P2P network.
    """
    def __init__(self, me: Identity):
        # Core components
        self.me = me
        self.connections = ConnectionStore()
        self.server = Server(me, self.connections)
        self.thread_pool = ThreadPoolExecutor(5, "game")

        # Game state
        self.phase = "lobby"    # Phases: "lobby" or "game"
        self.can_host = True    # Becomes False when joining another's game
        self.is_host = False    # True when other players connect to us
        
        # Player management
        self.players: List[Identity] = [me]
        self.symbols: Dict[Identity, str] = {}
        self.board_size: int = 4
        self.turn_order: List[Identity] = []

    def start(self):
        """Initialize the game server and start accepting connections"""
        self.server.set_on_connect(self.on_connect)
        self.server.start()
        print(f"Hello, {self.me}!")
        print(f"Wait for other players to join, or join a game with the command 'join <ip> <port>'")

    def stop(self):
        """Cleanup and close all connections"""
        _logger.info("Stopping game")
        self.server.stop()
        self.connections.stop_all()

    def run(self):
        """Main command loop for handling user input"""
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
                    
                elif command == "exit":
                    break
                    
                else:
                    print("Unknown command:", command)
                    print("Available commands: join, start, players, symbol, exit")
                    
            except Exception as e:
                _logger.error(f"Error processing command: {e}")

    def on_connect(self, conn: Connection):
        """Handle new connection from another player"""
        if self.phase == 'lobby':
            if self.can_host:
                self.is_host = True
                _logger.info(f"Connected to {conn.other}")
                
                # Set up message handlers
                conn.set_message_handler('choose_symbol', self.on_choose_symbol)
                conn.set_message_handler('start_game', self.on_start_game)
                
                # Update game state
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
        """Join another player's game"""
        if self.phase != "lobby":
            print(f"Cannot join game in the {self.phase} phase")
            return
            
        if self.is_host:
            print("You are already hosting a game, start the game with 'start'")
            return

        # Connect to host
        conn = self.connections.connect(Identity(ip=ip, port=port), self.me)
        
        # Set up message handlers
        conn.set_message_handler('choose_symbol', self.on_choose_symbol)
        conn.set_message_handler('start_game', self.on_start_game)
        
        print(f"Connected to {conn.other}")
        self.connections.add(conn)
        self.can_host = False

    def command_symbol(self, symbol: str):
        """Choose a symbol with improved error handling and validation"""
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

        # For non-host players, validate with host
        choice_msg = messages.ChooseSymbol(symbol=symbol)
        _logger.info(f"Sending symbol choice to host: {symbol}")

        # Get connection to host (should be the only connection for a client)
        host_conn = next(iter(self.connections.connections.values()))
        if not host_conn:
            _logger.error("No connection to host found")
            print("Error: Not connected to host")
            return

        _logger.info(f"Sending symbol choice to host at {host_conn.other}")
        host_conn.send(choice_msg)
        
        try:
            response = messages.ValidateSymbol(**host_conn.receive())
            _logger.info(f"Received validation response: {response.is_valid}")
            
            if response.is_valid:
                self.symbols[self.me] = symbol
                print(f"Successfully chose symbol: {symbol}")
            else:
                print("Symbol choice was invalid (already taken)")
                
        except Exception as e:
            _logger.error(f"Error during symbol validation: {e}")
            print("Error validating symbol choice")

    def command_players(self):
        """List all players in the game"""
        if self.phase == "lobby" and not self.is_host:
            print("Only hosts can list players in the lobby")
            return
            
        print("\nPlayers:")
        for player in self.players:
            symbol = self.symbols.get(player, "no symbol")
            print(f"- {player} ({symbol})")

    def command_start(self):
        """Start the game (host only)"""
        if self.phase != "lobby":
            print(f"Cannot start game in the {self.phase} phase")
            return
            
        if not self.is_host:
            print("You are not hosting the game")
            return
            
        if len(self.players) < 2:
            print("Need at least 2 players to start the game")
            return
            
        if len(self.symbols) != len(self.players):
            print("Not all players have chosen symbols")
            return

        # Generate random turn order
        self.turn_order = self.players.copy()
        random.shuffle(self.turn_order)

        # Create player info for start message
        player_info = [
            {
                "id": i + 1,
                "name": player.name,
                "address": f"{player.ip}:{player.port}",
                "symbol": self.symbols[player]
            }
            for i, player in enumerate(self.players)
        ]

        # Create and send start game message
        msg = messages.StartGame(
            players=player_info,
            board_size=self.board_size,
            turn_order=[self.players.index(p) + 1 for p in self.turn_order],
            session_settings={}
        )

        # Send to all players except self
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                conn.send(msg)

        # Process start game locally
        self.thread_pool.submit(self.on_start_game, msg)

    def on_choose_symbol(self, conn: Connection, msg: messages.ChooseSymbol):
        """Handle symbol choice from another player"""
        _logger.info(f"Validating symbol choice from {conn.other}: {msg.symbol}")
        
        # Check if symbol is available
        is_valid = msg.symbol not in self.symbols.values()
        _logger.info(f"Symbol {msg.symbol} validation result: {is_valid}")
        
        # Send response
        response = messages.ValidateSymbol(is_valid=is_valid)
        _logger.info(f"Sending validation to {conn.other}: {is_valid}")
        conn.send(response)
        
        # Record if valid
        if is_valid:
            _logger.info(f"Recording symbol {msg.symbol} for {conn.other}")
            self.symbols[conn.other] = msg.symbol

    def on_start_game(self, msg: messages.StartGame):
        """Handle game start"""
        self.phase = "game"
        print("\nGame started with players:")
        for player in msg.players:
            print(f"- {player['name']} ({player['symbol']})")
        # TODO: Initialize game board
        # TODO: Start first turn