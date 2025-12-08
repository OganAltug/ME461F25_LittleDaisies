from machine import ADC, Pin, PWM, disable_irq, enable_irq, freq, mem32
import time
import sys
import select
import gc

# --- CONFIGURATION ---
ADC_PIN_1 = 26
ADC_PIN_2 = 27
ADC_PIN_3 = 28

PWM_PIN_1 = 22   # CH1 PWM
PWM_PIN_2 = 21   # CH2 PWM
PWM_PIN_3 = 20   # CH3 PWM

BUTTON_PIN = 15
LED_PIN = 25

# --- HARDWARE FIX: FORCE PULL-DOWNS ---
PADS_BANK0_BASE = 0x4001c000
PAD_REG_26 = PADS_BANK0_BASE + 0x6C
PAD_REG_27 = PADS_BANK0_BASE + 0x70
PAD_REG_28 = PADS_BANK0_BASE + 0x74

def force_pulldown(reg_addr):
    val = mem32[reg_addr]
    val |= (1 << 3)   # PDE = 1
    val &= ~(1 << 2)  # PUE = 0
    mem32[reg_addr] = val

force_pulldown(PAD_REG_26)
force_pulldown(PAD_REG_27)
force_pulldown(PAD_REG_28)

# --- SYSTEM SETUP ---
freq(250_000_000)  # Overclock for faster sampling
TOTAL_SAMPLES = 1200
CONV = 3.3 / 65535

adc1 = ADC(Pin(ADC_PIN_1))
adc2 = ADC(Pin(ADC_PIN_2))
adc3 = ADC(Pin(ADC_PIN_3))

mode_btn = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)
led = Pin(LED_PIN, Pin.OUT)

# --- PWM SETUP (3 channels) ---
pwm1 = PWM(Pin(PWM_PIN_1))
pwm2 = PWM(Pin(PWM_PIN_2))
pwm3 = PWM(Pin(PWM_PIN_3))

# Default: 5 kHz, 50% duty each
DEFAULT_FREQ = 5000
DEFAULT_DUTY = 50

for p in (pwm1, pwm2, pwm3):
    p.freq(DEFAULT_FREQ)
    p.duty_u16(int(DEFAULT_DUTY * 655.35))

# Track current PWM settings for GUI labels
pwm_freq = [DEFAULT_FREQ, DEFAULT_FREQ, DEFAULT_FREQ]
pwm_duty = [DEFAULT_DUTY, DEFAULT_DUTY, DEFAULT_DUTY]

current_mode = 0   # 0=RUN, 1=SINGLE-ARMED, 2=STOPPED
last_btn_time = 0

# ---------------------------------------
# PWM STATUS -> GUI
# ---------------------------------------
def send_pwm_status():
    # Format: PWRn:freq,duty
    print(f"PWR1:{pwm_freq[0]},{pwm_duty[0]}")
    print(f"PWR2:{pwm_freq[1]},{pwm_duty[1]}")
    print(f"PWR3:{pwm_freq[2]},{pwm_duty[2]}")

# ---------------------------------------
# INPUT HANDLING
# ---------------------------------------
def check_inputs():
    global current_mode, last_btn_time

    # Button handling (local control)
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

    # USB serial commands
    if select.select([sys.stdin], [], [], 0)[0]:
        # Read first character for command type
        c = sys.stdin.read(1)

        # Run / Single / Halt
        if c == 'R':
            current_mode = 0
            print("MSG:REMOTE - RUN")
            return
        elif c == 'S':
            current_mode = 1
            print("MSG:REMOTE - SINGLE")
            return
        elif c == 'H':
            current_mode = 2
            print("MSG:REMOTE - STOPPED")
            return

        # Frequency or Duty update: "F1_5000", "D2_75"
        elif c in ('F', 'D'):
            rest = sys.stdin.readline().strip()  # e.g. "1_5000"
            try:
                ch_str, val_str = rest.split('_')
                ch_idx = int(ch_str) - 1   # channel index 0..2
                val = int(val_str)
            except:
                return

            if not (0 <= ch_idx <= 2):
                return

            if c == 'F':
                # Set frequency
                if ch_idx == 0:   pwm1.freq(val)
                elif ch_idx == 1: pwm2.freq(val)
                elif ch_idx == 2: pwm3.freq(val)
                pwm_freq[ch_idx] = val
                print(f"MSG:SET FREQ CH{ch_idx+1} = {val} Hz")
                send_pwm_status()

            elif c == 'D':
                # Set duty (%)
                duty = max(0, min(val, 100))
                duty_u16 = int(duty * 655.35)
                if ch_idx == 0:   pwm1.duty_u16(duty_u16)
                elif ch_idx == 1: pwm2.duty_u16(duty_u16)
                elif ch_idx == 2: pwm3.duty_u16(duty_u16)
                pwm_duty[ch_idx] = duty
                print(f"MSG:SET DUTY CH{ch_idx+1} = {duty}%")
                send_pwm_status()

# ---------------------------------------
# METRICS CALCULATION
# ---------------------------------------
def calculate_channel_metrics(data, sr):
    if not data:
        return (0,)*7

    vmax_raw = max(data)
    if vmax_raw < 800:  # noise floor / squelch
        return (0,)*7

    vmin_raw = min(data)
    vpp = (vmax_raw - vmin_raw) * CONV
    vmax = vmax_raw * CONV
    vmin = vmin_raw * CONV
    vavg = sum(data) / len(data) * CONV

    mid = (vmax_raw + vmin_raw) / 2
    edges = 0
    first = last = 0
    high_cnt = 0
    state = 0

    for i, v in enumerate(data):
        if v > mid:
            high_cnt += 1

        if state == 0 and v > mid:
            state = 1
            edges += 1
            if edges == 1:
                first = i
            last = i
        elif state == 1 and v < mid:
            state = 0

    freq_ch = 0
    period_ms = 0
    duty = 0

    if edges > 1:
        dist = last - first
        cycles = edges - 1
        freq_ch = sr / (dist / cycles)
        if freq_ch > 0:
            period_ms = 1000.0 / freq_ch
        duty = (high_cnt / len(data)) * 100.0

    return vmax, vmin, vpp, freq_ch, period_ms, vavg, duty

# ---------------------------------------
# CAPTURE & SEND
# ---------------------------------------
def capture_and_send(tag="RUN"):
    buf = [0] * TOTAL_SAMPLES

    irq_state = disable_irq()
    try:
        t0 = time.ticks_us()
        for i in range(0, TOTAL_SAMPLES, 3):
            buf[i]   = adc1.read_u16()
            buf[i+1] = adc2.read_u16()
            buf[i+2] = adc3.read_u16()
        t1 = time.ticks_us()
    finally:
        enable_irq(irq_state)

    dur = time.ticks_diff(t1, t0) / 1_000_000.0
    if dur <= 0:
        dur = 0.001
    sample_rate = (TOTAL_SAMPLES / 3) / dur

    m1 = calculate_channel_metrics(buf[0::3], sample_rate)
    m2 = calculate_channel_metrics(buf[1::3], sample_rate)
    m3 = calculate_channel_metrics(buf[2::3], sample_rate)

    s1 = ",".join(f"{x:.2f}" for x in m1)
    s2 = ",".join(f"{x:.2f}" for x in m2)
    s3 = ",".join(f"{x:.2f}" for x in m3)
    data_str = ",".join(str(x) for x in buf)

    print(f"METRICS:{s1};{s2};{s3}|DATA:{data_str}|TAG:{tag}")

# ---------------------------------------
# MAIN LOOP
# ---------------------------------------
def run():
    global current_mode
    print("Pico Triple Scope Ready.")
    send_pwm_status()

    while True:
        check_inputs()

        if current_mode == 0:
            led.value(1)
            capture_and_send("RUN")

        elif current_mode == 1:
            led.toggle()
            if adc1.read_u16() > 30000:
                capture_and_send("SINGLE")
                current_mode = 2

        elif current_mode == 2:
            led.value(0)
            time.sleep(0.1)

run()
