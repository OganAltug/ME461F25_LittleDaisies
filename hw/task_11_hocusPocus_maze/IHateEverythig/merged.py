import sys
import numpy as np
import random
import math
import heapq
import time
import multiprocessing
from collections import deque

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

    # --- PART 1 ENTRY POINT ---
    def solve_part1(self, method, bidirectional=False):
        if bidirectional:
            return self._solve_bidirectional(method)
        else:
            return self._solve_unidirectional(method)

    # --- UNIDIRECTIONAL (Classic) ---
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
        
        # Heuristic for A* / Greedy
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

    # --- BIDIRECTIONAL (New!) ---
    def _solve_bidirectional(self, method):
        # Forward Search (Start -> Out)
        f_start = self.start_node
        f_queue, f_stack, f_pq = deque(), [], []
        
        # Backward Search (Exits -> In) - Initialize with ALL exits
        b_starts = self.exits
        b_queue, b_stack, b_pq = deque(), [], []
        
        # Initialize Frontiers
        if method == "BFS":
            f_queue.append(f_start); b_queue.extend(b_starts)
        elif method == "DFS":
            f_stack.append(f_start); b_stack.extend(b_starts)
        else: # A*, Greedy, UCS
            heapq.heappush(f_pq, (0, 0, f_start))
            for i, ex in enumerate(b_starts): heapq.heappush(b_pq, (0, i, ex))

        f_came_from = {f_start: None}; b_came_from = {ex: None for ex in b_starts}
        f_cost = {f_start: 0}; b_cost = {ex: 0 for ex in b_starts}
        
        visited_order = []
        f_visited = set(); b_visited = set()
        
        steps = 0; f_tie = 0; b_tie = 0
        
        # Heuristics
        def f_h(node): 
            if not self.exits: return 0
            return min([math.hypot(node[0]-er, node[1]-ec) for er, ec in self.exits])
        def b_h(node): 
            return math.hypot(node[0]-f_start[0], node[1]-f_start[1])

        while (f_queue or f_stack or f_pq) and (b_queue or b_stack or b_pq):
            if steps % 500 == 0 and self.check_abort(): return None, None
            steps += 1

            # --- EXPAND FORWARD ---
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

            # --- EXPAND BACKWARD ---
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
        # Path from Start -> Meet
        path_start = []
        curr = meet_node
        while curr: path_start.append(curr); curr = f_came[curr]
        path_start.reverse()
        
        # Path from Meet -> Exit
        path_end = []
        curr = b_came[meet_node] # Start from parent of meet
        while curr: path_end.append(curr); curr = b_came[curr]
        
        return path_start + path_end

    # --- PART 2 ---
    def solve_part2(self, balls, rgb_scores, limit_str):
        # (Same as previous logic for Part 2)
        try: limit = float(limit_str)
        except: limit = float('inf')
        pois = [{'id': -1, 'loc': self.start_node, 'type': 'start', 'score': 0}]
        score_map = {0: rgb_scores[0], 1: rgb_scores[1], 2: rgb_scores[2]}
        for i, b in enumerate(balls): pois.append({'id': i, 'loc': b['loc'], 'type': 'ball', 'score': score_map[b['color']]})
        for i, ex in enumerate(self.exits): pois.append({'id': 1000+i, 'loc': ex, 'type': 'exit', 'score': 0})
        
        adj = {}; sources = [p for p in pois if p['type'] in ['start', 'ball']]
        targets = [p['loc'] for p in pois]; visited_all = set()
        
        for src in sources:
            if self.check_abort(): return [], []
            dists, paths, v_set = self._dijkstra_scan(src['loc'], targets)
            visited_all.update(v_set); adj[src['id']] = {}
            for t in pois:
                if t['loc'] in dists: adj[src['id']][t['id']] = (dists[t['loc']], paths[t['loc']])
        
        best_path_ids = self._solve_tsp_dfs(pois, adj, limit)
        full_path = []
        if best_path_ids:
            for i in range(len(best_path_ids)-1):
                _, seg = adj[best_path_ids[i]][best_path_ids[i+1]]
                full_path.extend(seg[1:] if full_path else seg)
        return full_path, list(visited_all)

    def _dijkstra_scan(self, start, targets):
        t_set = set(targets); pq = [(0, start)]; dists = {start:0}; parents = {start:None}; vis = set()
        while pq:
            c, curr = heapq.heappop(pq)
            if curr in vis: continue
            vis.add(curr)
            for (dr, dc), move in [((-1,0),1),((1,0),1),((0,-1),1),((0,1),1),((-1,-1),1.414),((-1,1),1.414),((1,-1),1.414),((1,1),1.414)]:
                nr, nc = curr[0]+dr, curr[1]+dc
                if 0<=nr<self.rows and 0<=nc<self.cols and self.image[nr,nc]==PATH_COLOR:
                    ncost = c+move
                    if (nr,nc) not in dists or ncost < dists[(nr,nc)]:
                        dists[(nr,nc)]=ncost; parents[(nr,nc)]=curr; heapq.heappush(pq,(ncost,(nr,nc)))
        paths = {}
        for t in t_set:
            if t in dists:
                p=[]; curr=t
                while curr: p.append(curr); curr=parents[curr]
                p.reverse(); paths[t]=p
        return dists, paths, vis

    def _solve_tsp_dfs(self, pois, adj, limit):
        start=-1; balls=[p['id'] for p in pois if p['type']=='ball']; exits=[p['id'] for p in pois if p['type']=='exit']
        scores={p['id']:p['score'] for p in pois}
        stack=[(start, set(), 0.0, 0, [start])]
        best_score=-1; best_path=[]
        
        while stack:
            curr, vis, dist, score, path = stack.pop()
            for ex in exits:
                if ex in adj[curr]:
                    d_ex, _ = adj[curr][ex]; tot_d = dist+d_ex
                    if tot_d <= limit:
                        if score > best_score: best_score=score; best_path=path+[ex]
            
            cands = []
            for b in balls:
                if b not in vis and b in adj[curr]: cands.append((b, adj[curr][b][0]))
            cands.sort(key=lambda x: x[1])
            
            for b, d_ball in cands:
                if dist+d_ball > limit: continue
                d_any_ex = min([adj[b][e][0] for e in exits if e in adj[b]], default=float('inf'))
                if dist+d_ball+d_any_ex <= limit:
                    nv = vis.copy(); nv.add(b)
                    stack.append((b, nv, dist+d_ball, score+scores[b], path+[b]))
        return best_path


def searchLikeThereIsNoTomorrow(MazeImage, RGBValues=[1, 2, 3], SolutionLength='inf'):
    """
    A self-contained solver for the Maze Orienteering problem.
    """
    import math
    from collections import deque
    
    # --- 1. INPUT HANDLING ---
    original_img = None
    if isinstance(MazeImage, str):
        try:
            import cv2
            original_img = cv2.cvtColor(cv2.imread(MazeImage), cv2.COLOR_BGR2RGB)
        except:
            from PIL import Image
            original_img = np.array(Image.open(MazeImage))
    else:
        original_img = MazeImage.copy()

    res_image = original_img.copy()
    rows, cols, _ = original_img.shape

    start_node = (rows // 2, cols // 2)
    exits = []
    balls = [] 
    
    def is_color(pixel, target):
        return np.array_equal(pixel[:3], target)

    ball_id_counter = 0
    
    for r in range(rows):
        for c in range(cols):
            px = original_img[r, c]
            if (r == 0 or r == rows-1 or c == 0 or c == cols-1):
                if np.mean(px) > 128:
                    exits.append((r, c))
                continue

            if is_color(px, [255, 0, 0]):
                balls.append({'id': ball_id_counter, 'loc': (r, c), 'score': RGBValues[0]})
                ball_id_counter += 1
            elif is_color(px, [0, 255, 0]):
                balls.append({'id': ball_id_counter, 'loc': (r, c), 'score': RGBValues[1]})
                ball_id_counter += 1
            elif is_color(px, [0, 0, 255]):
                balls.append({'id': ball_id_counter, 'loc': (r, c), 'score': RGBValues[2]})
                ball_id_counter += 1

    pois = [{'id': -1, 'loc': start_node, 'type': 'start', 'score': 0}]
    for b in balls:
        b['type'] = 'ball'
        pois.append(b)
    for i, ex in enumerate(exits):
        pois.append({'id': 1000 + i, 'loc': ex, 'type': 'exit', 'score': 0})

    def run_dijkstra(src_loc, target_locs):
        targets_set = set(target_locs)
        pq = [(0, src_loc)] 
        dists = {src_loc: 0}
        parents = {src_loc: None}
        visited_set = set()
        targets_found = 0
        
        while pq:
            cost, curr = heapq.heappop(pq)
            if curr in visited_set: continue
            visited_set.add(curr)
            if curr in targets_set: targets_found += 1
            r, c = curr
            moves = [((-1,0), 1), ((1,0), 1), ((0,-1), 1), ((0,1), 1),
                     ((-1,-1), 1.414), ((-1,1), 1.414), ((1,-1), 1.414), ((1,1), 1.414)]
            for (dr, dc), move_cost in moves:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    pixel_val = original_img[nr, nc]
                    if np.mean(pixel_val) > 20: 
                        new_cost = cost + move_cost
                        if (nr, nc) not in dists or new_cost < dists[(nr, nc)]:
                            dists[(nr, nc)] = new_cost
                            parents[(nr, nc)] = curr
                            heapq.heappush(pq, (new_cost, (nr, nc)))
        
        found_paths = {}
        found_dists = {}
        for t in targets_set:
            if t in dists:
                found_dists[t] = dists[t]
                p = []
                curr = t
                while curr:
                    p.append(curr); curr = parents[curr]
                p.reverse()
                found_paths[t] = p
        return found_dists, found_paths, visited_set

    sources = [p for p in pois if p['type'] in ['start', 'ball']]
    all_locs = [p['loc'] for p in pois]
    adj = {}; all_visited_pixels = set()
    
    for src in sources:
        dists, paths, v_set = run_dijkstra(src['loc'], all_locs)
        all_visited_pixels.update(v_set)
        adj[src['id']] = {}
        for dest in pois:
            if dest['loc'] in dists and dest['id'] != src['id']:
                adj[src['id']][dest['id']] = (dists[dest['loc']], paths[dest['loc']])

    try: limit_val = float(SolutionLength)
    except: limit_val = float('inf')

    start_id = -1
    ball_ids = [p['id'] for p in pois if p['type'] == 'ball']
    exit_ids = [p['id'] for p in pois if p['type'] == 'exit']
    id_map = {p['id']: p for p in pois}
    
    stack = [(start_id, set(), 0.0, 0, [start_id])]
    best_score = -1; best_path_ids = []; min_dist_for_best = float('inf')
    
    min_exit_dists = {}
    for pid in [start_id] + ball_ids:
        if pid in adj:
            d = float('inf')
            for eid in exit_ids:
                if eid in adj[pid]:
                    d = min(d, adj[pid][eid][0])
            min_exit_dists[pid] = d

    while stack:
        curr, vis, dist, score, path = stack.pop()
        for eid in exit_ids:
            if eid in adj[curr]:
                d_exit, _ = adj[curr][eid]
                total_d = dist + d_exit
                if total_d <= limit_val:
                    if score > best_score:
                        best_score = score; best_path_ids = path + [eid]; min_dist_for_best = total_d
                    elif score == best_score:
                        if total_d < min_dist_for_best:
                            min_dist_for_best = total_d; best_path_ids = path + [eid]
        
        candidates = []
        for bid in ball_ids:
            if bid not in vis and bid in adj[curr]:
                d_ball, _ = adj[curr][bid]
                candidates.append((bid, d_ball))
        candidates.sort(key=lambda x: x[1])

        for bid, d_ball in candidates:
            if dist + d_ball > limit_val: continue
            d_escape = min_exit_dists.get(bid, float('inf'))
            if dist + d_ball + d_escape <= limit_val:
                new_vis = vis.copy(); new_vis.add(bid)
                new_score = score + id_map[bid]['score']
                stack.append((bid, new_vis, dist + d_ball, new_score, path + [bid]))

    solution_list = []
    if best_path_ids:
        solution_list.append(list(id_map[best_path_ids[0]]['loc']))
        for i in range(len(best_path_ids) - 1):
            u, v = best_path_ids[i], best_path_ids[i+1]
            if u in adj and v in adj[u]:
                _, pixels = adj[u][v]
                for px in pixels[1:]: solution_list.append(list(px))
    
    visited_list = [list(loc) for loc in all_visited_pixels]
    for r, c in visited_list:
        if np.mean(res_image[r,c]) > 20: res_image[r, c] = [255, 255, 0]
    purple = [255, 0, 255] 
    for r, c in solution_list: res_image[r, c] = purple

    return res_image, solution_list, visited_list

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
            # Check for bidirectional flag (default False)
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
        self.setWindowTitle("Maze Runner: DOOM Edition V_BiDi_Combined")
        self.resize(1300, 950)
        self.apply_styles()
        self.maze_image = None; self.balls = []; self.worker = None; self.current_scale = 1.0
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
        
        # --- NEW: Bidirectional Checkbox ---
        self.check_bi = QCheckBox("Enable Bidirectional Search")
        p1_l.addWidget(self.check_bi)
        # -----------------------------------
        
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
        h_files = QHBoxLayout()
        btn_save = QPushButton("Save Img"); btn_save.clicked.connect(self.save_maze)
        btn_load = QPushButton("Load Img"); btn_load.clicked.connect(self.load_maze)
        h_files.addWidget(btn_save); h_files.addWidget(btn_load)
        layout.addLayout(h_files)
        self.layout_main.addWidget(panel)

    def setup_view(self):
        self.scene = QGraphicsScene(); self.view = QGraphicsView(self.scene)
        self.view.setBackgroundBrush(QBrush(QColor("#111"))); self.view.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag); self.layout_main.addWidget(self.view, stretch=1)

    def setup_info(self):
        panel = QWidget(); panel.setFixedWidth(250); l = QVBoxLayout()
        l.addWidget(QLabel("SYSTEM LOGS")); self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        l.addWidget(self.log_box); panel.setLayout(l); self.layout_main.addWidget(panel)

    def generate_maze(self, mode):
        self.log(f"Generating Mode {mode}..."); diff = self.spin_diff.value(); exits = self.spin_exits.value()
        ball_conf = {'min': self.spin_balls_min.value(), 'max': self.spin_balls_max.value()} if mode == 2 else None
        self.maze_image, self.balls = MazeGenerator.generate(diff, exits, ball_conf)
        self.display_maze()
        self.btn_run1.setEnabled(True); self.btn_run2.setEnabled(len(self.balls)>0)
        self.log(f"Generated. Balls: {len(self.balls)}")

    def display_maze(self):
        if self.maze_image is None: return
        h, w = self.maze_image.shape; qimg = QImage(self.maze_image.data, w, h, w, QImage.Format.Format_Grayscale8)
        scale = max(1, 800 // max(w, h)); self.current_scale = scale
        qpix = QPixmap.fromImage(qimg).scaled(w*scale, h*scale, Qt.AspectRatioMode.KeepAspectRatio)
        self.scene.clear(); self.scene.addPixmap(qpix); self.scene.setSceneRect(0, 0, w*scale, h*scale)
        if self.balls:
            ball_colors = {0: Qt.GlobalColor.red, 1: Qt.GlobalColor.green, 2: Qt.GlobalColor.blue}
            for b in self.balls:
                r, c = b['loc']; x, y = c * scale, r * scale; rad = scale / 1.5
                self.scene.addEllipse(x + scale/2 - rad, y + scale/2 - rad, rad*2, rad*2, QPen(Qt.GlobalColor.black), QBrush(ball_colors[b['color']]))

    def run_part1(self):
        if self.maze_image is None: return
        self.display_maze(); self.set_buttons_active(False)
        # Pass Bidirectional Flag
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
        scale = self.current_scale; h, w = self.maze_image.shape
        layer = QPixmap(w*scale, h*scale); layer.fill(Qt.GlobalColor.transparent); p = QPainter(layer)
        if visited:
            p.setBrush(QColor(255, 255, 0, 100)); p.setPen(Qt.PenStyle.NoPen)
            for r, c in visited: p.drawRect(c*scale, r*scale, scale, scale)
        if path and len(path) > 1:
            pen = QPen(QColor(255, 0, 255)); pen.setWidth(max(2, int(scale/2))); p.setPen(pen)
            
            p.drawPolyline([QPoint(int(c*scale+scale/2), int(r*scale+scale/2)) for r, c in path])
        p.end(); self.scene.addPixmap(layer)

    def save_maze(self):
        if self.maze_image is None: return
        f, _ = QFileDialog.getSaveFileName(self, "Save", "", "PNG (*.png)")
        if f: QImage(self.maze_image.data, self.maze_image.shape[1], self.maze_image.shape[0], self.maze_image.shape[1], QImage.Format.Format_Grayscale8).save(f); self.log("Saved.")

    def load_maze(self):
        f, _ = QFileDialog.getOpenFileName(self, "Load", "", "Img (*.png *.jpg *.bmp)")
        if f:
            qimg = QImage(f).convertToFormat(QImage.Format.Format_Grayscale8)
            if qimg.isNull(): return
            w, h = qimg.width(), qimg.height(); stride = qimg.bytesPerLine()
            ptr = qimg.bits(); ptr.setsize(h*stride)
            arr = np.frombuffer(ptr, np.uint8).reshape((h, stride))
            self.maze_image = np.where(arr[:, :w] > 128, 255, 0).astype(np.uint8).copy()
            self.balls = []; self.display_maze(); self.btn_run1.setEnabled(True); self.btn_run2.setEnabled(False); self.log(f"Loaded: {w}x{h}")

    @pyqtSlot(str)
    def log(self, m): self.log_box.append(f"> {m}")

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())