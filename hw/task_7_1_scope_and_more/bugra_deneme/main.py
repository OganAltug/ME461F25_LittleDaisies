from machine import ADC, Pin, PWM
import time
import sys
import select

# --- CONFIGURATION ---
ADC_PIN_1 = 26    # Channel 1 (Trigger Source)
ADC_PIN_2 = 27    # Channel 2
PWM_PIN = 0       # Signal Generator
BUTTON_PIN = 15   # Mode Button
LED_PIN = 25      # Status LED

# Total samples (divided by 2 for dual channel)
# 1000 total = 500 samples per channel
TOTAL_SAMPLES = 1000 
CONV_FACTOR = 3.3 / 65535

# --- HARDWARE SETUP ---
# High impedance inputs
adc1 = ADC(Pin(ADC_PIN_1, Pin.IN, Pin.PULL_DOWN)) 
adc2 = ADC(Pin(ADC_PIN_2, Pin.IN, Pin.PULL_DOWN))

mode_btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)
led = Pin(LED_PIN, Pin.OUT)

# --- SIGNAL GENERATOR (PWM) ---
# 1kHz, 30% Duty Cycle for testing
pwm = PWM(Pin(PWM_PIN))
pwm.freq(1000)
pwm.duty_u16(int(0.30 * 65535)) 

# --- STATE MACHINE ---
# 0 = RUN, 1 = ARMED, 2 = HOLD
current_mode = 0 
last_btn_time = 0

def check_inputs():
    global current_mode, last_btn_time
    
    # 1. Physical Button
    if mode_btn.value() == 1:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_btn_time) > 300: 
            last_btn_time = now
            if current_mode == 0:
                current_mode = 1 
                print("MSG:ARMED - WAITING FOR TRIGGER")
            else:
                current_mode = 0 
                print("MSG:CONTINUOUS RUN")

    # 2. Serial Commands
    if select.select([sys.stdin], [], [], 0)[0]:
        cmd = sys.stdin.read(1)
        if cmd == 'R': current_mode = 0; print("MSG:REMOTE - RUN")
        elif cmd == 'S': current_mode = 1; print("MSG:REMOTE - SINGLE")
        elif cmd == 'H': current_mode = 2; print("MSG:REMOTE - STOPPED")

def capture_and_send(tag="DATA"):
    # Buffer for interleaved data
    buf = [0] * TOTAL_SAMPLES
    
    # --- CRITICAL CAPTURE LOOP ---
    start_t = time.ticks_us()
    # Read pairs (CH1, CH2)
    for i in range(0, TOTAL_SAMPLES, 2):
        buf[i] = adc1.read_u16()   # CH1
        buf[i+1] = adc2.read_u16() # CH2
    end_t = time.ticks_us()
    
    # --- MATH (On Channel 1 Data) ---
    # Extract CH1 for metrics
    ch1_data = buf[0::2] # Slicing: start at 0, step 2
    samples_per_ch = TOTAL_SAMPLES / 2
    
    duration = time.ticks_diff(end_t, start_t) / 1_000_000
    if duration == 0: duration = 0.001
    sample_rate = samples_per_ch / duration
    
    # Voltage Metrics
    v_max = max(ch1_data)
    v_min = min(ch1_data)
    v_pp = (v_max - v_min) * CONV_FACTOR
    v_avg = (sum(ch1_data) / samples_per_ch) * CONV_FACTOR
    
    # Frequency & Duty Cycle
    mid = (v_max + v_min) // 2
    edges = 0
    first_edge = 0
    last_edge = 0
    state = 0
    high_samples = 0
    
    # Only calc if signal exists (> 0.15V noise floor)
    if (v_max - v_min) > 3000:
        for i, val in enumerate(ch1_data):
            if val > mid: high_samples += 1
            
            if state == 0 and val > mid:
                state = 1
                edges += 1
                if edges == 1: first_edge = i
                last_edge = i
            elif state == 1 and val < mid:
                state = 0
                
    freq = 0
    period_ms = 0
    duty = 0
    
    if edges > 1:
        dist = last_edge - first_edge
        cycles = edges - 1
        freq = sample_rate / (dist / cycles)
        period_ms = (1 / freq) * 1000
        # Duty Cycle
        duty = (high_samples / len(ch1_data)) * 100

    # --- SEND ---
    data_str = ",".join(str(x) for x in buf)
    # Added Duty to metrics list
    # Format: METRICS:vpp,freq,period,vavg,duty|...
    print(f"METRICS:{v_pp:.2f},{freq:.1f},{period_ms:.2f},{v_avg:.2f},{duty:.1f}|DATA:{data_str}|TAG:{tag}")

def run_scope():
    global current_mode
    while True:
        check_inputs()
        
        if current_mode == 0: # RUN
            led.value(1) 
            capture_and_send(tag="RUN")
            
        elif current_mode == 1: # ARMED
            led.toggle()
            # Trigger on CH1 Rising Edge
            if adc1.read_u16() > 20000:
                led.value(1) 
                # Captures BOTH channels automatically
                capture_and_send(tag="SINGLE")
                current_mode = 2 
            time.sleep(0.01)
            
        elif current_mode == 2: # HOLD
            led.value(0) 
            time.sleep(0.1)

print("Pico Dual Scope Ready.")
run_scope()