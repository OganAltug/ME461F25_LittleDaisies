import machine
import time
import _thread
import network
import socket
import sys
import select

# --- USER CONFIGURATION ---
SSID = "YOUR_WIFI_ID"
PASSWORD = "YOUR_WIFI_PASSWORD"
SERVO_PIN = 4
POT_PIN = 26       # ADC0 (GP26)

# --- CALIBRATION ---
SERVO_TOTAL_RANGE = 180 
SERVO_MIN_US = 500    
SERVO_MAX_US = 2500   

# --- GLOBAL STATE ---
state = {
    "mode": 1,        # 0=RELEASED, 1=LIBRARY, 2=MANUAL, 3=POT
    "val": 90,        # Current Angle
    "running": True
}

server_ip = None 

# --- WEB SERVER (Core 1) ---
def core1_web_server():
    global server_ip
    wlan = network.WLAN(network.STA_IF)
    
    # Force Reset Wi-Fi
    wlan.active(False)
    time.sleep(0.5)
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)

    # 10s Timeout
    max_wait = 20
    while max_wait > 0:
        if wlan.status() == 3 and wlan.isconnected(): break
        max_wait -= 1
        time.sleep(1)

    if wlan.status() == 3:
        server_ip = wlan.ifconfig()[0]
    else:
        server_ip = False 
        return

    try:
        addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(addr)
        s.listen(1)
    except: return

    while state["running"]:
        try:
            cl, addr = s.accept()
            request = cl.recv(1024).decode('utf-8')
            
            if "GET /set?angle=" in request:
                try:
                    val = int(request.split("angle=")[1].split(" ")[0])
                    if val < 0: val = 0
                    if val > SERVO_TOTAL_RANGE: val = SERVO_TOTAL_RANGE
                    state["val"] = val
                    state["mode"] = 1 # GUI forces Library Mode
                except: pass
                cl.send("HTTP/1.1 200 OK\r\n\r\nOK")
            
            elif "GET /release" in request:
                state["mode"] = 0
                cl.send("HTTP/1.1 200 OK\r\n\r\nReleased")
            
            else:
                # --- REVERTED TO ONCHANGE (Stable) ---
                html = f"""<!DOCTYPE html><html>
                <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ font-family: sans-serif; text-align: center; padding: 20px; }}
                        button {{ padding: 10px 15px; margin: 5px; font-size: 16px; cursor: pointer; }}
                        .rel-btn {{ background: #d32f2f; color: white; border: none; padding: 15px 30px; font-weight: bold; }}
                        input[type=range] {{ width: 80%; height: 25px; }}
                    </style>
                </head>
                <body>
                    <h1>Servo Control</h1>
                    <h2 id="status">Current: {state["val"]}&deg;</h2>
                    
                    <input type="range" min="0" max="{SERVO_TOTAL_RANGE}" value="{state["val"]}" 
                        oninput="document.getElementById('status').innerText='Target: ' + this.value + '&deg;'"
                        onchange="send(this.value)">
                    <br><br>
                    <div>
                        <button onclick="send(0)">0&deg;</button>
                        <button onclick="send(45)">45&deg;</button>
                        <button onclick="send(90)">90&deg;</button>
                        <button onclick="send(135)">135&deg;</button>
                        <button onclick="send(180)">180&deg;</button>
                    </div>
                    <br>
                    <button class="rel-btn" onclick="release()">RELEASE MOTOR</button>

                    <script>
                        function send(val) {{
                            fetch('/set?angle=' + val);
                            document.getElementById('status').innerText = 'Current: ' + val + '&deg;';
                            document.getElementById('status').style.color = 'black';
                        }}
                        function release() {{
                            fetch('/release');
                            document.getElementById('status').innerText = 'MOTOR RELEASED';
                            document.getElementById('status').style.color = 'red';
                        }}
                    </script>
                </body></html>"""
                cl.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html)
            cl.close()
        except: pass

# --- MAIN CONTROLLER (Core 0) ---
def main():
    _thread.start_new_thread(core1_web_server, ())
    
    pin = machine.Pin(SERVO_PIN, machine.Pin.OUT)
    adc = machine.ADC(POT_PIN)
    current_driver = 'none' 
    pwm_obj = None

    print("\n--- INITIALIZING ---")
    print("Connecting to Wi-Fi...", end="")
    while server_ip is None:
        time.sleep(0.5)
        print(".", end="")
    
    if server_ip:
        print(f"\nSUCCESS! Server: http://{server_ip}")
    else:
        print(f"\nWi-Fi Failed. REPL ONLY mode.")

    print(f"Config: 0-{SERVO_TOTAL_RANGE}deg | {SERVO_MIN_US}-{SERVO_MAX_US}us")
    print("Commands: <angle>, manual, library, pot, release, exit")

    while state["running"]:
        
        # 1. READ INPUT
        if select.select([sys.stdin], [], [], 0)[0]:
            raw = sys.stdin.readline()
            if raw:
                cmd = raw.strip().lower().replace('"', '').replace("'", "")
                time.sleep(0.2) 
                if not cmd: continue

                if cmd == "manual":
                    state["mode"] = 2
                    print("Mode: MANUAL")
                elif cmd == "library":
                    state["mode"] = 1
                    print("Mode: LIBRARY")
                elif cmd == "pot":
                    state["mode"] = 3
                    print("Mode: POT CONTROL")
                elif cmd == "release":
                    state["mode"] = 0
                    print("Mode: RELEASED")
                elif cmd == "exit":
                    state["running"] = False
                    break
                elif cmd.replace('.','',1).isdigit():
                    val = float(cmd)
                    if 0 <= val <= SERVO_TOTAL_RANGE:
                        state["val"] = val
                        print(f"Angle: {val}")
                        state["mode"] = 1
                    else:
                        print("Error: Out of range")
                        state["mode"] = 0 

        # 2. DRIVE MOTOR
        if state["mode"] == 3: # POT
            if current_driver != 'pwm':
                pin = machine.Pin(SERVO_PIN)
                pwm_obj = machine.PWM(pin)
                pwm_obj.freq(50)
                current_driver = 'pwm'
            
            pot_val = adc.read_u16()
            angle = (pot_val / 65535) * SERVO_TOTAL_RANGE
            
            # Update state["val"] so REPL knows where we are, 
            # but don't force mode change if user didn't ask.
            state["val"] = int(angle)
            
            pct = angle / SERVO_TOTAL_RANGE
            ns = int((SERVO_MIN_US + (pct * (SERVO_MAX_US - SERVO_MIN_US))) * 1000)
            pwm_obj.duty_ns(ns)
            time.sleep(0.05)

        elif state["mode"] == 1: # LIBRARY
            if current_driver != 'pwm':
                pin = machine.Pin(SERVO_PIN)
                pwm_obj = machine.PWM(pin)
                pwm_obj.freq(50)
                current_driver = 'pwm'
            
            pct = state["val"] / SERVO_TOTAL_RANGE
            ns = int((SERVO_MIN_US + (pct * (SERVO_MAX_US - SERVO_MIN_US))) * 1000)
            pwm_obj.duty_ns(ns)
            time.sleep(0.02)

        elif state["mode"] == 2: # MANUAL
            if current_driver != 'gpio':
                if pwm_obj: pwm_obj.deinit()
                pin = machine.Pin(SERVO_PIN, machine.Pin.OUT)
                current_driver = 'gpio'
            
            target_us = int(SERVO_MIN_US + (state["val"] / SERVO_TOTAL_RANGE) * (SERVO_MAX_US - SERVO_MIN_US))
            pin.value(1)
            time.sleep_us(target_us)
            pin.value(0)
            time.sleep_us(20000 - target_us)

        elif state["mode"] == 0: # RELEASED
            if current_driver == 'pwm': pwm_obj.duty_ns(0)
            else: pin.value(0)
            time.sleep(0.1)

    if pwm_obj: pwm_obj.deinit()
    print("Shutdown")

if __name__ == "__main__":
    main()
