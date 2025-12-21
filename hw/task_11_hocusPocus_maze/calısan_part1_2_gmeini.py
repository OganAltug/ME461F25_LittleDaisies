#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maze Homework GUI - Part I + Part II (v5_fixed)

Adds Part II:
- Generate maze with/without balls (R,G,B) placed in the middle of hallways.
- RGB bonus value boxes (default R=1,G=2,B=3)
- SolutionLength box (default "inf")
- RUN Part II button calls required function:
    searchLikeThereIsNoTomorrow(MazeImage, RGBValues=[1,2,3], SolutionLength='inf')
  and displays returned overlay + lists.

Key "centerline" requirement:
- For searching in Part II, we do NOT walk pixel-by-pixel inside thick corridors.
- We extract a 1-pixel-wide CENTERLINE (skeleton) of the free space (walls are black),
  then search on that centerline graph. Balls detected anywhere in a corridor are
  projected to the nearest centerline point, so they are treated as if they were
  on the corridor middle.

Robustness for colored balls & JPEG:
- Walls detected by "darkness" on RGB: wall if max(R,G,B) < wall_darkness.
- Colored balls (bright in one channel) are treated as FREE (not walls).

Dependencies:
  pip install pillow numpy

Run:
  python3 maze_homework_part12_gui_v5.py
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


def clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(x)))


def clampf(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def ensure_extension(path: str, fmt: str) -> str:
    fmt = fmt.upper()
    root, ext = os.path.splitext(path)
    ext = ext.lower()
    if fmt == "PNG":
        return root + ".png" if ext != ".png" else path
    return root + ".jpg" if ext not in (".jpg", ".jpeg") else path


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
                             ball_px: Optional[int] = None) -> Image.Image:
    """
    Render to RGB image:
      - walls: black
      - passages: white
      - optional balls: red/green/blue

    NOTE: ball_px defaults to ~half the tile size so balls are visible.
    """
    tile_px = max(2, int(tile_px))
    if ball_px is None:
        # Visible by default
        ball_px = max(3, (tile_px // 2) | 1)  # odd size
    ball_px = max(1, int(ball_px))

    img = Image.new("RGB", (maze.tile_w * tile_px, maze.tile_h * tile_px), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    # passages
    for y in range(maze.tile_h):
        for x in range(maze.tile_w):
            if maze.tiles[y][x] == 0:
                x0 = x * tile_px
                y0 = y * tile_px
                draw.rectangle([x0, y0, x0 + tile_px - 1, y0 + tile_px - 1], fill=(255, 255, 255))

    # balls
    if draw_balls and maze.balls:
        r = ball_px // 2
        for (bx, by), col in maze.balls:
            cx = bx * tile_px + tile_px // 2
            cy = by * tile_px + tile_px // 2
            if col == 'R':
                color = (255, 0, 0)
            elif col == 'G':
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)

    return img



def place_random_balls_on_maze(maze: MazeData, nmin: int, nmax: int, rng: random.Random):
    """
    Place N balls where N ~ Uniform([nmin,nmax]) onto free tiles.
    Preference: straight corridor tiles ("middle of hallways").

    This is used ONLY for generated mazes.
    """
    nmin = max(0, int(nmin))
    nmax = max(0, int(nmax))
    if nmin > nmax:
        nmin, nmax = nmax, nmin
    N = rng.randint(nmin, nmax) if nmax > 0 else 0
    if N <= 0:
        maze.balls = []
        return

    def is_free(x, y) -> bool:
        return 0 <= x < maze.tile_w and 0 <= y < maze.tile_h and maze.tiles[y][x] == 0

    def is_corridor_tile(x, y) -> bool:
        # corridor-like if degree==2 and straight (opposite neighbors)
        if not is_free(x, y):
            return False
        n = is_free(x, y-1)
        s = is_free(x, y+1)
        w = is_free(x-1, y)
        e = is_free(x+1, y)
        deg = int(n) + int(s) + int(w) + int(e)
        if deg != 2:
            return False
        return (n and s) or (w and e)

    candidates_corr: List[Coord] = []
    candidates_all: List[Coord] = []

    for y in range(1, maze.tile_h-1):
        for x in range(1, maze.tile_w-1):
            if maze.tiles[y][x] != 0:
                continue
            p = (x, y)
            if p == maze.start or p in maze.exits:
                continue
            candidates_all.append(p)
            if is_corridor_tile(x, y):
                candidates_corr.append(p)

    # Prefer corridor tiles, fallback to all free.
    candidates = candidates_corr if len(candidates_corr) >= N else candidates_all
    rng.shuffle(candidates)
    picked = candidates[:N]

    colors = ['R', 'G', 'B']
    maze.balls = [(p, rng.choice(colors)) for p in picked]


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




def polyline_length(path: List[Coord]) -> float:
    if not path or len(path) == 1:
        return 0.0
    d = 0.0
    for a, b in zip(path, path[1:]):
        dx = a[0] - b[0]
        dy = a[1] - b[1]
        d += math.hypot(dx, dy)
    return d


def _bresenham(x0: int, y0: int, x1: int, y1: int):
    """Yield integer points on a line from (x0,y0) to (x1,y1)."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        yield x, y
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def overlay_points(img: np.ndarray, pts: List[Coord], color=(255, 255, 0)) -> np.ndarray:
    """Overlay points on an RGB numpy image."""
    if img is None:
        return img
    H, W = img.shape[0], img.shape[1]
    r, g, b = color
    for x, y in pts:
        if 0 <= x < W and 0 <= y < H:
            img[y, x, 0] = r
            img[y, x, 1] = g
            img[y, x, 2] = b
    return img


def overlay_polyline(img: np.ndarray, path: List[Coord], color=(160, 0, 200)) -> np.ndarray:
    if img is None or not path:
        return img
    r, g, b = color
    H, W = img.shape[0], img.shape[1]
    for a, c in zip(path, path[1:]):
        for x, y in _bresenham(a[0], a[1], c[0], c[1]):
            if 0 <= x < W and 0 <= y < H:
                img[y, x, 0] = r
                img[y, x, 1] = g
                img[y, x, 2] = b
    return img


def _line_of_sight_free(a: Coord, b: Coord, free_mask: np.ndarray) -> bool:
    H, W = free_mask.shape
    for x, y in _bresenham(a[0], a[1], b[0], b[1]):
        if not (0 <= x < W and 0 <= y < H):
            return False
        if not free_mask[y, x]:
            return False
    return True


def compress_path_to_waypoints(pixel_path: List[Coord], free_mask: np.ndarray) -> List[Coord]:
    """
    Turn a dense pixel path into a compact waypoint list:
      - first compress by direction changes
      - then greedily skip intermediate points while keeping line-of-sight through free pixels
    """
    if not pixel_path:
        return []
    base = compress_polyline(pixel_path)
    if len(base) <= 2:
        return base

    out = [base[0]]
    i = 0
    while i < len(base) - 1:
        # choose farthest j we can see from current out[-1]
        j = len(base) - 1
        while j > i + 1:
            if _line_of_sight_free(out[-1], base[j], free_mask):
                break
            j -= 1
        out.append(base[j])
        i = j
    return out


def searchLikeThereIsNoTomorrow(MazeImage: Union[np.ndarray, str, Image.Image],
                               RGBValues: List[int] = [1, 2, 3],
                               SolutionLength: Union[str, float, int] = 'inf'):
    """
    Part II required API.

    Inputs:
      - MazeImage: numpy RGB array (H,W,3) OR path to image OR PIL.Image
      - RGBValues: [R,G,B] bonus values (positive ints)
      - SolutionLength: 'inf' or positive number (max allowed path length)

    Returns:
      - ResImage: numpy RGB array with overlay (visited=yellow, path=purple)
      - SolutionList: compact list of [x,y] waypoints (not necessarily consecutive)
      - VisitedList: list of visited pixels [x,y] (not necessarily consecutive)
    """
    # --- Load ---
    if isinstance(MazeImage, str):
        pil = Image.open(MazeImage).convert("RGB")
        img_arr = np.asarray(pil, dtype=np.uint8)
    elif isinstance(MazeImage, Image.Image):
        pil = MazeImage.convert("RGB")
        img_arr = np.asarray(pil, dtype=np.uint8)
    else:
        img_arr = np.asarray(MazeImage, dtype=np.uint8)
        if img_arr.ndim != 3 or img_arr.shape[2] != 3:
            raise ValueError("MazeImage must be RGB (H,W,3).")
        pil = Image.fromarray(img_arr)  # Pillow warns if we pass deprecated mode param

    # Crop surrounding background (keeps maze tight)
    pil2 = _auto_crop_rgb(pil)

    # --- Build masks ---
    # Free if not dark (walls are black-ish). This also treats colored balls as free.
    free = free_mask_from_rgb(pil2, wall_darkness=80)

    # Centerline: preferred movement (your 'move in the middle' requirement)
    skel = zhang_suen_thinning(free)
    walk_mask = skel if skel.any() else free

    W, H = pil2.width, pil2.height

    # --- Start on centerline near image center ---
    start_guess = (W / 2.0, H / 2.0)
    start = nearest_true(walk_mask, start_guess) or (W // 2, H // 2)

    # --- Exits: border pixels that are free, projected to centerline ---
    exits_raw = find_border_exits(free)
    exits: List[Coord] = []
    for e in exits_raw:
        pe = nearest_true(walk_mask, (float(e[0]), float(e[1])))
        if pe is not None:
            exits.append(pe)
    # dedupe
    seen = set()
    exits = [e for e in exits if not (e in seen or seen.add(e))]
    if not exits:
        # fallback to raw exits (if skeleton projection fails)
        exits = exits_raw

    if not exits:
        raise ValueError("No exits found on border.")

    # --- Balls: detect RGB-ish blobs and project to centerline ---
    val_map = {'R': int(RGBValues[0]), 'G': int(RGBValues[1]), 'B': int(RGBValues[2])}
    ball_centroids = detect_balls_rgb(pil2)  # returns [((x,y), 'R'|'G'|'B')]
    ball_points: List[Tuple[Coord, str]] = []
    for (cx, cy), lbl in ball_centroids:
        p = nearest_true(walk_mask, (cx, cy))
        if p is None:
            p = nearest_true(free, (cx, cy))
        if p is None:
            continue
        # avoid duplicates very close
        ball_points.append((p, lbl))

    # Deduplicate balls by coordinate (keep best value if clashes)
    tmp: Dict[Coord, str] = {}
    for p, lbl in ball_points:
        if p not in tmp:
            tmp[p] = lbl
        else:
            if val_map[lbl] > val_map[tmp[p]]:
                tmp[p] = lbl
    ball_points = [(p, lbl) for p, lbl in tmp.items()]

    # If no balls, just solve to nearest exit with chosen internal search (A*)
    # --- Parse length constraint ---
    if isinstance(SolutionLength, str):
        s = SolutionLength.strip().lower()
        Lmax = float("inf") if s == "inf" else float(s)
    else:
        Lmax = float(SolutionLength)
    if Lmax <= 0:
        Lmax = float("inf")

    # --- Helper: A* path on mask with visited ---
    def path_between(a: Coord, b: Coord):
        path, visited = astar_on_mask(walk_mask, a, b, allow_diag=True)
        return path, visited

    # --- If no balls, simplest: go to best exit (shortest) ---
    if not ball_points:
        best_path = None
        best_len = float("inf")
        visited_all: List[Coord] = []
        for e in exits:
            pth, vis = path_between(start, e)
            visited_all.extend(vis)
            if pth is None:
                continue
            d = polyline_length(pth)
            if d < best_len:
                best_len = d
                best_path = pth
        if best_path is None:
            # Return overlay with visited only
            out = np.asarray(pil2.convert("RGB"), dtype=np.uint8).copy()
            out = overlay_points(out, visited_all, color=(255, 255, 0))
            return out, [], [[x, y] for (x, y) in visited_all]
        if best_len > Lmax:
            # cannot satisfy length
            out = np.asarray(pil2.convert("RGB"), dtype=np.uint8).copy()
            out = overlay_points(out, visited_all, color=(255, 255, 0))
            return out, [], [[x, y] for (x, y) in visited_all]

        # Compact list + overlay
        sol_list = compress_path_to_waypoints(best_path, free)
        out = np.asarray(pil2.convert("RGB"), dtype=np.uint8).copy()
        out = overlay_points(out, visited_all, color=(255, 255, 0))
        out = overlay_polyline(out, best_path, color=(160, 0, 200))
        return out, [[x, y] for (x, y) in sol_list], [[x, y] for (x, y) in visited_all]

    # --- Build set of important nodes: start + balls + exits ---
    balls_coords = [p for p, _ in ball_points]
    balls_values = [val_map[lbl] for _, lbl in ball_points]
    N = len(balls_coords)

    points: List[Coord] = [start] + balls_coords + exits
    idx_start = 0
    idx_balls = list(range(1, 1 + N))
    idx_exits = list(range(1 + N, 1 + N + len(exits)))

    # Pairwise shortest distances between nodes
    dist = [[float("inf")] * len(points) for _ in range(len(points))]
    path_cache: Dict[Tuple[int, int], List[Coord]] = {}
    visited_all: List[Coord] = []

    def compute_pair(i: int, j: int):
        if i == j:
            dist[i][j] = 0.0
            path_cache[(i, j)] = [points[i]]
            return
        if (i, j) in path_cache:
            return
        pth, vis = path_between(points[i], points[j])
        visited_all.extend(vis)
        if pth is None:
            # keep INF
            return
        dist[i][j] = polyline_length(pth)
        path_cache[(i, j)] = pth

    # Precompute from start to all balls and exits, and between balls, and balls->exits
    for i in range(len(points)):
        for j in range(len(points)):
            if i == j:
                dist[i][j] = 0.0
                continue

    for j in idx_balls + idx_exits:
        compute_pair(idx_start, j)
    for i in idx_balls:
        for j in idx_balls:
            compute_pair(i, j)
        for j in idx_exits:
            compute_pair(i, j)

    # Helper: choose best exit from a node index
    def best_exit_from(i: int):
        bestd = float("inf")
        bestj = None
        for ej in idx_exits:
            d = dist[i][ej]
            if d < bestd:
                bestd = d
                bestj = ej
        return bestd, bestj

    # --- Solve: maximize points under length ---
    # If inf: collect all balls that are reachable from start and can reach an exit
    if math.isinf(Lmax):
        reachable_balls = []
        for bi in idx_balls:
            if math.isfinite(dist[idx_start][bi]):
                de, _ = best_exit_from(bi)
                if math.isfinite(de):
                    reachable_balls.append(bi)
        # Build a simple route: greedy by nearest-next among reachable balls, then best exit
        remaining = set(reachable_balls)
        route = [idx_start]
        cur = idx_start
        while remaining:
            nxt = min(remaining, key=lambda j: dist[cur][j])
            if not math.isfinite(dist[cur][nxt]):
                break
            route.append(nxt)
            remaining.remove(nxt)
            cur = nxt
        de, exj = best_exit_from(cur)
        if exj is not None and math.isfinite(de):
            route.append(exj)
        else:
            # fallback: go to any reachable exit from start
            de0, ex0 = best_exit_from(idx_start)
            if ex0 is not None and math.isfinite(de0):
                route = [idx_start, ex0]

    else:
        # Finite length: exact DP for up to 15 balls, else greedy
        if N <= 15:
            # DP[mask][i] = best score, and store length + parent
            # i: ball index (0..N-1) representing being at that ball
            INF = 1e18
            dp_score = [[-1] * N for _ in range(1 << N)]
            dp_len = [[INF] * N for _ in range(1 << N)]
            parent = [[None] * N for _ in range(1 << N)]

            # init: start -> ball
            for k in range(N):
                bi = 1 + k
                d = dist[idx_start][bi]
                if not math.isfinite(d):
                    continue
                dp_score[1 << k][k] = balls_values[k]
                dp_len[1 << k][k] = d
                parent[1 << k][k] = (None, None)

            best_score = -1
            best_len = INF
            best_end = None  # (mask, k)
            # also allow no-ball solution
            d0, ex0 = best_exit_from(idx_start)
            if math.isfinite(d0) and d0 <= Lmax:
                best_score = 0
                best_len = d0
                best_end = ("EXIT_DIRECT", ex0)

            for mask in range(1 << N):
                for k in range(N):
                    if dp_score[mask][k] < 0:
                        continue
                    cur_len = dp_len[mask][k]
                    cur_score = dp_score[mask][k]
                    cur_idx = 1 + k
                    # finish to exit
                    de, exj = best_exit_from(cur_idx)
                    if exj is not None and math.isfinite(de):
                        tot = cur_len + de
                        if tot <= Lmax:
                            if cur_score > best_score or (cur_score == best_score and tot < best_len):
                                best_score = cur_score
                                best_len = tot
                                best_end = (mask, k, exj)

                    # expand to new ball
                    for nk in range(N):
                        if mask & (1 << nk):
                            continue
                        nb_idx = 1 + nk
                        dstep = dist[cur_idx][nb_idx]
                        if not math.isfinite(dstep):
                            continue
                        new_len = cur_len + dstep
                        if new_len > Lmax:
                            continue
                        new_mask = mask | (1 << nk)
                        new_score = cur_score + balls_values[nk]
                        if (new_score > dp_score[new_mask][nk]) or (new_score == dp_score[new_mask][nk] and new_len < dp_len[new_mask][nk]):
                            dp_score[new_mask][nk] = new_score
                            dp_len[new_mask][nk] = new_len
                            parent[new_mask][nk] = (mask, k)

            # Reconstruct route from best_end
            route = [idx_start]
            if best_end is None:
                # nothing feasible
                route = [idx_start]
            elif isinstance(best_end, tuple) and best_end[0] == "EXIT_DIRECT":
                route = [idx_start, best_end[1]]
            else:
                mask, k, exj = best_end
                seq = []
                cur_mask, cur_k = mask, k
                while cur_k is not None:
                    seq.append(1 + cur_k)
                    pm = parent[cur_mask][cur_k]
                    if pm is None or pm == (None, None):
                        break
                    cur_mask, cur_k = pm
                seq.reverse()
                route += seq
                route.append(exj)
        else:
            # Greedy: pick best value/distance ball while still can exit within Lmax
            remaining = set(range(N))
            route = [idx_start]
            cur_idx = idx_start
            cur_len = 0.0
            best_score = 0
            best_len = float("inf")
            best_route = None

            # baseline: direct to exit
            de0, ex0 = best_exit_from(cur_idx)
            if ex0 is not None and math.isfinite(de0) and de0 <= Lmax:
                best_route = [idx_start, ex0]
                best_score = 0
                best_len = de0

            while remaining:
                best_gain = None
                best_nk = None
                best_next_len = None

                for nk in list(remaining):
                    nb_idx = 1 + nk
                    dstep = dist[cur_idx][nb_idx]
                    if not math.isfinite(dstep):
                        continue
                    new_len = cur_len + dstep
                    de, exj = best_exit_from(nb_idx)
                    if exj is None or not math.isfinite(de):
                        continue
                    if new_len + de > Lmax:
                        continue
                    gain = balls_values[nk] / max(1e-6, dstep)
                    if best_gain is None or gain > best_gain:
                        best_gain = gain
                        best_nk = nk
                        best_next_len = new_len

                if best_nk is None:
                    break
                # take it
                remaining.remove(best_nk)
                route.append(1 + best_nk)
                cur_len = float(best_next_len)
                cur_idx = 1 + best_nk
                best_score += balls_values[best_nk]

                de, exj = best_exit_from(cur_idx)
                if exj is not None and math.isfinite(de):
                    tot = cur_len + de
                    if tot <= Lmax:
                        if best_score > (0 if best_route is None else sum(balls_values[i-1] for i in route if 1 <= i <= N)) or (tot < best_len):
                            best_len = tot
                            best_route = route + [exj]

            route = best_route if best_route is not None else [idx_start]

    # --- Convert route (node indices) to pixel path ---
    pixel_path: List[Coord] = []
    for a, b in zip(route, route[1:]):
        compute_pair(a, b)
        seg = path_cache.get((a, b))
        if not seg:
            continue
        if not pixel_path:
            pixel_path.extend(seg)
        else:
            pixel_path.extend(seg[1:])

    # If we still don't end in an exit, attempt direct exit from last node
    if route and route[-1] not in idx_exits:
        last = route[-1]
        de, exj = best_exit_from(last)
        if exj is not None and math.isfinite(de):
            compute_pair(last, exj)
            seg = path_cache.get((last, exj))
            if seg:
                if not pixel_path:
                    pixel_path.extend(seg)
                else:
                    pixel_path.extend(seg[1:])

    # Final compact solution list
    sol_waypoints = compress_path_to_waypoints(pixel_path, free) if pixel_path else []
    visited_list = list(dict.fromkeys(visited_all))  # dedupe keep order

    # Overlay
    out = np.asarray(pil2.convert("RGB"), dtype=np.uint8).copy()
    out = overlay_points(out, visited_list, color=(255, 255, 0))
    out = overlay_polyline(out, pixel_path, color=(160, 0, 200))

    return out, [[x, y] for (x, y) in sol_waypoints], [[x, y] for (x, y) in visited_list]


# ============================================================
# Part I search methods on a free-space mask (no balls)
# ============================================================

def _neighbors4(mask_free: np.ndarray, p: Coord):
    x, y = p
    H, W = mask_free.shape
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x + dx, y + dy
        if 0 <= nx < W and 0 <= ny < H and mask_free[ny, nx]:
            yield (nx, ny)

def _manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0]-b[0]) + abs(a[1]-b[1])

def _h_to_nearest_exit(p: Coord, exits: List[Coord]) -> int:
    if not exits:
        return 0
    return min(_manhattan(p, e) for e in exits)

def reconstruct_path(parent: Dict[Coord, Optional[Coord]], current: Coord) -> List[Coord]:
    """
    Reconstructs the path from start to current node using the parent dictionary.
    """
    path = [current]
    while current in parent:
        pred = parent[current]
        if pred is None:
            break
        path.append(pred)
        current = pred
    path.reverse()
    return path

def search_part1(mask_free: np.ndarray,
                 start: Coord,
                 exits: List[Coord],
                 method: str = "Breadth First",
                 bidirectional: bool = False):
    """
    Returns: (path, visited_order)
      - path: list of (x,y) from start to one exit (or None)
      - visited_order: list of explored nodes (x,y) in the order popped/expanded
    """
    exits = list(dict.fromkeys(exits))
    if not exits:
        return None, []
    goal_set = set(exits)
    if start in goal_set:
        return [start], [start]

    if not bidirectional:
        # --- Unidirectional ---
        parent: Dict[Coord, Optional[Coord]] = {start: None}
        visited_order: List[Coord] = []
        explored: Set[Coord] = set()

        if method == "Breadth First":
            from collections import deque
            q = deque([start])
            while q:
                cur = q.popleft()
                if cur in explored:
                    continue
                explored.add(cur)
                visited_order.append(cur)
                if cur in goal_set:
                    return reconstruct_path(parent, cur), visited_order
                for nb in _neighbors4(mask_free, cur):
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
                visited_order.append(cur)
                if cur in goal_set:
                    return reconstruct_path(parent, cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    if nb not in parent:
                        parent[nb] = cur
                        stack.append(nb)

        else:
            # UCS / Greedy / A*
            pq: List[Tuple[float, float, Coord]] = []
            g: Dict[Coord, float] = {start: 0.0}
            heapq.heappush(pq, (0.0, random.random(), start))

            def prio(n: Coord) -> float:
                if method == "Uniform Cost":
                    return g[n]
                if method == "Best First (Greedy)":
                    return float(_h_to_nearest_exit(n, exits))
                return g[n] + float(_h_to_nearest_exit(n, exits))  # A*

            while pq:
                _, _, cur = heapq.heappop(pq)
                if cur in explored:
                    continue
                explored.add(cur)
                visited_order.append(cur)
                if cur in goal_set:
                    return reconstruct_path(parent, cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    ng = g[cur] + 1.0
                    if nb not in g or ng < g[nb]:
                        g[nb] = ng
                        parent[nb] = cur
                        heapq.heappush(pq, (prio(nb), random.random(), nb))

        return None, visited_order

    # --- Bidirectional (multi-source from all exits) ---
    # For BFS/DFS we alternate expansions from start frontier and exit frontier.
    # For UCS/Greedy/A* we use two priority queues; meeting point gives candidate solution.
    parent_f: Dict[Coord, Optional[Coord]] = {start: None}
    parent_b: Dict[Coord, Optional[Coord]] = {e: None for e in exits}
    explored_f: Set[Coord] = set()
    explored_b: Set[Coord] = set()
    visited_order: List[Coord] = []

    def meet_path(meet: Coord) -> List[Coord]:
        path_f = reconstruct_path(parent_f, meet)
        path_b = []
        cur = parent_b.get(meet)
        while cur is not None:
            path_b.append(cur)
            cur = parent_b.get(cur)
        return path_f + path_b

    if method == "Breadth First":
        from collections import deque
        qf = deque([start])
        qb = deque(exits)
        while qf and qb:
            cur = qf.popleft()
            if cur not in explored_f:
                explored_f.add(cur); visited_order.append(cur)
                if cur in explored_b:
                    return meet_path(cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    if nb not in parent_f:
                        parent_f[nb] = cur
                        qf.append(nb)

            cur = qb.popleft()
            if cur not in explored_b:
                explored_b.add(cur); visited_order.append(cur)
                if cur in explored_f:
                    return meet_path(cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    if nb not in parent_b:
                        parent_b[nb] = cur
                        qb.append(nb)
        return None, visited_order

    if method == "Depth First":
        sf = [start]
        sb = list(exits)
        while sf and sb:
            cur = sf.pop()
            if cur not in explored_f:
                explored_f.add(cur); visited_order.append(cur)
                if cur in explored_b:
                    return meet_path(cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    if nb not in parent_f:
                        parent_f[nb] = cur
                        sf.append(nb)

            cur = sb.pop()
            if cur not in explored_b:
                explored_b.add(cur); visited_order.append(cur)
                if cur in explored_f:
                    return meet_path(cur), visited_order
                for nb in _neighbors4(mask_free, cur):
                    if nb not in parent_b:
                        parent_b[nb] = cur
                        sb.append(nb)
        return None, visited_order

    # Priority bidirectional (UCS/Greedy/A*)
    gf: Dict[Coord, float] = {start: 0.0}
    gb: Dict[Coord, float] = {e: 0.0 for e in exits}

    def pf(n: Coord) -> float:
        if method == "Uniform Cost":
            return gf[n]
        if method == "Best First (Greedy)":
            return float(_h_to_nearest_exit(n, exits))
        return gf[n] + float(_h_to_nearest_exit(n, exits))

    def pb(n: Coord) -> float:
        # backward heuristic can target start
        if method == "Uniform Cost":
            return gb[n]
        if method == "Best First (Greedy)":
            return float(_manhattan(n, start))
        return gb[n] + float(_manhattan(n, start))

    pqf: List[Tuple[float, float, Coord]] = [(pf(start), random.random(), start)]
    pqb: List[Tuple[float, float, Coord]] = [(pb(e), random.random(), e) for e in exits]
    heapq.heapify(pqb)

    best_meet: Optional[Coord] = None
    best_cost = float("inf")

    while pqf and pqb:
        # Expand the side with smaller frontier key
        if pqf[0][0] <= pqb[0][0]:
            _, _, cur = heapq.heappop(pqf)
            if cur in explored_f:
                continue
            explored_f.add(cur); visited_order.append(cur)
            if cur in explored_b:
                total = gf.get(cur, 1e18) + gb.get(cur, 1e18)
                if total < best_cost:
                    best_cost = total
                    best_meet = cur
            for nb in _neighbors4(mask_free, cur):
                ng = gf[cur] + 1.0
                if nb not in gf or ng < gf[nb]:
                    gf[nb] = ng
                    parent_f[nb] = cur
                    heapq.heappush(pqf, (pf(nb), random.random(), nb))
        else:
            _, _, cur = heapq.heappop(pqb)
            if cur in explored_b:
                continue
            explored_b.add(cur); visited_order.append(cur)
            if cur in explored_f:
                total = gf.get(cur, 1e18) + gb.get(cur, 1e18)
                if total < best_cost:
                    best_cost = total
                    best_meet = cur
            for nb in _neighbors4(mask_free, cur):
                ng = gb[cur] + 1.0
                if nb not in gb or ng < gb[nb]:
                    gb[nb] = ng
                    parent_b[nb] = cur
                    heapq.heappush(pqb, (pb(nb), random.random(), nb))

        if best_meet is not None and method in ("Uniform Cost", "A*"):
            if pqf and pqb and pqf[0][0] + pqb[0][0] >= best_cost:
                break
        if best_meet is not None and method == "Best First (Greedy)":
            break

    if best_meet is None:
        return None, visited_order
    return meet_path(best_meet), visited_order


class MazeHomeworkApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Maze Homework - Part I + Part II (v4)")
        self.geometry("1320x820")
        self.minsize(1150, 680)

        self.generated_maze: Optional[MazeData] = None
        self._rng = random.Random()
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
        ttk.Checkbutton(lf, text="Generate WITH balls (Part II)", variable=self.var_gen_with_balls).grid(row=r, column=0, columnspan=2, sticky="w", pady=(6, 0))
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
        btns.columnconfigure((0,1), weight=1)
        ttk.Button(btns, text="Generate Maze", command=self.on_generate).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(btns, text="Load Maze (PNG/JPG)", command=self.on_load).grid(row=0, column=1, sticky="ew")
        r += 1

        btns2 = ttk.Frame(lf)
        btns2.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        btns2.columnconfigure((0,1), weight=1)
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
        ttk.Scale(c1, from_=0.3, to=6.0, variable=self.var_zoom_left1, command=self._on_zoom_left1).pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(c1, text="FIT", command=self._fit_left1).pack(side="left")
        self.preview_current = FitZoomCanvas(pv, bg="#111111")
        self.preview_current.grid(row=2, column=0, sticky="nsew", pady=(4, 12))

        ttk.Label(pv, text="Generated solution paths (Green)").grid(row=3, column=0, sticky="w")
        c2 = ttk.Frame(pv)
        c2.grid(row=4, column=0, sticky="ew")
        ttk.Label(c2, text="Zoom").pack(side="left")
        self.var_zoom_left2 = tk.DoubleVar(value=1.0)
        ttk.Scale(c2, from_=0.3, to=6.0, variable=self.var_zoom_left2, command=self._on_zoom_left2).pack(side="left", fill="x", expand=True, padx=(6, 6))
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
                place_random_balls_on_maze(maze, mn, mx, rng=self._rng)

            tile_px = int(self.var_tile_px.get())
            self.generated_img = tiles_to_image_with_balls(maze, tile_px=tile_px, draw_balls=with_balls, ball_px=None)

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

        base = tiles_to_image_with_balls(maze, tile_px=tile_px, draw_balls=True, ball_px=None)
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

    def _build_right(self):
        self.right.columnconfigure(0, weight=1)
        self.right.rowconfigure(2, weight=1)

        lf = ttk.LabelFrame(self.right, text="Search", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        row0 = ttk.Frame(lf)
        row0.grid(row=0, column=0, sticky="ew")
        ttk.Label(row0, text="Algorithm (Part I):").pack(side="left")
        self.var_algo = tk.StringVar(value="Breadth First")
        opts = ["Breadth First", "Depth First", "Uniform Cost", "Best First (Greedy)", "A*"]
        ttk.OptionMenu(row0, self.var_algo, self.var_algo.get(), *opts).pack(side="left", padx=(8, 12))
        self.var_bidir = tk.BooleanVar(value=False)
        ttk.Checkbutton(row0, text="Bidirectional (Part I)", variable=self.var_bidir).pack(side="left")

        row1 = ttk.Frame(lf)
        row1.grid(row=1, column=0, sticky="ew", pady=(8, 0))
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
        row2.grid(row=2, column=0, sticky="ew", pady=(10, 0))
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
    def on_run_part1(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return
        try:
            method = self.var_algo.get()
            bidir = bool(self.var_bidir.get())

            pil = _auto_crop_rgb(self.current_maze_img)
            free = free_mask_from_rgb(pil, wall_darkness=80)

            exits = find_border_exits(free)
            if not exits:
                messagebox.showwarning("No exits", "No exits detected on border in Part I analysis.")
                return

            # Start at center (closest free pixel if blocked)
            sx, sy = pil.width // 2, pil.height // 2
            if not free[sy, sx]:
                p = nearest_true(free, (pil.width / 2.0, pil.height / 2.0))
                if p:
                    sx, sy = p

            self.lbl_right_status.config(text="Part I: running...")
            self.update_idletasks()

            t0 = time.perf_counter()
            path, visited = search_part1(free, (sx, sy), exits, method=method, bidirectional=bidir)
            dt = time.perf_counter() - t0

            out = pil.convert("RGB").copy()
            draw = ImageDraw.Draw(out)

            # Draw visited (yellow) then path (purple)
            for x, y in visited:
                draw.point((x, y), fill=(255, 255, 0))
            if path:
                for x, y in path:
                    draw.point((x, y), fill=(160, 0, 200))

            # Refresh display (keep zoom)
            z = self.view_right.get_zoom_factor()
            self.view_right.set_image(out, reset_zoom=False)
            self.view_right.set_zoom_factor(z)
            self.update_idletasks()

            self.lbl_right_status.config(
                text=f"Part I: {method} | bidir={bidir} | {'FOUND' if path else 'NOT FOUND'} "
                     f"| visited={len(visited)} | time={dt:.4f}s"
            )
        except Exception as e:
            messagebox.showerror("RUN Part I Error", str(e))

    def on_run_part2(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return
        try:
            RGB = [int(self.var_R.get()), int(self.var_G.get()), int(self.var_B.get())]
        except Exception:
            RGB = [1, 2, 3]
        
        # FIX: used to refer to self.var_len (which didn't exist), now refers to self.var_L
        sol_len = self.var_L.get().strip() if hasattr(self, "var_L") else "inf"
        if sol_len == "":
            sol_len = "inf"

        self.lbl_right_status.config(text="Part II: running...")
        self.update_idletasks()

        t0 = time.perf_counter()
        ResImage, SolutionList, VisitedList = searchLikeThereIsNoTomorrow(self.current_maze_img, RGBValues=RGB, SolutionLength=sol_len)
        dt = time.perf_counter() - t0

        # ResImage may be numpy or PIL; normalize to PIL
        if isinstance(ResImage, np.ndarray):
            if ResImage.ndim == 2:
                ResImage = np.stack([ResImage]*3, axis=-1)
            out = Image.fromarray(ResImage.astype(np.uint8), mode="RGB")
        elif isinstance(ResImage, Image.Image):
            out = ResImage.convert("RGB")
        else:
            # fallback: redraw from current and overlay points
            pil = _auto_crop_rgb(self.current_maze_img).convert("RGB")
            out = pil.copy()
            draw = ImageDraw.Draw(out)
            for x, y in VisitedList:
                draw.point((x, y), fill=(255, 255, 0))
            for x, y in SolutionList:
                draw.point((x, y), fill=(160, 0, 200))

        z = self.view_right.get_zoom_factor()
        self.view_right.set_image(out, reset_zoom=False)
        self.view_right.set_zoom_factor(z)
        self.update_idletasks()

        self.lbl_right_status.config(
            text=f"Part II: done | sol_pts={len(SolutionList)} visited={len(VisitedList)} time={dt:.4f}s"
        )



def main():
    app = MazeHomeworkApp()
    app.mainloop()


if __name__ == "__main__":
    main()