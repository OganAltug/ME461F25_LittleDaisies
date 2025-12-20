import machine
import time
import math
import _thread
import network
import socket
import json

# --- CONFIGURATION ---
SSID = "YOUR_WIFI_ID"
PASSWORD = "YOUR_WIFI_PASSWORD"
MOTOR_PINS = [13, 26, 27, 28] 

# --- SHARED GLOBAL STATE ---
state_direction = 1       # 1 = CW, -1 = CCW
state_mode = "HALF"       # "FULL", "HALF", "MICRO", "CUSTOM"
state_micro_steps = 16    
state_delay = 0.02        
state_energized = False   
state_continuous = False  
state_single_step_req = False 

# Custom Sequence Data
custom_sequence = [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]] 
current_step_index = 0.0  
current_pin_state = [0, 0, 0, 0]

# --- MOTOR LOGIC (CORE 0) ---
def motor_core():
    global state_direction, state_mode, state_micro_steps, state_delay
    global state_energized, state_continuous, state_single_step_req
    global custom_sequence, current_step_index, current_pin_state
    
    pwms = []
    for pin_num in MOTOR_PINS:
        p = machine.PWM(machine.Pin(pin_num))
        p.freq(20000) 
        p.duty_u16(0)
        pwms.append(p)

    full_step_seq = [[1,0,0,0], [0,1,0,0], [0,0,1,0], [0,0,0,1]]
    half_step_seq = [[1,0,0,0], [1,1,0,0], [0,1,0,0], [0,1,1,0], [0,0,1,0], [0,0,1,1], [0,0,0,1], [1,0,0,1]]

    while True:
        # 1. STOP Logic
        if not state_energized:
            for pwm in pwms: pwm.duty_u16(0)
            current_pin_state = [0, 0, 0, 0]
            time.sleep(0.01)
            continue

        # 2. PAUSE Logic
        if not state_continuous and not state_single_step_req:
            time.sleep(0.01)
            continue

        # 3. Determine Active Sequence
        active_seq = []
        is_micro = False
        
        if state_mode == "FULL": active_seq = full_step_seq
        elif state_mode == "HALF": active_seq = half_step_seq
        elif state_mode == "CUSTOM": active_seq = custom_sequence
        elif state_mode == "MICRO": is_micro = True
        
        if not is_micro and len(active_seq) == 0:
            active_seq = full_step_seq 

        seq_len = state_micro_steps if is_micro else len(active_seq)

        # 4. Movement Logic
        if state_continuous or state_single_step_req:
            current_step_index += state_direction
            if state_single_step_req: state_single_step_req = False

        # Wrap-around
        if current_step_index >= seq_len: current_step_index = 0
        elif current_step_index < 0: current_step_index = seq_len - 1

        # 5. Calculate Outputs
        pwm_outputs = [0, 0, 0, 0]
        visual_outputs = [0, 0, 0, 0]
        
        if is_micro:
            angle = (current_step_index / seq_len) * 2 * math.pi
            c1 = max(0, math.cos(angle))
            c2 = max(0, math.sin(angle))
            c3 = max(0, -math.cos(angle))
            c4 = max(0, -math.sin(angle))
            pwm_outputs = [int(c1*65535), int(c2*65535), int(c3*65535), int(c4*65535)]
            visual_outputs = [1 if x > 0 else 0 for x in pwm_outputs]
        else:
            idx_int = int(current_step_index)
            if idx_int >= len(active_seq): idx_int = 0
            if idx_int < 0: idx_int = len(active_seq) - 1
            
            row = active_seq[idx_int]
            visual_outputs = row
            pwm_outputs = [val * 65535 for val in row]

        # 6. Apply to Hardware
        current_pin_state = visual_outputs
        for i in range(4):
            pwms[i].duty_u16(pwm_outputs[i])
            
        # 7. RESPONSIVE DELAY LOOP
        delay_ms = int(state_delay * 1000)
        if delay_ms < 1: delay_ms = 1
        
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < delay_ms:
            if not state_energized: break 
            if not state_continuous and not state_single_step_req: break
            time.sleep(0.001)

# --- WEB SERVER (CORE 1) ---
def server_core():
    global state_direction, state_mode, state_micro_steps, state_delay
    global state_energized, state_continuous, state_single_step_req
    global custom_sequence, current_step_index, current_pin_state
    
    wlan = network.WLAN(network.STA_IF)
    wlan.config(hostname="Pico-Stepper-Motor")
    wlan.active(True)
    wlan.connect(SSID, PASSWORD)
    
    while not wlan.isconnected(): time.sleep(1)
    print('IP Address:', wlan.ifconfig()[0])

    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)

    html_page = """<!DOCTYPE html>
    <html>
    <head>
        <title>Stepper Lab</title>
        <style>
            body { font-family: monospace; text-align: center; background: #eee; padding: 20px;}
            .panel { background: #fff; border: 2px solid #333; display: inline-block; padding: 20px; border-radius: 8px; text-align: left; min-width: 350px;}
            .section { margin-bottom: 15px; border-bottom: 2px dashed #ddd; padding-bottom: 10px; }
            .custom-box { background: #f9f9f9; border: 1px solid #ccc; padding: 10px; margin-top: 10px; }
            textarea { width: 95%; font-family: monospace; border: 1px solid #999;}
            button { padding: 8px 15px; cursor: pointer; font-weight: bold; margin: 2px;}
            input[type=number] { width: 80px; padding: 5px; }
            select { padding: 5px; }
            .led-box { font-size: 28px; font-weight: bold; letter-spacing: 5px; background: #222; color: #0f0; padding: 10px; text-align: center; margin-top: 5px;}
            .dir-disp { font-size: 20px; font-weight: bold; color: #0000FF; }
        </style>
    </head>
    <body>
        <div class="panel">
            <h2>Stepper Controller</h2>
            
            <div class="section">
                <div style="font-size: 12px; color: #666;">CURRENT PIN STATE</div>
                <div id="pinDisp" class="led-box">0 0 0 0</div>
                <br>
                <button onclick="singleStep()" style="width: 100%; padding: 12px; background: #ddd;">APPLY SINGLE STEP</button>
            </div>

            <div class="section" style="text-align: center;">
                <label>Direction: </label>
                <span id="dirDisp" class="dir-disp">CW</span>
                <br><br>
                <button onclick="setDir(1)" style="width: 40%; background: #e3f2fd;">Clockwise (CW)</button>
                <button onclick="setDir(-1)" style="width: 40%; background: #e3f2fd;">Counter-CW (CCW)</button>
            </div>

            <div class="section" style="text-align: center;">
                <button id="btnRun" onclick="setRun(1)" style="background:#4CAF50; color:white; width: 30%;">RUN</button>
                <button id="btnPause" onclick="setRun(0)" style="background:#FF9800; color:white; width: 30%;">PAUSE</button>
                <button onclick="stopMotor()" style="background:#f44336; color:white; width: 30%;">STOP</button>
            </div>

            <div class="section">
                <label>Mode:</label>
                <select id="modeSel">
                    <option value="FULL">Full Step</option>
                    <option value="HALF" selected>Half Step</option>
                    <option value="MICRO">Microstepping</option>
                    <option value="CUSTOM">Custom</option>
                </select>
                <button onclick="setMode()">Set</button>
                <br><br>
                
                <label>Delay (ms): </label>
                <input type="number" id="delayInput" value="20" min="1">
                <button onclick="setDelay()">Set</button>
                <br><br>
                
                <label>Microstep Div: </label>
                <input type="number" id="uStepInput" value="16" min="4" step="4">
                <button onclick="setMicro()">Set</button>
            </div>

            <div class="custom-box">
                <label style="font-weight:bold;">Custom Sequence Editor</label><br>
                <div style="font-size:10px; color:#555;">Enter lines of 1s and 0s (max 12 lines)</div>
                <textarea id="seqInput" rows="12">1000\n0100\n0010\n0001</textarea><br>
                <button onclick="uploadCustom()" style="width:100%; background: #e0e0e0;">Upload & Select Custom</button>
            </div>
            
            <div id="debug" style="font-size:10px; color:#888; margin-top: 10px;">Ready</div>
        </div>

        <script>
            let isContinuous = false;
            
            setInterval(getStatus, 150); 

            function getStatus() {
                fetch('/get_status').then(r => r.json()).then(data => {
                    document.getElementById('dirDisp').innerText = (data.dir === 1) ? "CW" : "CCW";
                    
                    if (isContinuous) {
                        document.getElementById('pinDisp').style.color = "#555";
                        document.getElementById('debug').innerText = "Running... (Display Paused)";
                    } else {
                        document.getElementById('pinDisp').style.color = "#0f0";
                        document.getElementById('pinDisp').innerText = data.pins.join(" ");
                        document.getElementById('debug').innerText = "Idle / Single Step";
                    }
                });
            }

            function setDir(d) {
                fetch('/direction?dir=' + d);
            }

            function uploadCustom() {
                let txt = document.getElementById('seqInput').value;
                let safe = txt.replace(/\\n/g, ','); 
                fetch('/set_custom?seq=' + safe).then(() => {
                    document.getElementById('modeSel').value = "CUSTOM";
                    setMode(); 
                });
            }

            function setMode() {
                let m = document.getElementById('modeSel').value;
                fetch('/config?mode=' + m);
            }

            function setDelay() {
                let d = document.getElementById('delayInput').value;
                fetch('/config?delay=' + d);
            }

            function setMicro() {
                let u = document.getElementById('uStepInput').value;
                fetch('/config?micro=' + u);
            }

            function setRun(state) {
                isContinuous = (state == 1);
                fetch('/run_mode?run=' + state);
            }

            function singleStep() {
                isContinuous = false;
                fetch('/single_step');
            }
            
            function stopMotor() {
                isContinuous = false;
                fetch('/stop_all');
            }
        </script>
    </body>
    </html>
    """

    while True:
        try:
            cl, addr = s.accept()
            req = str(cl.recv(4096))
            
            if '/get_status' in req:
                resp = json.dumps({"pins": current_pin_state, "dir": state_direction})
                cl.send('HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n' + resp)
            
            elif '/set_custom' in req:
                try:
                    raw = req.split('seq=')[1].split(' ')[0]
                    parts = raw.split('%2C') 
                    if len(parts) == 1: parts = raw.split(',')
                    new_seq = []
                    for line in parts:
                        line = line.strip()
                        if len(line) == 4:
                            row = [int(c) for c in line]
                            new_seq.append(row)
                    if len(new_seq) > 0:
                        custom_sequence = new_seq
                        current_step_index = 0
                        state_mode = "CUSTOM"
                except: pass
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')

            elif '/config' in req:
                if 'mode=FULL' in req: state_mode = "FULL"
                elif 'mode=HALF' in req: state_mode = "HALF"
                elif 'mode=MICRO' in req: state_mode = "MICRO"
                elif 'mode=CUSTOM' in req: state_mode = "CUSTOM"
                
                if 'delay=' in req:
                    try:
                        val = req.split('delay=')[1].split(' ')[0].split('&')[0]
                        state_delay = int(val) / 1000.0
                    except: pass
                
                if 'micro=' in req:
                    try:
                        val = req.split('micro=')[1].split(' ')[0].split('&')[0]
                        state_micro_steps = int(val)
                    except: pass
                
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')
                
            elif '/run_mode' in req:
                state_energized = True
                state_continuous = ('run=1' in req)
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')

            elif '/single_step' in req:
                state_energized = True
                state_continuous = False
                state_single_step_req = True
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')

            elif '/direction' in req:
                state_direction = 1 if 'dir=1' in req else -1
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')

            elif '/stop_all' in req:
                state_energized = False
                state_continuous = False
                cl.send('HTTP/1.0 200 OK\r\n\r\nOK')

            else:
                cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
                cl.send(html_page)
            
            cl.close()
        except Exception as e:
            try: cl.close()
            except: pass

# --- STARTUP ---
_thread.start_new_thread(server_core, ())
motor_core()