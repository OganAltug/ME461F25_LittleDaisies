import tkinter as tk
from PIL import Image, ImageTk
import cv2
from maze_solver import MazeSolver

def cv_to_tk(img):
    return ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))

class MazeApp(tk.Tk):
    def __init__(self, generator):
        super().__init__()
        self.generator = generator
        self.maze_img = None
        self.maze_bin = None

        self.title("Maze Generator & Solver")
        self.geometry("1200x600")

        self._layout()

    def _layout(self):
        left = tk.Frame(self)
        right = tk.Frame(self)
        left.pack(side="left", expand=True)
        right.pack(side="right", expand=True)

        self.left_canvas = tk.Canvas(left, width=500, height=500)
        self.right_canvas = tk.Canvas(right, width=500, height=500)
        self.left_canvas.pack()
        self.right_canvas.pack()

        tk.Button(left, text="Generate Maze", command=self.generate).pack()
        

    def generate(self):
        self.maze_img = self.generator.generate()
        self.maze_bin = self.generator.get_binary_maze()
        self._show(self.left_canvas, self.maze_img)

    def solve(self):
        solver = MazeSolver(self.maze_bin)
        start = (1, 1)
        goal = (self.maze_bin.shape[0]-2, self.maze_bin.shape[1]-2)

        path = solver.solve_bfs(start, goal) if self.alg.get() == "BFS" \
               else solver.solve_dfs(start, goal)

        img = self.maze_img.copy()
        for x, y in path:
            img[x, y] = [0, 0, 255]

        self._show(self.right_canvas, img)

    def _show(self, canvas, img):
        tk_img = cv_to_tk(img)
        canvas.image = tk_img
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
