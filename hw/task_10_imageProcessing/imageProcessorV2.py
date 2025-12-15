import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import random
import math
import os

# --- CONFIGURATION ---
BASE_SIZES = {
    1: 50,  # Large (Radius at base resolution)
    2: 35,  # Medium
    3: 20   # Small
}

# Standard Colors Database (Name -> BGR)
COLOR_DB = {
    'Red': (0, 0, 255),
    'Green': (0, 255, 0),
    'Blue': (255, 0, 0),
    'Cyan': (255, 255, 0),
    'Magenta': (255, 0, 255),
    'Yellow': (0, 255, 255),
    'Purple': (128, 0, 128),
    'Orange': (0, 165, 255),
    'Black': (0, 0, 0),
    'Gray': (128, 128, 128)
}

RESOLUTIONS = {
    "800x600 (Base)": (800, 600),
    "1024x768": (1024, 768),
    "1280x720 (HD)": (1280, 720),
    "1920x1080 (FHD)": (1920, 1080),
    "2560x1440 (2K)": (2560, 1440)
}

class ImageProcessingApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mechatronics Image Generator & Solver")
        
        # Maximize window
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.root.geometry(f"{int(screen_w*0.8)}x{int(screen_h*0.8)}")
        
        # Data Storage
        self.scene_data = [] # Stores metadata (x, y, shape, color, angle)
        self.img_noisy = None
        self.img_clean = None
        self.img_processed = None
        self.showing_clean = False
        
        # State Flags
        self.is_procedural = True # True if generated, False if uploaded
        self.is_jpeg_input = False # True if uploaded file was jpg
        
        # Variables
        self.res_var = tk.StringVar(value="800x600 (Base)")
        self.preview_size_var = tk.IntVar(value=800)
        self.jpeg_quality_var = tk.IntVar(value=95)
        
        self.noise_color_amt = tk.DoubleVar(value=0.0)
        self.noise_shape_amt = tk.DoubleVar(value=0.0)
        self.noise_color_type = tk.StringVar(value="Gaussian")
        self.noise_shape_type = tk.StringVar(value="Vertex Jitter")
        
        # Mappings
        self.shape_map_vars = {
            1: tk.StringVar(value="Star"),
            2: tk.StringVar(value="Rectangle"),
            3: tk.StringVar(value="Triangle")
        }
        
        self.color_map_vars = {
            1: tk.StringVar(value="Red"),
            2: tk.StringVar(value="Purple"),
            3: tk.StringVar(value="Cyan")
        }

        self.setup_gui()

    def setup_gui(self):
        control_frame = tk.Frame(self.root, bd=2, relief=tk.GROOVE, width=320)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        self.display_canvas = tk.Canvas(self.root, bg="#f0f0f0")
        self.display_canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.display_frame = tk.Frame(self.display_canvas, bg="#f0f0f0")
        self.display_canvas.create_window((0, 0), window=self.display_frame, anchor="nw")
        
        # --- CONTROLS ---
        tk.Label(control_frame, text="SETTINGS", font=("Arial", 10, "bold")).pack(pady=(10,5))
        
        # 1. Resolution & Zoom
        tk.Label(control_frame, text="Resolution (Gen Only):").pack(anchor="w", padx=5)
        ttk.Combobox(control_frame, textvariable=self.res_var, values=list(RESOLUTIONS.keys()), state="readonly").pack(fill=tk.X, padx=5)
        
        tk.Label(control_frame, text="Preview Zoom:", font=("Arial", 9)).pack(pady=(5, 0))
        tk.Scale(control_frame, variable=self.preview_size_var, from_=300, to=2000, 
                 orient=tk.HORIZONTAL, command=self.update_previews).pack(fill=tk.X, padx=5)

        # 2. Geometry Mapping
        tk.Label(control_frame, text="Shape ID Mapping:", font=("Arial", 9, "bold")).pack(pady=(15,2))
        shapes = ["Star", "Rectangle", "Triangle", "Circle"]
        for i in range(1, 4):
            f = tk.Frame(control_frame)
            f.pack(fill=tk.X, pady=1, padx=5)
            tk.Label(f, text=f"ID {i}:", width=4).pack(side=tk.LEFT)
            ttk.Combobox(f, textvariable=self.shape_map_vars[i], values=shapes, state="readonly").pack(side=tk.RIGHT, expand=True, fill=tk.X)

        # 3. Color Mapping
        tk.Label(control_frame, text="Color ID Mapping:", font=("Arial", 9, "bold")).pack(pady=(15,2))
        colors_list = sorted(list(COLOR_DB.keys()))
        for i in range(1, 4):
            f = tk.Frame(control_frame)
            f.pack(fill=tk.X, pady=1, padx=5)
            tk.Label(f, text=f"ID {i}:", width=4).pack(side=tk.LEFT)
            ttk.Combobox(f, textvariable=self.color_map_vars[i], values=colors_list, state="readonly").pack(side=tk.RIGHT, expand=True, fill=tk.X)

        # 4. Noise
        tk.Label(control_frame, text="Noise Settings:", font=("Arial", 9, "bold")).pack(pady=(15,2))
        
        tk.Label(control_frame, text="Color Noise (0-1):").pack(anchor="w", padx=5)
        tk.Scale(control_frame, variable=self.noise_color_amt, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5)
        ttk.Combobox(control_frame, textvariable=self.noise_color_type, values=["Gaussian", "Salt & Pepper"], state="readonly").pack(fill=tk.X, padx=5)

        tk.Label(control_frame, text="Shape Noise (Gen Only):").pack(anchor="w", padx=5, pady=(5,0))
        tk.Scale(control_frame, variable=self.noise_shape_amt, from_=0, to=1, resolution=0.1, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5)
        ttk.Combobox(control_frame, textvariable=self.noise_shape_type, values=["Vertex Jitter", "Distortion"], state="readonly").pack(fill=tk.X, padx=5)

        # 5. Actions
        tk.Label(control_frame, text="ACTIONS", font=("Arial", 10, "bold")).pack(pady=(20,5))
        
        # Generation / Upload
        tk.Button(control_frame, text="Generate New Scene", command=self.generate_new_scene, bg="#dddddd", height=1).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(control_frame, text="Upload Image (JPG/PNG)", command=self.upload_image, bg="#ffdddd", height=1).pack(fill=tk.X, padx=5, pady=2)
        
        # Processing
        tk.Button(control_frame, text="Apply Noise to Scene", command=self.apply_noise_to_current, bg="#e0e0e0", height=1).pack(fill=tk.X, padx=5, pady=2)
        
        self.btn_toggle = tk.Button(control_frame, text="Show Undistorted", command=self.toggle_clean_view, state="disabled")
        self.btn_toggle.pack(fill=tk.X, padx=5, pady=2)
        
        tk.Button(control_frame, text="Process (Solve)", command=self.solve_image, bg="#add8e6", height=2).pack(fill=tk.X, padx=5, pady=5)
        
        # Saving
        tk.Label(control_frame, text="Save Settings:", font=("Arial", 9, "bold")).pack(pady=(10,2))
        tk.Label(control_frame, text="JPEG Quality (0-100):").pack(anchor="w", padx=5)
        tk.Scale(control_frame, variable=self.jpeg_quality_var, from_=0, to=100, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5)
        
        tk.Button(control_frame, text="Save Distorted Image", command=lambda: self.save_single_image("distorted")).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(control_frame, text="Save Processed Image", command=lambda: self.save_single_image("processed")).pack(fill=tk.X, padx=5, pady=2)

        # Display
        self.panel_left = tk.Label(self.display_frame, text="[Original/Noisy Preview]", bg="#f0f0f0")
        self.panel_left.pack(side=tk.LEFT, padx=10, pady=10, anchor="n")
        self.panel_right = tk.Label(self.display_frame, text="[Processed Image Preview]", bg="#f0f0f0")
        self.panel_right.pack(side=tk.LEFT, padx=10, pady=10, anchor="n")
        
        self.display_frame.bind("<Configure>", lambda e: self.display_canvas.configure(scrollregion=self.display_canvas.bbox("all")))

    def update_previews(self, event=None):
        if self.showing_clean and self.img_clean is not None:
            self.display_image(self.img_clean, self.panel_left)
        elif self.img_noisy is not None:
            self.display_image(self.img_noisy, self.panel_left)
        if self.img_processed is not None:
            self.display_image(self.img_processed, self.panel_right)

    def upload_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png")])
        if not path:
            return
            
        # Check if input is JPEG
        ext = os.path.splitext(path)[1].lower()
        self.is_jpeg_input = (ext in ['.jpg', '.jpeg'])
        self.is_procedural = False
        
        # Load Image
        loaded_img = cv2.imread(path)
        if loaded_img is None:
            messagebox.showerror("Error", "Failed to load image.")
            return

        self.img_clean = loaded_img
        self.img_noisy = loaded_img.copy()
        self.img_processed = None
        self.scene_data = [] # Clear procedural data
        
        self.showing_clean = False
        self.btn_toggle.config(state="normal", text="Show Undistorted")
        self.display_image(self.img_noisy, self.panel_left)
        self.panel_right.config(image='', text="[Processed Image Preview]")
        
        messagebox.showinfo("Uploaded", f"Loaded: {os.path.basename(path)}\nMode: Pixel Noise Only (Shape noise disabled)")

    def generate_new_scene(self):
        """Generates locations, types, and colors. Saves them. Draws Clean Image."""
        self.is_procedural = True
        self.is_jpeg_input = False
        
        res_key = self.res_var.get()
        w, h = RESOLUTIONS[res_key]
        scale_factor = min(w / 800, h / 600)

        # Clear data
        self.scene_data = []
        self.img_clean = np.ones((h, w, 3), dtype=np.uint8) * 255
        
        # Grid placement
        objects_count = random.randint(10, 15)
        grid_rows, grid_cols = 4, 4
        cell_w, cell_h = w // grid_cols, h // grid_rows
        cells = [(c, r) for r in range(grid_rows) for c in range(grid_cols)]
        random.shuffle(cells)

        for i in range(min(objects_count, len(cells))):
            c, r = cells[i]
            cx = int((c + 0.5) * cell_w)
            cy = int((r + 0.5) * cell_h)
            
            jitter_x = int(cell_w * 0.25)
            jitter_y = int(cell_h * 0.25)
            cx += random.randint(-jitter_x, jitter_x)
            cy += random.randint(-jitter_y, jitter_y)

            shape_id = random.choice([1, 2, 3])
            size_id = random.choice([1, 2, 3])
            color_id = random.choice([1, 2, 3])
            
            shape_name = self.shape_map_vars[shape_id].get()
            radius = BASE_SIZES[size_id] * scale_factor
            
            color_name = self.color_map_vars[color_id].get()
            color_bgr = COLOR_DB[color_name]

            # Rotation
            if shape_name == "Rectangle":
                rotation_angle = random.randint(0, 90)
            else:
                rotation_angle = random.randint(0, 360)

            # Store Metadata for later noise application
            obj_data = {
                'cx': cx, 'cy': cy, 
                'shape': shape_name, 
                'r': radius, 
                'color': color_bgr, 
                'angle': rotation_angle
            }
            self.scene_data.append(obj_data)

            # Draw CLEAN version immediately
            self.draw_object(self.img_clean, obj_data, noise_c_amt=0, noise_s_amt=0)
            
        # Automatically generate a noisy version with current sliders to start
        self.apply_noise_to_current()

    def apply_noise_to_current(self):
        """Re-draws the scene using stored metadata (Procedural) OR applies pixel noise (Upload)."""
        if self.img_clean is None:
            messagebox.showwarning("No Scene", "Please generate or upload a scene first!")
            return

        # --- PATH A: PROCEDURAL (Vector Re-drawing) ---
        if self.is_procedural and self.scene_data:
            res_key = self.res_var.get()
            w, h = RESOLUTIONS[res_key]
            
            # Reset Noisy Image
            self.img_noisy = np.ones((h, w, 3), dtype=np.uint8) * 255
            
            # Re-draw all objects from metadata
            for obj in self.scene_data:
                self.draw_object(self.img_noisy, obj,
                                 noise_c_amt=self.noise_color_amt.get(),
                                 noise_s_amt=self.noise_shape_amt.get(),
                                 noise_c_type=self.noise_color_type.get(),
                                 noise_s_type=self.noise_shape_type.get())
            
            # Global Salt & Pepper (Procedural)
            if self.noise_color_type.get() == "Salt & Pepper" and self.noise_color_amt.get() > 0:
                prob = self.noise_color_amt.get() * 0.1
                noise_mask = np.random.rand(h, w)
                self.img_noisy[noise_mask < prob/2] = 255
                self.img_noisy[(noise_mask >= prob/2) & (noise_mask < prob)] = 0

        # --- PATH B: UPLOADED IMAGE (Raster Noise) ---
        else:
            img = self.img_clean.copy()
            h, w = img.shape[:2]
            noise_type = self.noise_color_type.get()
            amount = self.noise_color_amt.get()

            if amount > 0:
                if noise_type == "Gaussian":
                    # Gaussian noise calculation
                    mean = 0
                    sigma = amount * 100 # Scaling factor
                    gauss = np.random.normal(mean, sigma, (h, w, 3)).astype('int16')
                    img_int = img.astype('int16')
                    img_noisy_int = cv2.add(img_int, gauss)
                    self.img_noisy = np.clip(img_noisy_int, 0, 255).astype('uint8')
                
                elif noise_type == "Salt & Pepper":
                    prob = amount * 0.1
                    self.img_noisy = img.copy()
                    noise_mask = np.random.rand(h, w)
                    # Salt (White)
                    self.img_noisy[noise_mask < prob/2] = [255, 255, 255]
                    # Pepper (Black)
                    self.img_noisy[(noise_mask >= prob/2) & (noise_mask < prob)] = [0, 0, 0]
            else:
                self.img_noisy = img.copy()

        self.showing_clean = False
        self.btn_toggle.config(state="normal", text="Show Undistorted")
        self.display_image(self.img_noisy, self.panel_left)
        
        # Clear processed view since image changed
        self.img_processed = None
        self.panel_right.config(image='')

    def toggle_clean_view(self):
        if self.img_clean is None: return
        if self.showing_clean:
            self.display_image(self.img_noisy, self.panel_left)
            self.btn_toggle.config(text="Show Undistorted")
            self.showing_clean = False
        else:
            self.display_image(self.img_clean, self.panel_left)
            self.btn_toggle.config(text="Show Noisy")
            self.showing_clean = True

    def draw_object(self, img, obj, noise_c_amt=0, noise_s_amt=0, noise_c_type="Gaussian", noise_s_type="Vertex Jitter"):
        # Unpack
        cx, cy = obj['cx'], obj['cy']
        shape = obj['shape']
        r = obj['r']
        color = obj['color']
        angle = obj['angle']

        final_color = color
        if noise_c_amt > 0 and noise_c_type == "Gaussian":
            dev = int(100 * noise_c_amt)
            b, g, red = color
            def clamp(v): return max(0, min(255, v + random.randint(-dev, dev)))
            final_color = (clamp(b), clamp(g), clamp(red))

        points = []
        if shape == "Circle":
            if noise_s_amt > 0 and noise_s_type == "Distortion":
                axes = (int(r), int(r * (1 - noise_s_amt * 0.5)))
                cv2.ellipse(img, (cx, cy), axes, angle, 0, 360, final_color, -1)
                return
            elif noise_s_amt > 0 and noise_s_type == "Vertex Jitter":
                for i in range(0, 360, 15):
                    rad = math.radians(i)
                    nr = r + random.uniform(-r*0.3*noise_s_amt, r*0.3*noise_s_amt)
                    points.append([int(cx + nr*math.cos(rad)), int(cy + nr*math.sin(rad))])
            else:
                cv2.circle(img, (cx, cy), int(r), final_color, -1)
                return

        elif shape == "Rectangle":
            w_r = r
            h_r = r * 0.6
            if noise_s_amt > 0 and noise_s_type == "Distortion":
                h_r = h_r * (1 - noise_s_amt * 0.5)
            rect = ((cx, cy), (w_r*2, h_r*2), angle)
            box = cv2.boxPoints(rect)
            points = np.int0(box)

        elif shape == "Triangle":
            for i in range(3):
                theta = math.radians(angle + i * 120)
                points.append([int(cx + r * math.cos(theta)), int(cy + r * math.sin(theta))])

        elif shape == "Star":
            for i in range(10):
                theta = math.radians(angle + i * 36)
                rad = r if i % 2 == 0 else r * 0.4
                points.append([int(cx + rad * math.cos(theta)), int(cy + rad * math.sin(theta))])

        points = np.array(points, dtype=np.int32)
        
        if noise_s_amt > 0 and noise_s_type == "Vertex Jitter" and len(points) > 0:
            jitter = r * 0.4 * noise_s_amt
            noise_pts = []
            for p in points:
                nx = p[0] + random.uniform(-jitter, jitter)
                ny = p[1] + random.uniform(-jitter, jitter)
                noise_pts.append([int(nx), int(ny)])
            points = np.array(noise_pts, dtype=np.int32)

        if len(points) > 0:
            cv2.fillPoly(img, [points], final_color)

    def solve_image(self):
        if self.img_noisy is None: return
        img = self.img_noisy.copy()
        h_img, w_img = img.shape[:2]
        
        # Determine scale factor based on image dimensions relative to 800x600
        scale_factor = min(w_img / 800, h_img / 600)
        
        legend_height = int(200 * scale_factor)
        processed = np.ones((h_img + legend_height, w_img, 3), dtype=np.uint8) * 255
        processed[0:h_img, 0:w_img] = img
        
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # --- APPLICABLE BLUR LOGIC ---
        # 1. Salt & Pepper High Noise
        needs_blur = (self.noise_color_type.get() == "Salt & Pepper" and self.noise_color_amt.get() > 0.2)
        # 2. JPEG Input (Prompt Requirement)
        if self.is_jpeg_input:
            needs_blur = True
            
        if needs_blur:
            # Using Median Blur to remove salt/pepper or jpeg artifacts
            gray = cv2.medianBlur(gray, 3)
            
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 50 * (scale_factor**2): continue
            
            # Size
            if area > 5500 * (scale_factor**2): y_id = 1
            elif area > 2000 * (scale_factor**2): y_id = 2
            else: y_id = 3
            
            # Shape
            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0: continue
            compactness = (perimeter**2) / area
            detected = "Unknown"
            if compactness < 15: detected = "Circle"
            elif compactness < 19: detected = "Rectangle"
            elif compactness < 26: detected = "Triangle"
            else: detected = "Star"
            
            x_id = "?"
            for pid, pvar in self.shape_map_vars.items():
                if pvar.get() == detected:
                    x_id = pid
                    break

            # Color
            mask = np.zeros(gray.shape, dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_color = cv2.mean(img, mask=mask)[:3]
            z_id = "?"
            min_dist = float('inf')
            
            for cid in [1, 2, 3]:
                c_name = self.color_map_vars[cid].get()
                c_val = COLOR_DB[c_name]
                d = math.sqrt(sum([(a-b)**2 for a,b in zip(mean_color, c_val)]))
                if d < min_dist:
                    min_dist = d
                    z_id = cid
            
            label = f"{x_id}{y_id}{z_id}"
            
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
            else:
                rect = cv2.boundingRect(cnt)
                cX = rect[0] + rect[2]//2
                cY = rect[1] + rect[3]//2
            
            font_scale = 0.7 * scale_factor
            thickness = max(1, int(2 * scale_factor))
            (fw, fh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
            
            text_x = max(5, min(w_img - fw - 5, cX - fw // 2))
            text_y = max(fh + 5, min(h_img - 5, cY + fh // 2))
            
            # Draw Outline first
            cv2.drawContours(processed, [cnt], -1, (0, 0, 0), max(1, int(2*scale_factor)))
            # Draw Text
            cv2.putText(processed, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 
                        font_scale, (0,0,0), thickness + 3)
            cv2.putText(processed, label, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 
                        font_scale, (255,255,255), thickness)

        self.draw_bottom_legend(processed, w_img, h_img, scale_factor)
        self.img_processed = processed
        self.display_image(self.img_processed, self.panel_right)

    def draw_bottom_legend(self, img, w_img, h_img, scale):
        cv2.line(img, (0, h_img), (w_img, h_img), (0,0,0), 2)
        
        font_scale = 0.6 * scale
        thickness = max(1, int(1 * scale))
        line_height = int(35 * scale)
        start_y = h_img + int(40 * scale)
        col_w = w_img // 4
        
        cv2.putText(img, "LEGEND [XYZ]", (int(20*scale), start_y), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8*scale, (0,0,0), 2)
        
        # Col 1: X (Shape)
        cx = col_w
        cy = start_y
        cv2.putText(img, "X (Object):", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), 2)
        cy += line_height
        for i in range(1, 4):
            cv2.putText(img, f"{i}: {self.shape_map_vars[i].get()}", (cx, cy), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)
            cy += line_height

        # Col 2: Y (Size)
        cx = col_w * 2
        cy = start_y
        cv2.putText(img, "Y (Size):", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), 2)
        cy += line_height
        cv2.putText(img, "1: Large", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)
        cy += line_height
        cv2.putText(img, "2: Medium", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)
        cy += line_height
        cv2.putText(img, "3: Small", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)

        # Col 3: Z (Color)
        cx = col_w * 3
        cy = start_y
        cv2.putText(img, "Z (Color):", (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), 2)
        cy += line_height
        for i in range(1, 4):
            c_name = self.color_map_vars[i].get()
            box_s = int(20 * scale)
            cv2.rectangle(img, (cx, cy - int(15*scale)), (cx + box_s, cy - int(15*scale) + box_s), 
                          COLOR_DB[c_name], -1)
            cv2.rectangle(img, (cx, cy - int(15*scale)), (cx + box_s, cy - int(15*scale) + box_s), 
                          (0,0,0), 1)
            cv2.putText(img, f"{i}: {c_name}", (cx + int(30*scale), cy), 
                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0,0,0), thickness)
            cy += line_height

    def save_single_image(self, target_type):
        """Saves the requested image type independently."""
        img_to_save = None
        
        if target_type == "distorted":
            img_to_save = self.img_noisy
            default_name = "distorted_image"
        elif target_type == "processed":
            img_to_save = self.img_processed
            default_name = "processed_image"

        if img_to_save is None:
            messagebox.showwarning("Warning", f"No {target_type} image to save.")
            return

        # Default to current directory
        initial_dir = os.getcwd()

        file_path = filedialog.asksaveasfilename(
            initialdir=initial_dir,
            initialfile=default_name,
            defaultextension=".jpg",
            filetypes=[("JPEG Image", "*.jpg"), ("PNG Image", "*.png")]
        )

        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg']:
                quality = self.jpeg_quality_var.get()
                cv2.imwrite(file_path, img_to_save, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
            else:
                cv2.imwrite(file_path, img_to_save)
            messagebox.showinfo("Success", f"Saved to:\n{file_path}")

    def display_image(self, img, panel):
        h, w = img.shape[:2]
        max_dim = self.preview_size_var.get()
        ratio = min(max_dim/w, max_dim/h)
        disp_w, disp_h = int(w*ratio), int(h*ratio)
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        im_pil = Image.fromarray(img_rgb).resize((disp_w, disp_h), Image.Resampling.LANCZOS)
        imgtk = ImageTk.PhotoImage(image=im_pil)
        panel.config(image=imgtk, text="")
        panel.imgtk = imgtk

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageProcessingApp(root)
    root.mainloop()