import network
import socket
from machine import Pin, PWM
import time
import select
import sys

# --- WIFI CONFIGURATION ---
SSID = "Eren"
PASSWORD = "19981998"
PORT = 8080

# --- Setup Motor Pins with PWM ---
# Motor A (Left)
in1 = PWM(Pin(0))
in2 = PWM(Pin(1))
in1.freq(1000)
in2.freq(1000)

# Motor B (Right)
in3 = PWM(Pin(17))
in4 = PWM(Pin(16))
in3.freq(1000)
in4.freq(1000)

# Global State
current_speed_percent = 0
current_direction = "STOP" # STOP, FWD, BWD
active_motors = "BOTH" # A, B, BOTH

def set_motor_speed(pwm_pin_a, pwm_pin_b, speed_percent, direction):
    # Convert percent (0-100) to u16 duty (0-65535)
    duty = int((speed_percent / 100) * 65535)
    
    if direction == "STOP":
        pwm_pin_a.duty_u16(0)
        pwm_pin_b.duty_u16(0)
    elif direction == "FWD":
        # Forward: Pin A gets speed, Pin B is Low
        pwm_pin_a.duty_u16(duty)
        pwm_pin_b.duty_u16(0)
    elif direction == "BWD":
        # Backward: Pin A is Low, Pin B gets speed
        pwm_pin_a.duty_u16(0)
        pwm_pin_b.duty_u16(duty)

def update_motors():
    # Motor A Logic
    if active_motors in ["A", "BOTH"]:
        set_motor_speed(in1, in2, current_speed_percent, current_direction)
    else:
        set_motor_speed(in1, in2, 0, "STOP")
        
    # Motor B Logic
    if active_motors in ["B", "BOTH"]:
        set_motor_speed(in3, in4, current_speed_percent, current_direction)
    else:
        set_motor_speed(in3, in4, 0, "STOP")

def parse_command(cmd_str):
    """
    Expected format: "CMD:VALUE"
    """
    global current_speed_percent, current_direction, active_motors
    try:
        parts = cmd_str.strip().split(':')
        if len(parts) != 2: return

        key, val = parts[0], parts[1]

        if key == "SPD":
            current_speed_percent = int(val)
        elif key == "MOT":
            active_motors = val
        elif key == "DIR":
            if current_direction != "STOP":
                current_direction = val
        elif key == "ACT":
            if val == "STOP":
                current_direction = "STOP"
            elif val == "START":
                current_direction = "FWD" 
                
        update_motors()
        print(f"Executed: {key}={val}")
        
    except Exception as e:
        print(f"Cmd Error: {e}")

def setup_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    
    print(f"Attempting WiFi connection to {SSID}...")
    max_wait = 10
    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        time.sleep(1)
        
    if wlan.status() != 3:
        print("WiFi Connection Failed. Running in Serial Mode only.")
        return None
    else:
        ip = wlan.ifconfig()[0]
        print(f'WiFi Connected! IP: {ip}')
        
        addr = (ip, PORT)
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(1)
        print(f'WiFi Server listening on {ip}:{PORT}')
        return s

def run_dual_mode():
    # Attempt WiFi Setup
    server_sock = setup_wifi()
    
    # Input sources for select()
    # Always monitor stdin (Serial)
    input_sources = [sys.stdin]
    
    # If WiFi succeeded, monitor that too
    if server_sock:
        input_sources.append(server_sock)
        
    print("System Ready. Waiting for commands via WiFi or Serial...")
    
    # List of connected WiFi clients
    clients = []

    while True:
        # Check for readable sources (non-blocking)
        # We add clients to input_sources dynamically
        current_inputs = input_sources + clients
        
        readable, _, _ = select.select(current_inputs, [], [], 0.1)
        
        for source in readable:
            # 1. Handle Serial Input
            if source is sys.stdin:
                line = sys.stdin.readline()
                if line:
                    parse_command(line)

            # 2. Handle New WiFi Client Connection
            elif source is server_sock:
                cl, addr = server_sock.accept()
                print('WiFi Client connected from', addr)
                clients.append(cl)

            # 3. Handle Existing WiFi Client Message
            else:
                try:
                    data = source.recv(1024)
                    if data:
                        lines = data.decode('utf-8').split('\n')
                        for line in lines:
                            if line: parse_command(line)
                    else:
                        # Empty data means disconnect
                        print("WiFi Client disconnected")
                        clients.remove(source)
                        source.close()
                except Exception:
                    print("WiFi Client Error")
                    if source in clients: clients.remove(source)
                    source.close()

# Start
try:
    run_dual_mode()
except KeyboardInterrupt:
    print("Server stopped")