
import logging
import time

from . import messages

from .base import GameProtocol
from .connection import Connection

_logger = logging.getLogger(__name__)
RESYNC_TIMEOUT = 10.0

class SyncGameStateMixin(GameProtocol):
    def on_request_game_state(self, conn: Connection, msg: messages.RequestGameState):
        """Handle game state request from a reconnecting player."""
        _logger.info(f"Sending game state to {conn.other}")
        conn.send(messages.GameState(
            players=self.players,
            symbols=[self.symbols[player] for player in self.players],
            player_ids=[self.player_ids[player] for player in self.players],
            board_size=self.board_size,
            board=self.board,
            turn_order=self.turn_order,
            current_turn=self.current_turn,
            winner_id=self.winner_id,
            winner=self.winner
        ))

    def command_resync_game_state(self):
        """Resynchronize game state with all players."""
        if not self.host or self.host == self.me:
            print("Connect to a host first!")
            return
        synced = False
        def _on_game_state(conn: Connection, msg: messages.GameState):
            nonlocal synced
            self.players = msg.players
            for (i, player) in enumerate(self.players):
                self.symbols[player] = msg.symbols[i]
                self.player_ids[player] = msg.player_ids[i]
            self.board_size = msg.board_size
            self.board = msg.board
            self.turn_order = msg.turn_order
            self.current_turn = msg.current_turn
            self.winner_id = msg.winner_id
            self.winner = msg.winner
            synced = True
            print("Game state synchronized from host!")
            pass

        print("Resynchronizing game state with host...")
        host_conn = self.connections.get(self.host)
        host_conn.set_message_handler('game_state', _on_game_state)
        host_conn.send(messages.RequestGameState())
        
        deadline = time.time() + RESYNC_TIMEOUT
        while not synced and time.time() < deadline:
            _logger.debug(f"Waiting for game state synchronization from {self.host}")
            time.sleep(0.1)
        
        host_conn.set_message_handler(messages.GameState, None)

        self.connect_to_players(reconnect=True)

        if not synced:
            _logger.error(f"Failed to synchronize game state with host within {RESYNC_TIMEOUT}s")
            raise TimeoutError("Failed to synchronize game state with host")
