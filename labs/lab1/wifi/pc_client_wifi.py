import tkinter as tk
from tkinter import ttk, messagebox
import socket
import time

class MotorControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Pico Motor WiFi Controller")
        self.root.geometry("600x550")
        
        # Network Connection Variables
        self.sock = None
        self.is_connected = False
        self.target_port = 8080 # Port must match the Pico code
        
        # State Variables
        self.duty_cycle = tk.IntVar(value=0)
        self.motor_selection = tk.StringVar(value="BOTH")
        self.direction = tk.StringVar(value="FWD")
        self.system_running = False
        
        # Default IP (You will see the actual IP in the Pico shell when it runs)
        self.ip_address = tk.StringVar(value="192.168.1.X")
        
        self.setup_ui()
        
    def setup_ui(self):
        # --- Connection Section ---
        conn_frame = tk.LabelFrame(self.root, text="WiFi Connection", padx=10, pady=10)
        conn_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(conn_frame, text="Pico IP Address:").pack(side="left", padx=5)
        
        self.ip_entry = tk.Entry(conn_frame, textvariable=self.ip_address, width=20)
        self.ip_entry.pack(side="left", padx=5)
        
        self.btn_connect = tk.Button(conn_frame, text="Connect", command=self.toggle_connection, bg="#dddddd")
        self.btn_connect.pack(side="left", padx=5)
        
        tk.Label(conn_frame, text="(Port 8080)", fg="gray").pack(side="left", padx=5)

        # --- Controls Container ---
        controls_frame = tk.Frame(self.root)
        controls_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 1. Duty Cycle Section
        dc_frame = tk.LabelFrame(controls_frame, text="1. Duty Cycle (%)", padx=10, pady=10)
        dc_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        cycles = [0, 25, 50, 75, 100]
        for val in cycles:
            tk.Radiobutton(dc_frame, text=f"{val}%", variable=self.duty_cycle, 
                           value=val, command=self.send_settings).pack(anchor="w")

        # 2. Motor Selection
        motor_frame = tk.LabelFrame(controls_frame, text="2. Motor Selection", padx=10, pady=10)
        motor_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        tk.Radiobutton(motor_frame, text="Motor A", variable=self.motor_selection, 
                       value="A", command=self.send_settings).pack(anchor="w")
        tk.Radiobutton(motor_frame, text="Motor B", variable=self.motor_selection, 
                       value="B", command=self.send_settings).pack(anchor="w")
        tk.Radiobutton(motor_frame, text="Both", variable=self.motor_selection, 
                       value="BOTH", command=self.send_settings).pack(anchor="w")

        # 3. Direction
        dir_frame = tk.LabelFrame(controls_frame, text="3. Direction", padx=10, pady=10)
        dir_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        tk.Radiobutton(dir_frame, text="Forward", variable=self.direction, 
                       value="FWD", command=self.send_settings).pack(anchor="w")
        tk.Radiobutton(dir_frame, text="Backward", variable=self.direction, 
                       value="BWD", command=self.send_settings).pack(anchor="w")

        # 4. Start / Stop
        action_frame = tk.LabelFrame(controls_frame, text="4. Action", padx=10, pady=10)
        action_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        
        self.btn_start = tk.Button(action_frame, text="START", bg="#90ee90", width=10, command=self.start_system)
        self.btn_start.pack(pady=5)
        
        self.btn_stop = tk.Button(action_frame, text="STOP", bg="#ffcccb", width=10, command=self.stop_system)
        self.btn_stop.pack(pady=5)

        # --- Visualization Section ---
        vis_frame = tk.LabelFrame(self.root, text="PWM Signal Visualization (Approximation)", padx=10, pady=10)
        vis_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.canvas = tk.Canvas(vis_frame, bg="black", height=150)
        self.canvas.pack(fill="both", expand=True)
        
        # Initial draw
        self.draw_pwm_wave()

    def toggle_connection(self):
        if not self.is_connected:
            try:
                ip = self.ip_address.get()
                print(f"Connecting to {ip}:{self.target_port}...")
                
                # Create a TCP/IP socket
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(3) # 3 second timeout for connection attempt
                self.sock.connect((ip, self.target_port))
                
                self.is_connected = True
                self.btn_connect.config(text="Disconnect", bg="#ffcccb")
                messagebox.showinfo("Success", f"Connected to {ip}")
            except Exception as e:
                self.sock = None
                messagebox.showerror("Connection Error", f"Could not connect to {ip}\n\nError: {e}")
        else:
            if self.sock:
                try:
                    self.sock.close()
                except:
                    pass
            self.sock = None
            self.is_connected = False
            self.btn_connect.config(text="Connect", bg="#dddddd")

    def send_command(self, cmd_string):
        if self.is_connected and self.sock:
            try:
                full_cmd = cmd_string + "\n"
                self.sock.sendall(full_cmd.encode('utf-8'))
                print(f"Sent: {full_cmd.strip()}")
            except Exception as e:
                print(f"Socket Error: {e}")
                # Optional: Disconnect on write error
                # self.toggle_connection()

    def send_settings(self):
        # Update visualizing first
        self.draw_pwm_wave()
        
        # Send Data to Pico
        self.send_command(f"SPD:{self.duty_cycle.get()}")
        self.send_command(f"MOT:{self.motor_selection.get()}")
        if self.system_running:
             self.send_command(f"DIR:{self.direction.get()}")

    def start_system(self):
        self.system_running = True
        self.send_settings() # Ensure parameters are synced
        self.send_command("ACT:START")
        self.draw_pwm_wave()

    def stop_system(self):
        self.system_running = False
        self.send_command("ACT:STOP")
        self.draw_pwm_wave()

    def draw_pwm_wave(self):
        self.canvas.delete("all")
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        # Fallback if canvas hasn't rendered yet
        if w < 10: w = 560
        if h < 10: h = 150

        # Logic for what to display
        duty = self.duty_cycle.get()
        is_active = self.system_running
        
        # Color based on motor/direction
        color = "#00ff00" # Green default
        if self.direction.get() == "BWD": color = "#00ccff" # Blueish for reverse
        
        # If stopped, draw flat line at bottom
        if not is_active or duty == 0:
            self.canvas.create_line(0, h-10, w, h-10, fill="red", width=2)
            self.canvas.create_text(w/2, h/2, text="STOPPED / 0V", fill="white")
            return

        # If 100%, draw flat line at top
        if duty == 100:
            self.canvas.create_line(0, 10, w, 10, fill=color, width=2)
            self.canvas.create_text(w/2, h/2, text="100% DUTY", fill="white")
            return

        # Draw Square Wave
        # Period width in pixels
        period = 80 
        high_w = period * (duty / 100)
        low_w = period - high_w
        
        x = 0
        while x < w:
            # High Pulse
            self.canvas.create_line(x, h-10, x, 10, fill=color, width=2) # Rising edge
            self.canvas.create_line(x, 10, x + high_w, 10, fill=color, width=2) # High State
            x += high_w
            
            # Low Pulse
            self.canvas.create_line(x, 10, x, h-10, fill=color, width=2) # Falling edge
            self.canvas.create_line(x, h-10, x + low_w, h-10, fill=color, width=2) # Low State
            x += low_w

        self.canvas.create_text(w/2, h-30, text=f"Duty Cycle: {duty}%", fill="white", font=("Arial", 12, "bold"))

if __name__ == "__main__":
    root = tk.Tk()
    app = MotorControlGUI(root)
    root.mainloop()