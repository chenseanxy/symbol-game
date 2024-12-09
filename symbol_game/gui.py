import tkinter as tk

class GUI:
    """Symbols Game GUI class.

    Useful methods of the class:
        click:
            Poll a button click from the user, returns the coordinates of the button.
        update_title:
            Update the title of the window, e.g. to indicate whose turn it is.
        update_board:
            Refresh the GUI with updated board.
    """

    def __init__(self, board: list[list, list]):
        """Initialize the GUI with the initial board."""
        self.root = tk.Tk()
        self.root.title("Symbols Game")
        self.clicked_coordinates = None

        # Create and render initial grid
        self.buttons = {}
        self.create_board(len(board))
        self.update_board(board)

    def create_board(self, size: int) -> None:
        """Helper: Initializes the grid with given size."""
        for row in range(size):
            for col in range(size):
                button = tk.Button(
                    self.root,
                    text=" ",
                    width=5,
                    height=5,
                    command=lambda r=row, c=col: self.on_button_click(r, c)
                )
                button.grid(row=row, column=col, padx=5, pady=5)
                self.buttons[(row, col)] = button

    def on_button_click(self, row, col):
        """Helper: Handle a button click and store the clicked coordinates."""
        self.clicked_coordinates = (row, col)
        self.root.globalsetvar("clicked", True)

    def exit(self):
        """Helper: Run the main Tkinter event loop.

        Should be called in the end of the game to preserve window until closed.
        """
        self.root.mainloop()
        self.root.destroy()

    def click(self) -> tuple[int, int]:
        """Poll a click from the user to get coordinates.

        Returns:
            Tuple (row, col) of the clicked button.
        """
        self.clicked_coordinates = None
        self.root.globalsetvar("clicked", False)
        self.root.wait_variable(tk.BooleanVar(self.root, name="clicked"))
        return self.clicked_coordinates

    def update_board(self, board: list[list]) -> None:
        """Refresh the grid with updated board.

        Args:
            board: 2D list representing the board with symbols.

        Returns:
            None.
        """
        size = len(board)
        for row in range(size):
            for col in range(size):
                symbol = board[row][col]
                self.buttons[(row, col)].config(text=symbol)

    def update_title(self, title: str) -> None:
        """Update the title of the GUI.

        Can be useful e.g. to indicate whose turn it is or the completion of game.

        Args:
            title: New title for the screen.

        Returns:
            None.
        """
        self.root.title(title)
