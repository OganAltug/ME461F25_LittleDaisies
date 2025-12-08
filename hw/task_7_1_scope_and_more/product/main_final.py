from machine import ADC, Pin, PWM, disable_irq, enable_irq, freq, mem32
import time
import sys
import select
import gc

# --- CONFIGURATION ---
ADC_PIN_1 = 26
ADC_PIN_2 = 27
ADC_PIN_3 = 28
PWM_PIN = 0
BUTTON_PIN = 15
LED_PIN = 25

# --- HARDWARE FIX: FORCE PULL-DOWNS ---
PADS_BANK0_BASE = 0x4001c000
PAD_REG_26 = PADS_BANK0_BASE + 0x6C
PAD_REG_27 = PADS_BANK0_BASE + 0x70
PAD_REG_28 = PADS_BANK0_BASE + 0x74

def force_pulldown(reg_addr):
    val = mem32[reg_addr]
    val |= (1 << 3)  # Set PDE
    val &= ~(1 << 2) # Clear PUE
    mem32[reg_addr] = val

force_pulldown(PAD_REG_26)
force_pulldown(PAD_REG_27)
force_pulldown(PAD_REG_28)

# --- SETUP ---
freq(250000000) # Overclock
TOTAL_SAMPLES = 1200 
CONV_FACTOR = 3.3 / 65535

adc1 = ADC(Pin(ADC_PIN_1, Pin.IN))
adc2 = ADC(Pin(ADC_PIN_2, Pin.IN))
adc3 = ADC(Pin(ADC_PIN_3, Pin.IN))

mode_btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)
led = Pin(LED_PIN, Pin.OUT)

pwm = PWM(Pin(PWM_PIN))
pwm.freq(800)
pwm.duty_u16(int(0.60 * 65535))

current_mode = 0
last_btn_time = 0

def check_inputs():
    global current_mode, last_btn_time
    if mode_btn.value() == 1:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_btn_time) > 300:
            last_btn_time = now
            if current_mode == 0:
                current_mode = 1
                print("MSG:ARMED")
            else:
                current_mode = 0
                print("MSG:RUNNING")

    if select.select([sys.stdin], [], [], 0)[0]:
        cmd = sys.stdin.read(1)
        if cmd == 'R': current_mode = 0; print("MSG:REMOTE - RUN")
        elif cmd == 'S': current_mode = 1; print("MSG:REMOTE - SINGLE")
        elif cmd == 'H': current_mode = 2; print("MSG:REMOTE - STOPPED")

def find_best_trigger():
    v1 = adc1.read_u16()
    v2 = adc2.read_u16()
    v3 = adc3.read_u16()
    
    thresh = 32768
    # Simple check for active signal
    if v1 > 10000: return adc1, thresh
    if v2 > 10000: return adc2, thresh
    if v3 > 10000: return adc3, thresh
    return adc1, thresh

def calculate_channel_metrics(data, sample_rate):
    if not data: return 0,0,0,0,0,0,0
    
    v_max_raw = max(data)
    # Squelch noise < 0.05V
    if v_max_raw < 1000: return 0,0,0,0,0,0,0
    
    v_min_raw = min(data)
    
    # Voltage Conversions
    v_max = v_max_raw * CONV_FACTOR
    v_min = v_min_raw * CONV_FACTOR
    v_pp = (v_max_raw - v_min_raw) * CONV_FACTOR
    v_avg = (sum(data) / len(data)) * CONV_FACTOR
    
    mid = (v_max_raw + v_min_raw) // 2
    edges = 0
    first_edge = 0
    last_edge = 0
    state = 0
    high_samples = 0
    
    if (v_max_raw - v_min_raw) > 2000:
        for i, val in enumerate(data):
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
        if freq > 0: period_ms = (1 / freq) * 1000
        duty = (high_samples / len(data)) * 100
        
    return v_max, v_min, v_pp, freq, period_ms, v_avg, duty

def capture_and_send(tag="DATA", auto_trigger=False):
    buf = [0] * TOTAL_SAMPLES
    
    trig_adc, trig_thresh = find_best_trigger()
    gc.collect()
    irq_state = disable_irq()
    
    try:
        if auto_trigger:
            timeout = 100000
            t0 = time.ticks_us()
            while trig_adc.read_u16() > trig_thresh:
                if time.ticks_diff(time.ticks_us(), t0) > timeout: break
            t0 = time.ticks_us()
            while trig_adc.read_u16() < trig_thresh:
                if time.ticks_diff(time.ticks_us(), t0) > timeout: break

        start_t = time.ticks_us()
        for i in range(0, TOTAL_SAMPLES, 3):
            buf[i] = adc1.read_u16()
            buf[i+1] = adc2.read_u16()
            buf[i+2] = adc3.read_u16()
        end_t = time.ticks_us()

    finally:
        enable_irq(irq_state)
    
    duration = time.ticks_diff(end_t, start_t) / 1_000_000
    if duration == 0: duration = 0.001
    sample_rate = (TOTAL_SAMPLES/3) / duration
    
    m1 = calculate_channel_metrics(buf[0::3], sample_rate)
    m2 = calculate_channel_metrics(buf[1::3], sample_rate)
    m3 = calculate_channel_metrics(buf[2::3], sample_rate)

    # Zero out buffer if squelched (Vmax=0)
    if m1[0] == 0: 
        for i in range(0, TOTAL_SAMPLES, 3): buf[i] = 0
    if m2[0] == 0: 
        for i in range(1, TOTAL_SAMPLES, 3): buf[i+1] = 0
    if m3[0] == 0: 
        for i in range(2, TOTAL_SAMPLES, 3): buf[i+2] = 0

    # Format: vmax, vmin, vpp, freq, period, avg, duty
    # Added m[0] and m[1] to the start
    s1 = f"{m1[0]:.2f},{m1[1]:.2f},{m1[2]:.2f},{m1[3]:.1f},{m1[4]:.2f},{m1[5]:.2f},{m1[6]:.1f}"
    s2 = f"{m2[0]:.2f},{m2[1]:.2f},{m2[2]:.2f},{m2[3]:.1f},{m2[4]:.2f},{m2[5]:.2f},{m2[6]:.1f}"
    s3 = f"{m3[0]:.2f},{m3[1]:.2f},{m3[2]:.2f},{m3[3]:.1f},{m3[4]:.2f},{m3[5]:.2f},{m3[6]:.1f}"

    data_str = ",".join(str(x) for x in buf)
    print(f"METRICS:{s1};{s2};{s3}|DATA:{data_str}|TAG:{tag}")

def run_scope():
    global current_mode
    print("Pico Triple Scope Ready.")
    while True:
        check_inputs()
        if current_mode == 0:
            led.value(1) 
            capture_and_send(tag="RUN", auto_trigger=True)
        elif current_mode == 1:
            led.toggle()
            if adc1.read_u16() > 30000:
                capture_and_send(tag="SINGLE", auto_trigger=False)
                current_mode = 2
            time.sleep(0.01)
        elif current_mode == 2:
            led.value(0) 
            time.sleep(0.1)

run_scope()

