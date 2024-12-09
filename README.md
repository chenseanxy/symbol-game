# symbol-game

## Dev guide

### Dependencies

See `pyprojects.toml`. If you have poetry, you can install all dependencies with `poetry install`.

### Running the game

Minimum setup: `python -m symbol_game --address localhost --port 10081`
Quickly setup two nodes:
- server `python -m symbol_game --address localhost --port 10080 --name a --host --symbol x`
- client `python -m symbol_game --address localhost --port 10081 --name b --join localhost:10080 --symbol o`
- logs `tail -f *.log`

### Connectivity

- `messages.identity`: globally identifying one node (using ip, port pairs), port being the listening port
- `connection.Server`: for accepting connections from other nodes
- `connection.Connection`: for sending and receiving messages through an existing socket
    - automatically identifies the node on the other end on connection
    - `connection.thread_pool` can be used to wait for a message from the other node
- `connection.ConnectionStore`: for managing all established connections in the node

#### Wait for a message from a node

By default, `connection.receive()` will block until a message is received. To unblock it, use the thread pool:

```python
def wait_start_game():
    # This func will run in the background
    # which waits for a StartGame message and then calls on_start_game
    msg = messages.StartGame(**conn.receive())
    self.on_start_game(msg)
conn.thread_pool.submit(wait_start_game)
```

### Game

- game.Game: game states
- Game.run: cli frontend, dispatches to command_* functions
