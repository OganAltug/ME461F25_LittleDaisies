from maze_generator import randomMaze
from gui import MazeApp

gen = randomMaze(25, 25, 20)
app = MazeApp(gen)
app.mainloop()
