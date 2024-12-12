# author: Sean
import logging

from . import messages

from .base import GameProtocol
from .messages import Identity
from .connection import Connection

_logger = logging.getLogger(__name__)


class LobbyMixin(GameProtocol):
    def command_players(self):
        """Display current player list with their symbols."""
        if self.phase == "lobby" and not self.is_host:
            print("Only hosts can list players in the lobby")
            return
            
        print("\nPlayers:")
        for player in self.players:
            symbol = self.symbols.get(player, "no symbol")
            print(f"- {player} ({symbol})")

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
