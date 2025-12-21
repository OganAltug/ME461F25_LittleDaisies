"""
Maze Solver GUI (Updated)
- Adjustable maze size (rows/cols odd)
- Center start "square room" like the reference image
- Scrollable + zoomable canvases so full solution is always visible
- Generate / Load / Save (PNG/JPG)
- Solve with BFS, DFS, UCS, Greedy, A*
- Optional bidirectional search (multi-source from all exits)
- Draw explored (yellow) + final path (purple)
- Draw all shortest paths to exits (green) in second panel

Dependencies:
  pip install pillow

Run:
  python maze_solver_gui.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageTk
import random
import heapq
from collections import deque


# ============================================================
# Maze generation
# ============================================================

def _neighbors_2step(r, c):
    return [(r - 2, c), (r + 2, c), (r, c - 2), (r, c + 2)]


def generate_perfect_maze(rows_odd: int, cols_odd: int, seed=None):
    """
    Perfect maze on an odd grid:
      1 = wall
      0 = passage

    Uses randomized DFS carving (classic).
    """
    if seed is not None:
        random.seed(seed)

    if rows_odd % 2 == 0 or cols_odd % 2 == 0:
        raise ValueError("rows and cols must be odd.")

    grid = [[1] * cols_odd for _ in range(rows_odd)]

    # start cell for carving (odd coordinates near center)
    sr = rows_odd // 2
    sc = cols_odd // 2
    if sr % 2 == 0:
        sr -= 1
    if sc % 2 == 0:
        sc -= 1

    stack = [(sr, sc)]
    grid[sr][sc] = 0

    while stack:
        r, c = stack[-1]
        candidates = []
        for nr, nc in _neighbors_2step(r, c):
            if 1 <= nr < rows_odd - 1 and 1 <= nc < cols_odd - 1 and grid[nr][nc] == 1:
                candidates.append((nr, nc))
        if not candidates:
            stack.pop()
            continue

        nr, nc = random.choice(candidates)
        wr, wc = (r + nr) // 2, (c + nc) // 2
        grid[wr][wc] = 0
        grid[nr][nc] = 0
        stack.append((nr, nc))

    return grid


def carve_center_square_room(grid, room_size_odd: int):
    """
    Makes an open square room in the middle (like your sample image).
    This introduces cycles (not a perfect maze anymore), but that’s fine for this homework.
    """
    rows = len(grid)
    cols = len(grid[0])
    s = max(3, room_size_odd)
    if s % 2 == 0:
        s += 1
    s = min(s, rows - 3, cols - 3)  # keep inside bounds

    cr, cc = rows // 2, cols // 2
    r0 = cr - s // 2
    c0 = cc - s // 2
    r1 = r0 + s - 1
    c1 = c0 + s - 1

    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            grid[r][c] = 0

    # Ensure at least one "doorway" from the room to the maze
    # (open 1 cell in each direction if possible)
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        rr = cr + dr * (s // 2 + 1)
        cc2 = cc + dc * (s // 2 + 1)
        if 1 <= rr < rows - 1 and 1 <= cc2 < cols - 1:
            grid[rr][cc2] = 0


def add_random_exits(grid, num_exits: int):
    """
    Creates exits as boundary holes that connect to an interior passage.
    """
    rows = len(grid)
    cols = len(grid[0])
    candidates = []

    for c in range(1, cols - 1):
        if grid[1][c] == 0:
            candidates.append((0, c))
        if grid[rows - 2][c] == 0:
            candidates.append((rows - 1, c))

    for r in range(1, rows - 1):
        if grid[r][1] == 0:
            candidates.append((r, 0))
        if grid[r][cols - 2] == 0:
            candidates.append((r, cols - 1))

    random.shuffle(candidates)
    exits = []
    used = set()
    for cell in candidates:
        if len(exits) >= num_exits:
            break
        if cell in used:
            continue
        r, c = cell
        grid[r][c] = 0
        exits.append(cell)
        used.add(cell)
    return exits


def find_exits(grid):
    rows = len(grid)
    cols = len(grid[0])

    def is_open(r, c):
        return 0 <= r < rows and 0 <= c < cols and grid[r][c] == 0

    exits = []
    for c in range(cols):
        if is_open(0, c) and is_open(1, c):
            exits.append((0, c))
        if is_open(rows - 1, c) and is_open(rows - 2, c):
            exits.append((rows - 1, c))
    for r in range(rows):
        if is_open(r, 0) and is_open(r, 1):
            exits.append((r, 0))
        if is_open(r, cols - 1) and is_open(r, cols - 2):
            exits.append((r, cols - 1))

    return list(dict.fromkeys(exits))


def find_start_center(grid):
    rows = len(grid)
    cols = len(grid[0])
    sr, sc = rows // 2, cols // 2
    if grid[sr][sc] == 0:
        return (sr, sc)

    # Find nearest open cell if center is wall
    q = deque([(sr, sc)])
    seen = {(sr, sc)}
    while q:
        r, c = q.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in seen:
                if grid[nr][nc] == 0:
                    return (nr, nc)
                seen.add((nr, nc))
                q.append((nr, nc))
    return (sr, sc)


# ============================================================
# Image <-> Grid
# ============================================================

def grid_to_image(grid, cell_px=8):
    """
    Renders a maze with thick walls by scaling cells (cell_px).
    Walls = black, passages = white.
    """
    rows = len(grid)
    cols = len(grid[0])
    img = Image.new("RGB", (cols * cell_px, rows * cell_px), "white")
    draw = ImageDraw.Draw(img)

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 1:
                x0, y0 = c * cell_px, r * cell_px
                x1, y1 = x0 + cell_px - 1, y0 + cell_px - 1
                draw.rectangle([x0, y0, x1, y1], fill="black")
    return img


def image_to_grid(img, target_rows_odd, target_cols_odd):
    """
    Convert an input image into a binary maze grid by thresholding.
    Resamples to the requested odd grid shape.
    """
    g = img.convert("L")
    g = g.resize((target_cols_odd, target_rows_odd), Image.NEAREST)

    w, h = g.size
    px = g.load()
    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            grid[y][x] = 1 if px[x, y] < 128 else 0

    return grid


# ============================================================
# Search
# ============================================================

def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def heuristic_to_nearest_exit(node, exits):
    return min(manhattan(node, e) for e in exits) if exits else 0


def reconstruct_path(parent, end):
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def valid_neighbors(grid, node):
    r, c = node
    rows = len(grid)
    cols = len(grid[0])
    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == 0:
            yield (nr, nc)


def search_unidirectional(grid, start, exits, method: str):
    if not exits:
        return None, set(), []

    goal_set = set(exits)
    parent = {start: None}
    explored = set()
    explored_list = []

    if method == "Breadth First":
        q = deque([start])
        while q:
            cur = q.popleft()
            if cur in explored:
                continue
            explored.add(cur)
            explored_list.append(cur)
            if cur in goal_set:
                return reconstruct_path(parent, cur), explored, explored_list
            for nb in valid_neighbors(grid, cur):
                if nb not in parent:
                    parent[nb] = cur
                    q.append(nb)

    elif method == "Depth First":
        stack = [start]
        while stack:
            cur = stack.pop()
            if cur in explored:
                continue
            explored.add(cur)
            explored_list.append(cur)
            if cur in goal_set:
                return reconstruct_path(parent, cur), explored, explored_list
            for nb in valid_neighbors(grid, cur):
                if nb not in parent:
                    parent[nb] = cur
                    stack.append(nb)

    elif method in ("Uniform Cost", "Best First (Greedy)", "A*"):
        pq = []
        g_cost = {start: 0}

        def prio(n):
            if method == "Uniform Cost":
                return g_cost[n]
            if method == "Best First (Greedy)":
                return heuristic_to_nearest_exit(n, exits)
            return g_cost[n] + heuristic_to_nearest_exit(n, exits)  # A*

        heapq.heappush(pq, (prio(start), start))

        while pq:
            _, cur = heapq.heappop(pq)
            if cur in explored:
                continue
            explored.add(cur)
            explored_list.append(cur)
            if cur in goal_set:
                return reconstruct_path(parent, cur), explored, explored_list

            for nb in valid_neighbors(grid, cur):
                newg = g_cost[cur] + 1
                if nb not in g_cost or newg < g_cost[nb]:
                    g_cost[nb] = newg
                    parent[nb] = cur
                    heapq.heappush(pq, (prio(nb), nb))

    else:
        raise ValueError("Unknown method")

    return None, explored, explored_list


def _meet_and_reconstruct(meet, parent_f, parent_b):
    path_f = reconstruct_path(parent_f, meet)
    path_b = []
    cur = parent_b.get(meet)
    while cur is not None:
        path_b.append(cur)
        cur = parent_b.get(cur)
    return path_f + path_b


def search_bidirectional(grid, start, exits, method: str):
    if not exits:
        return None, set(), []
    goal_set = set(exits)
    if start in goal_set:
        return [start], {start}, [start]

    parent_f = {start: None}
    parent_b = {e: None for e in exits}
    explored_f, explored_b = set(), set()
    explored_list = []

    # BFS/DFS bidirectional (simple)
    if method == "Breadth First":
        qf = deque([start])
        qb = deque(exits)
        while qf and qb:
            cur = qf.popleft()
            if cur not in explored_f:
                explored_f.add(cur); explored_list.append(cur)
                if cur in explored_b:
                    return _meet_and_reconstruct(cur, parent_f, parent_b), explored_f | explored_b, explored_list
                for nb in valid_neighbors(grid, cur):
                    if nb not in parent_f:
                        parent_f[nb] = cur
                        qf.append(nb)

            cur = qb.popleft()
            if cur not in explored_b:
                explored_b.add(cur); explored_list.append(cur)
                if cur in explored_f:
                    return _meet_and_reconstruct(cur, parent_f, parent_b), explored_f | explored_b, explored_list
                for nb in valid_neighbors(grid, cur):
                    if nb not in parent_b:
                        parent_b[nb] = cur
                        qb.append(nb)
        return None, explored_f | explored_b, explored_list

    if method == "Depth First":
        sf = [start]
        sb = list(exits)
        while sf and sb:
            cur = sf.pop()
            if cur not in explored_f:
                explored_f.add(cur); explored_list.append(cur)
                if cur in explored_b:
                    return _meet_and_reconstruct(cur, parent_f, parent_b), explored_f | explored_b, explored_list
                for nb in valid_neighbors(grid, cur):
                    if nb not in parent_f:
                        parent_f[nb] = cur
                        sf.append(nb)

            cur = sb.pop()
            if cur not in explored_b:
                explored_b.add(cur); explored_list.append(cur)
                if cur in explored_f:
                    return _meet_and_reconstruct(cur, parent_f, parent_b), explored_f | explored_b, explored_list
                for nb in valid_neighbors(grid, cur):
                    if nb not in parent_b:
                        parent_b[nb] = cur
                        sb.append(nb)
        return None, explored_f | explored_b, explored_list

    # Priority bidirectional (UCS/Greedy/A*)
    gf = {start: 0}
    gb = {e: 0 for e in exits}

    def pf(n):
        if method == "Uniform Cost":
            return gf[n]
        if method == "Best First (Greedy)":
            return heuristic_to_nearest_exit(n, exits)
        return gf[n] + heuristic_to_nearest_exit(n, exits)

    def pb(n):
        if method == "Uniform Cost":
            return gb[n]
        if method == "Best First (Greedy)":
            return manhattan(n, start)
        return gb[n] + manhattan(n, start)

    pqf = [(pf(start), start)]
    pqb = [(pb(e), e) for e in exits]
    heapq.heapify(pqb)

    best_meet = None
    best_cost = float("inf")

    while pqf and pqb:
        if pqf[0][0] <= pqb[0][0]:
            _, cur = heapq.heappop(pqf)
            if cur in explored_f:
                continue
            explored_f.add(cur); explored_list.append(cur)

            if cur in explored_b:
                total = gf.get(cur, 10**9) + gb.get(cur, 10**9)
                if total < best_cost:
                    best_cost = total
                    best_meet = cur

            for nb in valid_neighbors(grid, cur):
                newg = gf[cur] + 1
                if nb not in gf or newg < gf[nb]:
                    gf[nb] = newg
                    parent_f[nb] = cur
                    heapq.heappush(pqf, (pf(nb), nb))
        else:
            _, cur = heapq.heappop(pqb)
            if cur in explored_b:
                continue
            explored_b.add(cur); explored_list.append(cur)

            if cur in explored_f:
                total = gf.get(cur, 10**9) + gb.get(cur, 10**9)
                if total < best_cost:
                    best_cost = total
                    best_meet = cur

            for nb in valid_neighbors(grid, cur):
                newg = gb[cur] + 1
                if nb not in gb or newg < gb[nb]:
                    gb[nb] = newg
                    parent_b[nb] = cur
                    heapq.heappush(pqb, (pb(nb), nb))

        if best_meet is not None and method in ("Uniform Cost", "A*"):
            if pqf and pqb and pqf[0][0] + pqb[0][0] >= best_cost:
                break
        if best_meet is not None and method == "Best First (Greedy)":
            break

    if best_meet is None:
        return None, explored_f | explored_b, explored_list

    return _meet_and_reconstruct(best_meet, parent_f, parent_b), explored_f | explored_b, explored_list


# ============================================================
# Drawing overlays
# ============================================================

def draw_overlays(base_img, start, exits, explored_list, path, cell_px,
                  explored_color=(255, 255, 0),  # yellow
                  path_color=(150, 0, 200),      # purple
                  start_color=(0, 120, 255),
                  exit_color=(255, 60, 60)):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    def rect(node):
        r, c = node
        x0, y0 = c * cell_px, r * cell_px
        return [x0, y0, x0 + cell_px - 1, y0 + cell_px - 1]

    for n in explored_list:
        if n != start:
            draw.rectangle(rect(n), fill=explored_color)

    if path:
        for n in path:
            draw.rectangle(rect(n), fill=path_color)

    draw.rectangle(rect(start), fill=start_color)
    for e in exits:
        draw.rectangle(rect(e), fill=exit_color)

    return img


def draw_green_all_paths(base_img, grid, start, exits, cell_px):
    img = base_img.copy()
    draw = ImageDraw.Draw(img)

    def rect(node):
        r, c = node
        x0, y0 = c * cell_px, r * cell_px
        return [x0, y0, x0 + cell_px - 1, y0 + cell_px - 1]

    # BFS tree from start
    q = deque([start])
    parent = {start: None}
    while q:
        cur = q.popleft()
        for nb in valid_neighbors(grid, cur):
            if nb not in parent:
                parent[nb] = cur
                q.append(nb)

    for e in exits:
        if e not in parent:
            continue
        cur = e
        path = []
        while cur is not None:
            path.append(cur)
            cur = parent.get(cur)
        path.reverse()
        for n in path:
            if n != start and n != e:
                draw.rectangle(rect(n), fill=(0, 200, 0))  # green
    return img


# ============================================================
# Scrollable + Zoomable Canvas Widget
# ============================================================

class ZoomCanvas(ttk.Frame):
    def __init__(self, master, width=520, height=520):
        super().__init__(master)
        self.canvas = tk.Canvas(self, width=width, height=height, bg="#222222",
                                highlightthickness=1, highlightbackground="#555")
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")

        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._pil_original = None
        self._tk_img = None
        self._zoom = 1.0

    def set_zoom(self, zoom: float):
        self._zoom = max(0.1, min(4.0, zoom))
        self._redraw()

    def set_image(self, pil_img: Image.Image):
        self._pil_original = pil_img
        self._redraw()

    def _redraw(self):
        self.canvas.delete("all")
        if self._pil_original is None:
            return
        w, h = self._pil_original.size
        nw, nh = max(1, int(w * self._zoom)), max(1, int(h * self._zoom))
        img = self._pil_original.resize((nw, nh), Image.NEAREST)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, image=self._tk_img, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, nw, nh))


# ============================================================
# GUI
# ============================================================

class MazeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maze Solver (Updated Part I)")
        self.geometry("1200x900")

        self.grid_data = None
        self.start = None
        self.exits = None

        self.cell_px = 8
        self.base_img = None
        self.overlay_img = None
        self.green_img = None

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Maze size controls
        ttk.Label(top, text="Rows (odd):").pack(side=tk.LEFT)
        self.rows_var = tk.IntVar(value=101)
        ttk.Spinbox(top, from_=31, to=401, increment=2, width=6, textvariable=self.rows_var).pack(side=tk.LEFT, padx=6)

        ttk.Label(top, text="Cols (odd):").pack(side=tk.LEFT)
        self.cols_var = tk.IntVar(value=101)
        ttk.Spinbox(top, from_=31, to=401, increment=2, width=6, textvariable=self.cols_var).pack(side=tk.LEFT, padx=6)

        # Center square room
        ttk.Label(top, text="Center room (odd):").pack(side=tk.LEFT, padx=(12, 2))
        self.room_var = tk.IntVar(value=21)
        ttk.Spinbox(top, from_=3, to=81, increment=2, width=6, textvariable=self.room_var).pack(side=tk.LEFT, padx=6)

        # Exits
        ttk.Label(top, text="Exits (1..5):").pack(side=tk.LEFT, padx=(12, 2))
        self.exit_var = tk.IntVar(value=1)
        ttk.Spinbox(top, from_=1, to=5, width=5, textvariable=self.exit_var).pack(side=tk.LEFT, padx=6)

        # Wall thickness (cell_px)
        ttk.Label(top, text="Thickness:").pack(side=tk.LEFT, padx=(12, 2))
        self.thick_var = tk.IntVar(value=8)
        thick = ttk.Scale(top, from_=3, to=16, orient="horizontal",
                          command=self._on_thickness_change)
        thick.set(8)
        thick.pack(side=tk.LEFT, padx=6)

        # Search method
        ttk.Label(top, text="Search:").pack(side=tk.LEFT, padx=(12, 2))
        self.method_var = tk.StringVar(value="Breadth First")
        methods = ["Breadth First", "Depth First", "Uniform Cost", "Best First (Greedy)", "A*"]
        ttk.OptionMenu(top, self.method_var, self.method_var.get(), *methods).pack(side=tk.LEFT, padx=6)

        # Bidirectional
        self.bidir_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Bidirectional", variable=self.bidir_var).pack(side=tk.LEFT, padx=12)

        # Buttons
        ttk.Button(top, text="Generate Maze", command=self.on_generate).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Load Maze", command=self.on_load).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Save Maze", command=self.on_save_maze).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Save Solution", command=self.on_save_solution).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Run Search", command=self.on_run_search).pack(side=tk.LEFT, padx=6)

        # Zoom controls
        zoom_bar = ttk.Frame(self)
        zoom_bar.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 10))

        ttk.Label(zoom_bar, text="Zoom:").pack(side=tk.LEFT)
        self.zoom_var = tk.DoubleVar(value=1.0)
        z = ttk.Scale(zoom_bar, from_=0.25, to=2.5, orient="horizontal",
                      command=self._on_zoom_change)
        z.set(1.0)
        z.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        # Canvases
        area = ttk.Frame(self)
        area.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=10, pady=10)
        area.columnconfigure(0, weight=1)
        area.rowconfigure(0, weight=1)
        area.rowconfigure(1, weight=1)

        ttk.Label(area, text="Search visualization (Yellow explored, Purple path)").grid(row=0, column=0, sticky="w")
        self.view_main = ZoomCanvas(area)
        self.view_main.grid(row=0, column=0, sticky="nsew", pady=(4, 12))

        ttk.Label(area, text="All shortest paths to exits (Green)").grid(row=1, column=0, sticky="w")
        self.view_green = ZoomCanvas(area)
        self.view_green.grid(row=1, column=0, sticky="nsew", pady=(4, 0))

        # Info
        self.info = ttk.Label(self, text="Ready.", justify="left")
        self.info.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

    def _on_zoom_change(self, _):
        zoom = float(self.zoom_var.get()) if self.zoom_var.get() else 1.0
        # ttk.Scale passes string sometimes; read directly from widget by using .get():
        # But easiest: read from the scale callback value:
        try:
            zoom = float(_)
        except Exception:
            zoom = 1.0
        self.view_main.set_zoom(zoom)
        self.view_green.set_zoom(zoom)

    def _on_thickness_change(self, val):
        try:
            self.cell_px = int(float(val))
        except Exception:
            self.cell_px = 8

        # Re-render if we already have a maze
        if self.grid_data is not None:
            self.base_img = grid_to_image(self.grid_data, cell_px=self.cell_px)
            self.start = find_start_center(self.grid_data)
            self.exits = find_exits(self.grid_data)
            self.overlay_img = self.base_img.copy()
            self.green_img = draw_green_all_paths(self.base_img, self.grid_data, self.start, self.exits, self.cell_px)
            self.view_main.set_image(self.overlay_img)
            self.view_green.set_image(self.green_img)

    def _set_info(self, s):
        self.info.configure(text=s)

    def on_generate(self):
        try:
            rows = int(self.rows_var.get())
            cols = int(self.cols_var.get())
        except Exception:
            rows, cols = 101, 101

        if rows % 2 == 0:
            rows += 1
        if cols % 2 == 0:
            cols += 1
        rows = max(31, min(401, rows))
        cols = max(31, min(401, cols))

        try:
            num_exits = int(self.exit_var.get())
        except Exception:
            num_exits = 1
        num_exits = max(1, min(5, num_exits))

        try:
            room = int(self.room_var.get())
        except Exception:
            room = 21
        if room % 2 == 0:
            room += 1

        self.grid_data = generate_perfect_maze(rows, cols)
        carve_center_square_room(self.grid_data, room)
        add_random_exits(self.grid_data, num_exits)

        self.start = find_start_center(self.grid_data)
        self.exits = find_exits(self.grid_data)

        self.base_img = grid_to_image(self.grid_data, cell_px=self.cell_px)
        self.overlay_img = self.base_img.copy()
        self.green_img = draw_green_all_paths(self.base_img, self.grid_data, self.start, self.exits, self.cell_px)

        self.view_main.set_image(self.overlay_img)
        self.view_green.set_image(self.green_img)

        self._set_info(
            f"Generated maze {rows}x{cols}\n"
            f"Center room: {room}\n"
            f"Start: {self.start}\n"
            f"Exits found: {len(self.exits)}"
        )

    def on_load(self):
        path = filedialog.askopenfilename(
            title="Load Maze Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg")]
        )
        if not path:
            return
        try:
            img = Image.open(path)
        except Exception as e:
            messagebox.showerror("Load error", str(e))
            return

        # Use UI size as target grid (odd)
        rows = int(self.rows_var.get())
        cols = int(self.cols_var.get())
        if rows % 2 == 0:
            rows += 1
        if cols % 2 == 0:
            cols += 1
        rows = max(31, min(401, rows))
        cols = max(31, min(401, cols))

        self.grid_data = image_to_grid(img, rows, cols)
        self.start = find_start_center(self.grid_data)
        self.exits = find_exits(self.grid_data)

        self.base_img = grid_to_image(self.grid_data, cell_px=self.cell_px)
        self.overlay_img = self.base_img.copy()
        self.green_img = draw_green_all_paths(self.base_img, self.grid_data, self.start, self.exits, self.cell_px)

        self.view_main.set_image(self.overlay_img)
        self.view_green.set_image(self.green_img)

        self._set_info(
            f"Loaded maze -> resampled to {rows}x{cols}\n"
            f"Start: {self.start}\n"
            f"Exits found: {len(self.exits)}"
        )

    def on_save_maze(self):
        if self.base_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Maze",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPG", "*.jpg *.jpeg")]
        )
        if not path:
            return
        try:
            self.base_img.save(path)
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def on_save_solution(self):
        if self.overlay_img is None:
            messagebox.showwarning("No solution", "Run a search first (or generate/load a maze).")
            return
        path = filedialog.asksaveasfilename(
            title="Save Solution Image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPG", "*.jpg *.jpeg")]
        )
        if not path:
            return
        try:
            self.overlay_img.save(path)
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def on_run_search(self):
        if self.grid_data is None:
            messagebox.showwarning("No maze", "Generate or load a maze first.")
            return

        method = self.method_var.get()
        bidir = bool(self.bidir_var.get())

        self.start = find_start_center(self.grid_data)
        self.exits = find_exits(self.grid_data)

        if not self.exits:
            messagebox.showwarning("No exits", "No exits detected on the boundary.")
            return

        if bidir:
            path, explored, explored_list = search_bidirectional(self.grid_data, self.start, self.exits, method)
        else:
            path, explored, explored_list = search_unidirectional(self.grid_data, self.start, self.exits, method)

        self.base_img = grid_to_image(self.grid_data, cell_px=self.cell_px)

        if path is None:
            self.overlay_img = draw_overlays(self.base_img, self.start, self.exits,
                                             explored_list, None, self.cell_px)
            result = "NO PATH FOUND"
            plen = 0
        else:
            self.overlay_img = draw_overlays(self.base_img, self.start, self.exits,
                                             explored_list, path, self.cell_px)
            result = "PATH FOUND"
            plen = len(path)

        self.green_img = draw_green_all_paths(self.base_img, self.grid_data, self.start, self.exits, self.cell_px)

        self.view_main.set_image(self.overlay_img)
        self.view_green.set_image(self.green_img)

        self._set_info(
            f"Search: {method} | Bidirectional: {bidir}\n"
            f"{result}\n"
            f"Path length: {plen}\n"
            f"Explored nodes: {len(explored)}"
        )


if __name__ == "__main__":
    app = MazeApp()
    app.mainloop()
