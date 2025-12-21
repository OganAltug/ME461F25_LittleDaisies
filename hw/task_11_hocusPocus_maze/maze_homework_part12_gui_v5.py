#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maze Homework GUI - Part I + Part II (v5)

CHANGE (what you asked):
✅ Part I logic from your first code is now implemented in this Part I+II code:
- Part I uses FAST analysis grid downsampling (e.g., 201x201) instead of pixel-by-pixel.
- Robust wall detection via RGB darkness: wall if max(R,G,B) < wall_darkness.
- Same Part I algorithms: BFS / DFS / Uniform Cost / Greedy / A*
- Optional Bidirectional search (same logic)
- Same Part I visualization: explored=yellow, path=purple, start=blue
- Right panel now includes Part I analysis controls: grid size + wall darkness (like first code)

Part II is kept as-is (centerline skeleton + ball projection + DP/greedy).

Dependencies:
  pip install pillow numpy
"""

import os
import time
import math
import random
import heapq
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union

import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw, ImageOps


Coord = Tuple[int, int]  # (x, y)


# =========================
# Utilities
# =========================

def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(x)))


def clampf(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def ensure_extension(path: str, fmt: str) -> str:
    fmt = fmt.upper()
    root, ext = os.path.splitext(path)
    ext = ext.lower()
    if fmt == "PNG":
        return root + ".png" if ext != ".png" else path
    return root + ".jpg" if ext not in (".jpg", ".jpeg") else path


# =========================
# Fit + Zoom canvas
# =========================

class FitZoomCanvas(ttk.Frame):
    """Initially FITTED. Zoom factor multiplies fit scale. Ctrl+wheel zoom, drag to pan."""
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
        self._zoom_factor = clampf(z, 0.2, 8.0)
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
# Maze generation (tile grid)
# =========================

@dataclass
class MazeData:
    tile_w: int
    tile_h: int
    tiles: List[List[int]]   # 1=wall,0=free
    start: Coord             # tile coords (x,y)
    exits: List[Coord]       # tile coords (x,y)
    balls: List[Tuple[Coord, str]]  # (tile coord, 'R'|'G'|'B')


class MazeGenerator:
    def __init__(self, cells_w: int, cells_h: int, seed: Optional[int] = None):
        self.cw = max(3, int(cells_w))
        self.ch = max(3, int(cells_h))
        self.rng = random.Random(seed)

    def generate(self, exits: int) -> MazeData:
        cw, ch = self.cw, self.ch
        tw, th = 2 * cw + 1, 2 * ch + 1
        tiles = [[1 for _ in range(tw)] for _ in range(th)]

        visited = [[False for _ in range(cw)] for _ in range(ch)]

        def cell_to_tile(cx: int, cy: int) -> Coord:
            return (2 * cx + 1, 2 * cy + 1)

        sx, sy = cw // 2, ch // 2
        stx, sty = cell_to_tile(sx, sy)
        tiles[sty][stx] = 0

        stack = [(sx, sy)]
        visited[sy][sx] = True

        while stack:
            cx, cy = stack[-1]
            candidates = []
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < cw and 0 <= ny < ch and not visited[ny][nx]:
                    candidates.append((nx, ny))
            if not candidates:
                stack.pop()
                continue

            nx, ny = self.rng.choice(candidates)
            cx_t, cy_t = cell_to_tile(cx, cy)
            nx_t, ny_t = cell_to_tile(nx, ny)
            wx, wy = (cx_t + nx_t) // 2, (cy_t + ny_t) // 2

            tiles[cy_t][cx_t] = 0
            tiles[wy][wx] = 0
            tiles[ny_t][nx_t] = 0

            visited[ny][nx] = True
            stack.append((nx, ny))

        exits = clamp(exits, 1, 5)
        cand: List[Coord] = []
        for x in range(1, tw-1):
            if tiles[1][x] == 0:        cand.append((x, 0))
            if tiles[th-2][x] == 0:     cand.append((x, th-1))
        for y in range(1, th-1):
            if tiles[y][1] == 0:        cand.append((0, y))
            if tiles[y][tw-2] == 0:     cand.append((tw-1, y))

        cand = list(dict.fromkeys(cand))
        self.rng.shuffle(cand)
        exits_list = cand[:exits]
        for ex, ey in exits_list:
            tiles[ey][ex] = 0

        start = (stx, sty)
        maze = MazeData(tw, th, tiles, start, exits_list, balls=[])
        carve_center_room(maze, room_tiles=3)
        return maze


def carve_center_room(maze: MazeData, room_tiles: int = 3):
    s = max(3, int(room_tiles))
    if s % 2 == 0:
        s += 1
    cx, cy = maze.start
    half = s // 2

    x0 = clamp(cx - half, 1, maze.tile_w - 2)
    x1 = clamp(cx + half, 1, maze.tile_w - 2)
    y0 = clamp(cy - half, 1, maze.tile_h - 2)
    y1 = clamp(cy + half, 1, maze.tile_h - 2)

    for y in range(y0, y1+1):
        for x in range(x0, x1+1):
            maze.tiles[y][x] = 0

    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        ox, oy = cx + dx*(half+1), cy + dy*(half+1)
        if 1 <= ox < maze.tile_w-1 and 1 <= oy < maze.tile_h-1:
            maze.tiles[oy][ox] = 0


def tiles_to_image_with_balls(maze: MazeData, tile_px: int = 10,
                             draw_balls: bool = False,
                             ball_px: int = 1) -> Image.Image:
    tile_px = max(2, int(tile_px))
    img = Image.new("RGB", (maze.tile_w * tile_px, maze.tile_h * tile_px), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    for y in range(maze.tile_h):
        for x in range(maze.tile_w):
            if maze.tiles[y][x] == 0:
                x0 = x * tile_px
                y0 = y * tile_px
                draw.rectangle([x0, y0, x0 + tile_px - 1, y0 + tile_px - 1], fill=(255, 255, 255))

    if draw_balls and maze.balls:
        for (bx, by), col in maze.balls:
            cx = bx * tile_px + tile_px // 2
            cy = by * tile_px + tile_px // 2
            r = max(0, int(ball_px)//2)
            if col == 'R':
                color = (255, 0, 0)
            elif col == 'G':
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            draw.rectangle([cx-r, cy-r, cx+r, cy+r], fill=color)

    return img


def place_random_balls_on_maze(maze: MazeData, nmin: int, nmax: int, rng: random.Random):
    nmin = max(0, int(nmin))
    nmax = max(0, int(nmax))
    if nmin > nmax:
        nmin, nmax = nmax, nmin
    N = rng.randint(nmin, nmax) if nmax > 0 else 0
    if N <= 0:
        maze.balls = []
        return

    free_tiles: List[Coord] = []
    for y in range(1, maze.tile_h-1):
        for x in range(1, maze.tile_w-1):
            if maze.tiles[y][x] != 0:
                continue
            p = (x, y)
            if p == maze.start or p in maze.exits:
                continue
            if abs(x - maze.start[0]) + abs(y - maze.start[1]) <= 2:
                continue
            free_tiles.append(p)

    rng.shuffle(free_tiles)
    picked = free_tiles[:N]
    colors = ['R', 'G', 'B']
    maze.balls = [(p, rng.choice(colors)) for p in picked]


# =========================
# Part I (from first code): image-based analysis + search
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
        grid_w = max(51, int(grid_w))
        grid_h = max(51, int(grid_h))
        wall_darkness = clamp(int(wall_darkness), 5, 200)

        rgb = img.convert("RGB")
        gray = ImageOps.autocontrast(rgb.convert("L"))
        gray = MazeAnalyzer._auto_crop(gray)

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
            if free[grid_h - 1][x]:
                exits.append((x, grid_h - 1))
        for y in range(grid_h):
            if free[y][0]:
                exits.append((0, y))
            if free[y][grid_w - 1]:
                exits.append((grid_w - 1, y))
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
# Part II helpers (unchanged)
# =========================

def _auto_crop_rgb(img_rgb: Image.Image) -> Image.Image:
    gray = ImageOps.autocontrast(img_rgb.convert("L"))
    bw = gray.point(lambda p: 0 if p < 245 else 255, mode="L")
    bbox = ImageOps.invert(bw).getbbox()
    if not bbox:
        return img_rgb
    x0, y0, x1, y1 = bbox
    pad_x = max(5, int(0.05 * (x1 - x0)))
    pad_y = max(5, int(0.05 * (y1 - y0)))
    x0 = max(0, x0 - pad_x); y0 = max(0, y0 - pad_y)
    x1 = min(img_rgb.width, x1 + pad_x); y1 = min(img_rgb.height, y1 + pad_y)
    return img_rgb.crop((x0, y0, x1, y1))


def free_mask_from_rgb(img_rgb: Image.Image, wall_darkness: int = 80) -> np.ndarray:
    wall_darkness = clamp(wall_darkness, 5, 200)
    arr = np.asarray(img_rgb.convert("RGB"), dtype=np.uint8)
    mx = arr.max(axis=2)
    return mx >= wall_darkness


def detect_balls_rgb(img_rgb: Image.Image) -> List[Tuple[Tuple[float, float], str]]:
    arr = np.asarray(img_rgb.convert("RGB"), dtype=np.uint8)
    r = arr[:, :, 0].astype(np.int16)
    g = arr[:, :, 1].astype(np.int16)
    b = arr[:, :, 2].astype(np.int16)

    red = (r > 170) & (g < 120) & (b < 120) & (r - np.maximum(g, b) > 60)
    green = (g > 170) & (r < 120) & (b < 120) & (g - np.maximum(r, b) > 60)
    blue = (b > 170) & (r < 120) & (g < 120) & (b - np.maximum(r, g) > 60)

    balls = []
    for mask, lbl in [(red, 'R'), (green, 'G'), (blue, 'B')]:
        ys, xs = np.where(mask)
        if len(xs) == 0:
            continue
        visited = np.zeros(mask.shape, dtype=bool)
        H, W = mask.shape
        for y0, x0 in zip(ys, xs):
            if visited[y0, x0]:
                continue
            q = [(y0, x0)]
            visited[y0, x0] = True
            comp = []
            while q:
                y, x = q.pop()
                comp.append((x, y))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < H and 0 <= nx < W and (not visited[ny, nx]) and mask[ny, nx]:
                            visited[ny, nx] = True
                            q.append((ny, nx))
            if len(comp) < 1:
                continue
            cx = float(sum(p[0] for p in comp)) / len(comp)
            cy = float(sum(p[1] for p in comp)) / len(comp)
            balls.append(((cx, cy), lbl))
    return balls


def zhang_suen_thinning(binary_free: np.ndarray) -> np.ndarray:
    img = binary_free.astype(np.uint8).copy()
    changed = True
    H, W = img.shape

    def neighbors(y, x):
        p2 = img[y-1, x]
        p3 = img[y-1, x+1]
        p4 = img[y, x+1]
        p5 = img[y+1, x+1]
        p6 = img[y+1, x]
        p7 = img[y+1, x-1]
        p8 = img[y, x-1]
        p9 = img[y-1, x-1]
        return [p2, p3, p4, p5, p6, p7, p8, p9]

    def transitions(nei):
        n = nei + [nei[0]]
        return sum((n[i] == 0 and n[i+1] == 1) for i in range(8))

    while changed:
        changed = False
        to_remove = []
        for y in range(1, H-1):
            for x in range(1, W-1):
                if img[y, x] != 1:
                    continue
                nei = neighbors(y, x)
                B = sum(nei)
                A = transitions(nei)
                if 2 <= B <= 6 and A == 1 and (nei[0] * nei[2] * nei[4] == 0) and (nei[2] * nei[4] * nei[6] == 0):
                    to_remove.append((y, x))
        if to_remove:
            for y, x in to_remove:
                img[y, x] = 0
            changed = True

        to_remove = []
        for y in range(1, H-1):
            for x in range(1, W-1):
                if img[y, x] != 1:
                    continue
                nei = neighbors(y, x)
                B = sum(nei)
                A = transitions(nei)
                if 2 <= B <= 6 and A == 1 and (nei[0] * nei[2] * nei[6] == 0) and (nei[0] * nei[4] * nei[6] == 0):
                    to_remove.append((y, x))
        if to_remove:
            for y, x in to_remove:
                img[y, x] = 0
            changed = True

    return img.astype(bool)


def nearest_true(mask: np.ndarray, pt: Tuple[float, float]) -> Optional[Coord]:
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return None
    x0, y0 = float(pt[0]), float(pt[1])
    dx = xs.astype(np.float32) - x0
    dy = ys.astype(np.float32) - y0
    d2 = dx*dx + dy*dy
    i = int(d2.argmin())
    return (int(xs[i]), int(ys[i]))


def find_border_exits(free: np.ndarray) -> List[Coord]:
    H, W = free.shape
    exits: List[Coord] = []
    for x in range(W):
        if free[0, x]:
            exits.append((x, 0))
        if free[H-1, x]:
            exits.append((x, H-1))
    for y in range(H):
        if free[y, 0]:
            exits.append((0, y))
        if free[y, W-1]:
            exits.append((W-1, y))
    out, seen = [], set()
    for e in exits:
        if e not in seen:
            seen.add(e)
            out.append(e)
    return out


def astar_on_mask(mask_free: np.ndarray, start: Coord, goal: Coord,
                 allow_diag: bool = True) -> Tuple[Optional[List[Coord]], List[Coord]]:
    H, W = mask_free.shape

    def h(p: Coord) -> float:
        return abs(p[0] - goal[0]) + abs(p[1] - goal[1])

    neigh = [(-1,0),(1,0),(0,-1),(0,1)]
    if allow_diag:
        neigh += [(-1,-1),(-1,1),(1,-1),(1,1)]

    g_cost: Dict[Coord, float] = {start: 0.0}
    parent: Dict[Coord, Optional[Coord]] = {start: None}
    openpq: List[Tuple[float, float, Coord]] = [(h(start), random.random(), start)]
    closed: Set[Coord] = set()
    visited_order: List[Coord] = []

    while openpq:
        _, _, cur = heapq.heappop(openpq)
        if cur in closed:
            continue
        closed.add(cur)
        visited_order.append(cur)
        if cur == goal:
            path: List[Coord] = []
            c = cur
            while c is not None:
                path.append(c)
                c = parent.get(c)
            path.reverse()
            return path, visited_order

        cx, cy = cur
        for dx, dy in neigh:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < W and 0 <= ny < H):
                continue
            if not mask_free[ny, nx]:
                continue
            step = math.sqrt(2.0) if (dx != 0 and dy != 0) else 1.0
            ng = g_cost[cur] + step
            nb = (nx, ny)
            if nb not in g_cost or ng < g_cost[nb]:
                g_cost[nb] = ng
                parent[nb] = cur
                heapq.heappush(openpq, (ng + h(nb), random.random(), nb))

    return None, visited_order


def compress_polyline(path: List[Coord]) -> List[Coord]:
    if not path:
        return []
    if len(path) <= 2:
        return path[:]
    out = [path[0]]
    prev = path[0]
    dx0 = path[1][0] - prev[0]
    dy0 = path[1][1] - prev[1]
    dx0 = 0 if dx0 == 0 else (1 if dx0 > 0 else -1)
    dy0 = 0 if dy0 == 0 else (1 if dy0 > 0 else -1)
    last_dir = (dx0, dy0)

    for i in range(1, len(path)):
        cur = path[i]
        dx = cur[0] - prev[0]
        dy = cur[1] - prev[1]
        dx = 0 if dx == 0 else (1 if dx > 0 else -1)
        dy = 0 if dy == 0 else (1 if dy > 0 else -1)
        d = (dx, dy)
        if d != last_dir:
            out.append(prev)
            last_dir = d
        prev = cur
    out.append(path[-1])
    cleaned = [out[0]]
    for p in out[1:]:
        if p != cleaned[-1]:
            cleaned.append(p)
    return cleaned


def searchLikeThereIsNoTomorrow(MazeImage: Union[np.ndarray, str],
                               RGBValues: List[int] = [1, 2, 3],
                               SolutionLength: Union[str, float, int] = 'inf'):
    if isinstance(MazeImage, str):
        pil = Image.open(MazeImage).convert("RGB")
        img_arr = np.asarray(pil, dtype=np.uint8)
    else:
        img_arr = np.asarray(MazeImage, dtype=np.uint8)
        if img_arr.ndim != 3 or img_arr.shape[2] != 3:
            raise ValueError("MazeImage must be RGB (H,W,3).")
        pil = Image.fromarray(img_arr, mode="RGB")

    pil2 = _auto_crop_rgb(pil)
    free = free_mask_from_rgb(pil2, wall_darkness=80)
    skel = zhang_suen_thinning(free)

    start_guess = (pil2.width / 2.0, pil2.height / 2.0)
    start = nearest_true(skel, start_guess)
    if start is None:
        start = nearest_true(free, start_guess) or (pil2.width//2, pil2.height//2)

    exits_raw = find_border_exits(free)
    exits = []
    for e in exits_raw:
        p = nearest_true(skel, (float(e[0]), float(e[1])))
        if p is not None:
            exits.append(p)
    seen = set()
    exits = [e for e in exits if not (e in seen or seen.add(e))]
    if not exits:
        exits = exits_raw
    if not exits:
        raise ValueError("No exits found on border.")

    val_map = {'R': int(RGBValues[0]), 'G': int(RGBValues[1]), 'B': int(RGBValues[2])}

    ball_centroids = detect_balls_rgb(pil2)
    ball_points = []
    for (cx, cy), lbl in ball_centroids:
        p = nearest_true(skel, (cx, cy))
        if p is None:
            p = (int(round(cx)), int(round(cy)))
        ball_points.append((p, lbl))

    best_at: Dict[Coord, str] = {}
    for p, lbl in ball_points:
        if p not in best_at or val_map[lbl] > val_map[best_at[p]]:
            best_at[p] = lbl
    balls = [(p, lbl) for p, lbl in best_at.items()]
    N = len(balls)
    ball_values = [val_map[lbl] for _, lbl in balls]

    if isinstance(SolutionLength, str):
        s = SolutionLength.strip().lower()
        Lmax = float("inf") if s == "inf" else float(SolutionLength)
    else:
        Lmax = float(SolutionLength)
    if Lmax <= 0:
        Lmax = float("inf")

    walk_mask = skel if skel.any() else free

    points: List[Coord] = [start] + [p for p, _ in balls] + exits
    idx_start = 0
    idx_balls = list(range(1, 1 + N))
    idx_exits = list(range(1 + N, 1 + N + len(exits)))

    dist = [[float("inf")] * len(points) for _ in range(len(points))]
    paths: Dict[Tuple[int, int], List[Coord]] = {}
    visited_all: List[Coord] = []

    def compute_pair(i: int, j: int):
        if i == j:
            dist[i][j] = 0.0
            paths[(i, j)] = [points[i]]
            return
        if (i, j) in paths:
            return
        path, visited = astar_on_mask(walk_mask, points[i], points[j], allow_diag=True)
        visited_all.extend(visited)
        if path is None:
            return
        d = 0.0
        for a, b in zip(path, path[1:]):
            dx = abs(a[0]-b[0])
            dy = abs(a[1]-b[1])
            d += math.sqrt(2.0) if (dx == 1 and dy == 1) else 1.0
        dist[i][j] = d
        paths[(i, j)] = path

    for i in range(len(points)):
        for j in range(len(points)):
            if i == j:
                dist[i][j] = 0.0
            else:
                compute_pair(i, j)

    def best_exit_from(i: int) -> Tuple[float, int]:
        bestd, bestj = float("inf"), idx_exits[0]
        for j in idx_exits:
            if dist[i][j] < bestd:
                bestd, bestj = dist[i][j], j
        return bestd, bestj

    best_solution_points: List[int] = []
    best_length = float("inf")
    best_score = -1
    best_goal_exit_idx = None

    d0, ex0 = best_exit_from(idx_start)
    if d0 < float("inf") and d0 <= Lmax:
        best_solution_points = [idx_start, ex0]
        best_length = d0
        best_score = 0
        best_goal_exit_idx = ex0

    if N <= 15:
        size = 1 << N
        DP = [[float("inf")] * N for _ in range(size)]
        parent_dp: List[List[Optional[Tuple[int, int]]]] = [[None] * N for _ in range(size)]

        for bi in range(N):
            i = idx_balls[bi]
            d = dist[idx_start][i]
            if d < float("inf"):
                m = 1 << bi
                DP[m][bi] = d
                parent_dp[m][bi] = None

        for m in range(size):
            for bi in range(N):
                curd = DP[m][bi]
                if curd == float("inf"):
                    continue

                node_i = idx_balls[bi]
                de, exj = best_exit_from(node_i)
                totlen = curd + de
                if totlen <= Lmax:
                    score = 0
                    mm = m
                    while mm:
                        lsb = mm & -mm
                        k = (lsb.bit_length() - 1)
                        score += ball_values[k]
                        mm -= lsb
                    if (score > best_score) or (score == best_score and totlen < best_length):
                        best_score = score
                        best_length = totlen
                        best_goal_exit_idx = exj
                        seq = []
                        cm, cbi = m, bi
                        while True:
                            seq.append(cbi)
                            prev = parent_dp[cm][cbi]
                            if prev is None:
                                break
                            pm, pbi = prev
                            cm, cbi = pm, pbi
                        seq.reverse()
                        best_solution_points = [idx_start] + [idx_balls[k] for k in seq] + [exj]

                for bj in range(N):
                    if m & (1 << bj):
                        continue
                    ni = idx_balls[bi]
                    nj = idx_balls[bj]
                    nd = curd + dist[ni][nj]
                    nm = m | (1 << bj)
                    if nd < DP[nm][bj]:
                        DP[nm][bj] = nd
                        parent_dp[nm][bj] = (m, bi)
    else:
        current = idx_start
        remaining = set(range(N))
        picked_ball_indices: List[int] = []
        cur_len = 0.0
        score = 0

        while True:
            best_gain = None
            best_bj = None
            best_next_len = None
            best_next_node = None

            for bj in list(remaining):
                node_ball = idx_balls[bj]
                d_to = dist[current][node_ball]
                if d_to == float("inf"):
                    continue
                de, exj = best_exit_from(node_ball)
                if de == float("inf"):
                    continue
                new_len = cur_len + d_to
                finish_len = new_len + de
                if finish_len > Lmax:
                    continue
                gain = ball_values[bj] / max(1e-6, d_to)
                if best_gain is None or gain > best_gain:
                    best_gain = gain
                    best_bj = bj
                    best_next_len = new_len
                    best_next_node = node_ball

            if best_bj is None:
                break

            remaining.remove(best_bj)
            picked_ball_indices.append(best_bj)
            cur_len = best_next_len
            score += ball_values[best_bj]
            current = best_next_node

            de, exj = best_exit_from(current)
            tot = cur_len + de
            if tot <= Lmax and (score > best_score or (score == best_score and tot < best_length)):
                best_score = score
                best_length = tot
                best_goal_exit_idx = exj
                best_solution_points = [idx_start] + [idx_balls[k] for k in picked_ball_indices] + [exj]

    full_path: List[Coord] = []
    if best_solution_points and len(best_solution_points) >= 2:
        for a, b in zip(best_solution_points, best_solution_points[1:]):
            seg = paths.get((a, b))
            if not seg:
                continue
            if not full_path:
                full_path.extend(seg)
            else:
                full_path.extend(seg[1:])

    sol_comp = compress_polyline(full_path)
    SolutionList = [[int(x), int(y)] for (x, y) in sol_comp]

    seenv = set()
    VisitedList = []
    for p in visited_all:
        if p not in seenv:
            seenv.add(p)
            VisitedList.append([int(p[0]), int(p[1])])

    out = pil2.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for x, y in visited_all:
        if 0 <= x < out.width and 0 <= y < out.height:
            draw.point((x, y), fill=(255, 255, 0))
    for x, y in full_path:
        if 0 <= x < out.width and 0 <= y < out.height:
            draw.point((x, y), fill=(160, 0, 200))

    ResImage = np.asarray(out, dtype=np.uint8)
    return ResImage, SolutionList, VisitedList


# =========================
# Main GUI
# =========================

class MazeHomeworkApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maze Homework - Part I + Part II (v5)")
        self.geometry("1320x840")
        self.minsize(1150, 680)

        self.generated_maze: Optional[MazeData] = None
        self.generated_img: Optional[Image.Image] = None
        self.generated_solution_img: Optional[Image.Image] = None
        self.loaded_img: Optional[Image.Image] = None
        self.current_maze_img: Optional[Image.Image] = None
        self.current_label: str = "None"

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(0, weight=1)

        self.left = ttk.Frame(self, padding=10)
        self.right = ttk.Frame(self, padding=10)
        self.left.grid(row=0, column=0, sticky="nsew")
        self.right.grid(row=0, column=1, sticky="nsew")

        self._build_left()
        self._build_right()

        try:
            ttk.Style(self).theme_use("clam")
        except Exception:
            pass

    # ---------- Left ----------
    def _build_left(self):
        self.left.columnconfigure(0, weight=1)
        self.left.rowconfigure(1, weight=1)

        lf = ttk.LabelFrame(self.left, text="Maze Generation / Loading", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        r = 0
        ttk.Label(lf, text="Maze size (cells)").grid(row=r, column=0, sticky="w")
        self.var_cells_w = tk.IntVar(value=18)
        self.var_cells_h = tk.IntVar(value=18)
        fr = ttk.Frame(lf)
        fr.grid(row=r, column=1, sticky="w")
        ttk.Spinbox(fr, from_=3, to=80, textvariable=self.var_cells_w, width=5).pack(side="left")
        ttk.Label(fr, text=" x ").pack(side="left")
        ttk.Spinbox(fr, from_=3, to=80, textvariable=self.var_cells_h, width=5).pack(side="left")
        r += 1

        ttk.Label(lf, text="Tile pixel size").grid(row=r, column=0, sticky="w")
        self.var_tile_px = tk.IntVar(value=10)
        ttk.Spinbox(lf, from_=4, to=25, textvariable=self.var_tile_px, width=8).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(lf, text="Number of exits (1..5)").grid(row=r, column=0, sticky="w")
        self.var_exits = tk.IntVar(value=1)
        ttk.Spinbox(lf, from_=1, to=5, textvariable=self.var_exits, width=8).grid(row=r, column=1, sticky="w")
        r += 1

        self.var_gen_with_balls = tk.BooleanVar(value=False)
        ttk.Checkbutton(lf, text="Generate WITH balls (Part II)", variable=self.var_gen_with_balls)\
            .grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
        r += 1

        ttk.Label(lf, text="Min balls (default 0)").grid(row=r, column=0, sticky="w")
        self.var_min_balls = tk.IntVar(value=0)
        ttk.Spinbox(lf, from_=0, to=200, textvariable=self.var_min_balls, width=8).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Label(lf, text="Max balls (default 0)").grid(row=r, column=0, sticky="w")
        self.var_max_balls = tk.IntVar(value=0)
        ttk.Spinbox(lf, from_=0, to=200, textvariable=self.var_max_balls, width=8).grid(row=r, column=1, sticky="w")
        r += 1

        ttk.Label(lf, text="Save format").grid(row=r, column=0, sticky="w")
        self.var_save_fmt = tk.StringVar(value="PNG")
        ttk.OptionMenu(lf, self.var_save_fmt, self.var_save_fmt.get(), "PNG", "JPG").grid(row=r, column=1, sticky="w")
        r += 1

        btns = ttk.Frame(lf)
        btns.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btns.columnconfigure((0, 1), weight=1)
        ttk.Button(btns, text="Generate Maze", command=self.on_generate).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Load Maze (PNG/JPG)", command=self.on_load).grid(row=0, column=1, sticky="ew")
        r += 1

        btns2 = ttk.Frame(lf)
        btns2.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        btns2.columnconfigure((0, 1), weight=1)
        ttk.Button(btns2, text="Save Current Maze", command=self.on_save_current).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns2, text="Save Green Solution", command=self.on_save_solution).grid(row=0, column=1, sticky="ew")
        r += 1

        pv = ttk.LabelFrame(self.left, text="Preview", padding=6)
        pv.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        pv.columnconfigure(0, weight=1)
        pv.rowconfigure(2, weight=1)
        pv.rowconfigure(5, weight=1)

        ttk.Label(pv, text="Current Maze").grid(row=0, column=0, sticky="w")
        c1 = ttk.Frame(pv)
        c1.grid(row=1, column=0, sticky="ew")
        ttk.Label(c1, text="Zoom").pack(side="left")
        self.var_zoom_left1 = tk.DoubleVar(value=1.0)
        ttk.Scale(c1, from_=0.3, to=6.0, variable=self.var_zoom_left1, command=self._on_zoom_left1)\
            .pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(c1, text="FIT", command=self._fit_left1).pack(side="left")

        self.preview_current = FitZoomCanvas(pv, bg="#111111")
        self.preview_current.grid(row=2, column=0, sticky="nsew", pady=(4, 12))

        ttk.Label(pv, text="Generated solution paths (Green)").grid(row=3, column=0, sticky="w")
        c2 = ttk.Frame(pv)
        c2.grid(row=4, column=0, sticky="ew")
        ttk.Label(c2, text="Zoom").pack(side="left")
        self.var_zoom_left2 = tk.DoubleVar(value=1.0)
        ttk.Scale(c2, from_=0.3, to=6.0, variable=self.var_zoom_left2, command=self._on_zoom_left2)\
            .pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(c2, text="FIT", command=self._fit_left2).pack(side="left")

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

        self.view_right.set_image(img, reset_zoom=True)
        self.var_zoom_right.set(1.0)
        self.lbl_right_status.config(text=f"Ready. Using: {label}")

    def on_generate(self):
        try:
            gen = MazeGenerator(self.var_cells_w.get(), self.var_cells_h.get())
            maze = gen.generate(self.var_exits.get())
            self.generated_maze = maze

            with_balls = bool(self.var_gen_with_balls.get())
            if with_balls:
                mn = int(self.var_min_balls.get())
                mx = int(self.var_max_balls.get())
                place_random_balls_on_maze(maze, mn, mx, rng=random.Random())

            tile_px = int(self.var_tile_px.get())
            self.generated_img = tiles_to_image_with_balls(maze, tile_px=tile_px, draw_balls=with_balls, ball_px=1)

            self.generated_solution_img = self._make_green_preview_from_generated(maze, tile_px)
            self.preview_solution.set_image(self.generated_solution_img, reset_zoom=True)
            self.var_zoom_left2.set(1.0)

            label = f"Generated ({self.var_cells_w.get()}x{self.var_cells_h.get()} cells)" + (" + balls" if with_balls else "")
            self._set_current_maze(self.generated_img, label)
        except Exception as e:
            messagebox.showerror("Generate Error", str(e))

    def _make_green_preview_from_generated(self, maze: MazeData, tile_px: int) -> Image.Image:
        tw, th = maze.tile_w, maze.tile_h
        start = maze.start
        exits = maze.exits

        q = [start]
        parent: Dict[Coord, Optional[Coord]] = {start: None}

        def neigh(p: Coord):
            x, y = p
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x+dx, y+dy
                if 0 <= nx < tw and 0 <= ny < th and maze.tiles[ny][nx] == 0:
                    yield (nx, ny)

        while q:
            cur = q.pop(0)
            for nb in neigh(cur):
                if nb not in parent:
                    parent[nb] = cur
                    q.append(nb)

        base = tiles_to_image_with_balls(maze, tile_px=tile_px, draw_balls=True, ball_px=1)
        draw = ImageDraw.Draw(base)

        def center(p: Coord):
            x, y = p
            return (x*tile_px + tile_px//2, y*tile_px + tile_px//2)

        width = max(2, tile_px//3)
        for ex in exits:
            if ex not in parent:
                continue
            path = []
            cur = ex
            while cur is not None:
                path.append(cur)
                cur = parent.get(cur)
            path.reverse()
            pts = [center(p) for p in path]
            if len(pts) >= 2:
                draw.line(pts, fill=(0, 180, 0), width=width)
        return base

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

    def on_save_current(self):
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
            messagebox.showwarning("Nothing to save", "Generate a maze first (green preview appears).")
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

    # ---------- Right ----------
    def _build_right(self):
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(2, weight=1)

        lf = ttk.LabelFrame(self.right, text="Search", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        # Part I analysis controls (added from first code)
        rowA = ttk.Frame(lf)
        rowA.grid(row=0, column=0, sticky="ew")
        self.var_grid_w = tk.IntVar(value=201)
        self.var_grid_h = tk.IntVar(value=201)
        self.var_wall_dark = tk.IntVar(value=80)

        ttk.Label(rowA, text="Part I analysis grid").pack(side="left")
        ttk.Spinbox(rowA, from_=51, to=401, increment=10, textvariable=self.var_grid_w, width=6).pack(side="left", padx=(8, 2))
        ttk.Label(rowA, text="x").pack(side="left")
        ttk.Spinbox(rowA, from_=51, to=401, increment=10, textvariable=self.var_grid_h, width=6).pack(side="left", padx=(2, 12))

        ttk.Label(rowA, text="Wall darkness").pack(side="left")
        ttk.Spinbox(rowA, from_=5, to=200, increment=5, textvariable=self.var_wall_dark, width=6).pack(side="left", padx=(8, 0))
        ttk.Label(rowA, text="(maxRGB < this => WALL)").pack(side="left", padx=(8, 0))

        row0 = ttk.Frame(lf)
        row0.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(row0, text="Algorithm (Part I):").pack(side="left")
        self.var_algo = tk.StringVar(value="Breadth First")
        opts = ["Breadth First", "Depth First", "Uniform Cost", "Best First (Greedy)", "A*"]
        ttk.OptionMenu(row0, self.var_algo, self.var_algo.get(), *opts).pack(side="left", padx=(8, 12))
        self.var_bidir = tk.BooleanVar(value=False)
        ttk.Checkbutton(row0, text="Bidirectional (Part I)", variable=self.var_bidir).pack(side="left")

        row1 = ttk.Frame(lf)
        row1.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(row1, text="RGB bonus values (Part II)").pack(side="left")
        self.var_R = tk.IntVar(value=1)
        self.var_G = tk.IntVar(value=2)
        self.var_B = tk.IntVar(value=3)
        ttk.Label(row1, text="R").pack(side="left", padx=(10, 2))
        ttk.Entry(row1, textvariable=self.var_R, width=4).pack(side="left")
        ttk.Label(row1, text="G").pack(side="left", padx=(10, 2))
        ttk.Entry(row1, textvariable=self.var_G, width=4).pack(side="left")
        ttk.Label(row1, text="B").pack(side="left", padx=(10, 2))
        ttk.Entry(row1, textvariable=self.var_B, width=4).pack(side="left")

        ttk.Label(row1, text="SolutionLength").pack(side="left", padx=(16, 4))
        self.var_L = tk.StringVar(value="inf")
        ttk.Entry(row1, textvariable=self.var_L, width=8).pack(side="left")

        row2 = ttk.Frame(lf)
        row2.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(row2, text="RUN Part I", command=self.on_run_part1).pack(side="left")
        ttk.Button(row2, text="RUN Part II", command=self.on_run_part2).pack(side="left", padx=(8, 0))

        ttk.Label(row2, text="Zoom").pack(side="left", padx=(16, 4))
        self.var_zoom_right = tk.DoubleVar(value=1.0)
        ttk.Scale(row2, from_=0.3, to=6.0, variable=self.var_zoom_right, command=self._on_zoom_right).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(row2, text="FIT", command=self._fit_right).pack(side="left", padx=(0, 10))

        self.lbl_right_status = ttk.Label(row2, text="Ready.")
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

    # ✅ Part I updated to use first-code logic
    def on_run_part1(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return

        img = self.current_maze_img
        try:
            method = self.var_algo.get()
            bidir = bool(self.var_bidir.get())

            self.lbl_right_status.config(text=f"Part I: analyzing ({self.current_label})...")
            self.update_idletasks()

            analyzed = MazeAnalyzer.analyze_rgb_darkness(
                img,
                self.var_grid_w.get(),
                self.var_grid_h.get(),
                self.var_wall_dark.get()
            )

            if not analyzed.exits:
                messagebox.showwarning(
                    "No exits found",
                    "No open cells detected on the border.\n"
                    "Try increasing Wall darkness, or increase analysis grid size."
                )
                self.view_right.set_image(analyzed.base_image, reset_zoom=False)
                return

            self.lbl_right_status.config(text=f"Part I: searching ({method}, bidir={bidir})...")
            self.update_idletasks()

            t0 = time.perf_counter()
            if bidir:
                result = search_bidirectional(analyzed.free, analyzed.start, analyzed.exits, method)
            else:
                result = search_unidirectional(analyzed.free, analyzed.start, analyzed.exits, method)
            dt = time.perf_counter() - t0

            drawn = draw_search_result(analyzed, result, cell_px=5)

            z = self.view_right.get_zoom_factor()
            self.view_right.set_image(drawn, reset_zoom=False)
            self.view_right.set_zoom_factor(z)

            if result.found:
                self.lbl_right_status.config(
                    text=f"Part I: FOUND | path={len(result.path)} explored={len(result.explored)} time={dt:.4f}s"
                )
            else:
                self.lbl_right_status.config(
                    text=f"Part I: NOT FOUND | explored={len(result.explored)} time={dt:.4f}s"
                )

        except Exception as e:
            messagebox.showerror("RUN Part I Error", str(e))
            self.lbl_right_status.config(text="Ready.")

    def on_run_part2(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return
        try:
            RGB = [int(self.var_R.get()), int(self.var_G.get()), int(self.var_B.get())]
        except Exception:
            RGB = [1, 2, 3]
        L = self.var_L.get().strip() if self.var_L.get() else "inf"

        try:
            img = np.asarray(self.current_maze_img.convert("RGB"), dtype=np.uint8)
            self.lbl_right_status.config(text="Part II: running...")
            self.update_idletasks()

            t0 = time.perf_counter()
            ResImage, SolutionList, VisitedList = searchLikeThereIsNoTomorrow(img, RGBValues=RGB, SolutionLength=L)
            dt = time.perf_counter() - t0

            out = Image.fromarray(ResImage.astype(np.uint8), mode="RGB")
            z = self.view_right.get_zoom_factor()
            self.view_right.set_image(out, reset_zoom=False)
            self.view_right.set_zoom_factor(z)

            self.lbl_right_status.config(text=f"Part II: done | sol_pts={len(SolutionList)} visited={len(VisitedList)} time={dt:.4f}s")
        except Exception as e:
            messagebox.showerror("RUN Part II Error", str(e))
            self.lbl_right_status.config(text="Ready.")


def main():
    app = MazeHomeworkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
