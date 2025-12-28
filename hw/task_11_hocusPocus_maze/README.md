# Part 1: Classic Maze Solver Implementation

## 1. The Solver Architecture

The Part 1 solver is designed to be **polymorphic**. Rather than implementing four distinct functions for Breadth-First Search (BFS), Depth-First Search (DFS), A*, and Greedy Best-First Search, the codebase utilizes a unified "Unidirectional" loop (`_solve_unidirectional`). The behavior of this loop transforms based entirely on the underlying data structure used to store the "frontier" (nodes waiting to be visited).

### The "Container" Strategy

The variable `method` determines which container holds the nodes. This structural change dictates the traversal pattern:

* **Breadth-First Search (BFS):** Utilizes a `deque` (Double Ended Queue). Nodes are added to the back and removed from the front (FIFO). In unweighted graphs like a perfect maze, this guarantees the shortest path.
* **Depth-First Search (DFS):** Utilizes a standard `list` acting as a Stack. Nodes are added to the back and removed from the back (LIFO). This results in a "snake-like" path that plunges deep into the maze quickly but often produces suboptimal, winding solutions.
* **A* (A-Star) & Greedy:** Utilizes a `heapq` (Priority Queue). Nodes are not stored by insertion order but by a "Priority Score" calculated via a cost function and heuristic.

### Heuristic Logic (The "Compass")

For **A*** and **Greedy** algorithms, the solver computes a heuristic `h(n)` to guide the search, reducing the search space significantly.

```python
def h(node):
    # Euclidean Distance to the nearest exit
    return min([math.hypot(node[0]-er, node[1]-ec) for er, ec in self.exits])

```

* **Greedy Best-First:** Determines priority solely by `h(n)` ("How close am I to the exit?"). It moves rapidly towards the goal but can easily get trapped in dead ends or find non-optimal paths.
* **A* (A-Star):** Determines priority by `cost_so_far + h(n)`. It balances the distance traveled ("short path so far") with the estimated remaining distance ("close to exit"). This guarantees the shortest path while being significantly faster than BFS.

---

## 2. Speed Optimizations

To ensure the GUI remains responsive even when solving large maze resolutions (high difficulty settings), several algorithmic and Python-specific optimizations were engineered into the solution.

### Optimization A: `set` vs `list` for Lookups (The O(1) Rule)

This is the critical optimization for pathfinding performance.

* **The Naive Approach:** Storing visited nodes in a list (`visited = []`). Checking `if node in visited` requires linearly scanning the list. As the number of visited nodes () grows, this operation approaches **O(N)**, making the total algorithm **O(N²)**.
* **The Optimized Approach:**
```python
visited_set = set()
# ...
if curr in visited_set: continue

```


Python `set` objects are implemented as hash tables. Checking for existence is **O(1)** (instant constant time), regardless of the maze size.

### Optimization B: `deque` for FIFO Queues

In the BFS implementation, `collections.deque` is used instead of a list.

* **The Problem:** Doing `list.pop(0)` in Python is an **O(N)** operation. Python must shift every remaining element in memory one step to the left to fill the gap left by the removed item.
* **The Fix:**
```python
queue = deque()
curr = queue.popleft() # O(1)

```


A `deque` acts as a doubly linked list. Popping from the left is an **O(1)** operation, preventing the solver from slowing down as the queue grows.

### Optimization C: Bidirectional Search (The "Pincer" Attack)

Standard search algorithms expand from the Start node until they hit the Exit. **Bidirectional Search** launches two simultaneous searches:

1. **Forward Frontier:** Starts at `(0,0)` expanding outward.
2. **Backward Frontier:** Starts at `(exit_r, exit_c)` expanding inward.

**Performance Gain:**
Mathematically, if a maze search area is a circle of radius , a unidirectional search covers Area . A bidirectional search covers two small circles of radius , totaling Area . Because the branching factor of a maze is exponential, this reduction often improves speed by **far more than 50%**.

The code detects the collision of these two frontiers effectively:

```python
# If the current node from Forward search exists in the Backward search's "came_from" dictionary...
if curr_f in b_came_from: 
    # ...WE MET! Stitch the two paths together immediately.
    return self._reconstruct_bi(curr_f, f_came_from, b_came_from), visited_order

```

### Optimization D: The `heapq` Module

For A*, the algorithm requires retrieving the node with the *lowest cost* at every step.

* **Naive Approach:** Sorting a list every time a node is added is slow (**O(N log N)**).
* **Optimized Approach:** Python's `heapq` maintains a binary heap invariant. Pushing a new node and popping the smallest item are both extremely efficient **O(log N)** operations.
```python
# Storing: (Priority, Tie-Breaker, Node)
heapq.heappush(pq, (prio, tie, nxt))

```


*Note:* The `tie` variable is used to prevent Python from attempting to compare two `(row, col)` tuples when priorities are identical, avoiding unnecessary comparison overhead.

---

## 3. Deep Dive: Python Data Structures Used

### 1. `heapq` (Binary Heap)

* **What it is:** `heapq` is not a distinct class but a module that provides functions to treat a standard Python `list` as a **Binary Heap**. Specifically, it implements a **Min-Heap**, where `heap[0]` is always the smallest element.
* **Time Complexity:**
* `heappush`: **O(log N)**
* `heappop`: **O(log N)**
* `min` access: **O(1)**


* **Under the Hood:** It organizes the list as a binary tree flattened into an array. For any index `k`, the children are at `2*k+1` and `2*k+2`. The parent is always smaller than the children. This structure allows efficient re-ordering without sorting the entire list.

### 2. `set` (Hash Table)

* **What it is:** An unordered collection of unique elements.
* **Time Complexity:**
* `add`: **O(1)** (Average case)
* `x in s` (Lookup): **O(1)** (Average case)


* **Under the Hood:** Python calculates the `hash()` of the key (e.g., the coordinate tuple `(5, 10)`). It uses this hash value to calculate an index in a sparse array (bucket). If `(5, 10)` is hashed to index 124, Python jumps directly to index 124 to check if it's there. This avoids scanning the whole collection.

### 3. `list` (Dynamic Array)

* **What it is:** A mutable, ordered sequence of items. It is implemented as a variable-length array (contiguous memory block) containing pointers to Python objects.
* **Time Complexity:**
* `append`: **O(1)** (Amortized - sometimes requires resizing)
* `pop()` (from end): **O(1)**
* `pop(0)` (from start): **O(N)**
* `insert(0, x)`: **O(N)**


* **Why use it for DFS (Stack)?** Since DFS only adds and removes from the *end* (Top of Stack), the `list` is highly efficient (**O(1)**).
* **Why NOT use it for BFS (Queue)?** Removing from the start forces Python to `memmove` every subsequent pointer in memory to close the gap, which is disastrously slow for large queues.

### 4. `deque` (Doubly Linked List of Blocks)

* **What it is:** Provided by `collections.deque`, this stands for "Double-Ended Queue". It is a generalization of stacks and queues.
* **Time Complexity:**
* `append` / `appendleft`: **O(1)**
* `pop` / `popleft`: **O(1)**


* **Under the Hood:** It is implemented as a **doubly linked list of fixed-length memory blocks** (arrays). Unlike a standard linked list (which stores one item per node), a `deque` stores a block of items per node.
* Because it is a linked list, removing the first block is just pointer manipulation (instant).
* Because it uses blocks, it has better CPU cache locality than a standard linked list.

Here is a detailed explanation of the **Part 2 Implementation (The Collector)** and the specific optimizations used to solve this complex problem.

---

# Part 2: The Collector (Constrained TSP)

## 1. The Strategy: "Abstract and Solve"

The Part 2 challenge is significantly harder than Part 1. It is a variation of the famous **Traveling Salesperson Problem (TSP)**, specifically the **Orienteering Problem**: *How do I maximize my score (collecting balls) within a strict "fuel" (distance) budget, without ever crossing my own path?*

Trying to solve this pixel-by-pixel (like Part 1) is impossible because the number of possibilities is infinite. Instead, the code breaks the problem into **two distinct stages**:

1. **The Geometer (Graph Construction):** Converts the messy pixel maze into a clean mathematical graph.
2. **The Strategist (Combinatorial Solver):** Uses logic to find the best sequence of moves on that graph.

---

## 2. Stage 1: Building the Graph (The "Roadmap")

Before the robot makes a single decision, we calculate the shortest path from **Every Point of Interest (POI)** to **Every Other POI**.

* **POIs:** The Start Point, every Ball, and every Exit.
* **The Algorithm:** **Dijkstra’s Algorithm**.
* *Why not A*?* A* is great for Point A to Point B. But here, if we are at the Start node, we need to know the distance to Ball 1, Ball 2, Ball 3, *and* the Exits simultaneously. Dijkstra scans the entire map once and returns the distance to *all* targets in one pass.



### The Adjacency Matrix

The result of this stage is a lookup table (dictionary) called `adj`:

```python
adj[Ball_1_ID][Ball_2_ID] = (Distance, [List_of_Pixels])

```

* **Optimization:** We don't just store the distance. We store the **exact list of pixels** (`[pixel_list]`) required to walk that path. This is crucial for the "No Crossing" constraint later.

---

## 3. Stage 2: Solving the TSP (The "Route Planner")

Now that we have a graph, we use a **Recursive Depth-First Search (DFS)** to try different sequences (e.g., Start → Red → Green → Exit).

### The "State" Machine

To simulate the robot's journey without actually moving it on screen, the recursive function passes a "State" packet that tracks everything:

1. **Current Location:** ID of the ball we are currently at.
2. **Current Score:** Total points gathered so far.
3. **Current Distance:** Total distance traveled.
4. **Global Pixel Set:** A `set` containing *every single pixel* visited so far in this specific history.

### The Logic Loop

For every step of the recursion, the solver does the following:

1. **Identify Candidates:** Look at all unvisited balls and exits.
2. **Pruning (The Filter):** Discard impossible moves immediately (see optimizations below).
3. **The Collision Check:**
* This is the most unique part of your requirement ("shouldn't pass through the same pixel more than a single time").
* The solver takes the `[List_of_Pixels]` for the proposed path (calculated in Stage 1).
* It checks if **ANY** of those pixels are already in the `Global Pixel Set`.
* If there is an overlap, the path is **blocked**. The robot cannot backtrack or cross its own tail.


4. **Recurse:** If the move is valid, add the score, update the pixel set, and dive deeper.

---

## 4. Speed Optimizations

Since TSP is an NP-Hard problem (computation time grows exponentially), brute-forcing it would freeze the computer. We engineered several "Pruning" optimizations to cut off dead-end branches early.

### Optimization A: The "Survival" Pruning (Lookahead)

The robot is not allowed to just grab a ball; it must grab a ball *and then be able to leave*.
Before moving to a ball, the code runs this check:

```python
dist_so_far + dist_to_ball + dist_from_ball_to_nearest_exit <= limit

```

If this equation is False, the solver **ignores** that ball.

* **Why it matters:** Without this, the robot might greedily grab a ball deep in a tunnel, use up all its "fuel" (distance limit), and realize too late that it cannot reach an exit. This saves millions of wasted calculation steps.

### Optimization B: Heuristic Sorting

When the robot looks at valid balls to visit next, it doesn't pick them randomly. It sorts them by **Distance (Closest First)**.

```python
candidates.sort(key=lambda x: x[dist], reverse=True) # Stack is LIFO, so reverse puts closest on top

```

* **Why it matters:** By checking nearby balls first, the solver is more likely to find a "good enough" solution quickly.

### Optimization C: `set.isdisjoint()`

For the pixel collision check, we use Python's optimized set operations.

* **Naive Way:** Loop through every pixel in the new path and check if it exists in the history list. This is slow.
* **Optimized Way:**
```python
if not new_path_pixels.isdisjoint(visited_pixels_set):
    continue # Path crosses history!

```


This function is implemented in C at the low level of Python and allows checking collision between thousands of pixels instantly.

### Optimization D: Pre-Calculation Cache

We never run pathfinding (Dijkstra/A*) during the recursion.

* All pathfinding is done **once** in Stage 1.
* During the complex recursive logic, we only look up integers and sets from the `adj` dictionary. This makes the recursive steps strictly combinatorial (math-only), involving no image processing or grid scanning.