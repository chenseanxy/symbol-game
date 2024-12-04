
from pydantic import BaseModel
from typing import Literal, Optional

class Identity(BaseModel):
    '''
    Identity of a node
    Contains IP address, port, and name
    '''

    ip: str
    port: int
    name: Optional[str] = None

    @property
    def addr(self):
        '''(ip, port) tuple'''
        return (self.ip, self.port)

    def __hash__(self):
        return hash((self.ip, self.port))
    
    def __eq__(self, other):
        return self.ip == other.ip and self.port == other.port
    
    def __str__(self):
        return f"{self.name} ({self.ip}:{self.port})"


class BaseMessage(BaseModel):
    '''
    Base class for all messages
    '''
    method: str


class Hello(BaseMessage):
    '''
    Message sent when a new node joins
    '''
    method: Literal['hello'] = 'hello'
    identity: Identity


class StartGame(BaseMessage):
    '''
    Message sent to start the game
    '''
    method: Literal['start_game'] = 'start_game'
    players: list[Identity]


message_types = {
    'hello': Hello,
}
