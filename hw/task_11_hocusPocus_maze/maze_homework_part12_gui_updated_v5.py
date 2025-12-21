#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Maze Homework GUI (Part I + Part II) - Updated v5

Adds Part II (as requested):
- Generate maze WITH or WITHOUT RGB balls (placed in the middle of hallways).
- RGB bonus value boxes (default R=1, G=2, B=3).
- SolutionLength box (default 'inf').
- RUN Part II button calls:
    searchLikeThereIsNoTomorrow(MazeImage, RGBValues=[R,G,B], SolutionLength=...)
  and displays returned overlay + lists.

Key Part II "centerline" requirement:
- For searching in Part II, we extract a 1-pixel-wide CENTERLINE (skeleton) of the free space,
  so movement behaves like it is in the middle of corridors even if they are thick.
- Detected balls are snapped to the centerline as well.

Dependencies:
  pip install pillow numpy
Run:
  python3 maze_homework_part12_gui_updated_v5.py
"""

import random
import heapq
import time
import os
from collections import deque
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple, Union

import numpy as np
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


def _tile_free_degree(maze: MazeData, p: Coord) -> int:
    x, y = p
    deg = 0
    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
        nx, ny = x + dx, y + dy
        if 0 <= nx < maze.tile_w and 0 <= ny < maze.tile_h and maze.tiles[ny][nx] == 0:
            deg += 1
    return deg


def add_rgb_balls_to_rendered_maze(img: Image.Image, maze: MazeData, tile_px: int,
                                  n_min: int, n_max: int, seed: Optional[int] = None) -> Tuple[Image.Image, List[Tuple[Coord, Tuple[int,int,int]]]]:
    """
    Places N balls (N in [n_min, n_max]) on *hallway* tiles (degree=2 preferred) and draws them
    as small filled circles at the CENTER of the tile (middle of hallway thickness).

    Returns:
      new_img, balls = [ ((tile_x, tile_y), (r,g,b)), ... ]
    """
    rng = random.Random(seed)
    n_min = max(0, int(n_min))
    n_max = max(0, int(n_max))
    if n_min > n_max:
        n_min, n_max = n_max, n_min
    N = 0 if n_max == 0 else rng.randint(n_min, n_max)

    if N <= 0:
        return img, []

    # candidates: free tiles, not on border exits, not inside the 3x3 room (close to start), prefer degree==2
    sx, sy = maze.start
    room_forbid = set()
    for yy in range(sy-1, sy+2):
        for xx in range(sx-1, sx+2):
            if 0 <= xx < maze.tile_w and 0 <= yy < maze.tile_h:
                room_forbid.add((xx, yy))

    free_tiles = [(x, y) for y in range(1, maze.tile_h-1) for x in range(1, maze.tile_w-1) if maze.tiles[y][x] == 0]
    hall_tiles = [p for p in free_tiles if _tile_free_degree(maze, p) == 2 and p not in room_forbid]
    cand = hall_tiles if len(hall_tiles) >= N else [p for p in free_tiles if p not in room_forbid]

    rng.shuffle(cand)
    chosen = cand[:N]

    colors = [(255,0,0), (0,255,0), (0,0,255)]
    balls: List[Tuple[Coord, Tuple[int,int,int]]] = []
    out = img.copy()
    draw = ImageDraw.Draw(out)

    rad = max(1, tile_px // 3)
    for (tx, ty) in chosen:
        col = rng.choice(colors)
        cx = tx * tile_px + tile_px // 2
        cy = ty * tile_px + tile_px // 2
        draw.ellipse([cx-rad, cy-rad, cx+rad, cy+rad], fill=col, outline=None)
        balls.append(((tx, ty), col))
    return out, balls


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


def overlay_green_paths_on_bw(base_img: Image.Image, maze: MazeData, paths: List[List[Coord]],
                             tile_px: int = 8) -> Image.Image:
    img = base_img.copy()
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
# Image-based analysis (Part II readiness)
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
        Robust wall detection for colored balls:
          wall if max(R,G,B) < wall_darkness
          otherwise free.
        """
        grid_w = max(51, int(grid_w))
        grid_h = max(51, int(grid_h))
        wall_darkness = clamp(int(wall_darkness), 5, 200)

        rgb = img.convert("RGB")
        gray = ImageOps.autocontrast(rgb.convert("L"))
        gray = MazeAnalyzer._auto_crop(gray)

        # Crop using bbox computed on grayscale, apply crop to RGB too
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
# Part II core function
# =========================

def _pick_analysis_grid_for_image(w: int, h: int) -> Tuple[int, int]:
    """
    Picks an analysis grid size automatically for Part II.
    Keeps it <= 401 for performance, and tries to preserve aspect ratio.
    """
    m = max(1, min(w, h))
    base = int(round(m / 4))
    base = clamp(base, 101, 401)
    if base % 2 == 0:
        base += 1

    # preserve aspect ratio
    if w >= h:
        gw = base
        gh = int(round(base * h / w))
    else:
        gh = base
        gw = int(round(base * w / h))

    gw = clamp(gw, 51, 401)
    gh = clamp(gh, 51, 401)
    if gw % 2 == 0: gw += 1
    if gh % 2 == 0: gh += 1
    return gw, gh


def _rgb_ball_masks(rgb_small: Image.Image) -> Tuple[List[List[bool]], List[List[bool]], List[List[bool]]]:
    """
    Returns 3 masks on the resized analysis image for (R,G,B) ball pixels.
    Thresholds are tolerant to JPEG artifacts.
    """
    w, h = rgb_small.size
    px = rgb_small.load()

    rmask = [[False]*w for _ in range(h)]
    gmask = [[False]*w for _ in range(h)]
    bmask = [[False]*w for _ in range(h)]

    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            # Strong primary color, weak others
            if r >= 180 and g <= 120 and b <= 120 and r - max(g, b) >= 60:
                rmask[y][x] = True
            elif g >= 180 and r <= 120 and b <= 120 and g - max(r, b) >= 60:
                gmask[y][x] = True
            elif b >= 180 and r <= 120 and g <= 120 and b - max(r, g) >= 60:
                bmask[y][x] = True
    return rmask, gmask, bmask


def _connected_components(mask: List[List[bool]]) -> List[List[Coord]]:
    h = len(mask)
    w = len(mask[0]) if h else 0
    seen = [[False]*w for _ in range(h)]
    comps: List[List[Coord]] = []
    for y in range(h):
        for x in range(w):
            if mask[y][x] and not seen[y][x]:
                q = deque([(x, y)])
                seen[y][x] = True
                comp: List[Coord] = []
                while q:
                    cx, cy = q.popleft()
                    comp.append((cx, cy))
                    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True
                            q.append((nx, ny))
                if comp:
                    comps.append(comp)
    return comps


def _zhang_suen_thinning(free: List[List[bool]]) -> List[List[bool]]:
    """
    Zhang-Suen thinning (skeletonization) on a boolean foreground image.
    Foreground=True (free space), Background=False (walls).
    """
    h = len(free)
    w = len(free[0]) if h else 0

    # represent as 0/1 int for speed
    img = [[1 if free[y][x] else 0 for x in range(w)] for y in range(h)]

    def neighbors8(x: int, y: int):
        # p2..p9
        p2 = img[y-1][x]
        p3 = img[y-1][x+1]
        p4 = img[y][x+1]
        p5 = img[y+1][x+1]
        p6 = img[y+1][x]
        p7 = img[y+1][x-1]
        p8 = img[y][x-1]
        p9 = img[y-1][x-1]
        return p2, p3, p4, p5, p6, p7, p8, p9

    def count_nonzero(ns):
        return sum(ns)

    def transitions(ns):
        # ns is p2..p9
        p2,p3,p4,p5,p6,p7,p8,p9 = ns
        seq = [p2,p3,p4,p5,p6,p7,p8,p9,p2]
        t = 0
        for i in range(8):
            if seq[i] == 0 and seq[i+1] == 1:
                t += 1
        return t

    changed = True
    # avoid borders
    while changed:
        changed = False
        to_del = []

        # step 1
        for y in range(1, h-1):
            row = img[y]
            for x in range(1, w-1):
                if row[x] != 1:
                    continue
                ns = neighbors8(x, y)
                n = count_nonzero(ns)
                if n < 2 or n > 6:
                    continue
                if transitions(ns) != 1:
                    continue
                p2,p3,p4,p5,p6,p7,p8,p9 = ns
                if p2 * p4 * p6 != 0:
                    continue
                if p4 * p6 * p8 != 0:
                    continue
                to_del.append((x, y))

        if to_del:
            for x, y in to_del:
                img[y][x] = 0
            changed = True

        to_del = []
        # step 2
        for y in range(1, h-1):
            row = img[y]
            for x in range(1, w-1):
                if row[x] != 1:
                    continue
                ns = neighbors8(x, y)
                n = count_nonzero(ns)
                if n < 2 or n > 6:
                    continue
                if transitions(ns) != 1:
                    continue
                p2,p3,p4,p5,p6,p7,p8,p9 = ns
                if p2 * p4 * p8 != 0:
                    continue
                if p2 * p6 * p8 != 0:
                    continue
                to_del.append((x, y))

        if to_del:
            for x, y in to_del:
                img[y][x] = 0
            changed = True

    skel = [[bool(img[y][x]) for x in range(w)] for y in range(h)]
    return skel


def _snap_to_mask(p: Coord, free: List[List[bool]], mask: List[List[bool]], max_radius: int = 30) -> Coord:
    """
    Snap point p to nearest True cell in `mask`, searching within free space.
    If none found quickly, returns original p (or nearest free cell).
    """
    w = len(free[0]); h = len(free)
    x0, y0 = p
    x0 = clamp(x0, 0, w-1)
    y0 = clamp(y0, 0, h-1)

    if mask[y0][x0]:
        return (x0, y0)

    # If starting point is wall, snap to nearest free first
    if not free[y0][x0]:
        q = deque([(x0, y0)])
        seen = {(x0, y0)}
        found = None
        while q and found is None:
            x, y = q.popleft()
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen:
                    seen.add((nx, ny))
                    if free[ny][nx]:
                        found = (nx, ny)
                        break
                    q.append((nx, ny))
        if found:
            x0, y0 = found

    q = deque([(x0, y0)])
    seen = {(x0, y0)}
    depth = { (x0,y0): 0 }
    while q:
        x, y = q.popleft()
        d = depth[(x,y)]
        if d > max_radius:
            break
        if mask[y][x]:
            return (x, y)
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and free[ny][nx]:
                seen.add((nx, ny))
                depth[(nx,ny)] = d + 1
                q.append((nx, ny))
    return (x0, y0)


def _bfs_path_on_mask(mask: List[List[bool]], src: Coord, dst: Coord) -> Tuple[List[Coord], List[Coord]]:
    """
    BFS shortest path on a boolean `mask` graph using 4-neighbors.
    Returns (path, visited_in_order). Empty path if unreachable.
    """
    w = len(mask[0]); h = len(mask)
    sx, sy = src; tx, ty = dst
    if not (0 <= sx < w and 0 <= sy < h and 0 <= tx < w and 0 <= ty < h):
        return [], []
    if not mask[sy][sx] or not mask[ty][tx]:
        return [], []

    q = deque([src])
    parent: Dict[Coord, Optional[Coord]] = {src: None}
    visited: List[Coord] = []

    while q:
        cur = q.popleft()
        visited.append(cur)
        if cur == dst:
            break
        x, y = cur
        for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
            nx, ny = x + dx, y + dy
            nb = (nx, ny)
            if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and nb not in parent:
                parent[nb] = cur
                q.append(nb)

    if dst not in parent:
        return [], visited

    path = []
    cur = dst
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path, visited


def _path_length_grid(path: List[Coord]) -> float:
    if len(path) < 2:
        return 0.0
    # 4-neighbor steps => each step length 1
    return float(len(path) - 1)


def _scale_points_to_image(points: List[Coord], W: int, H: int, gw: int, gh: int) -> List[List[int]]:
    sx = W / float(gw)
    sy = H / float(gh)
    out: List[List[int]] = []
    for x, y in points:
        px = int((x + 0.5) * sx)
        py = int((y + 0.5) * sy)
        px = clamp(px, 0, W-1)
        py = clamp(py, 0, H-1)
        out.append([px, py])
    return out


def searchLikeThereIsNoTomorrow(MazeImage, RGBValues = [1,2,3], SolutionLength = 'inf'):
    """
    Part II required function (DO NOT change signature).

    MazeImage: numpy array (H,W,3) or PIL image or filepath.
    RGBValues: [Rvalue, Gvalue, Bvalue]
    SolutionLength: 'inf' or positive number (pixel-wise, on original image scale).

    Returns:
      ResImage (numpy array, RGB),
      SolutionList (list of [x,y] on original image),
      VisitedList (list of [x,y] on original image)
    """
    # --- Load image ---
    if isinstance(MazeImage, str):
        img0 = Image.open(MazeImage).convert("RGB")
    elif isinstance(MazeImage, Image.Image):
        img0 = MazeImage.convert("RGB")
    else:
        arr = np.asarray(MazeImage)
        if arr.ndim == 2:
            arr = np.stack([arr]*3, axis=-1)
        if arr.shape[-1] == 4:
            arr = arr[..., :3]
        img0 = Image.fromarray(arr.astype(np.uint8), mode="RGB")

    W, H = img0.size

    # parse SolutionLength
    L_px: Optional[float] = None
    try:
        if isinstance(SolutionLength, str) and SolutionLength.strip().lower() == "inf":
            L_px = None
        elif SolutionLength is None:
            L_px = None
        else:
            L_px = float(SolutionLength)
            if not (L_px > 0):
                L_px = None
    except Exception:
        L_px = None

    # choose analysis grid
    gw, gh = _pick_analysis_grid_for_image(W, H)

    # analyze free/walls on resized
    wall_dark = 80
    analyzed = MazeAnalyzer.analyze_rgb_darkness(img0, gw, gh, wall_darkness=wall_dark)

    # if no exits, return base
    if not analyzed.exits:
        res = np.asarray(img0).copy()
        return res, [], []

    # Build resized RGB for ball detection, matching analyze crop/resize approach:
    rgb_small = img0.convert("RGB").resize((gw, gh), Image.Resampling.NEAREST)

    # Detect balls (RGB regions)
    rmask, gmask, bmask = _rgb_ball_masks(rgb_small)
    comps_r = _connected_components(rmask)
    comps_g = _connected_components(gmask)
    comps_b = _connected_components(bmask)

    balls: List[Tuple[Coord, int]] = []  # (pos_on_grid, value)
    values = [int(RGBValues[0]), int(RGBValues[1]), int(RGBValues[2])]
    values = [max(1, v) for v in values]

    def comp_centroid(comp: List[Coord]) -> Coord:
        sx = sum(p[0] for p in comp)
        sy = sum(p[1] for p in comp)
        n = max(1, len(comp))
        return (int(round(sx/n)), int(round(sy/n)))

    for comp in comps_r:
        if len(comp) >= 2:
            balls.append((comp_centroid(comp), values[0]))
    for comp in comps_g:
        if len(comp) >= 2:
            balls.append((comp_centroid(comp), values[1]))
    for comp in comps_b:
        if len(comp) >= 2:
            balls.append((comp_centroid(comp), values[2]))

    # centerline skeleton
    free = analyzed.free
    skel = _zhang_suen_thinning(free)

    # ensure start/exits are on skeleton
    start_s = _snap_to_mask(analyzed.start, free, skel)
    exits_s = [_snap_to_mask(g, free, skel) for g in analyzed.exits]

    # snap balls to skeleton (critical)
    snapped_balls: List[Tuple[Coord, int]] = []
    seen_ball_pos: Set[Coord] = set()
    for (p, val) in balls:
        ps = _snap_to_mask(p, free, skel)
        if ps not in seen_ball_pos:
            snapped_balls.append((ps, val))
            seen_ball_pos.add(ps)

    # Also add guaranteed connectivity: add free-grid shortest paths from start to each exit into skeleton
    # This avoids rare thinning disconnections.
    def bfs_free_path(src: Coord, dst: Coord) -> List[Coord]:
        w = analyzed.grid_w; h = analyzed.grid_h
        q = deque([src])
        parent = {src: None}
        while q:
            cur = q.popleft()
            if cur == dst:
                break
            x, y = cur
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x + dx, y + dy
                nb = (nx, ny)
                if 0 <= nx < w and 0 <= ny < h and free[ny][nx] and nb not in parent:
                    parent[nb] = cur
                    q.append(nb)
        if dst not in parent:
            return []
        path = []
        cur = dst
        while cur is not None:
            path.append(cur)
            cur = parent[cur]
        path.reverse()
        return path

    for g in exits_s:
        p = bfs_free_path(start_s, g)
        for (x, y) in p:
            skel[y][x] = True

    # Helper: BFS on skeleton with visited capture
    def bfs_path(src: Coord, dst: Coord) -> Tuple[List[Coord], List[Coord]]:
        return _bfs_path_on_mask(skel, src, dst)

    # Precompute base shortest paths to exits and choose best (for limited length we evaluate each exit)
    # scale factor from grid to original pixels (for length constraint)
    scale = (W / gw + H / gh) / 2.0
    L_grid = None if L_px is None else (L_px / scale)

    # Build distance maps lazily (from a node -> dist array)
    dist_cache: Dict[Coord, List[List[int]]] = {}

    def bfs_dist(src: Coord) -> Tuple[List[List[int]], List[Coord]]:
        if src in dist_cache:
            # no visited list for cached
            return dist_cache[src], []
        w = analyzed.grid_w; h = analyzed.grid_h
        dist = [[-1]*w for _ in range(h)]
        q = deque([src])
        dist[src[1]][src[0]] = 0
        visited: List[Coord] = []
        while q:
            x, y = q.popleft()
            visited.append((x, y))
            d = dist[y][x]
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and skel[ny][nx] and dist[ny][nx] == -1:
                    dist[ny][nx] = d + 1
                    q.append((nx, ny))
        dist_cache[src] = dist
        return dist, visited

    def dist(a: Coord, b: Coord) -> int:
        da, _ = bfs_dist(a)
        return da[b[1]][b[0]]

    # Score and route building (greedy insertion for limited length, exact max for inf by collecting all reachable balls)
    best_points = -1
    best_route_nodes: List[Coord] = []
    best_visited_nodes: List[Coord] = []

    # quick reachability from start
    d_start, visited_start = bfs_dist(start_s)

    # If L is inf: take all balls reachable and reachable exit, then any exit
    if L_grid is None:
        # find exits reachable
        reachable_exits = [g for g in exits_s if d_start[g[1]][g[0]] >= 0]
        if not reachable_exits:
            res = np.asarray(img0).copy()
            return res, [], _scale_points_to_image(visited_start[:5000], W, H, gw, gh)

        # collect all balls in component
        reachable_balls = [(p, v) for (p, v) in snapped_balls if d_start[p[1]][p[0]] >= 0]
        total_points = sum(v for _, v in reachable_balls)

        # Build a spanning tree walk (BFS tree) to "visit everything" (collect all balls)
        w = analyzed.grid_w; h = analyzed.grid_h
        parent = {start_s: None}
        q = deque([start_s])
        order: List[Coord] = []
        while q:
            cur = q.popleft()
            order.append(cur)
            x, y = cur
            for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                nx, ny = x + dx, y + dy
                nb = (nx, ny)
                if 0 <= nx < w and 0 <= ny < h and skel[ny][nx] and nb not in parent:
                    parent[nb] = cur
                    q.append(nb)

        # DFS traversal of tree to produce a walk
        children: Dict[Coord, List[Coord]] = {k: [] for k in parent.keys()}
        for node, par in parent.items():
            if par is not None:
                children[par].append(node)

        walk: List[Coord] = []
        stack = [(start_s, 0)]
        walk.append(start_s)
        while stack:
            node, idx = stack[-1]
            if idx < len(children[node]):
                nxt = children[node][idx]
                stack[-1] = (node, idx + 1)
                stack.append((nxt, 0))
                walk.append(nxt)
            else:
                stack.pop()
                if stack:
                    walk.append(stack[-1][0])

        # end at nearest exit from current end
        end = walk[-1]
        best_exit = min(reachable_exits, key=lambda g: dist(end, g) if dist(end, g) >= 0 else 10**9)
        seg, vis = bfs_path(end, best_exit)
        if seg:
            walk.extend(seg[1:])

        best_points = total_points
        best_route_nodes = walk
        best_visited_nodes = visited_start  # enough as "intermediate" for inf
    else:
        # Finite length: evaluate each exit with greedy insertion
        reachable_exits = [g for g in exits_s if d_start[g[1]][g[0]] >= 0]
        if not reachable_exits:
            res = np.asarray(img0).copy()
            return res, [], _scale_points_to_image(visited_start[:5000], W, H, gw, gh)

        # Pre-sort balls by value descending (helps greedy)
        reachable_balls = [(p, v) for (p, v) in snapped_balls if d_start[p[1]][p[0]] >= 0]
        reachable_balls.sort(key=lambda t: t[1], reverse=True)

        # limit candidates for speed (still good accuracy in typical homework sizes)
        cand_balls = reachable_balls[:min(len(reachable_balls), 120)]

        for goal in reachable_exits:
            base_d = dist(start_s, goal)
            if base_d < 0:
                continue
            route = [start_s, goal]
            route_len = float(base_d)
            collected: Set[Coord] = set()
            points = 0
            visited_nodes: List[Coord] = []
            improved = True
            # Greedy insertion loop
            while improved:
                improved = False
                best_gain = 0.0
                best_choice = None  # (ball_pos, ball_val, insert_idx, inc_len)
                for (bp, bv) in cand_balls:
                    if bp in collected:
                        continue
                    # Try all insertion places
                    best_local = None
                    for i in range(len(route) - 1):
                        a = route[i]
                        b = route[i+1]
                        dab = dist(a, b)
                        if dab < 0:
                            continue
                        da = dist(a, bp)
                        db = dist(bp, b)
                        if da < 0 or db < 0:
                            continue
                        inc = da + db - dab
                        if inc < 0:
                            inc = 0
                        if route_len + inc <= L_grid + 1e-9:
                            # value / (inc+eps)
                            score = bv / (inc + 0.75)
                            if best_local is None or score > best_local[0]:
                                best_local = (score, i+1, inc)
                    if best_local is None:
                        continue
                    score, ins, inc = best_local
                    if score > best_gain:
                        best_gain = score
                        best_choice = (bp, bv, ins, inc)

                if best_choice is not None:
                    bp, bv, ins, inc = best_choice
                    route.insert(ins, bp)
                    collected.add(bp)
                    points += bv
                    route_len += inc
                    improved = True

            # route length already <= L_grid; now construct concrete node path by concatenating BFS paths
            full_path: List[Coord] = []
            all_vis: List[Coord] = []
            ok = True
            for i in range(len(route) - 1):
                seg, vis = bfs_path(route[i], route[i+1])
                all_vis.extend(vis)
                if not seg:
                    ok = False
                    break
                if i == 0:
                    full_path.extend(seg)
                else:
                    full_path.extend(seg[1:])

            if not ok:
                continue

            # compute points along the concrete path (collect-once rule)
            ball_map: Dict[Coord, int] = {p: v for (p, v) in cand_balls}
            got: Set[Coord] = set()
            real_points = 0
            for node in full_path:
                if node in ball_map and node not in got:
                    got.add(node)
                    real_points += ball_map[node]

            # ensure length constraint on grid length
            real_len = _path_length_grid(full_path)
            if real_len > L_grid + 1e-6:
                continue

            # choose best
            if (real_points > best_points) or (real_points == best_points and len(full_path) < len(best_route_nodes) if best_route_nodes else True):
                best_points = real_points
                best_route_nodes = full_path
                best_visited_nodes = visited_start + all_vis

    # Build ResImage overlay on original image
    out_img = img0.copy().convert("RGB")
    draw = ImageDraw.Draw(out_img)

    # Convert route/visited to original pixel coords
    sol_xy = _scale_points_to_image(best_route_nodes, W, H, gw, gh)
    vis_xy = _scale_points_to_image(best_visited_nodes, W, H, gw, gh)

    # Draw visited (yellow) - sample for speed
    max_vis_draw = 7000
    if len(vis_xy) > max_vis_draw:
        step = max(1, len(vis_xy) // max_vis_draw)
        vis_draw = vis_xy[::step]
    else:
        vis_draw = vis_xy

    for (x, y) in vis_draw:
        # small dot
        draw.point((x, y), fill=(255, 255, 0))

    # Draw solution path (purple)
    if len(sol_xy) >= 2:
        pts = [(p[0], p[1]) for p in sol_xy]
        draw.line(pts, fill=(160, 0, 200), width=2)

    # Return numpy image + lists in original pixel coordinates
    res_arr = np.asarray(out_img).copy()
    SolutionList = sol_xy
    VisitedList = vis_xy
    return res_arr, SolutionList, VisitedList


# =========================
# Part I Search algorithms (existing)
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
        self.title("Maze Homework - Part I + Part II (Updated v5)")
        self.geometry("1280x780")
        self.minsize(1100, 650)

        # State (left determines current maze)
        self.generated_maze: Optional[MazeData] = None
        self.generated_img: Optional[Image.Image] = None  # may include balls
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

        # Generate mode: with/without balls
        ttk.Label(lf, text="Generation mode").grid(row=row, column=0, sticky="w")
        self.var_gen_mode = tk.StringVar(value="Without balls")
        ttk.OptionMenu(lf, self.var_gen_mode, self.var_gen_mode.get(), "Without balls", "With balls").grid(row=row, column=1, sticky="w")
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
            # Balls min/max sanity
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
            base = tiles_to_bw_image(maze, tile_px=tile_px)

            # optional balls
            if self.var_gen_mode.get() == "With balls":
                base, _balls = add_rgb_balls_to_rendered_maze(
                    base, maze, tile_px=tile_px, n_min=mn, n_max=mx
                )

            self.generated_img = base

            paths_dict = solve_on_tiles_shortest_paths(maze)
            paths = list(paths_dict.values())
            self.generated_solution_img = overlay_green_paths_on_bw(self.generated_img, maze, paths, tile_px=tile_px)
            self.preview_solution.set_image(self.generated_solution_img, reset_zoom=True)
            self.var_zoom_left2.set(1.0)

            label = f"Generated ({self.var_cells_w.get()}x{self.var_cells_h.get()} cells, {self.var_gen_mode.get()})"
            self._set_current_maze(self.generated_img, label)
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
        self.right.rowconfigure(3, weight=1)

        lf = ttk.LabelFrame(self.right, text="Search (Analyze pixels + run algorithm)", padding=10)
        lf.grid(row=0, column=0, sticky="ew")

        res = ttk.Frame(lf)
        res.grid(row=0, column=0, sticky="ew")
        self.var_grid_w = tk.IntVar(value=201)
        self.var_grid_h = tk.IntVar(value=201)
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
        ttk.Label(algo, text="Algorithm (Part I):").pack(side="left")
        self.var_algo = tk.StringVar(value="Breadth First")
        opts = ["Breadth First", "Depth First", "Uniform Cost", "Best First (Greedy)", "A*"]
        ttk.OptionMenu(algo, self.var_algo, self.var_algo.get(), *opts).pack(side="left", padx=(8, 0))

        self.var_bidir = tk.BooleanVar(value=False)
        ttk.Checkbutton(algo, text="Bidirectional", variable=self.var_bidir).pack(side="left", padx=(16, 0))

        # Part II controls
        part2 = ttk.LabelFrame(self.right, text="Part II Settings", padding=10)
        part2.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        part2.columnconfigure(1, weight=1)

        self.var_r_val = tk.IntVar(value=1)
        self.var_g_val = tk.IntVar(value=2)
        self.var_b_val = tk.IntVar(value=3)
        self.var_sol_len = tk.StringVar(value="inf")

        ttk.Label(part2, text="R value").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(part2, from_=1, to=50, textvariable=self.var_r_val, width=8).grid(row=0, column=1, sticky="w")

        ttk.Label(part2, text="G value").grid(row=0, column=2, sticky="w", padx=(12, 0))
        ttk.Spinbox(part2, from_=1, to=50, textvariable=self.var_g_val, width=8).grid(row=0, column=3, sticky="w")

        ttk.Label(part2, text="B value").grid(row=0, column=4, sticky="w", padx=(12, 0))
        ttk.Spinbox(part2, from_=1, to=50, textvariable=self.var_b_val, width=8).grid(row=0, column=5, sticky="w")

        ttk.Label(part2, text="SolutionLength").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(part2, textvariable=self.var_sol_len, width=12).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(part2, text="('inf' or positive number)").grid(row=1, column=2, columnspan=4, sticky="w", pady=(8, 0))

        runbar = ttk.Frame(lf)
        runbar.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(runbar, text="RUN Part I", command=self.on_run_part1).pack(side="left")
        ttk.Button(runbar, text="RUN Part II", command=self.on_run_part2).pack(side="left", padx=(8, 0))

        ttk.Label(runbar, text="Zoom").pack(side="left", padx=(16, 4))
        self.var_zoom_right = tk.DoubleVar(value=1.0)
        ttk.Scale(runbar, from_=0.3, to=6.0, variable=self.var_zoom_right, command=self._on_zoom_right).pack(
            side="left", fill="x", expand=True, padx=(0, 8)
        )
        ttk.Button(runbar, text="FIT", command=self._fit_right).pack(side="left", padx=(0, 10))

        self.lbl_right_status = ttk.Label(runbar, text="Ready.")
        self.lbl_right_status.pack(side="left")

        pv = ttk.LabelFrame(self.right, text="Display (Fit + Zoom)", padding=6)
        pv.grid(row=3, column=0, sticky="nsew", pady=(10, 0))
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

    def on_run_part2(self):
        if self.current_maze_img is None:
            messagebox.showwarning("No maze", "Generate or load a maze first (left side).")
            return
        try:
            self.lbl_right_status.config(text="RUN Part II: searching (centerline + balls)...")
            self.update_idletasks()

            img = self.current_maze_img.convert("RGB")
            arr = np.asarray(img).copy()

            rgb_vals = [int(self.var_r_val.get()), int(self.var_g_val.get()), int(self.var_b_val.get())]
            sol_len = self.var_sol_len.get().strip()

            t0 = time.perf_counter()
            res_arr, sol_list, vis_list = searchLikeThereIsNoTomorrow(arr, RGBValues=rgb_vals, SolutionLength=sol_len)
            dt = time.perf_counter() - t0

            res_img = Image.fromarray(res_arr.astype(np.uint8), mode="RGB")

            z = self.view_right.get_zoom_factor()
            self.view_right.set_image(res_img, reset_zoom=False)
            self.view_right.set_zoom_factor(z)

            self.lbl_right_status.config(text=f"Part II done | solutionPts={len(sol_list)} visitedPts={len(vis_list)} time={dt:.3f}s")

        except Exception as e:
            messagebox.showerror("RUN Part II Error", str(e))
            self.lbl_right_status.config(text="Ready.")


def main():
    app = MazeHomeworkApp()
    app.mainloop()


if __name__ == "__main__":
    main()
