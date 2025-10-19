import tkinter as tk
from tkinter import ttk
import random
import math

# --- Constants ---
COLORS = ["#FF6347", "#1E90FF", "#32CD32", "#FFD700"]
COLOR_NAMES = ["Red", "Blue", "Green", "Gold"]
OPTIONS = ["bounce", "Red", "Blue", "Green", "Gold", "Disappear A", "Disappear B", "Disappear Both"]

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
STATUS_HEIGHT = 30

# --- Polygon Class ---
class Polygon:
    def __init__(self, x, y, sides, radius, color, velocity):
        self.x = x
        self.y = y
        self.sides = sides
        self.radius = radius
        self.color = color
        self.dx, self.dy = velocity

    def draw(self, canvas, show_circle):
        coords = []
        for i in range(self.sides):
            angle = 2 * math.pi * i / self.sides
            xi = self.x + self.radius * math.cos(angle)
            yi = self.y + self.radius * math.sin(angle)
            coords.extend([xi, yi])
        canvas.create_polygon(coords, fill=self.color, outline="white", width=2, tags="shape")
        if show_circle:
            canvas.create_oval(
                self.x - self.radius, self.y - self.radius,
                self.x + self.radius, self.y + self.radius,
                outline="gray", dash=(4,4), width=1.5, tags="circle"
            )

    def area(self):
        return 0.5 * self.sides * (self.radius ** 2) * math.sin(2 * math.pi / self.sides)

    def collide(self, other, use_area_mass, rule_table, shapes, canvas_host=None):
        dx = other.x - self.x
        dy = other.y - self.y
        dist = math.hypot(dx, dy)
        if dist == 0: return
        if dist < self.radius + other.radius:
            # Apply color rule first
            outcome = rule_table.get((self.color, other.color), "bounce")
            if outcome in COLOR_NAMES:
                self.color = COLORS[COLOR_NAMES.index(outcome)]
            elif outcome == "Disappear A":
                if self in shapes:
                    shapes.remove(self)
                    if canvas_host:
                        canvas_host.show_message("“Once you start down the AI path, forever will it dominate your destiny. Consume you, it will.” — Yoda", self.x, self.y)
                return
            elif outcome == "Disappear B":
                if other in shapes:
                    shapes.remove(other)
                    if canvas_host:
                        canvas_host.show_message("ah bu acidi", other.x, other.y)
                return
            elif outcome == "Disappear Both":
                if self in shapes:
                    shapes.remove(self)
                    if canvas_host:
                        canvas_host.show_message("“Once you start down the AI path, forever will it dominate your destiny. Consume you, it will.” — Yoda", self.x, self.y)
                if other in shapes:
                    shapes.remove(other)
                    if canvas_host:
                        canvas_host.show_message("iste buna kaza derim", other.x, other.y)
                return
            # Elastic collision physics
            nx = dx / dist
            ny = dy / dist
            dvx = self.dx - other.dx
            dvy = self.dy - other.dy
            m1 = self.area() if use_area_mass else 1
            m2 = other.area() if use_area_mass else 1
            p = 2 * (dvx*nx + dvy*ny) / (m1 + m2)
            self.dx -= p * m2 * nx
            self.dy -= p * m2 * ny
            other.dx += p * m1 * nx
            other.dy += p * m1 * ny
            # Slight separation
            overlap = 0.5 * (self.radius + other.radius - dist + 1)
            self.x -= overlap * nx
            self.y -= overlap * ny
            other.x += overlap * nx
            other.y += overlap * ny

# --- Specific Shape Classes ---
class Triangle(Polygon):
    def __init__(self, x, y, velocity):
        super().__init__(x, y, 3, 40, "#FF6347", velocity)
    def move(self, width, height):
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 - self.radius: self.x = width + self.radius
        elif self.x > width + self.radius: self.x = 0 - self.radius
        if self.y < STATUS_HEIGHT - self.radius: self.y = height + self.radius
        elif self.y > height + self.radius: self.y = STATUS_HEIGHT - self.radius

class Pentagon(Polygon):
    def __init__(self, x, y, velocity):
        super().__init__(x, y, 5, 38, "#32CD32", velocity)
    def move(self, width, height):
        self.x += self.dx
        self.y += self.dy
        if self.x < 0 - self.radius: self.x = width + self.radius
        elif self.x > width + self.radius: self.x = 0 - self.radius
        if self.y < STATUS_HEIGHT - self.radius: self.y = height + self.radius
        elif self.y > height + self.radius: self.y = STATUS_HEIGHT - self.radius

class Square(Polygon):
    def __init__(self, x, y, velocity):
        super().__init__(x, y, 4, 35, "#1E90FF", velocity)
    def move(self, width, height):
        self.x += self.dx
        self.y += self.dy
        min_y = STATUS_HEIGHT + self.radius
        max_y = height - self.radius
        min_x = self.radius
        max_x = width - self.radius
        if self.x < min_x: self.x = min_x; self.dx *= -1
        elif self.x > max_x: self.x = max_x; self.dx *= -1
        if self.y < min_y: self.y = min_y; self.dy *= -1
        elif self.y > max_y: self.y = max_y; self.dy *= -1

class Hexagon(Polygon):
    def __init__(self, x, y, velocity):
        super().__init__(x, y, 6, 45, "#FFD700", velocity)
    def move(self, width, height):
        self.x += self.dx
        self.y += self.dy
        min_y = STATUS_HEIGHT + self.radius
        max_y = height - self.radius
        min_x = self.radius
        max_x = width - self.radius
        if self.x < min_x: self.x = min_x; self.dx *= -1
        elif self.x > max_x: self.x = max_x; self.dx *= -1
        if self.y < min_y: self.y = min_y; self.dy *= -1
        elif self.y > max_y: self.y = max_y; self.dy *= -1

# --- Simulation Host ---
class CanvasHost:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.root = tk.Tk()
        self.root.title("Polygon Physics + Rule Editor")
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg="#1a202c")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.side_frame = tk.Frame(self.root, bg="#1a202c")
        self.side_frame.pack(side="right", fill="y")

        self.show_circles = False
        self.use_area_mass = False
        self.speed_fps = 50
        self.speed_delay_ms = int(1000/self.speed_fps)
        self.canvas.bind("<Button-1>", self.toggle_circles)
        self.root.bind("m", self.toggle_mass_mode)
        self.root.bind("b", lambda e: self.spawn_polygon("blue"))
        self.root.bind("g", lambda e: self.spawn_polygon("green"))
        self.root.bind("r", lambda e: self.spawn_polygon("red"))
        self.root.bind("y", lambda e: self.spawn_polygon("gold"))
        self.root.bind("q", lambda e: self.quit_game())

        self.velocities = self._generate_velocities(4)
        self.shapes = [
            Triangle(random.randint(50, width-50), random.randint(STATUS_HEIGHT+50,height-50), self.velocities[0]),
            Square(random.randint(50, width-50), random.randint(STATUS_HEIGHT+50,height-50), self.velocities[1]),
            Pentagon(random.randint(50, width-50), random.randint(STATUS_HEIGHT+50,height-50), self.velocities[2]),
            Hexagon(random.randint(50, width-50), random.randint(STATUS_HEIGHT+50,height-50), self.velocities[3])
        ]
        self.rule_table = {(c1, c2): "bounce" for c1 in COLORS for c2 in COLORS}
        self.messages = []

        self.create_rule_editor(self.side_frame)
        self.create_fps_slider(self.side_frame)

    def _generate_velocities(self, n):
        velocities = []
        for i in range(n):
            angle = 2*math.pi*i/n + random.uniform(-0.3,0.3)
            speed = random.uniform(3,6)
            dx = math.cos(angle)*speed
            dy = math.sin(angle)*speed
            velocities.append((dx,dy))
        return velocities

    def toggle_circles(self, event=None):
        self.show_circles = not self.show_circles

    def toggle_mass_mode(self, event=None):
        self.use_area_mass = not self.use_area_mass

    def quit_game(self):
        self.root.destroy()

    def spawn_polygon(self, color_name):
        shape_class = {"red": Triangle,"blue": Square,"green": Pentagon,"gold": Hexagon}[color_name]
        for _ in range(100):
            x = random.randint(50, self.width-50)
            y = random.randint(STATUS_HEIGHT+50, self.height-50)
            if all(math.hypot(x-s.x, y-s.y) > s.radius+40 for s in self.shapes):
                angle = random.uniform(0,2*math.pi)
                speed = random.uniform(3,6)
                dx = math.cos(angle)*speed
                dy = math.sin(angle)*speed
                self.shapes.append(shape_class(x,y,(dx,dy)))
                break

    def show_message(self, text, x, y):
        self.messages.append((text, x, y))

    def create_rule_editor(self, parent):
        tk.Label(parent, text="Collision Rules", bg="#1a202c", fg="white", font=("Arial",14,"bold")).grid(row=0,column=0,columnspan=5,pady=5)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dark.TCombobox",
                        fieldbackground="#2a2a2a",
                        background="#2a2a2a",
                        foreground="white",
                        arrowcolor="white",
                        font=("Arial",10))
        style.map("Dark.TCombobox",
                  fieldbackground=[('readonly','#2a2a2a')],
                  background=[('active','#3a3a3a')])

        self.combo_boxes = {}
        # Header row
        for j, cname in enumerate(COLOR_NAMES):
            tk.Label(parent,text=cname,bg="#1a202c",fg="white",font=("Arial",10,"bold")).grid(row=1,column=j+1,padx=3,pady=3)
        # Rows
        for i, c1 in enumerate(COLORS):
            tk.Label(parent,text=COLOR_NAMES[i],bg="#1a202c",fg="white",font=("Arial",10,"bold")).grid(row=i+2,column=0,padx=3,pady=3)
            for j, c2 in enumerate(COLORS):
                cb = ttk.Combobox(parent, values=OPTIONS, width=14, style="Dark.TCombobox", font=("Arial",10))
                cb.set("bounce")
                cb.grid(row=i+2,column=j+1,padx=2,pady=2)
                cb.bind("<<ComboboxSelected>>", lambda e,a=c1,b=c2,cb=cb: self.update_rule(a,b,cb))
                self.combo_boxes[(c1,c2)] = cb

        tk.Button(parent, text="Randomize Rules", command=self.randomize_rules,
                  bg="#2a2a2a", fg="white", activebackground="#3a3a3a", font=("Arial",12,"bold")).grid(
                  row=len(COLORS)+3, column=0, columnspan=len(COLORS)+1, pady=10, sticky="ew")

    def randomize_rules(self):
        for c1 in COLORS:
            for c2 in COLORS:
                rule = random.choice(OPTIONS)
                self.rule_table[(c1,c2)] = rule
                self.combo_boxes[(c1,c2)].set(rule)

    def update_rule(self,color1,color2,combobox):
        self.rule_table[(color1,color2)] = combobox.get()

    def create_fps_slider(self,parent):
        # tk.Label(parent, text="Game Speed (FPS)", bg="#1a202c", fg="white").grid(row=7,column=0,columnspan=5,pady=10)
        self.fps_slider = tk.Scale(parent, from_=10, to=120, orient="horizontal",
                                   command=self.update_fps, bg="#1a202c", fg="white", troughcolor="#000000",
                                   highlightbackground="#1a202c", width=15, length=250)
        self.fps_slider.set(self.speed_fps)
        self.fps_slider.grid(row=8,column=0,columnspan=5,pady=5)
        self.fps_label = tk.Label(parent, text=f"FPS: {self.speed_fps}", bg="#1a202c", fg="white")
        self.fps_label.grid(row=9,column=0,columnspan=5,pady=5)

    def update_fps(self, val):
        self.speed_fps = int(val)
        self.speed_delay_ms = int(1000/self.speed_fps)
        self.fps_label.config(text=f"FPS: {self.speed_fps}")

    def update(self):
        self.canvas.delete("shape")
        self.canvas.delete("circle")
        # Draw disappearance messages first
        for msg, x, y in self.messages:
            self.canvas.create_text(x, y, text=msg, fill="white", font=("Arial",10), tags="message")
        self.messages = []

        for shape in self.shapes:
            shape.move(self.width,self.height)

        shapes_copy = self.shapes.copy()
        for i in range(len(shapes_copy)):
            for j in range(i+1,len(shapes_copy)):
                shapes_copy[i].collide(shapes_copy[j], self.use_area_mass, self.rule_table, self.shapes, canvas_host=self)

        for shape in self.shapes:
            shape.draw(self.canvas, self.show_circles)

        mode = "Area Mass" if self.use_area_mass else "Equal Mass"
        self.canvas.delete("status")
        self.canvas.create_text(10,10, anchor="nw", text=f"Mass Mode: {mode}", fill="white", font=("Arial",12,"bold"), tags="status")
        self.root.after(self.speed_delay_ms, self.update)

    def run(self):
        self.update()
        self.root.mainloop()

# --- Run Simulation ---
if __name__ == "__main__":
    host = CanvasHost(CANVAS_WIDTH, CANVAS_HEIGHT)
    host.run()
