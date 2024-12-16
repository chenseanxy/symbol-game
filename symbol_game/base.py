from typing import Protocol, Literal, Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor

from . import connection
from .messages import Identity


class GameProtocol(Protocol):
    """
    Essential game states & game state related methods
    """

    # Connectivity
    me: Identity
    connections: connection.ConnectionStore
    server: connection.Server
    thread_pool: ThreadPoolExecutor

    # Frontend
    frontend: Literal['cli', 'gui']
    gui: Optional['GuiProtocol']

    # Game phase and role management
    phase: Literal['lobby', 'game', 'end']
    # Identity of the host: None, self.me, or some other node
    host: Optional[Identity]

    # Player and symbol management
    players: List[Identity]
    symbols: Dict[Identity, str]
    player_ids: Dict[Identity, int]
    pending_symbol: Optional[str]   # Symbol waiting for validation

    # Game state
    board_size: int
    board: List[List[Optional[str]]]
    turn_order: List[int]       # Order of player IDs
    current_turn: int           # Index of turn_order
    winner_id: Optional[int]    # Winning player ID
    winner: Optional[Identity]  # Winning player identity

    @property
    def can_host(self) -> bool:
        return self.host is None or self.host == self.me

    @property
    def is_host(self) -> bool:
        return self.host is not None and self.host == self.me

    def is_my_turn(self) -> bool:
        """Check if it's this player's turn."""
        return self.turn_order[self.current_turn] == self.player_ids[self.me]

    def display_board(self) -> None:
        """Display the current state of the game board."""
        pass

    def prompt(self) -> None:
        '''Dispatch update to frontend and give a new command prompt'''
        pass

    def setup_handlers(self, conn: connection.Connection) -> None:
        '''Set up message handlers for new connections'''
        pass

    def connect_to_players(self, reconnect: bool = False) -> None:
        """
        Connect to all players with smaller IDs for turn order.
        if reconnect: try to proactively connect to all players
        """
        pass

class GuiProtocol(Protocol):
    pass
