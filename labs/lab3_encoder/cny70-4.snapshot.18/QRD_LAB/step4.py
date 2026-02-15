from machine import Pin, ADC
import time

# =========================================================
# FIXED BUTTONS + ADC THRESHOLDING QUADRATURE ENCODER
# + VALID-TRANSITION FILTER (reject impossible jumps)
# + STATE PRINT ONLY ON CHANGE
# + DIRECTION FIX (DIR_SIGN flips counting direction for X1/X2/X4)
# =========================================================

# -------------------------
# PINS
# -------------------------
PIN_A_ADC = 27   # GP27 / ADC1
PIN_B_ADC = 28   # GP28 / ADC2

BTN_L_PIN = 14   # Mode
BTN_R_PIN = 15   # Reset

# -------------------------
# DIRECTION FIX
# If your X4 counts backwards, set DIR_SIGN = -1 (or +1).
# Try -1 first; if still wrong, switch to +1.
# -------------------------
DIR_SIGN = -1

# -------------------------
# ADC + BUTTON SETUP
# -------------------------
adc_a = ADC(PIN_A_ADC)
adc_b = ADC(PIN_B_ADC)

# Buttons: pick the correct wiring
# If your button connects to 3.3V when pressed -> PULL_DOWN + IRQ_RISING
btn_l = Pin(BTN_L_PIN, Pin.IN, Pin.PULL_DOWN)
btn_r = Pin(BTN_R_PIN, Pin.IN, Pin.PULL_DOWN)
BTN_TRIGGER = Pin.IRQ_RISING

# If your button connects to GND when pressed -> PULL_UP + IRQ_FALLING
# btn_l = Pin(BTN_L_PIN, Pin.IN, Pin.PULL_UP)
# btn_r = Pin(BTN_R_PIN, Pin.IN, Pin.PULL_UP)
# BTN_TRIGGER = Pin.IRQ_FALLING

# -------------------------
# THRESHOLDING (u16)
# NOTE: THRESH=5000 is usually too low. Typical QRD readings are often 10k–60k.
# Use telemetry to tune THRESH/HYST.
# -------------------------
THRESH = 5000
HYST   = 500
TH_LOW = THRESH - HYST
TH_HIGH = THRESH + HYST

SAMPLES = 3

# -------------------------
# MODES / GLOBALS
# -------------------------
encoder_count = 0
encoding_mode = 1  # 1,2,4
mode_names = {1: "X1", 2: "X2", 4: "X4"}

mode_request = False
reset_request = False

IRQ_DEBOUNCE_MS = 200
_last_irq_ms = 0

TELEMETRY_EVERY_MS = 500
last_telemetry = time.ticks_ms()

# X4 delta table (for valid single-step transitions)
_quad_delta = {
    (0, 1): +1, (1, 3): +1, (3, 2): +1, (2, 0): +1,
    (0, 2): -1, (2, 3): -1, (3, 1): -1, (1, 0): -1,
}

# -------------------------
# HELPERS
# -------------------------
def read_u16_avg(adc, n=SAMPLES):
    s = 0
    for _ in range(n):
        s += adc.read_u16()
        time.sleep_us(120)
    return s // n

def schmitt_bit(raw, prev_bit):
    # raw < TH_LOW -> 1, raw > TH_HIGH -> 0
    if raw < TH_LOW:
        return 1
    if raw > TH_HIGH:
        return 0
    return prev_bit

def _irq_mode(pin):
    global mode_request, _last_irq_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms) < IRQ_DEBOUNCE_MS:
        return
    _last_irq_ms = now
    mode_request = True

def _irq_reset(pin):
    global reset_request, _last_irq_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_irq_ms) < IRQ_DEBOUNCE_MS:
        return
    _last_irq_ms = now
    reset_request = True

def cycle_mode():
    global encoding_mode
    if encoding_mode == 1:
        encoding_mode = 2
    elif encoding_mode == 2:
        encoding_mode = 4
    else:
        encoding_mode = 1
    print("[MODE]", mode_names[encoding_mode])

def do_reset():
    global encoder_count
    encoder_count = 0
    print("[RESET] count=0")

def popcount2(x):
    return (x & 1) + ((x >> 1) & 1)

def is_valid_transition(prev_state, curr_state):
    # Only accept single-bit changes
    if curr_state == prev_state:
        return False
    return popcount2(prev_state ^ curr_state) == 1

# -------------------------
# IRQ ATTACH
# -------------------------
btn_l.irq(trigger=BTN_TRIGGER, handler=_irq_mode)
btn_r.irq(trigger=BTN_TRIGGER, handler=_irq_reset)

# -------------------------
# INIT
# -------------------------
a_raw = read_u16_avg(adc_a)
b_raw = read_u16_avg(adc_b)

a_bit = 1 if a_raw < THRESH else 0
b_bit = 1 if b_raw < THRESH else 0

prev_state = (a_bit << 1) | b_bit
prev_a = a_bit

invalid_skips = 0  # debug counter

# print only when state CHANGES compared to last printed
last_printed_state = prev_state

print("Encoder ready (ADC thresholding + IRQ buttons + valid-transition filter).")
print("A=ADC GP{}, B=ADC GP{}, ButtonL=GP{}, ButtonR=GP{}".format(PIN_A_ADC, PIN_B_ADC, BTN_L_PIN, BTN_R_PIN))
print("DIR_SIGN =", DIR_SIGN, "(flip to +1 or -1 if direction is wrong)")
print("THRESH={}, HYST={}, TH_LOW={}, TH_HIGH={}".format(THRESH, HYST, TH_LOW, TH_HIGH))
print("Mode:", mode_names[encoding_mode])
print("Initial state={:02b}".format(prev_state))
print("Rotate disk by hand...")

# -------------------------
# MAIN LOOP
# -------------------------
while True:
    # ---- handle button requests ----
    if mode_request:
        mode_request = False
        cycle_mode()

    if reset_request:
        reset_request = False
        do_reset()

    # ---- Read ADCs ----
    a_raw = read_u16_avg(adc_a)
    b_raw = read_u16_avg(adc_b)

    # ---- Threshold -> digital bits ----
    a_bit = schmitt_bit(a_raw, a_bit)
    b_bit = schmitt_bit(b_raw, b_bit)

    curr_state = (a_bit << 1) | b_bit
    curr_a = a_bit

    # ---- STATE PRINT: only when state CHANGES ----
    if curr_state != last_printed_state:
        print("state={:02b}".format(curr_state))
        last_printed_state = curr_state

    # ---- VALID TRANSITION FILTER + COUNT ----
    if curr_state != prev_state:
        if not is_valid_transition(prev_state, curr_state):
            invalid_skips += 1
            # ignore: do not update prev_state
        else:
            if encoding_mode == 4:
                encoder_count += DIR_SIGN * _quad_delta.get((prev_state, curr_state), 0)

            elif encoding_mode == 2:
                if curr_a != prev_a:
                    step = (+1 if (curr_a ^ b_bit) else -1)
                    encoder_count += DIR_SIGN * step

            else:  # X1
                if prev_a == 0 and curr_a == 1:
                    step = (+1 if (curr_a ^ b_bit) else -1)
                    encoder_count += DIR_SIGN * step

            prev_state = curr_state
            prev_a = curr_a

    # ---- Telemetry (periodic) ----
    now = time.ticks_ms()
    if time.ticks_diff(now, last_telemetry) > TELEMETRY_EVERY_MS:
        print("mode={}, count={}, A_u16={}, B_u16={}, state={:02b}, invalid_skips={}".format(
            mode_names[encoding_mode], encoder_count, a_raw, b_raw, curr_state, invalid_skips
        ))
        last_telemetry = now

    time.sleep_ms(2)

