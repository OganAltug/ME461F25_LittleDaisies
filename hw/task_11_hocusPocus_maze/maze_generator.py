import numpy as np
import cv2
import random

class randomMaze:
    def __init__(self, rows=25, columns=25, cell_size=20):
        self.rows = rows
        self.columns = columns
        self.cell_size = cell_size

        self.maze_height = rows * cell_size
        self.maze_width = columns * cell_size

        self.maze = np.ones((self.maze_height, self.maze_width), dtype=np.uint8) * 255
        #self.directions = [(0,1), (-1,0), (1,0), (0,-1)]

        # diagonal lines were wanted
        self.directions = [(0,1), (-1,0), (1,0), (0,-1),
                          (1,-1), (-1,-1)]

        self.visited = np.zeros((self.rows, self.columns), dtype=bool)

        for i in range(self.rows//2 - 3, self.rows//2 +4):
            for j in range(self.columns//2 - 3, self.columns//2 +4):
                self.visited[i][j] = True


    def diagonal_cross_block(self, x, y, dx, dy):
        if abs(dx) != 1 or abs(dy) != 1:
            return False
        #for diagonal movements, if a selected line is diagonal, then that block cannot be used.
        #   [0 , 1]
        #   [1 , 0], basicly it should draw a line  diagonally to the sight side. 
        # But, we should turn the flag and make it visited to the other points to not cross lines.
        mid1_x = x
        mid1_y = y + dy
        mid2_x = x + dx
        mid2_y = y
        return self.visited[mid1_x][mid1_y] and self.visited[mid2_x][mid2_y]

    def draw_line(self, x_step, y_step):
        self.visited[x_step][y_step] = True
        #randomly selected directions
        random.shuffle(self.directions)

        for dy, dx in self.directions:
            nx, ny = x_step + dx, y_step + dy
            if 0 <= nx < self.columns and 0 <= ny < self.rows:
                if not self.visited[nx][ny]:
                    if self.diagonal_cross_block(x_step, y_step, dx, dy):
                        continue
                    # we are not 
                    x1 = x_step * self.cell_size + self.cell_size // 2
                    y1 = y_step * self.cell_size + self.cell_size // 2
                    x2 = nx * self.cell_size + self.cell_size // 2
                    y2 = ny * self.cell_size + self.cell_size // 2

                    cv2.line(self.maze, (x1, y1), (x2, y2), 0, 2)
                    self.draw_line(nx, ny)

    def generate(self):
        start_r = random.randint(0, self.rows - 1)
        start_c = random.randint(0, self.columns - 1)
        self.draw_line(start_c, start_r)
        return self.maze

    def get_binary_maze(self):
        """Convert image maze to solver grid"""
        return (self.maze == 255).astype(np.uint8)
