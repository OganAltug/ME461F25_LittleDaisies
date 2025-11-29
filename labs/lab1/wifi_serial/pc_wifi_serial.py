import tkinter as tk
from tkinter import ttk, messagebox
import socket
import serial
import serial.tools.list_ports
import time

class DualModeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Dual Mode Motor Controller (WiFi + Serial)")
        self.root.geometry("600x600")
        
        # Connection Objects
        self.sock = None
        self.ser = None
        
        # Connection State
        # "WIFI", "SERIAL", or None
        self.active_mode = None 
        self.target_port = 8080 
        
        # GUI Variables
        self.ip_address = tk.StringVar(value="192.168.1.X")
        self.duty_cycle = tk.IntVar(value=0)
        self.motor_selection = tk.StringVar(value="BOTH")
        self.direction = tk.StringVar(value="FWD")
        self.system_running = False
        self.status_text = tk.StringVar(value="Not Connected")
        
        self.setup_ui()
        
    def setup_ui(self):
        # --- Connection Configuration ---
        config_frame = tk.LabelFrame(self.root, text="Connection Configuration", padx=10, pady=10)
        config_frame.pack(fill="x", padx=10, pady=5)
        
        # WiFi Config
        tk.Label(config_frame, text="WiFi IP:").grid(row=0, column=0, padx=5, pady=5)
        tk.Entry(config_frame, textvariable=self.ip_address, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        # Serial Config
        tk.Label(config_frame, text="Serial Port:").grid(row=0, column=2, padx=5, pady=5)
        self.port_combo = ttk.Combobox(config_frame, values=self.get_serial_ports(), width=15)
        self.port_combo.grid(row=0, column=3, padx=5, pady=5)
        self.port_combo.set("Select Port")
        
        # Refresh Button
        tk.Button(config_frame, text="↻", command=self.refresh_ports).grid(row=0, column=4, padx=2)

        # Connect Button (Big)
        self.btn_connect = tk.Button(config_frame, text="AUTO CONNECT", bg="#dddddd", command=self.toggle_connection, font=("Arial", 10, "bold"))
        self.btn_connect.grid(row=0, column=5, padx=10, sticky="nsew")

        # Status Bar
        status_bar = tk.Label(self.root, textvariable=self.status_text, relief="sunken", anchor="w", bg="#f0f0f0")
        status_bar.pack(fill="x", side="bottom")

        # --- Controls ---
        controls_frame = tk.Frame(self.root)
        controls_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # 1. Duty Cycle
        dc_frame = tk.LabelFrame(controls_frame, text="1. Duty Cycle (%)", padx=10, pady=10)
        dc_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        for val in [0, 25, 50, 75, 100]:
            tk.Radiobutton(dc_frame, text=f"{val}%", variable=self.duty_cycle, value=val, command=self.send_settings).pack(anchor="w")

        # 2. Motors
        motor_frame = tk.LabelFrame(controls_frame, text="2. Motor Selection", padx=10, pady=10)
        motor_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        for text, val in [("Motor A", "A"), ("Motor B", "B"), ("Both", "BOTH")]:
            tk.Radiobutton(motor_frame, text=text, variable=self.motor_selection, value=val, command=self.send_settings).pack(anchor="w")

        # 3. Direction
        dir_frame = tk.LabelFrame(controls_frame, text="3. Direction", padx=10, pady=10)
        dir_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        tk.Radiobutton(dir_frame, text="Forward", variable=self.direction, value="FWD", command=self.send_settings).pack(anchor="w")
        tk.Radiobutton(dir_frame, text="Backward", variable=self.direction, value="BWD", command=self.send_settings).pack(anchor="w")

        # 4. Action
        action_frame = tk.LabelFrame(controls_frame, text="4. Action", padx=10, pady=10)
        action_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
        self.btn_start = tk.Button(action_frame, text="START", bg="#90ee90", width=12, command=self.start_system)
        self.btn_start.pack(pady=5)
        self.btn_stop = tk.Button(action_frame, text="STOP", bg="#ffcccb", width=12, command=self.stop_system)
        self.btn_stop.pack(pady=5)

        # --- Visualization ---
        vis_frame = tk.LabelFrame(self.root, text="PWM Signal", padx=10, pady=10)
        vis_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.canvas = tk.Canvas(vis_frame, bg="black", height=150)
        self.canvas.pack(fill="both", expand=True)
        self.draw_pwm_wave()

    def get_serial_ports(self):
        return [port.device for port in serial.tools.list_ports.comports()]

    def refresh_ports(self):
        self.port_combo['values'] = self.get_serial_ports()

    def toggle_connection(self):
        if self.active_mode:
            self.disconnect()
        else:
            self.connect_logic()

    def connect_logic(self):
        self.status_text.set("Attempting Connection...")
        self.root.update()

        # 1. Try WiFi First
        ip = self.ip_address.get()
        if self.try_connect_wifi(ip):
            return

        # 2. Try Serial Second
        port = self.port_combo.get()
        if port and port != "Select Port":
            if self.try_connect_serial(port):
                return
        
        # 3. Failed
        self.status_text.set("Failed to connect via WiFi or Serial.")
        messagebox.showerror("Connection Failed", "Could not connect to Pico via WiFi or Serial.")

    def try_connect_wifi(self, ip):
        try:
            print(f"Trying WiFi: {ip}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2.0) # 2 Second timeout
            self.sock.connect((ip, self.target_port))
            
            self.active_mode = "WIFI"
            self.on_connect_success(f"Connected: WiFi ({ip})")
            return True
        except Exception as e:
            print(f"WiFi Failed: {e}")
            self.sock = None
            return False

    def try_connect_serial(self, port):
        try:
            print(f"Trying Serial: {port}...")
            self.ser = serial.Serial(port, 115200, timeout=1)
            
            self.active_mode = "SERIAL"
            self.on_connect_success(f"Connected: Serial ({port})")
            return True
        except Exception as e:
            print(f"Serial Failed: {e}")
            self.ser = None
            return False

    def on_connect_success(self, msg):
        self.is_connected = True
        self.btn_connect.config(text="DISCONNECT", bg="#ffcccb")
        self.status_text.set(msg)
        messagebox.showinfo("Connected", msg)

    def disconnect(self):
        if self.sock: self.sock.close()
        if self.ser: self.ser.close()
        self.sock = None
        self.ser = None
        self.active_mode = None
        self.btn_connect.config(text="AUTO CONNECT", bg="#dddddd")
        self.status_text.set("Disconnected")

    def failover_switch(self):
        """Called when a send fails. Attempts to switch mode."""
        print("Communication failed! Attempting failover...")
        
        failed_mode = self.active_mode
        self.disconnect() # Clean up broken connection
        
        if failed_mode == "WIFI":
            # WiFi Failed -> Try Serial
            port = self.port_combo.get()
            if port and port != "Select Port":
                self.status_text.set("WiFi lost. Switching to Serial...")
                self.root.update()
                if self.try_connect_serial(port):
                    print("Failover to Serial Successful")
                    return True
        elif failed_mode == "SERIAL":
            # Serial Failed -> Try WiFi (Unlikely but consistent logic)
            ip = self.ip_address.get()
            self.status_text.set("Serial lost. Switching to WiFi...")
            self.root.update()
            if self.try_connect_wifi(ip):
                print("Failover to WiFi Successful")
                return True
                
        self.status_text.set("Connection Lost. Failover failed.")
        return False

    def send_command(self, cmd_string, retry=True):
        if not self.active_mode:
            return

        full_cmd = cmd_string + "\n"
        try:
            if self.active_mode == "WIFI":
                self.sock.sendall(full_cmd.encode('utf-8'))
            elif self.active_mode == "SERIAL":
                self.ser.write(full_cmd.encode('utf-8'))
            print(f"Sent ({self.active_mode}): {cmd_string}")
            
        except Exception as e:
            print(f"Send Error: {e}")
            # If transmission failed, try to failover ONCE
            if retry:
                if self.failover_switch():
                    # If failover worked, try sending again immediately
                    self.send_command(cmd_string, retry=False)

    def send_settings(self):
        self.draw_pwm_wave()
        self.send_command(f"SPD:{self.duty_cycle.get()}")
        self.send_command(f"MOT:{self.motor_selection.get()}")
        if self.system_running:
             self.send_command(f"DIR:{self.direction.get()}")

    def start_system(self):
        self.system_running = True
        self.send_settings()
        self.send_command("ACT:START")
        self.draw_pwm_wave()

    def stop_system(self):
        self.system_running = False
        self.send_command("ACT:STOP")
        self.draw_pwm_wave()

    def draw_pwm_wave(self):
        # (Same drawing logic as previous versions)
        self.canvas.delete("all")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 10: w = 560
        if h < 10: h = 150
        duty = self.duty_cycle.get()
        color = "#00ff00" if self.direction.get() == "FWD" else "#00ccff"
        
        if not self.system_running or duty == 0:
            self.canvas.create_line(0, h-10, w, h-10, fill="red", width=2)
            self.canvas.create_text(w/2, h/2, text="STOPPED", fill="white")
            return

        if duty == 100:
            self.canvas.create_line(0, 10, w, 10, fill=color, width=2)
            return

        period = 80 
        high_w = period * (duty / 100)
        low_w = period - high_w
        x = 0
        while x < w:
            self.canvas.create_line(x, h-10, x, 10, fill=color, width=2)
            self.canvas.create_line(x, 10, x + high_w, 10, fill=color, width=2)
            x += high_w
            self.canvas.create_line(x, 10, x, h-10, fill=color, width=2)
            self.canvas.create_line(x, h-10, x + low_w, h-10, fill=color, width=2)
            x += low_w

if __name__ == "__main__":
    root = tk.Tk()
    app = DualModeGUI(root)
    root.mainloop()