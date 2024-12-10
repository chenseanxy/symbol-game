from symbol_game.gui import GUI

if __name__ == "__main__":
    board = [
        [" ", " ", " ", " "],
        [" ", " ", " ", " "],
        [" ", " ", " ", " "],
        [" ", " ", " ", " "]
    ]

    gui = GUI(board)
    p = 0
    for _ in range(len(board)**2):
        gui.update_title(f"Player {p + 1}'s Turn")

        # 1. Poll for click
        coords = gui.click()

        # 2. Update board accordingly
        board[coords[0]][coords[1]] = 'X' if p == 0 else 'O'
        gui.update_board(board)

        p = (p + 1) % 2

    gui.exit()