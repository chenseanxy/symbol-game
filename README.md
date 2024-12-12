# symbol-game

## Dev guide

### Dependencies

See `pyprojects.toml`. If you have poetry, you can install all dependencies with `poetry install`.

### Running the game

Minimum setup: `python -m symbol_game --address localhost --port 10081`
Quickly setup two nodes:
- server `python -m symbol_game --address localhost --port 10080 --name a --host --symbol x`
- client `python -m symbol_game --address localhost --port 10081 --name b --join localhost:10080 --symbol o`
- logs `tail -f logs/*.log`
Add gui: `--gui`

### Connectivity

- `messages.identity`: globally identifying one node (using ip, port pairs), port being the listening port
- `connection.Server`: for accepting connections from other nodes
- `connection.Connection`: for sending and receiving messages through an existing socket
    - automatically identifies the node on the other end on connection
- `connection.ConnectionStore`: for managing all established connections in the node

#### Wait for a message from a node

`connection.Connection` receives messages and dispatches them to the handler based on message type.

To receive a certain type of message, define a handler in your mixin register it in `game.Game.setup_handlers`:

```python
# in your mixin:
def handle_message(self, conn: Connection, message: YourMessage):
    # handle message
    pass

# in game.Game:
def setup_handlers(self, conn: Connection):
    # ...
    conn.add_handler('your_message_type', self.handle_message)
    # ...
```

To block until a message arrives:

> Note: user interactions are blocked as well, so be careful

```python
# This can handle multiple message arriving as well
received_messages = [None]
def on_receive(id, conn: Connection, message: Message):
    received_messages[id] = message

# partial(on_receive, 0) here directs the message to land on received[0]
conn.add_handler('your_message_type', partial(on_receive, 0))

while not all(received_messages):
    time.sleep(0.01)
```

### Game

- `base.GameProtocol`: defines basic game state types and game state helper funcs
- Mixins: different phases of the game with their commands and message handlers
    - `logic_lobby`: lobby phase
    - `logic_start_game`: starting game
    - `logic_turns`: in-game game turns
- `game.Game`: game states
- `Game.run`: cli frontend, dispatches to command_* functions
