import tkinter as tk
from tkinter import simpledialog, messagebox

class GUI:
    """Symbols Game GUI class"""
    def __init__(self, root, game):
        self.game = game
        self.root = root
        self.root.title("Symbols Game")
        self.buttons = {}
        self.grid_frame = None

        self.state_label = tk.Label(root, text="Welcome to the Symbols Game!", wraplength=400)
        self.state_label.pack(pady=10)

        self.create_controls()
        self.wait_for_start()

    def create_controls(self) -> None:
        """Creates buttons for common controls in the GUI."""
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)

        tk.Button(button_frame, text="Join", width=10, command=self.join_command).grid(row=0, column=0, padx=5)
        tk.Button(button_frame, text="Symbol", width=10, command=self.symbol_command).grid(row=0, column=1, padx=5)
        tk.Button(button_frame, text="Start", width=10, command=self.start_command).grid(row=0, column=2, padx=5)
        tk.Button(button_frame, text="Exit", width=10, command=self.exit_command).grid(row=0, column=5, padx=5)


    def create_board(self) -> None:
        """Helper: Initializes the playing grid with given size."""
        self.grid_frame = tk.Frame(self.root)
        self.grid_frame.pack(pady=10)

        size = len(self.game.board)
        for row in range(size):
            for col in range(size):
                button = tk.Button(
                    self.grid_frame,
                    text=" ",
                    width=5,
                    height=4,
                    command=lambda r=row, c=col: self.move_command(r, c)
                )
                button.grid(row=row, column=col, padx=5, pady=5)
                self.buttons[(row, col)] = button


    def update_label(self) -> None:
        """Update text info to the GUI"""
        if self.game.phase == "game":
            if self.game.is_my_turn():
                message="\nIt's your turn!"
            else:
                next_player = next(p for p in self.game.players
                                   if self.game.player_ids[p] == self.game.turn_order[self.game.current_turn])
                message=f"\nIt's {next_player.name}'s turn!"
            self.state_label.config(text=message)


    def update_board(self) -> None:
        """Refresh the grid with updated board."""
        size = len(self.game.board)
        for row in range(size):
            for col in range(size):
                symbol = self.game.board[row][col]
                self.buttons[(row, col)].config(text=symbol)

    def join_command(self):
        ip = simpledialog.askstring("Join Command", "Enter IP Address:")
        port = simpledialog.askstring("Join Command", "Enter Port:")
        if ip and port:
            self.game.run_command(f"join {ip} {port}")

    def symbol_command(self):
        symbol = simpledialog.askstring("Symbol Command", "Enter your symbol (e.g., X, O):")
        if symbol:
            self.game.run_command(f"symbol {symbol}")

    def move_command(self, x, y):
        self.game.run_command(f"move {x} {y}")
        self.update_board()

    def start_command(self):
        if self.game.phase == "lobby":
            self.game.run_command("start")

        if self.grid_frame:
            self.grid_frame.destroy()
            self.grid_frame = None
            self.buttons = {}

        self.create_board()
        self.periodic_update()

    def exit_command(self):
        if messagebox.askyesno("Exit", "Are you sure you want to exit?"):
            self.game.run_command("exit")
            self.root.destroy()

    def wait_for_start(self):
        if self.game.phase == "game":
            if self.grid_frame is None:
                self.start_command()
        else:
            self.root.after(100, self.wait_for_start)

    def periodic_update(self):
        if self.game.phase == "game":
            self.update_board()
            self.update_label()
        self.root.after(100, self.periodic_update)
