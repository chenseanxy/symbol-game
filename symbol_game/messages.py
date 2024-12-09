from pydantic import BaseModel
from typing import Literal, Optional, List, Dict, Any

class Identity(BaseModel):
    '''
    Identity of a node - contains connection information
    '''
    ip: str
    port: int
    name: Optional[str] = None

    @property
    def addr(self):
        return (self.ip, self.port)

    def __hash__(self):
        return hash((self.ip, self.port))
    
    def __eq__(self, other):
        return self.ip == other.ip and self.port == other.port
    
    def __str__(self):
        return f"{self.name} ({self.ip}:{self.port})"

class BaseMessage(BaseModel):
    '''Base class for all game messages'''
    method: str

class Hello(BaseMessage):
    '''Initial connection message'''
    method: Literal['hello'] = 'hello'
    identity: Identity

class StartGame(BaseMessage):
    '''
    Message sent to start the game with complete game configuration
    '''
    method: Literal['start_game'] = 'start_game'
    players: List[Dict[str, Any]]  # Player information including ID, name, address, symbol
    board_size: int                # Size of the game board (e.g., 4x4)
    turn_order: List[int]          # Order of player IDs for turns
    session_settings: Dict[str, Any] = {}  # Additional game settings

class ChooseSymbol(BaseMessage):
    '''Symbol selection message'''
    method: Literal['choose_symbol'] = 'choose_symbol'
    symbol: str

class ValidateSymbol(BaseMessage):
    '''Response to symbol selection'''
    method: Literal['validate_symbol'] = 'validate_symbol'
    is_valid: bool

# Registry of message types
message_types = {
    'hello': Hello,
    'choose_symbol': ChooseSymbol,
    'validate_symbol': ValidateSymbol,
    'start_game': StartGame,
}