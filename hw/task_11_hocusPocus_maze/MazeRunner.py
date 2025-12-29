import sys
import numpy as np
import random
import math
import heapq
import time
import multiprocessing
from collections import deque

# Try to import OpenCV for clustering/noise reduction
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QComboBox, 
                             QSpinBox, QTextEdit, QGraphicsView, QGraphicsScene, 
                             QGroupBox, QFileDialog, QLineEdit, QCheckBox)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor, QBrush

# ==========================================
# GLOBAL CONSTANTS
# ==========================================
PATH_COLOR = 255
WALL_COLOR = 0

DOOM_BG = "#2A2A2A"
DOOM_RED = "#AA0000"
DOOM_TEXT = "#CCCCCC"

# ==========================================
# PART 1: MAZE LOGIC (Generator & Solver)
# ==========================================

class MazeGenerator:
    @staticmethod
    def generate(difficulty, num_exits=1, ball_config=None):
        multiplier = difficulty * 10
        rows = int(multiplier) * 2 + 1
        cols = int(multiplier) * 2 + 1
        grid = np.zeros((rows, cols), dtype=np.uint8)

        center_r, center_c = rows // 2, cols // 2
        room_rad = max(2, difficulty // 2)
        for r in range(center_r - room_rad, center_r + room_rad + 1):
            for c in range(center_c - room_rad, center_c + room_rad + 1):
                if 0 < r < rows-1 and 0 < c < cols-1: grid[r, c] = 1

        stack = [(center_r - room_rad, center_c)]
        while stack:
            r, c = stack[-1]
            neighbors = []
            for dr, dc in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
                nr, nc = r + dr, c + dc
                if 0 < nr < rows - 1 and 0 < nc < cols - 1 and grid[nr, nc] == 0:
                    neighbors.append((nr, nc))
            if neighbors:
                nr, nc = random.choice(neighbors)
                grid[r + (nr - r)//2, c + (nc - c)//2] = 1
                grid[nr, nc] = 1
                stack.append((nr, nc))
            else: stack.pop()

        exits_created = 0; attempts = 0
        while exits_created < num_exits and attempts < 1000:
            attempts += 1
            side = random.choice(['top', 'bottom', 'left', 'right'])
            if side == 'top': r, c, dr, dc = 0, random.randint(1, cols-2), 1, 0
            elif side == 'bottom': r, c, dr, dc = rows-1, random.randint(1, cols-2), -1, 0
            elif side == 'left': r, c, dr, dc = random.randint(1, rows-2), 0, 0, 1
            elif side == 'right': r, c, dr, dc = random.randint(1, rows-2), cols-1, 0, -1
            if grid[r, c] == 1: continue
            drill_r, drill_c = r, c; tunnel = []; found = False
            for _ in range(min(rows, cols)//3):
                tunnel.append((drill_r, drill_c))
                for nr, nc in [(drill_r+1, drill_c), (drill_r-1, drill_c), (drill_r, drill_c+1), (drill_r, drill_c-1)]:
                    if 0 <= nr < rows and 0 <= nc < cols and grid[nr, nc] == 1 and (nr, nc) not in tunnel:
                        found = True; break
                if found: break
                drill_r += dr; drill_c += dc
                if not (0 <= drill_r < rows and 0 <= drill_c < cols): break
            if found:
                for tr, tc in tunnel: grid[tr, tc] = 1
                exits_created += 1

        balls = []
        if ball_config:
            num_balls = random.randint(ball_config['min'], ball_config['max'])
            candidates = []
            for r in range(1, rows-1):
                for c in range(1, cols-1):
                    if grid[r, c] == 1 and math.hypot(r - center_r, c - center_c) > room_rad + 2:
                        candidates.append((r, c))
            if candidates:
                for br, bc in random.sample(candidates, min(num_balls, len(candidates))):
                    balls.append({'loc': (br, bc), 'color': random.choice([0, 1, 2])})

        image = np.zeros((rows, cols), dtype=np.uint8)
        image[grid == 1] = PATH_COLOR
        return image, balls


class MazeSolver:
    def __init__(self, maze_image, abort_func):
        self.image = maze_image
        self.rows, self.cols = maze_image.shape
        self.start_node = (self.rows // 2, self.cols // 2)
        self.exits = self._find_exits()
        self.check_abort = abort_func

    def _find_exits(self):
        exits = []
        for c in range(self.cols):
            if self.image[0, c] == PATH_COLOR: exits.append((0, c))
            if self.image[self.rows-1, c] == PATH_COLOR: exits.append((self.rows-1, c))
        for r in range(self.rows):
            if self.image[r, 0] == PATH_COLOR: exits.append((r, 0))
            if self.image[r, self.cols-1] == PATH_COLOR: exits.append((r, self.cols-1))
        return exits

    def _get_neighbors(self, node):
        r, c = node
        for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols and self.image[nr, nc] == PATH_COLOR:
                yield (nr, nc)

    # --- PART 1 ---
    def solve_part1(self, method, bidirectional=False):
        if bidirectional:
            return self._solve_bidirectional(method)
        else:
            return self._solve_unidirectional(method)

    def _solve_unidirectional(self, method):
        start = self.start_node
        queue, stack, pq = deque(), [], []
        
        if method == "BFS": queue.append(start)
        elif method == "DFS": stack.append(start)
        else: heapq.heappush(pq, (0, 0, start))

        came_from = {start: None}
        cost_so_far = {start: 0}
        visited_order = []
        visited_set = set()
        
        steps = 0; tie = 0
        def h(node):
            if not self.exits: return 0
            return min([math.hypot(node[0]-er, node[1]-ec) for er, ec in self.exits])

        while (queue or stack or pq):
            if steps % 500 == 0 and self.check_abort(): return None, None
            steps += 1

            if method == "BFS": curr = queue.popleft()
            elif method == "DFS": curr = stack.pop()
            else: _, _, curr = heapq.heappop(pq)

            if curr in visited_set: continue
            visited_set.add(curr)
            visited_order.append(curr)

            if curr[0] in [0, self.rows-1] or curr[1] in [0, self.cols-1]:
                return self._reconstruct(curr, came_from), visited_order

            for nxt in self._get_neighbors(curr):
                new_cost = cost_so_far.get(curr, 0) + 1
                if method in ["BFS", "DFS"]:
                    if nxt not in came_from:
                        came_from[nxt] = curr
                        if method == "BFS": queue.append(nxt)
                        else: stack.append(nxt)
                else:
                    if nxt not in cost_so_far or new_cost < cost_so_far.get(nxt, float('inf')):
                        cost_so_far[nxt] = new_cost
                        came_from[nxt] = curr
                        prio = new_cost
                        if method == "Greedy": prio = h(nxt)
                        elif method == "A*": prio += h(nxt)
                        tie += 1
                        heapq.heappush(pq, (prio, tie, nxt))
        return [], visited_order

    def _solve_bidirectional(self, method):
        f_start = self.start_node
        f_queue, f_stack, f_pq = deque(), [], []
        b_starts = self.exits
        b_queue, b_stack, b_pq = deque(), [], []
        
        if method == "BFS":
            f_queue.append(f_start); b_queue.extend(b_starts)
        elif method == "DFS":
            f_stack.append(f_start); b_stack.extend(b_starts)
        else:
            heapq.heappush(f_pq, (0, 0, f_start))
            for i, ex in enumerate(b_starts): heapq.heappush(b_pq, (0, i, ex))

        f_came_from = {f_start: None}; b_came_from = {ex: None for ex in b_starts}
        f_cost = {f_start: 0}; b_cost = {ex: 0 for ex in b_starts}
        visited_order = []; f_visited = set(); b_visited = set()
        steps = 0; f_tie = 0; b_tie = 0
        
        def f_h(node): 
            if not self.exits: return 0
            return min([math.hypot(node[0]-er, node[1]-ec) for er, ec in self.exits])
        def b_h(node): 
            return math.hypot(node[0]-f_start[0], node[1]-f_start[1])

        while (f_queue or f_stack or f_pq) and (b_queue or b_stack or b_pq):
            if steps % 500 == 0 and self.check_abort(): return None, None
            steps += 1

            # Forward
            curr_f = None
            if f_queue: curr_f = f_queue.popleft()
            elif f_stack: curr_f = f_stack.pop()
            elif f_pq: _, _, curr_f = heapq.heappop(f_pq)

            if curr_f:
                if curr_f in b_came_from: return self._reconstruct_bi(curr_f, f_came_from, b_came_from), visited_order
                if curr_f not in f_visited:
                    f_visited.add(curr_f); visited_order.append(curr_f)
                    for nxt in self._get_neighbors(curr_f):
                        new_c = f_cost.get(curr_f, 0) + 1
                        if method in ["BFS", "DFS"]:
                            if nxt not in f_came_from:
                                f_came_from[nxt] = curr_f
                                if method == "BFS": f_queue.append(nxt)
                                else: f_stack.append(nxt)
                        else:
                            if nxt not in f_cost or new_c < f_cost.get(nxt, float('inf')):
                                f_cost[nxt] = new_c; f_came_from[nxt] = curr_f
                                prio = new_c
                                if method == "Greedy": prio = f_h(nxt)
                                elif method == "A*": prio += f_h(nxt)
                                f_tie += 1; heapq.heappush(f_pq, (prio, f_tie, nxt))

            # Backward
            curr_b = None
            if b_queue: curr_b = b_queue.popleft()
            elif b_stack: curr_b = b_stack.pop()
            elif b_pq: _, _, curr_b = heapq.heappop(b_pq)

            if curr_b:
                if curr_b in f_came_from: return self._reconstruct_bi(curr_b, f_came_from, b_came_from), visited_order
                if curr_b not in b_visited:
                    b_visited.add(curr_b); visited_order.append(curr_b)
                    for nxt in self._get_neighbors(curr_b):
                        new_c = b_cost.get(curr_b, 0) + 1
                        if method in ["BFS", "DFS"]:
                            if nxt not in b_came_from:
                                b_came_from[nxt] = curr_b
                                if method == "BFS": b_queue.append(nxt)
                                else: b_stack.append(nxt)
                        else:
                            if nxt not in b_cost or new_c < b_cost.get(nxt, float('inf')):
                                b_cost[nxt] = new_c; b_came_from[nxt] = curr_b
                                prio = new_c
                                if method == "Greedy": prio = b_h(nxt)
                                elif method == "A*": prio += b_h(nxt)
                                b_tie += 1; heapq.heappush(b_pq, (prio, b_tie, nxt))
        return [], visited_order

    def _reconstruct(self, curr, came_from):
        path = []
        while curr: path.append(curr); curr = came_from[curr]
        path.reverse()
        return path

    def _reconstruct_bi(self, meet_node, f_came, b_came):
        path_start = []
        curr = meet_node
        while curr: path_start.append(curr); curr = f_came[curr]
        path_start.reverse()
        path_end = []
        curr = b_came[meet_node] 
        while curr: path_end.append(curr); curr = b_came[curr]
        return path_start + path_end

    # --- PART 2: CONSTRAINED TSP ---
    def solve_part2(self, balls, rgb_scores, limit_str):
        try: limit = float(limit_str)
        except: limit = float('inf')
        
        # 1. Identify POIs
        pois = [{'id': -1, 'loc': self.start_node, 'type': 'start', 'score': 0}]
        score_map = {0: rgb_scores[0], 1: rgb_scores[1], 2: rgb_scores[2]}
        for i, b in enumerate(balls): 
            pois.append({'id': i, 'loc': b['loc'], 'type': 'ball', 'score': score_map[b['color']]})
        for i, ex in enumerate(self.exits): 
            pois.append({'id': 1000+i, 'loc': ex, 'type': 'exit', 'score': 0})
        
        # 2. Build Adjacency Matrix (Graph) with PATHS
        adj = {}; sources = [p for p in pois if p['type'] in ['start', 'ball']]
        targets = [p['loc'] for p in pois]; visited_all = set()
        
        for src in sources:
            if self.check_abort(): return [], []
            dists, paths, v_set = self._dijkstra_scan(src['loc'], targets)
            visited_all.update(v_set)
            adj[src['id']] = {}
            for t in pois:
                if t['loc'] in dists and t['id'] != src['id']:
                    # Store (distance, list_of_pixels)
                    adj[src['id']][t['id']] = (dists[t['loc']], paths[t['loc']])
        
        # 3. Solve TSP with Unique Pixel Constraint
        best_path_ids = self._solve_tsp_dfs(pois, adj, limit)
        
        # 4. Reconstruct
        full_path = []
        if best_path_ids:
            for i in range(len(best_path_ids)-1):
                u, v = best_path_ids[i], best_path_ids[i+1]
                if u in adj and v in adj[u]:
                    _, seg = adj[u][v]
                    # Don't duplicate the join point
                    full_path.extend(seg[1:] if full_path else seg)
                    
        return full_path, list(visited_all)

    def _dijkstra_scan(self, start, targets):
        t_set = set(targets); pq = [(0, start)]
        dists = {start:0}; parents = {start:None}; vis = set()
        
        while pq:
            c, curr = heapq.heappop(pq)
            if curr in vis: continue
            vis.add(curr)
            
            # 8-direction movement
            moves = [((-1,0),1),((1,0),1),((0,-1),1),((0,1),1),
                     ((-1,-1),1.414),((-1,1),1.414),((1,-1),1.414),((1,1),1.414)]
                     
            for (dr, dc), move in moves:
                nr, nc = curr[0]+dr, curr[1]+dc
                if 0<=nr<self.rows and 0<=nc<self.cols and self.image[nr,nc]==PATH_COLOR:
                    ncost = c + move
                    if (nr,nc) not in dists or ncost < dists[(nr,nc)]:
                        dists[(nr,nc)]=ncost; parents[(nr,nc)]=curr
                        heapq.heappush(pq, (ncost,(nr,nc)))
                        
        paths = {}
        for t in t_set:
            if t in dists:
                p=[]; curr=t
                while curr: p.append(curr); curr=parents[curr]
                p.reverse()
                paths[t] = p
        return dists, paths, vis

    def _solve_tsp_dfs(self, pois, adj, limit):
        start_id = -1
        balls = [p['id'] for p in pois if p['type']=='ball']
        exits = [p['id'] for p in pois if p['type']=='exit']
        scores = {p['id']: p['score'] for p in pois}
        
        # Stack: (current_id, visited_poi_set, current_dist, current_score, path_ids, visited_pixels_set)
        # Note: visited_pixels_set tracks global pixel usage to prevent self-intersection
        stack = [(start_id, {start_id}, 0.0, 0, [start_id], set())]
        
        best_score = -1
        best_path = []
        
        while stack:
            curr, vis_pois, dist, score, path, vis_pixels = stack.pop()
            
            # Try to Exit
            for ex in exits:
                if ex in adj[curr]:
                    d_ex, p_pixels = adj[curr][ex]
                    
                    # Check Pixel Collision (excluding start point which is 'curr')
                    segment_pixels = set(p_pixels[1:])
                    if not segment_pixels.isdisjoint(vis_pixels):
                        continue # Path blocked by own tail
                        
                    tot_d = dist + d_ex
                    if tot_d <= limit:
                        if score > best_score:
                            best_score = score
                            best_path = path + [ex]
                        elif score == best_score:
                            # Prefer shorter path for same score
                            pass

            # Try to go to unvisited Balls
            # Sort candidates by distance (heuristic)
            cands = []
            for b in balls:
                if b not in vis_pois and b in adj[curr]:
                    d_ball, p_pixels = adj[curr][b]
                    cands.append((b, d_ball, p_pixels))
            
            cands.sort(key=lambda x: x[1], reverse=True) # Sort reverse because stack is LIFO
            
            for b, d_ball, p_pixels in cands:
                if dist + d_ball > limit: continue
                
                # 1. Check if exit is reachable from ball (heuristic pruning)
                d_any_ex = float('inf')
                for e in exits:
                    if e in adj[b]: d_any_ex = min(d_any_ex, adj[b][e][0])
                if dist + d_ball + d_any_ex > limit: continue
                
                # 2. STRICT PIXEL CONSTRAINT
                segment_pixels = set(p_pixels[1:])
                if not segment_pixels.isdisjoint(vis_pixels):
                    continue # This path crosses a previous path
                
                # 3. Add to stack
                nv_pois = vis_pois.copy(); nv_pois.add(b)
                nv_pixels = vis_pixels.union(segment_pixels)
                
                stack.append((b, nv_pois, dist+d_ball, score+scores[b], path+[b], nv_pixels))
                
        return best_path


# ==========================================
# PART 2: WORKER THREAD
# ==========================================

class SolverWorker(QThread):
    sig_log = pyqtSignal(str)
    sig_done = pyqtSignal(object, object)
    sig_aborted = pyqtSignal()

    def __init__(self, maze_image, config, balls):
        super().__init__()
        self.image = maze_image
        self.config = config
        self.balls = balls
        self.abort_flag = False
        self.solver = None

    def check_abort(self): return self.abort_flag
    def stop(self): self.abort_flag = True

    def run(self):
        self.solver = MazeSolver(self.image, self.check_abort)
        mode = self.config['mode']
        self.sig_log.emit(f"Worker Started: {mode}")
        start_time = time.time(); path = []; visited = []

        if mode == 'Part1':
            algo = self.config.get('algo', 'BFS')
            bidirectional = self.config.get('bidirectional', False)
            
            self.sig_log.emit(f"Algo: {algo} | BiDi: {bidirectional}")
            path, visited = self.solver.solve_part1(algo, bidirectional)
            
        elif mode == 'Part2':
            rgb = self.config.get('rgb', [1, 2, 3])
            limit = self.config.get('limit', 'inf')
            path, visited = self.solver.solve_part2(self.balls, rgb, limit)
        
        if self.abort_flag or path is None:
            self.sig_log.emit("Search Aborted.")
            self.sig_aborted.emit()
        else:
            dt = time.time() - start_time
            self.sig_log.emit(f"Done in {dt:.3f}s. Path Len: {len(path)}")
            self.sig_done.emit(path, visited)

# ==========================================
# PART 3: MAIN WINDOW
# ==========================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Maze Runner: Visual Fix Edition")
        self.resize(1300, 950)
        self.apply_styles()
        
        # State Data
        self.maze_image = None  # Binary (0/255) for logic
        self.loaded_pixmap = None # Original visual for display
        self.balls = [] 
        self.worker = None
        self.current_scale = 1.0
        
        central = QWidget(); self.setCentralWidget(central); self.layout_main = QHBoxLayout(central)
        self.setup_controls(); self.setup_view(); self.setup_info()

    def apply_styles(self):
        self.setStyleSheet(f"""
            QMainWindow {{ background-color: {DOOM_BG}; }}
            QLabel, QCheckBox {{ color: {DOOM_TEXT}; font-weight: bold; font-family: Segoe UI; }}
            QGroupBox {{ color: #FF8800; border: 1px solid {DOOM_RED}; margin-top: 10px; font-weight: bold; }}
            QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; }}
            QPushButton {{ background-color: {DOOM_RED}; color: white; border: 1px solid #550000; padding: 6px; }}
            QPushButton:hover {{ background-color: #FF2222; border: 1px solid white; }}
            QPushButton:disabled {{ background-color: #440000; color: #888; }}
            QComboBox, QSpinBox, QLineEdit {{ background-color: #111; color: white; border: 1px solid #444; padding: 4px; }}
            QTextEdit {{ background-color: black; color: #00FF00; font-family: Consolas; }}
        """)

    def setup_controls(self):
        panel = QGroupBox("CONTROL DECK"); panel.setFixedWidth(340); layout = QVBoxLayout(); panel.setLayout(layout)
        
        layout.addWidget(QLabel("--- MAZE CONFIG ---"))
        h_gen = QHBoxLayout()
        self.spin_diff = QSpinBox(); self.spin_diff.setRange(1, 10); self.spin_diff.setValue(2); self.spin_diff.setPrefix("Diff: ")
        self.spin_exits = QSpinBox(); self.spin_exits.setRange(1, 5); self.spin_exits.setValue(1); self.spin_exits.setPrefix("Exits: ")
        h_gen.addWidget(self.spin_diff); h_gen.addWidget(self.spin_exits)
        layout.addLayout(h_gen); layout.addSpacing(10)

        p1_box = QGroupBox("PART 1: CLASSIC")
        p1_l = QVBoxLayout()
        btn_gen1 = QPushButton("GENERATE PART 1 (Clean)"); btn_gen1.clicked.connect(lambda: self.generate_maze(1))
        p1_l.addWidget(btn_gen1)
        p1_l.addWidget(QLabel("Algorithm:"))
        self.combo_algo = QComboBox(); self.combo_algo.addItems(["BFS", "DFS", "A*", "Greedy", "Uniform Cost"])
        p1_l.addWidget(self.combo_algo)
        
        self.check_bi = QCheckBox("Enable Bidirectional Search")
        p1_l.addWidget(self.check_bi)
        
        self.btn_run1 = QPushButton("► RUN PART 1 SOLVER"); self.btn_run1.clicked.connect(self.run_part1); self.btn_run1.setEnabled(False)
        p1_l.addWidget(self.btn_run1)
        p1_box.setLayout(p1_l); layout.addWidget(p1_box); layout.addSpacing(10)

        p2_box = QGroupBox("PART 2: COLLECTOR")
        p2_l = QVBoxLayout()
        h_balls = QHBoxLayout()
        self.spin_balls_min = QSpinBox(); self.spin_balls_min.setPrefix("Min: "); self.spin_balls_min.setValue(3)
        self.spin_balls_max = QSpinBox(); self.spin_balls_max.setPrefix("Max: "); self.spin_balls_max.setValue(6)
        h_balls.addWidget(self.spin_balls_min); h_balls.addWidget(self.spin_balls_max)
        p2_l.addLayout(h_balls)
        btn_gen2 = QPushButton("GENERATE PART 2 (With Balls)"); btn_gen2.clicked.connect(lambda: self.generate_maze(2))
        p2_l.addWidget(btn_gen2); p2_l.addSpacing(10)
        p2_l.addWidget(QLabel("RGB Scores:")); h_rgb = QHBoxLayout()
        self.spin_r = QSpinBox(); self.spin_r.setPrefix("R: "); self.spin_r.setValue(1)
        self.spin_g = QSpinBox(); self.spin_g.setPrefix("G: "); self.spin_g.setValue(2)
        self.spin_b = QSpinBox(); self.spin_b.setPrefix("B: "); self.spin_b.setValue(3)
        h_rgb.addWidget(self.spin_r); h_rgb.addWidget(self.spin_g); h_rgb.addWidget(self.spin_b)
        p2_l.addLayout(h_rgb)
        h_lim = QHBoxLayout(); h_lim.addWidget(QLabel("Limit:"))
        self.txt_limit = QLineEdit("inf"); self.txt_limit.setPlaceholderText("Length (inf/500)")
        h_lim.addWidget(self.txt_limit); p2_l.addLayout(h_lim)
        self.btn_run2 = QPushButton("► RUN PART 2"); self.btn_run2.clicked.connect(self.run_part2); self.btn_run2.setEnabled(False)
        p2_l.addWidget(self.btn_run2)
        p2_box.setLayout(p2_l); layout.addWidget(p2_box); layout.addSpacing(15)

        self.btn_stop = QPushButton("■ EMERGENCY STOP"); self.btn_stop.setStyleSheet("background-color: #FF5500; color: black; font-weight: bold;")
        self.btn_stop.clicked.connect(self.terminate_search); self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop); layout.addStretch()

        # --- FILE IO & PREPROCESSING ---
        f_box = QGroupBox("FILE I/O")
        f_l = QVBoxLayout()
        
        # Noise Reduction Checkbox
        self.check_noise = QCheckBox("Denoise (Median Blur)")
        self.check_noise.setToolTip("Useful for JPEGs. Requires OpenCV.")
        if not OPENCV_AVAILABLE:
            self.check_noise.setEnabled(False)
            self.check_noise.setText("Denoise (No OpenCV)")
        f_l.addWidget(self.check_noise)

        h_files = QHBoxLayout()
        btn_save = QPushButton("Save Img"); btn_save.clicked.connect(self.save_maze)
        btn_load = QPushButton("Load Img"); btn_load.clicked.connect(self.load_maze)
        h_files.addWidget(btn_save); h_files.addWidget(btn_load)
        f_l.addLayout(h_files)
        
        # --- NEW: FIT BUTTON ---
        btn_fit = QPushButton("⤢ FIT VIEW"); btn_fit.clicked.connect(self.fit_view_to_screen)
        f_l.addWidget(btn_fit)
        
        f_box.setLayout(f_l)
        layout.addWidget(f_box)
        
        self.layout_main.addWidget(panel)

    def setup_view(self):
        self.scene = QGraphicsScene(); self.view = QGraphicsView(self.scene)
        self.view.setBackgroundBrush(QBrush(QColor("#111"))); self.view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.layout_main.addWidget(self.view, stretch=1)

    def setup_info(self):
        panel = QWidget(); panel.setFixedWidth(250); l = QVBoxLayout()
        l.addWidget(QLabel("MISSION LOGS")); self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        l.addWidget(self.log_box); panel.setLayout(l); self.layout_main.addWidget(panel)
        
    def fit_view_to_screen(self):
        """ Scales the current scene content to fit strictly within the view """
        if self.scene.itemsBoundingRect().width() > 0:
            self.view.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self.log("View fitted to screen.")

    def generate_maze(self, mode):
        self.log(f"Generating Mode {mode}..."); diff = self.spin_diff.value(); exits = self.spin_exits.value()
        ball_conf = {'min': self.spin_balls_min.value(), 'max': self.spin_balls_max.value()} if mode == 2 else None
        
        # Reset Loaded State
        self.loaded_pixmap = None
        
        self.maze_image, self.balls = MazeGenerator.generate(diff, exits, ball_conf)
        self.display_maze()
        self.btn_run1.setEnabled(True); self.btn_run2.setEnabled(len(self.balls)>0)
        self.log(f"Generated. Balls: {len(self.balls)}")

    def display_maze(self):
        # 1. DISPLAY LOGIC
        self.scene.clear()
        
        if self.loaded_pixmap:
            # Case A: Loaded Image -> Show exact original
            w, h = self.loaded_pixmap.width(), self.loaded_pixmap.height()
            self.scene.addPixmap(self.loaded_pixmap)
            self.scene.setSceneRect(0, 0, w, h)
            self.current_scale = 1.0 # Assume 1:1 for now, view handles zoom
            
            # NOTE: We do NOT draw balls here for loaded images because 
            # they are already in the pixel data of self.loaded_pixmap.
            
        elif self.maze_image is not None:
            # Case B: Generated Maze -> Construct visual from binary
            h, w = self.maze_image.shape
            qimg = QImage(self.maze_image.data, w, h, w, QImage.Format.Format_Grayscale8)
            scale = max(1, 800 // max(w, h))
            self.current_scale = scale
            
            qpix = QPixmap.fromImage(qimg).scaled(w*scale, h*scale, Qt.AspectRatioMode.KeepAspectRatio)
            self.scene.addPixmap(qpix)
            self.scene.setSceneRect(0, 0, w*scale, h*scale)
            
            # Draw Balls Overlay (Since they are not in the binary image)
            if self.balls:
                ball_colors = {0: Qt.GlobalColor.red, 1: Qt.GlobalColor.green, 2: Qt.GlobalColor.blue}
                for b in self.balls:
                    r, c = b['loc']
                    x, y = c * scale, r * scale
                    rad = scale / 1.5
                    self.scene.addEllipse(x + scale/2 - rad, y + scale/2 - rad, rad*2, rad*2, 
                                        QPen(Qt.GlobalColor.black), QBrush(ball_colors[b['color']]))

    def run_part1(self):
        if self.maze_image is None: return
        self.display_maze(); self.set_buttons_active(False)
        config = {'mode': 'Part1', 'algo': self.combo_algo.currentText(), 'bidirectional': self.check_bi.isChecked()}
        self.start_worker(config)

    def run_part2(self):
        if self.maze_image is None: return
        self.display_maze(); self.set_buttons_active(False)
        config = {'mode': 'Part2', 'rgb': [self.spin_r.value(), self.spin_g.value(), self.spin_b.value()], 'limit': self.txt_limit.text()}
        self.start_worker(config)

    def start_worker(self, config):
        self.worker = SolverWorker(self.maze_image, config, self.balls)
        self.worker.sig_log.connect(self.log); self.worker.sig_done.connect(self.on_done); self.worker.sig_aborted.connect(self.on_aborted)
        self.worker.start()

    def terminate_search(self):
        if self.worker: self.log("Stopping..."); self.worker.stop()

    @pyqtSlot(object, object)
    def on_done(self, path, visited):
        self.draw_results(path, visited); self.cleanup_worker(); self.log("Ready.")
    
    @pyqtSlot()
    def on_aborted(self):
        self.cleanup_worker(); self.log("Aborted.")

    def cleanup_worker(self):
        if self.worker: self.worker.quit(); self.worker.wait(); self.worker = None
        self.set_buttons_active(True)

    def set_buttons_active(self, active):
        self.btn_run1.setEnabled(active); self.btn_run2.setEnabled(active and len(self.balls)>0); self.btn_stop.setEnabled(not active)

    def draw_results(self, path, visited):
        # Determine scale based on whether it's loaded (scale=1) or generated (scale=calc)
        scale = 1.0 if self.loaded_pixmap else self.current_scale
        
        h, w = self.maze_image.shape
        layer = QPixmap(w*int(scale), h*int(scale))
        layer.fill(Qt.GlobalColor.transparent)
        p = QPainter(layer)
        
        # 1. Draw Visited Nodes (Yellow Transparency)
        if visited:
            p.setBrush(QColor(255, 255, 0, 100)) # Yellow transparent
            p.setPen(Qt.PenStyle.NoPen)
            for r, c in visited:
                p.drawRect(int(c*scale), int(r*scale), int(max(1, scale)), int(max(1, scale)))
        
        # 2. Draw Path (Purple Line)
        if path and len(path) > 1:
            pen = QPen(QColor(255, 0, 255))
            pen.setWidth(max(2, int(scale/2)))
            p.setPen(pen)
            
            # If scale is 1, draw point to point. If scale > 1, draw center to center
            offset = scale / 2 if scale > 1 else 0
            
            points = [QPoint(int(c*scale + offset), int(r*scale + offset)) for r, c in path]
            p.drawPolyline(points)
            
        p.end()
        self.scene.addPixmap(layer)

    def save_maze(self):
        if self.maze_image is None: return
        f, _ = QFileDialog.getSaveFileName(self, "Save Maze", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if f: 
            # 1. Create Base Image (Grayscale)
            h, w = self.maze_image.shape
            base_img = QImage(self.maze_image.data, w, h, w, QImage.Format.Format_Grayscale8)
            
            # 2. Convert to RGB so we can draw colored balls
            rgb_img = base_img.convertToFormat(QImage.Format.Format_RGB888)
            
            # 3. Draw Balls at Exact Coordinates
            if self.balls:
                painter = QPainter(rgb_img)
                colors = {0: QColor(255, 0, 0), 1: QColor(0, 255, 0), 2: QColor(0, 0, 255)}
                
                for b in self.balls:
                    r, c = b['loc']
                    # Get color (default white if unknown)
                    color = colors.get(b['color'], QColor(255, 255, 255))
                    painter.setPen(color)
                    # Draw EXACT pixel (x=c, y=r)
                    painter.drawPoint(c, r)
                
                painter.end()

            # 4. Save
            rgb_img.save(f)
            self.log(f"Saved to {f}")

    def get_blob_centers(self, mask):
        """
        Uses connected components to find one center point per ball blob.
        Fallback to manual calculation if OpenCV is missing.
        """
        centers = []
        if OPENCV_AVAILABLE:
            # OpenCV Connected Components
            num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
            
            # Start from 1 (0 is background)
            for i in range(1, num_labels):
                area = stats[i, cv2.CC_STAT_AREA]
                if area < 3: continue  # Ignore tiny noise
                
                # Centroid is (x, y) -> (col, row)
                cx, cy = centroids[i]
                centers.append((int(cy), int(cx)))
        else:
            # Fallback: Simple distance check (Dedup pixels)
            points = np.argwhere(mask)
            valid_balls = []
            for r, c in points:
                too_close = False
                for vr, vc in valid_balls:
                    if math.hypot(r-vr, c-vc) < 8: # Min distance 8 pixels
                        too_close = True
                        break
                if not too_close:
                    valid_balls.append((r, c))
            centers = valid_balls
            
        return centers

    def load_maze(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load Maze", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if f:
            # 1. LOAD FOR VISUALS (High Quality)
            self.loaded_pixmap = QPixmap(f)
            
            # 2. LOAD FOR LOGIC (Numpy Analysis)
            # Load as RGB for ball detection
            qimg_color = QImage(f).convertToFormat(QImage.Format.Format_RGB888)
            if qimg_color.isNull(): return
            
            w, h = qimg_color.width(), qimg_color.height()
            ptr = qimg_color.bits()
            ptr.setsize(h * w * 3)
            rgb_arr = np.frombuffer(ptr, np.uint8).reshape((h, w, 3)).copy()

            self.balls = []
            
            # Detect Colors (Strict Thresholds)
            mask_r = (rgb_arr[:,:,0] > 180) & (rgb_arr[:,:,1] < 100) & (rgb_arr[:,:,2] < 100)
            mask_g = (rgb_arr[:,:,0] < 100) & (rgb_arr[:,:,1] > 180) & (rgb_arr[:,:,2] < 100)
            mask_b = (rgb_arr[:,:,0] < 100) & (rgb_arr[:,:,1] < 100) & (rgb_arr[:,:,2] > 180)
            
            # Cluster Blobs
            centers_r = self.get_blob_centers(mask_r)
            centers_g = self.get_blob_centers(mask_g)
            centers_b = self.get_blob_centers(mask_b)
            
            for r, c in centers_r: self.balls.append({'loc': (r, c), 'color': 0})
            for r, c in centers_g: self.balls.append({'loc': (r, c), 'color': 1})
            for r, c in centers_b: self.balls.append({'loc': (r, c), 'color': 2})

            # Process Maze Structure (Grayscale)
            qimg_gray = qimg_color.convertToFormat(QImage.Format.Format_Grayscale8)
            stride = qimg_gray.bytesPerLine()
            ptr_g = qimg_gray.bits()
            ptr_g.setsize(h * stride)
            gray_data = np.frombuffer(ptr_g, np.uint8).reshape((h, stride))
            gray_data = gray_data[:, :w].copy()

            if self.check_noise.isChecked() and OPENCV_AVAILABLE:
                gray_data = cv2.medianBlur(gray_data, 5)

            # Logic Maze (Binary)
            self.maze_image = np.where(gray_data > 128, 255, 0).astype(np.uint8)

            # Ensure Balls are Walkable in Logic
            for b in self.balls:
                br, bc = b['loc']
                for dr in range(-1, 2):
                    for dc in range(-1, 2):
                        nr, nc = br+dr, bc+dc
                        if 0 <= nr < h and 0 <= nc < w:
                            self.maze_image[nr, nc] = PATH_COLOR

            # UI Updates
            self.display_maze() # Will use self.loaded_pixmap
            self.btn_run1.setEnabled(True)
            self.btn_run2.setEnabled(len(self.balls) > 0)
            
            self.log(f"Loaded: {w}x{h} | Balls detected: {len(self.balls)}")

    @pyqtSlot(str)
    def log(self, m): self.log_box.append(f"> {m}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())