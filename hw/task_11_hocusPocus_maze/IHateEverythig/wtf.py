import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import collections
import heapq

# --- Configuration ---
CELL_SIZE = 25
COLS = 30
ROWS = 20
COLOR_BG = "white"
COLOR_WALL = "black"
COLOR_START = "green"
COLOR_END = "red"
COLOR_PATH = "blue"
COLOR_VISITED = "yellow"     # Cells we have finished checking
COLOR_FRONTIER = "cyan"      # Cells currently in the queue (the "Frontier")

class MazeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Maze Solver - Improved")
        
        # Data Grid: 0=Empty, 1=Wall
        self.grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        self.start_pos = None
        self.end_pos = None
        self.running = False
        
        # Setup GUI
        self._setup_ui()
        
    def _setup_ui(self):
        # Control Panel
        control_frame = tk.Frame(self.root, padx=5, pady=5)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Instructions
        tk.Label(control_frame, text="Left Click: Wall/Start/End").pack(anchor="w")
        tk.Label(control_frame, text="Right Click: Erase").pack(anchor="w")
        tk.Label(control_frame, text="1. Place Start (S)").pack(anchor="w")
        tk.Label(control_frame, text="2. Place End (E)").pack(anchor="w")
        tk.Label(control_frame, text="3. Draw Walls").pack(anchor="w")
        
        tk.Frame(control_frame, height=10).pack() # Spacer

        # Algorithms
        tk.Label(control_frame, text="Algorithm:").pack(anchor="w")
        self.algo_var = tk.StringVar(value="BFS")
        ttk.Combobox(control_frame, textvariable=self.algo_var, 
                     values=["BFS", "DFS", "A*", "Greedy BFS"], state="readonly").pack(fill=tk.X)
        
        tk.Frame(control_frame, height=10).pack()

        # Action Buttons
        tk.Button(control_frame, text="Solve Maze", bg="#ddffdd", command=self.start_solve).pack(fill=tk.X, pady=2)
        tk.Button(control_frame, text="Reset Solution", command=self.reset_solution).pack(fill=tk.X, pady=2)
        tk.Button(control_frame, text="Clear Walls", command=self.clear_walls).pack(fill=tk.X, pady=2)
        
        tk.Frame(control_frame, height=20).pack()
        
        # Save/Load
        tk.Label(control_frame, text="File Operations:").pack(anchor="w")
        tk.Button(control_frame, text="Save Maze", command=self.save_maze).pack(fill=tk.X, pady=2)
        tk.Button(control_frame, text="Load Maze", command=self.load_maze).pack(fill=tk.X, pady=2)

        # Canvas
        self.canvas = tk.Canvas(self.root, width=COLS*CELL_SIZE, height=ROWS*CELL_SIZE, bg=COLOR_BG)
        self.canvas.pack(side=tk.LEFT, padx=10, pady=10)
        
        # Bindings
        self.canvas.bind("<Button-1>", self.handle_click)
        self.canvas.bind("<B1-Motion>", self.handle_drag)
        self.canvas.bind("<Button-3>", self.handle_right_click)
        self.canvas.bind("<B3-Motion>", self.handle_right_drag)
        
        self.draw_grid_lines()

    def draw_grid_lines(self):
        for i in range(COLS + 1):
            self.canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, ROWS * CELL_SIZE, fill="#ccc")
        for i in range(ROWS + 1):
            self.canvas.create_line(0, i * CELL_SIZE, COLS * CELL_SIZE, i * CELL_SIZE, fill="#ccc")

    # --- Input Handling ---
    def handle_click(self, event):
        self._modify_grid(event, mode="draw")

    def handle_drag(self, event):
        self._modify_grid(event, mode="draw")
        
    def handle_right_click(self, event):
        self._modify_grid(event, mode="erase")
        
    def handle_right_drag(self, event):
        self._modify_grid(event, mode="erase")

    def _modify_grid(self, event, mode):
        if self.running: return
        
        c = event.x // CELL_SIZE
        r = event.y // CELL_SIZE
        
        if not (0 <= c < COLS and 0 <= r < ROWS): return

        if mode == "erase":
            # Clear cell
            self.grid[r][c] = 0
            if (r, c) == self.start_pos: self.start_pos = None
            if (r, c) == self.end_pos: self.end_pos = None
            self.draw_cell(r, c, COLOR_BG)
            
        elif mode == "draw":
            # Logic: Start -> End -> Walls
            if self.start_pos is None:
                self.start_pos = (r, c)
                self.grid[r][c] = 0 # Start is not a wall
                self.draw_cell(r, c, COLOR_START, text="S")
            elif self.end_pos is None and (r, c) != self.start_pos:
                self.end_pos = (r, c)
                self.grid[r][c] = 0
                self.draw_cell(r, c, COLOR_END, text="E")
            elif (r, c) != self.start_pos and (r, c) != self.end_pos:
                self.grid[r][c] = 1
                self.draw_cell(r, c, COLOR_WALL)

    def draw_cell(self, r, c, color, text=None):
        x1 = c * CELL_SIZE
        y1 = r * CELL_SIZE
        x2 = x1 + CELL_SIZE
        y2 = y1 + CELL_SIZE
        
        # Overwrite area
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=color, outline="#ccc")
        if text:
            self.canvas.create_text(x1 + CELL_SIZE/2, y1 + CELL_SIZE/2, text=text, fill="white", font=("Arial", 10, "bold"))

    # --- Save / Load ---
    def save_maze(self):
        data = {
            "grid": self.grid,
            "start": self.start_pos,
            "end": self.end_pos
        }
        f = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if f:
            with open(f, 'w') as file:
                json.dump(data, file)

    def load_maze(self):
        f = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json")])
        if f:
            with open(f, 'r') as file:
                data = json.load(file)
                self.grid = data["grid"]
                # Convert lists back to tuples for positions
                self.start_pos = tuple(data["start"]) if data["start"] else None
                self.end_pos = tuple(data["end"]) if data["end"] else None
                self.redraw_all()

    def redraw_all(self):
        self.canvas.delete("all")
        self.draw_grid_lines()
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid[r][c] == 1:
                    self.draw_cell(r, c, COLOR_WALL)
        if self.start_pos:
            self.draw_cell(self.start_pos[0], self.start_pos[1], COLOR_START, "S")
        if self.end_pos:
            self.draw_cell(self.end_pos[0], self.end_pos[1], COLOR_END, "E")

    def reset_solution(self):
        self.running = False
        self.redraw_all()

    def clear_walls(self):
        self.running = False
        self.grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        self.start_pos = None
        self.end_pos = None
        self.redraw_all()

    # --- Algorithms ---
    def start_solve(self):
        if not self.start_pos or not self.end_pos:
            messagebox.showwarning("Missing Info", "Please place both Start (S) and End (E) points.")
            return
        if self.running: return
        
        self.reset_solution()
        self.running = True
        
        algo = self.algo_var.get()
        generator = None
        
        if algo == "BFS":
            generator = self.solve_bfs()
        elif algo == "DFS":
            generator = self.solve_dfs()
        elif algo == "A*":
            generator = self.solve_astar()
        elif algo == "Greedy BFS":
            generator = self.solve_greedy_bfs()
            
        self.animate(generator)

    def animate(self, generator):
        if not self.running: return
        try:
            # Get next step from algorithm
            # We skip 'visited' drawing here because the generator yields visited nodes
            # and frontier nodes separately if we wanted, but simple yielding is enough.
            next_step = next(generator)
            
            # The generator yields a dict with instructions like: {'type': 'visited', 'coords': (r,c)}
            if next_step['type'] == 'visited':
                if next_step['coords'] != self.start_pos and next_step['coords'] != self.end_pos:
                    self.draw_cell(next_step['coords'][0], next_step['coords'][1], COLOR_VISITED)
            
            elif next_step['type'] == 'frontier':
                if next_step['coords'] != self.start_pos and next_step['coords'] != self.end_pos:
                    self.draw_cell(next_step['coords'][0], next_step['coords'][1], COLOR_FRONTIER)

            elif next_step['type'] == 'path':
                for (r, c) in next_step['path']:
                    if (r, c) != self.start_pos and (r, c) != self.end_pos:
                        self.draw_cell(r, c, COLOR_PATH)
                self.running = False
                return

            self.root.after(20, lambda: self.animate(generator)) # Speed: 20ms
            
        except StopIteration:
            self.running = False
            messagebox.showinfo("Result", "No path found!")

    # --- Logic ---
    def get_neighbors(self, r, c):
        neighs = []
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]: # Up, Down, Left, Right
            nr, nc = r + dr, c + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS and self.grid[nr][nc] == 0:
                neighs.append((nr, nc))
        return neighs

    def reconstruct_path(self, parent_map, current):
        path = []
        while current in parent_map:
            path.append(current)
            current = parent_map[current]
        return path[::-1] # Reverse

    def solve_bfs(self):
        queue = collections.deque([self.start_pos])
        visited = set([self.start_pos])
        parent_map = {}
        
        while queue:
            current = queue.popleft()
            
            if current == self.end_pos:
                yield {'type': 'path', 'path': self.reconstruct_path(parent_map, current)}
                return

            # Visual: Mark current as processed (Yellow)
            yield {'type': 'visited', 'coords': current}

            for neighbor in self.get_neighbors(*current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent_map[neighbor] = current
                    queue.append(neighbor)
                    # Visual: Mark neighbor as in frontier (Cyan/Light Blue)
                    yield {'type': 'frontier', 'coords': neighbor}

    def solve_dfs(self):
        # Using a stack for DFS
        stack = [self.start_pos]
        visited = set([self.start_pos])
        parent_map = {}

        while stack:
            current = stack.pop()
            
            if current == self.end_pos:
                yield {'type': 'path', 'path': self.reconstruct_path(parent_map, current)}
                return

            yield {'type': 'visited', 'coords': current}

            # Randomize order slightly so DFS doesn't just draw straight lines every time (optional)
            neighbors = self.get_neighbors(*current)
            
            for neighbor in neighbors:
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent_map[neighbor] = current
                    stack.append(neighbor)
                    yield {'type': 'frontier', 'coords': neighbor}

    def heuristic(self, a, b):
        # Manhattan distance
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def solve_astar(self):
        # Priority Queue: (f_score, cell)
        count = 0 # Tie-breaker
        open_set = []
        heapq.heappush(open_set, (0, count, self.start_pos))
        
        parent_map = {}
        g_score = {self.start_pos: 0}
        f_score = {self.start_pos: self.heuristic(self.start_pos, self.end_pos)}
        
        open_set_hash = {self.start_pos} # For fast lookup
        visited = set()

        while open_set:
            current = heapq.heappop(open_set)[2]
            open_set_hash.remove(current)

            if current == self.end_pos:
                yield {'type': 'path', 'path': self.reconstruct_path(parent_map, current)}
                return

            visited.add(current)
            yield {'type': 'visited', 'coords': current}

            for neighbor in self.get_neighbors(*current):
                temp_g_score = g_score[current] + 1
                
                if temp_g_score < g_score.get(neighbor, float('inf')):
                    parent_map[neighbor] = current
                    g_score[neighbor] = temp_g_score
                    f_score[neighbor] = temp_g_score + self.heuristic(neighbor, self.end_pos)
                    
                    if neighbor not in open_set_hash:
                        count += 1
                        heapq.heappush(open_set, (f_score[neighbor], count, neighbor))
                        open_set_hash.add(neighbor)
                        yield {'type': 'frontier', 'coords': neighbor}

    def solve_greedy_bfs(self):
        # Like A* but only looks at Heuristic (h), ignores path cost (g)
        count = 0
        open_set = []
        heapq.heappush(open_set, (0, count, self.start_pos))
        parent_map = {}
        visited = set([self.start_pos])

        while open_set:
            current = heapq.heappop(open_set)[2]

            if current == self.end_pos:
                yield {'type': 'path', 'path': self.reconstruct_path(parent_map, current)}
                return
            
            yield {'type': 'visited', 'coords': current}
            
            for neighbor in self.get_neighbors(*current):
                if neighbor not in visited:
                    visited.add(neighbor)
                    parent_map[neighbor] = current
                    count += 1
                    # Priority is just the heuristic
                    priority = self.heuristic(neighbor, self.end_pos)
                    heapq.heappush(open_set, (priority, count, neighbor))
                    yield {'type': 'frontier', 'coords': neighbor}

if __name__ == "__main__":
    root = tk.Tk()
    app = MazeApp(root)
    root.mainloop()