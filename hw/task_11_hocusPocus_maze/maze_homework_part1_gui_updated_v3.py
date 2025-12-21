#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maze Homework GUI (Part I) - Updated v3

Requested updates:
1) Generation has a CENTER ROOM at least 3x3 tiles (open square). The middle tile is the start.
   - If user gives even "cells" size, we still generate normally and center aligns to a tile.
2) Zoom + Fit buttons:
   - Right panel: zoom slider + "FIT" button (reset to fitted view).
   - Left panel (both previews): zoom slider + "FIT" button.
   - Ctrl+MouseWheel zoom and drag-to-pan still supported.
3) Removed min/max exits. Only "Number of exits (1..5)" remains.
4) Added Min/Max balls controls (default 0). (Balls not drawn yet; will be used in Part II.)
5) Analysis method improved for future colored balls:
   - Walls are detected by "darkness" on RGB (max(R,G,B) < wall_darkness => WALL)
   - This keeps colored balls (red/green/blue) as FREE space automatically.
   - More robust for JPEG artifacts than a pure grayscale threshold.
6) Saving as JPEG fixed:
   - Added "Save format: PNG/JPG" selector.
   - Save dialogs will automatically append the correct extension if you don’t type it.

Dependencies: Pillow
  pip install pillow
Run:
  python3 maze_homework_part1_gui_updated_v3.py
"""

import random
import heapq
import time
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from PIL import Image, ImageTk, ImageDraw, ImageOps

Coord = Tuple[int, int]


# =========================
# Utilities
# =========================

def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))

def clampf(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def ensure_extension(path: str, fmt: str) -> str:
    """
    Ensures path ends with correct extension for fmt ("PNG" or "JPG").
    """
    fmt = fmt.upper()
    root, ext = os.path.splitext(path)
    ext = ext.lower()
    if fmt == "PNG":
        if ext not in (".png",):
            return root + ".png"
        return path
    # JPG
    if ext not in (".jpg", ".jpeg"):
        return root + ".jpg"
    return path


# =========================
# Maze generation (tile grid)
# =========================

@dataclass
class MazeData:
    tile_w: int
    tile_h: int
    tiles: List[List[int]]  # 1 = wall, 0 = free
    start: Coord            # in tile coordinates
    exits: List[Coord]      # in tile coordinates


class MazeGenerator:
    """
    Perfect maze on a cell grid (w x h), converted to a tile grid (2w+1 x 2h+1).
    Walls at even indices, cells at odd indices.
    """
    def __init__(self, cells_w: int, cells_h: int, seed: Optional[int] = None):
        self.cells_w = max(3, int(cells_w))
        self.cells_h = max(3, int(cells_h))
        self.rng = random.Random(seed)

    def generate(self, desired_exits: int) -> MazeData:
        w, h = self.cells_w, self.cells_h
        tw, th = 2 * w + 1, 2 * h + 1

        tiles = [[1 for _ in range(tw)] for _ in range(th)]
        visited = [[False for _ in range(w)] for _ in range(h)]

        def cell_to_tile(cx: int, cy: int) -> Coord:
            return (2 * cx + 1, 2 * cy + 1)

        # Start at center cell
        sx, sy = w // 2, h // 2
        tx, ty = cell_to_tile(sx, sy)
        tiles[ty][tx] = 0
        stack = [(sx, sy)]
        visited[sy][sx] = True

        # Randomized DFS carving
        while stack:
            cx, cy = stack[-1]
            nbrs = []
            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx]:
                    nbrs.append((nx, ny))
            if not nbrs:
                stack.pop()
                continue

            nx, ny = self.rng.choice(nbrs)

            cx_t, cy_t = cell_to_tile(cx, cy)
            nx_t, ny_t = cell_to_tile(nx, ny)
            wall_x, wall_y = (cx_t + nx_t) // 2, (cy_t + ny_t) // 2

            tiles[cy_t][cx_t] = 0
            tiles[wall_y][wall_x] = 0
            tiles[ny_t][nx_t] = 0

            visited[ny][nx] = True
            stack.append((nx, ny))

        # Create exits (1..5)
        desired_exits = clamp(int(desired_exits), 1, 5)

        # Candidate exits: border tiles adjacent to an inner free tile
        candidates: List[Coord] = []
        for x in range(1, tw-1):
            if tiles[1][x] == 0:
                candidates.append((x, 0))
            if tiles[th-2][x] == 0:
                candidates.append((x, th-1))
        for y in range(1, th-1):
            if tiles[y][1] == 0:
                candidates.append((0, y))
            if tiles[y][tw-2] == 0:
                candidates.append((tw-1, y))

        candidates = list(dict.fromkeys(candidates))
        self.rng.shuffle(candidates)
        exits = candidates[:desired_exits]
        for ex, ey in exits:
            tiles[ey][ex] = 0  # hole in the outer wall

        start = (tx, ty)
        maze = MazeData(tile_w=tw, tile_h=th, tiles=tiles, start=start, exits=exits)

        # Center room: at least 3x3 tiles; start is the middle tile
        carve_center_room_tiles(maze, room_tiles=3)

        return maze


def carve_center_room_tiles(maze: MazeData, room_tiles: int = 3):
    """
    Opens a square room centered at maze.start with size room_tiles x room_tiles
    (minimum 3x3). Keeps inside bounds.
    """
    s = max(3, int(room_tiles))
    if s % 2 == 0:
        s += 1  # keep odd so start is centered
    cx, cy = maze.start
    half = s // 2

    x0 = clamp(cx - half, 1, maze.tile_w - 2)
    x1 = clamp(cx + half, 1, maze.tile_w - 2)
    y0 = clamp(cy - half, 1, maze.tile_h - 2)
    y1 = clamp(cy + half, 1, maze.tile_h - 2)

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            maze.tiles[y][x] = 0

    # Ensure at least one doorway out of the room (open one step beyond each side if possible)
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        ox, oy = cx + dx * (half + 1), cy + dy * (half + 1)
        if 1 <= ox < maze.tile_w - 1 and 1 <= oy < maze.tile_h - 1:
            maze.tiles[oy][ox] = 0


def tiles_to_bw_image(maze: MazeData, tile_px: int = 8) -> Image.Image:
    """
    STRICT BLACK/WHITE render with BLACK outer border.
    - background black
    - free tiles (including exits) white
    """
    tile_px = max(2, int(tile_px))
    img = Image.new("RGB", (maze.tile_w * tile_px, maze.tile_h * tile_px), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(maze.tile_h):
        for x in range(maze.tile_w):
            if maze.tiles[y][x] == 0:
                x0 = x * tile_px
                y0 = y * tile_px
                draw.rectangle([x0, y0, x0 + tile_px - 1, y0 + tile_px - 1], fill=(255, 255, 255))
    return img


def solve_on_tiles_shortest_paths(maze: MazeData) -> Dict[Coord, List[Coord]]:
    start = maze.start
    goals = set(maze.exits)
    q = [start]
    parent: Dict[Coord, Optional[Coord]] = {start: None}

    def neighbors(p: Coord):
        x, y = p
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < maze.tile_w and 0 <= ny < maze.tile_h and maze.tiles[ny][nx] == 0:
                yield (nx, ny)

    found = set()
    while q and found != goals:
        cur = q.pop(0)
        if cur in goals:
            found.add(cur)
            if found == goals:
                break
        for nb in neighbors(cur):
            if nb not in parent:
                parent[nb] = cur
                q.append(nb)

    paths: Dict[Coord, List[Coord]] = {}
    for g in goals:
        if g not in parent:
            continue
        path = []
        cur = g
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        paths[g] = path
    return paths


def overlay_green_paths_on_bw(base_bw: Image.Image, maze: MazeData, paths: List[List[Coord]],
                             tile_px: int = 8) -> Image.Image:
    img = base_bw.copy()
    draw = ImageDraw.Draw(img)

    def tile_center(x: int, y: int) -> Tuple[int, int]:
        return (x*tile_px + tile_px//2, y*tile_px + tile_px//2)

    width_px = max(2, tile_px // 3)
    for path in paths:
        if len(path) < 2:
            continue
        pts = [tile_center(x, y) for (x, y) in path]
        draw.line(pts, fill=(0, 180, 0), width=width_px)
    return img


# =========================
# Image-based analysis (for Part II readiness)
# =========================

@dataclass
class AnalyzedMaze:
    grid_w: int
    grid_h: int
    free: List[List[bool]]  # free[y][x]
    start: Coord
    exits: List[Coord]
    base_image: Image.Image  # BW visualization (walls black, free white)


class MazeAnalyzer:
    @staticmethod
    def _auto_crop(gray: Image.Image) -> Image.Image:
        bw = gray.point(lambda p: 0 if p < 245 else 255, mode="L")
        bbox = ImageOps.invert(bw).getbbox()
        if not bbox:
            return gray
        x0, y0, x1, y1 = bbox
        pad_x = max(5, int(0.05 * (x1 - x0)))
        pad_y = max(5, int(0.05 * (y1 - y0)))
        x0 = max(0, x0 - pad_x)
        y0 = max(0, y0 - pad_y)
        x1 = min(gray.width, x1 + pad_x)
        y1 = min(gray.height, y1 + pad_y)
        return gray.crop((x0, y0, x1, y1))

    @staticmethod
    def analyze_rgb_darkness(img: Image.Image, grid_w: int, grid_h: int, wall_darkness: int = 80) -> AnalyzedMaze:
        """
        Robust wall detection for future colored balls:
          wall if max(R,G,B) < wall_darkness
          otherwise free.

        Why this helps:
          - Walls are black-ish.
          - Paths are white-ish.
          - Balls are colored (R/G/B high) => treated as free automatically.
          - JPEG artifacts still keep walls relatively dark.
        """
        grid_w = max(51, int(grid_w))
        grid_h = max(51, int(grid_h))
        wall_darkness = clamp(int(wall_darkness), 5, 200)

        rgb = img.convert("RGB")
        gray = ImageOps.autocontrast(rgb.convert("L"))
        gray = MazeAnalyzer._auto_crop(gray)

        # Crop using bbox computed on grayscale, apply crop to RGB too
        # (recompute bbox to crop rgb consistently)
        bw = gray.point(lambda p: 0 if p < 245 else 255, mode="L")
        bbox = ImageOps.invert(bw).getbbox()
        if bbox:
            x0, y0, x1, y1 = bbox
            pad_x = max(5, int(0.05 * (x1 - x0)))
            pad_y = max(5, int(0.05 * (y1 - y0)))
            x0 = max(0, x0 - pad_x)
            y0 = max(0, y0 - pad_y)
            x1 = min(rgb.width, x1 + pad_x)
            y1 = min(rgb.height, y1 + pad_y)
            rgb = rgb.crop((x0, y0, x1, y1))

        # NEAREST to avoid corner rounding
        rgb = rgb.resize((grid_w, grid_h), Image.Resampling.NEAREST)
        px = rgb.load()

        free = [[False for _ in range(grid_w)] for _ in range(grid_h)]
        for y in range(grid_h):
            for x in range(grid_w):
                r, g, b = px[x, y]
                free[y][x] = (max(r, g, b) >= wall_darkness)

        exits: List[Coord] = []
        for x in range(grid_w):
            if free[0][x]:
                exits.append((x, 0))
            if free[grid_h-1][x]:
                exits.append((x, grid_h-1))
        for y in range(grid_h):
            if free[y][0]:
                exits.append((0, y))
            if free[y][grid_w-1]:
                exits.append((grid_w-1, y))
        exits = list(dict.fromkeys(exits))

        cx, cy = grid_w // 2, grid_h // 2
        start = (cx, cy)
        if not free[cy][cx]:
            q = [start]
            seen = {start}
            found = None
            while q and found is None:
                x, y = q.pop(0)
                for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < grid_w and 0 <= ny < grid_h and (nx, ny) not in seen:
                        seen.add((nx, ny))
                        if free[ny][nx]:
                            found = (nx, ny)
                            break
                        q.append((nx, ny))
            if found:
                start = found

        base = Image.new("RGB", (grid_w, grid_h), (0, 0, 0))
        bpx = base.load()
        for y in range(grid_h):
            for x in range(grid_w):
                if free[y][x]:
                    bpx[x, y] = (255, 255, 255)

        return AnalyzedMaze(grid_w, grid_h, free, start, exits, base)


# =========================
# Search algorithms
# =========================

@dataclass
class SearchResult:
    found: bool
    path: List[Coord]
    explored: List[Coord]
    goal: Optional[Coord]


def _neighbors_4(free: List[List[bool]], p: Coord) -> List[Coord]:
    x, y = p
    h = len(free)
    w = len(free[0]) if h else 0
    out = []
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and free[ny][nx]:
            out.append((nx, ny))
    return out


def _reconstruct(parent: Dict[Coord, Optional[Coord]], end: Coord) -> List[Coord]:
    path = []
    cur = end
    while cur is not None:
        path.append(cur)
        cur = parent.get(cur)
    path.reverse()
    return path


def _nearest_exit_heuristic(exits: List[Coord], p: Coord) -> int:
    return 0 if not exits else min(manhattan(p, g) for g in exits)


def search_unidirectional(free: List[List[bool]], start: Coord, exits: List[Coord], method: str) -> SearchResult:
    goals = set(exits)
    explored: List[Coord] = []
    parent: Dict[Coord, Optional[Coord]] = {start: None}

    if method == "Breadth First":
        q = [start]
        seen = {start}
        while q:
            cur = q.pop(0)
            explored.append(cur)
            if cur in goals:
                return SearchResult(True, _reconstruct(parent, cur), explored, cur)
            for nb in _neighbors_4(free, cur):
                if nb not in seen:
                    seen.add(nb)
                    parent[nb] = cur
                    q.append(nb)
        return SearchResult(False, [], explored, None)

    if method == "Depth First":
        stack = [start]
        seen = {start}
        while stack:
            cur = stack.pop()
            explored.append(cur)
            if cur in goals:
                return SearchResult(True, _reconstruct(parent, cur), explored, cur)
            for nb in _neighbors_4(free, cur):
                if nb not in seen:
                    seen.add(nb)
                    parent[nb] = cur
                    stack.append(nb)
        return SearchResult(False, [], explored, None)

    if method in ("Uniform Cost", "Best First (Greedy)", "A*"):
        heap = []
        g_cost: Dict[Coord, int] = {start: 0}
        seen: Set[Coord] = set()

        def priority(node: Coord) -> int:
            g = g_cost[node]
            h = _nearest_exit_heuristic(exits, node)
            if method == "Uniform Cost":
                return g
            if method == "Best First (Greedy)":
                return h
            return g + h

        heapq.heappush(heap, (priority(start), 0.0, start))

        while heap:
            _, _, cur = heapq.heappop(heap)
            if cur in seen:
                continue
            seen.add(cur)
            explored.append(cur)
            if cur in goals:
                return SearchResult(True, _reconstruct(parent, cur), explored, cur)

            for nb in _neighbors_4(free, cur):
                ng = g_cost[cur] + 1
                if nb not in g_cost or ng < g_cost[nb]:
                    g_cost[nb] = ng
                    parent[nb] = cur
                    heapq.heappush(heap, (priority(nb), random.random(), nb))

        return SearchResult(False, [], explored, None)

    raise ValueError(f"Unknown method: {method}")


def search_bidirectional(free: List[List[bool]], start: Coord, exits: List[Coord], method: str) -> SearchResult:
    if not exits:
        return SearchResult(False, [], [], None)

    explored: List[Coord] = []
    goals_set = set(exits)

    parent_f: Dict[Coord, Optional[Coord]] = {start: None}
    parent_b: Dict[Coord, Optional[Coord]] = {g: None for g in exits}

    seen_f: Set[Coord] = set()
    seen_b: Set[Coord] = set()

    g_f: Dict[Coord, int] = {start: 0}
    g_b: Dict[Coord, int] = {g: 0 for g in exits}

    def prio_f(node: Coord) -> int:
        g = g_f[node]
        h = _nearest_exit_heuristic(exits, node)
        if method == "Uniform Cost":
            return g
        if method == "Best First (Greedy)":
            return h
        if method == "A*":
            return g + h
        return g

    def prio_b(node: Coord) -> int:
        g = g_b[node]
        h = manhattan(node, start)
        if method == "Uniform Cost":
            return g
        if method == "Best First (Greedy)":
            return h
        if method == "A*":
            return g + h
        return g

    if method == "Breadth First":
        frontier_f = [start]
        frontier_b = list(exits)
        pop_f = lambda: frontier_f.pop(0) if frontier_f else None
        pop_b = lambda: frontier_b.pop(0) if frontier_b else None
        push_f = lambda n: frontier_f.append(n)
        push_b = lambda n: frontier_b.append(n)
    elif method == "Depth First":
        frontier_f = [start]
        frontier_b = list(exits)
        pop_f = lambda: frontier_f.pop() if frontier_f else None
        pop_b = lambda: frontier_b.pop() if frontier_b else None
        push_f = lambda n: frontier_f.append(n)
        push_b = lambda n: frontier_b.append(n)
    else:
        frontier_f = []
        frontier_b = []
        heapq.heappush(frontier_f, (prio_f(start), 0.0, start))
        for g in exits:
            heapq.heappush(frontier_b, (prio_b(g), 0.0, g))

        def pop_f():
            while frontier_f:
                _, _, n = heapq.heappop(frontier_f)
                if n not in seen_f:
                    return n
            return None

        def pop_b():
            while frontier_b:
                _, _, n = heapq.heappop(frontier_b)
                if n not in seen_b:
                    return n
            return None

        def push_f(n):
            heapq.heappush(frontier_f, (prio_f(n), random.random(), n))

        def push_b(n):
            heapq.heappush(frontier_b, (prio_b(n), random.random(), n))

    meet: Optional[Coord] = None

    while True:
        cur_f = pop_f()
        if cur_f is None:
            break
        if cur_f not in seen_f:
            seen_f.add(cur_f)
            explored.append(cur_f)
            if cur_f in seen_b:
                meet = cur_f
                break
            for nb in _neighbors_4(free, cur_f):
                if nb in seen_f:
                    continue
                if method in ("Uniform Cost", "A*"):
                    ng = g_f[cur_f] + 1
                    if nb not in g_f or ng < g_f[nb]:
                        g_f[nb] = ng
                        parent_f[nb] = cur_f
                        push_f(nb)
                else:
                    if nb not in parent_f:
                        parent_f[nb] = cur_f
                        g_f[nb] = g_f[cur_f] + 1
                        push_f(nb)

        cur_b = pop_b()
        if cur_b is None:
            break
        if cur_b not in seen_b:
            seen_b.add(cur_b)
            explored.append(cur_b)
            if cur_b in seen_f:
                meet = cur_b
                break
            for nb in _neighbors_4(free, cur_b):
                if nb in seen_b:
                    continue
                if method in ("Uniform Cost", "A*"):
                    ng = g_b[cur_b] + 1
                    if nb not in g_b or ng < g_b[nb]:
                        g_b[nb] = ng
                        parent_b[nb] = cur_b
                        push_b(nb)
                else:
                    if nb not in parent_b:
                        parent_b[nb] = cur_b
                        g_b[nb] = g_b[cur_b] + 1
                        push_b(nb)

    if meet is None:
        return SearchResult(False, [], explored, None)

    path_f = _reconstruct(parent_f, meet)

    path_b = [meet]
    cur = meet
    while cur not in goals_set:
        cur = parent_b.get(cur)
        if cur is None:
            break
        path_b.append(cur)

    full = path_f + path_b[1:]
    goal = path_b[-1] if path_b and path_b[-1] in goals_set else None
    return SearchResult(True, full, explored, goal)


def draw_search_result(analyzed: AnalyzedMaze, result: SearchResult, cell_px: int = 5) -> Image.Image:
    cell_px = max(2, int(cell_px))

    base_small = analyzed.base_image.copy().convert("RGB")
    base = base_small.resize((analyzed.grid_w * cell_px, analyzed.grid_h * cell_px), Image.Resampling.NEAREST)
    draw = ImageDraw.Draw(base)

    def rect(node: Coord):
        x, y = node
        x0 = x * cell_px
        y0 = y * cell_px
        return [x0, y0, x0 + cell_px - 1, y0 + cell_px - 1]

    for n in result.explored:
        if analyzed.free[n[1]][n[0]]:
            draw.rectangle(rect(n), fill=(255, 255, 0))  # yellow

    for n in result.path:
        if analyzed.free[n[1]][n[0]]:
            draw.rectangle(rect(n), fill=(160, 0, 200))  # purple

    draw.rectangle(rect(analyzed.start), fill=(80, 160, 255))  # blue start marker
    return base


# =========================
# Fit + Zoom canvas
# =========================

class FitZoomCanvas(ttk.Frame):
    """
    Shows an image initially FITTED to the widget. Zoom factor multiplies the fit scale.
    - Ctrl+MouseWheel zoom
    - Drag to pan
    - Scrollbars available
    """
    def __init__(self, master, *, bg="#111111"):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.hbar.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self._pil: Optional[Image.Image] = None
        self._tk: Optional[ImageTk.PhotoImage] = None
        self._zoom_factor: float = 1.0
        self._fit_scale: float = 1.0

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.canvas.bind("<Control-Button-4>", self._on_ctrl_wheel_linux_up)
        self.canvas.bind("<Control-Button-5>", self._on_ctrl_wheel_linux_down)

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self._drag_from = None

    def set_image(self, img: Optional[Image.Image], *, reset_zoom: bool = True):
        self._pil = img
        if reset_zoom:
            self._zoom_factor = 1.0
        self._render()

    def set_zoom_factor(self, z: float):
        self._zoom_factor = clampf(float(z), 0.2, 8.0)
        self._render()

    def fit(self):
        self._zoom_factor = 1.0
        self._render()

    def get_zoom_factor(self) -> float:
        return self._zoom_factor

    def _on_resize(self, _event):
        self._render()

    def _compute_fit_scale(self) -> float:
        if self._pil is None:
            return 1.0
        cw = max(1, self.canvas.winfo_width())
        ch = max(1, self.canvas.winfo_height())
        iw, ih = self._pil.size
        return min(cw / iw, ch / ih) * 0.98

    def _render(self):
        self.canvas.delete("all")
        if self._pil is None:
            self.canvas.configure(scrollregion=(0, 0, 1, 1))
            return

        self._fit_scale = self._compute_fit_scale()
        scale = self._fit_scale * self._zoom_factor

        iw, ih = self._pil.size
        nw = max(1, int(iw * scale))
        nh = max(1, int(ih * scale))
        img = self._pil.resize((nw, nh), Image.Resampling.NEAREST)
        self._tk = ImageTk.PhotoImage(img)

        self.canvas.create_image(0, 0, anchor="nw", image=self._tk)
        self.canvas.configure(scrollregion=(0, 0, nw, nh))

        if abs(self._zoom_factor - 1.0) < 1e-6:
            self.canvas.xview_moveto(0.0)
            self.canvas.yview_moveto(0.0)

    def _on_ctrl_wheel(self, event):
        step = 1.12 if event.delta > 0 else 0.88
        self.set_zoom_factor(self._zoom_factor * step)

    def _on_ctrl_wheel_linux_up(self, _event):
        self.set_zoom_factor(self._zoom_factor * 1.12)

    def _on_ctrl_wheel_linux_down(self, _event):
        self.set_zoom_factor(self._zoom_factor * 0.88)

    def _on_press(self, event):
        self._drag_from = (event.x, event.y)

    def _on_drag(self, event):
        if self._drag_from is None:
            return
        dx = self._drag_from[0] - event.x
        dy = self._drag_from[1] - event.y
        self._drag_from = (event.x, event.y)
        self.canvas.xview_scroll(int(dx), "units")
        self.canvas.yview_scroll(int(dy), "units")


# =========================
# Main GUI
# =========================

class MazeHomeworkApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maze Homework - Part I (Updated v3)")
        self.geometry("1280x780")
        self.minsize(1100, 650)

        # State (left determines current maze)
        self.generated_maze: Optional[MazeData] = None
        self.generated_bw_img: Optional[Image.Image] = None
        self.generated_solution_img: Optional[Image.Image] = None
        self.loaded_img: Optional[Image.Image] = None

        self.current_maze_img: Optional[Image.Image] = None
        self.current_label: str = "None"

        # Layout: left 1/3, right 2/3
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self.left = ttk.Frame(self, padding=10)
        self.right = ttk.Frame(self, padding=10)
        self.left.grid(row=0, column=0, sticky="nsew")
        self.right.grid(row=0, column=1, sticky="nsew")

        self._build_left()
        self._build_right()

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

    # ---------- Left side ----------
    def _build_left(self):
        self.left.columnconfigure(0, weight=1)
        self.left.rowconfigure(1, weight=1)

        lf = ttk.LabelFrame(self.left, text="Maze Generation / Loading", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        row = 0
        ttk.Label(lf, text="Maze size (cells)").grid(row=row, column=0, sticky="w")
        self.var_cells_w = tk.IntVar(value=18)
        self.var_cells_h = tk.IntVar(value=18)
        frm_size = ttk.Frame(lf)
        frm_size.grid(row=row, column=1, sticky="w")
        ttk.Spinbox(frm_size, from_=3, to=80, textvariable=self.var_cells_w, width=5).pack(side="left")
        ttk.Label(frm_size, text=" x ").pack(side="left")
        ttk.Spinbox(frm_size, from_=3, to=80, textvariable=self.var_cells_h, width=5).pack(side="left")
        row += 1

        ttk.Label(lf, text="Tile pixel size (save/render)").grid(row=row, column=0, sticky="w")
        self.var_tile_px = tk.IntVar(value=10)
        ttk.Spinbox(lf, from_=4, to=25, textvariable=self.var_tile_px, width=8).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(lf, text="Number of exits (1..5)").grid(row=row, column=0, sticky="w")
        self.var_exits = tk.IntVar(value=1)
        ttk.Spinbox(lf, from_=1, to=5, textvariable=self.var_exits, width=8).grid(row=row, column=1, sticky="w")
        row += 1

        # Balls min/max (Part II)
        ttk.Label(lf, text="Min balls (default 0)").grid(row=row, column=0, sticky="w")
        self.var_min_balls = tk.IntVar(value=0)
        ttk.Spinbox(lf, from_=0, to=200, textvariable=self.var_min_balls, width=8).grid(row=row, column=1, sticky="w")
        row += 1

        ttk.Label(lf, text="Max balls (default 0)").grid(row=row, column=0, sticky="w")
        self.var_max_balls = tk.IntVar(value=0)
        ttk.Spinbox(lf, from_=0, to=200, textvariable=self.var_max_balls, width=8).grid(row=row, column=1, sticky="w")
        row += 1

        # Save format selection
        ttk.Label(lf, text="Save format").grid(row=row, column=0, sticky="w")
        self.var_save_fmt = tk.StringVar(value="PNG")
        ttk.OptionMenu(lf, self.var_save_fmt, self.var_save_fmt.get(), "PNG", "JPG").grid(row=row, column=1, sticky="w")
        row += 1

        btns = ttk.Frame(lf)
        btns.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btns.columnconfigure((0,1), weight=1)
        ttk.Button(btns, text="Generate Maze", command=self.on_generate).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Load Maze (PNG/JPG)", command=self.on_load).grid(row=0, column=1, sticky="ew")
        row += 1

        btns2 = ttk.Frame(lf)
        btns2.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        btns2.columnconfigure((0,1), weight=1)
        ttk.Button(btns2, text="Save Current Maze", command=self.on_save_current_maze).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns2, text="Save Green Solution", command=self.on_save_solution).grid(row=0, column=1, sticky="ew")
        row += 1

        pv = ttk.LabelFrame(self.left, text="Preview", padding=6)
        pv.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        pv.columnconfigure(0, weight=1)
        pv.rowconfigure(2, weight=1)
        pv.rowconfigure(5, weight=1)

        # Current maze controls
        ttk.Label(pv, text="Current Maze").grid(row=0, column=0, sticky="w")
        ctrl1 = ttk.Frame(pv)
        ctrl1.grid(row=1, column=0, sticky="ew")
        ttk.Label(ctrl1, text="Zoom").pack(side="left")
        self.var_zoom_left1 = tk.DoubleVar(value=1.0)
        ttk.Scale(ctrl1, from_=0.3, to=6.0, variable=self.var_zoom_left1, command=self._on_zoom_left1).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(ctrl1, text="FIT", command=self._fit_left1).pack(side="left")

        self.preview_current = FitZoomCanvas(pv, bg="#111111")
        self.preview_current.grid(row=2, column=0, sticky="nsew", pady=(4, 12))

        # Solution preview controls
        ttk.Label(pv, text="Solution preview (green) - generated only").grid(row=3, column=0, sticky="w")
        ctrl2 = ttk.Frame(pv)
        ctrl2.grid(row=4, column=0, sticky="ew")
        ttk.Label(ctrl2, text="Zoom").pack(side="left")
        self.var_zoom_left2 = tk.DoubleVar(value=1.0)
        ttk.Scale(ctrl2, from_=0.3, to=6.0, variable=self.var_zoom_left2, command=self._on_zoom_left2).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(ctrl2, text="FIT", command=self._fit_left2).pack(side="left")

        self.preview_solution = FitZoomCanvas(pv, bg="#111111")
        self.preview_solution.grid(row=5, column=0, sticky="nsew", pady=(4, 0))

        self.lbl_left_status = ttk.Label(self.left, text="Current maze: None")
        self.lbl_left_status.grid(row=2, column=0, sticky="ew", pady=(8, 0))

    def _on_zoom_left1(self, val):
        try:
            self.preview_current.set_zoom_factor(float(val))
        except Exception:
            pass

    def _on_zoom_left2(self, val):
        try:
            self.preview_solution.set_zoom_factor(float(val))
        except Exception:
            pass

    def _fit_left1(self):
        self.var_zoom_left1.set(1.0)
        self.preview_current.fit()

    def _fit_left2(self):
        self.var_zoom_left2.set(1.0)
        self.preview_solution.fit()

    def _set_current_maze(self, img: Image.Image, label: str):
        self.current_maze_img = img
        self.current_label = label

        self.preview_current.set_image(img, reset_zoom=True)
        self.var_zoom_left1.set(1.0)

        self.lbl_left_status.config(text=f"Current maze: {label}")

        # Also refresh right panel base view
        self.view_right.set_image(img, reset_zoom=True)
        self.var_zoom_right.set(1.0)
        self.lbl_right_status.config(text=f"Ready. Using: {label}")

    def on_generate(self):
        try:
            # Balls min/max sanity (not used yet)
            mn = int(self.var_min_balls.get())
            mx = int(self.var_max_balls.get())
            if mn < 0: mn = 0
            if mx < 0: mx = 0
            if mn > mx:
                mn, mx = mx, mn
                self.var_min_balls.set(mn)
                self.var_max_balls.set(mx)

            gen = MazeGenerator(self.var_cells_w.get(), self.var_cells_h.get())
            maze = gen.generate(self.var_exits.get())
            self.generated_maze = maze

            tile_px = self.var_tile_px.get()
            self.generated_bw_img = tiles_to_bw_image(maze, tile_px=tile_px)

            paths_dict = solve_on_tiles_shortest_paths(maze)
            paths = list(paths_dict.values())
            self.generated_solution_img = overlay_green_paths_on_bw(self.generated_bw_img, maze, paths, tile_px=tile_px)
            self.preview_solution.set_image(self.generated_solution_img, reset_zoom=True)
            self.var_zoom_left2.set(1.0)

            self._set_current_maze(self.generated_bw_img, f"Generated ({self.var_cells_w.get()}x{self.var_cells_h.get()} cells)")
        except Exception as e:
            messagebox.showerror("Generate Error", str(e))

    def on_load(self):
        fp = filedialog.askopenfilename(
            title="Select maze image",
            filetypes=[("Images", "*.png *.jpg *.jpeg"), ("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg")]
        )
        if not fp:
            return
        try:
            img = Image.open(fp).convert("RGB")
            self.loaded_img = img
            self.preview_solution.set_image(None, reset_zoom=True)
            self.var_zoom_left2.set(1.0)
            self._set_current_maze(img, "Loaded image")
        except Exception as e:
            messagebox.showerror("Load Error", str(e))

    def on_save_current_maze(self):
        if self.current_maze_img is None:
            messagebox.showwarning("Nothing to save", "Generate or load a maze first.")
            return
        fmt = self.var_save_fmt.get().upper()
        fp = filedialog.asksaveasfilename(
            title="Save current maze",
            defaultextension=".png" if fmt == "PNG" else ".jpg",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg")]
        )
        if not fp:
            return
        fp = ensure_extension(fp, fmt)
        try:
            if fmt == "PNG":
                self.current_maze_img.save(fp, format="PNG")
            else:
                self.current_maze_img.save(fp, format="JPEG", quality=95, subsampling=0)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def on_save_solution(self):
        if self.generated_solution_img is None:
            messagebox.showwarning("Nothing to save", "Generate a maze first (solution preview appears).")
            return
        fmt = self.var_save_fmt.get().upper()
        fp = filedialog.asksaveasfilename(
            title="Save green-solution image",
            defaultextension=".png" if fmt == "PNG" else ".jpg",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg *.jpeg")]
        )
        if not fp:
            return
        fp = ensure_extension(fp, fmt)
        try:
            if fmt == "PNG":
                self.generated_solution_img.save(fp, format="PNG")
            else:
                self.generated_solution_img.save(fp, format="JPEG", quality=95, subsampling=0)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ---------- Right side ----------
    def _build_right(self):
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(2, weight=1)

        lf = ttk.LabelFrame(self.right, text="Search (Analyze pixels + run algorithm)", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        res = ttk.Frame(lf)
        res.grid(row=0, column=0, sticky="ew")
        self.var_grid_w = tk.IntVar(value=201)
        self.var_grid_h = tk.IntVar(value=201)

        # Changed from grayscale threshold -> wall darkness (RGB)
        self.var_wall_dark = tk.IntVar(value=80)

        ttk.Label(res, text="Analysis grid (nodes)").pack(side="left")
        ttk.Spinbox(res, from_=51, to=401, increment=10, textvariable=self.var_grid_w, width=6).pack(side="left", padx=(8, 2))
        ttk.Label(res, text="x").pack(side="left")
        ttk.Spinbox(res, from_=51, to=401, increment=10, textvariable=self.var_grid_h, width=6).pack(side="left", padx=(2, 12))

        ttk.Label(res, text="Wall darkness").pack(side="left")
        ttk.Spinbox(res, from_=5, to=200, increment=5, textvariable=self.var_wall_dark, width=6).pack(side="left", padx=(8, 0))
        ttk.Label(res, text="(maxRGB < this => WALL)").pack(side="left", padx=(8, 0))

        algo = ttk.Frame(lf)
        algo.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(algo, text="Algorithm:").pack(side="left")
        self.var_algo = tk.StringVar(value="Breadth First")
        opts = ["Breadth First", "Depth First", "Uniform Cost", "Best First (Greedy)", "A*"]
        ttk.OptionMenu(algo, self.var_algo, self.var_algo.get(), *opts).pack(side="left", padx=(8, 0))

        self.var_bidir = tk.BooleanVar(value=False)
        ttk.Checkbutton(algo, text="Bidirectional", variable=self.var_bidir).pack(side="left", padx=(16, 0))

        runbar = ttk.Frame(lf)
        runbar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(runbar, text="RUN Part I", command=self.on_run_part1).pack(side="left")

        ttk.Label(runbar, text="Zoom").pack(side="left", padx=(16, 4))
        self.var_zoom_right = tk.DoubleVar(value=1.0)
        ttk.Scale(runbar, from_=0.3, to=6.0, variable=self.var_zoom_right, command=self._on_zoom_right).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(runbar, text="FIT", command=self._fit_right).pack(side="left", padx=(0, 10))

        self.lbl_right_status = ttk.Label(runbar, text="Ready.")
        self.lbl_right_status.pack(side="left")

        pv = ttk.LabelFrame(self.right, text="Display (Fit + Zoom)", padding=6)
        pv.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        pv.columnconfigure(0, weight=1)
        pv.rowconfigure(0, weight=1)

        self.view_right = FitZoomCanvas(pv, bg="#111111")
        self.view_right.grid(row=0, column=0, sticky="nsew")

    def _on_zoom_right(self, val):
        try:
            self.view_right.set_zoom_factor(float(val))
        except Exception:
            pass

    def _fit_right(self):
        self.var_zoom_right.set(1.0)
        self.view_right.fit()

    def on_run_part1(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return

        img = self.current_maze_img

        try:
            self.lbl_right_status.config(text=f"Analyzing ({self.current_label})...")
            self.update_idletasks()

            analyzed = MazeAnalyzer.analyze_rgb_darkness(
                img, self.var_grid_w.get(), self.var_grid_h.get(), self.var_wall_dark.get()
            )

            if not analyzed.exits:
                messagebox.showwarning(
                    "No exits found",
                    "No open cells detected on the border.\n"
                    "Try increasing Wall darkness (more walls), or increase analysis grid size."
                )
                self.view_right.set_image(analyzed.base_image, reset_zoom=False)
                return

            method = self.var_algo.get()
            bidir = bool(self.var_bidir.get())

            self.lbl_right_status.config(text=f"Searching ({method}, bidir={bidir})...")
            self.update_idletasks()

            t0 = time.perf_counter()
            if bidir:
                result = search_bidirectional(analyzed.free, analyzed.start, analyzed.exits, method)
            else:
                result = search_unidirectional(analyzed.free, analyzed.start, analyzed.exits, method)
            dt = time.perf_counter() - t0

            drawn = draw_search_result(analyzed, result, cell_px=5)

            # Keep user's zoom
            z = self.view_right.get_zoom_factor()
            self.view_right.set_image(drawn, reset_zoom=False)
            self.view_right.set_zoom_factor(z)

            if result.found:
                self.lbl_right_status.config(text=f"FOUND | path={len(result.path)} explored={len(result.explored)} time={dt:.4f}s")
            else:
                self.lbl_right_status.config(text=f"NOT FOUND | explored={len(result.explored)} time={dt:.4f}s")

        except Exception as e:
            messagebox.showerror("RUN Error", str(e))
            self.lbl_right_status.config(text="Ready.")


def main():
    app = MazeHomeworkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
