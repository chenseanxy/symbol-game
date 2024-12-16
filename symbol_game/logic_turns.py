# author: Sergei

import logging
import time
from typing import Dict
from functools import partial

from . import messages

from .base import GameProtocol
from .connection import Connection

_logger = logging.getLogger(__name__)
VALIDATION_TIMEOUT = 3.0
VALIDATION_RETRIES = 3

class GameTurnsMixin(GameProtocol):
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
            validations[player] = response  # Only accept last message if multiple

        # Setup task handlers
        for player in self.players:
            if player != self.me:
                conn = self.connections.get(player)
                _logger.info(f"Sending move proposal to {player}: {move_msg=}")
                conn.set_message_handler(
                    'validate_move',
                    partial(on_validation, player)
                )
                validations[player] = None      # Mark as pending

        validated = False
        tries = 0
        while not validated:
            if tries > VALIDATION_RETRIES:
                print("Move validation retries exceeded")
                _logger.error(f"Move validation retries exceeded: {VALIDATION_RETRIES} {validations}")
                break
            if tries > 0:
                print("Retrying proposing move...")
                _logger.info("")
            else:
                print("Proposing move to other players...")
            tries += 1

            # Send out proposal
            for (player, response) in validations.items():
                if response is None:
                    _logger.info(f"Sending move proposal to {player}: {move_msg}")
                    try:
                        conn = self.connections.get(player)
                        conn.send(move_msg)
                    except Exception as e:
                        # Connection closed, broken pipe, etc
                        _logger.error(f"Error sending proposal to {player}: {type(e).__name__}: {e}")
                        # Do not retry connection
                        # Wait for players to reconnect

            # Wait for all validations to come back, timeout after 10 seconds
            deadline = time.time() + VALIDATION_TIMEOUT
            validated = False
            while any(v is None for v in validations.values()):
                _logger.debug(f"Waiting for validation responses: {validations}")
                if time.time() > deadline:
                    print("Validation responses timed out")
                    _logger.error(f"Validation responses timed out: {validations}")
                    break
                time.sleep(0.1)
            else:
                validated = True
        
        # Reset message handlers
        for player in validations.keys():
            conn = self.connections.get(player)
            conn.set_message_handler('validate_move', None)

        if not validated:
            return

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
            self.phase = "end"
            winner = next((v.winning_player for v in validations.values() if v.winning_player), None)

            # print endgame msg
            if winner:
                self.winner_id = winner
                self.winner = next(p for p in self.players if self.player_ids[p] == winner)
                
                print(f"\nGame Over! {self.winner.name} wins!")
            else:
                print("\nGame Over! It's a tie!")
            return

        # move to next turn
        self.current_turn = (self.current_turn + 1) % len(self.turn_order)

        # announce next player's turn
        next_player = next(p for p in self.players 
                        if self.player_ids[p] == self.turn_order[self.current_turn])
        print(f"\nIt's {next_player.name}'s turn!")

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
        else:
            next_player = next(p for p in self.players 
                            if self.player_ids[p] == self.turn_order[self.current_turn])
            print(f"\nIt's {next_player.name}'s turn!")
        self.prompt()
