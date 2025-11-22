from machine import ADC, Pin, PWM, mem32
import time
import uctypes
import array

# --- DEBUG ---
DEBUG_MODE = 1 

# --- HARDWARE CONSTANTS ---
ADC_BASE = 0x4004c000
ADC_CS = ADC_BASE + 0x00
ADC_RESULT = ADC_BASE + 0x04
ADC_FCS = ADC_BASE + 0x08
ADC_FIFO = ADC_BASE + 0x0C
ADC_DIV = ADC_BASE + 0x10

DMA_BASE = 0x50000000
DMA_CH0_READ_ADDR = DMA_BASE + 0x000
DMA_CH0_WRITE_ADDR = DMA_BASE + 0x004
DMA_CH0_TRANS_COUNT = DMA_BASE + 0x008
DMA_CH0_CTRL_TRIG = DMA_BASE + 0x00C

# --- CONFIGURATION ---
ADC_PIN_NUM = 26
PWM_PIN_NUM = 0   
SAMPLE_COUNT = 1000
# Set divider to 0 for max speed, or 96 for 1MS/s approx (96MHz clock)
# 0 is actually safe and provides 500kS/s standard max
ADC_CLK_DIV = 0   

TRIGGER_LEVEL_RAW = 2048 
TRIGGER_TIMEOUT_MS = 100 

TEST_FREQ = 1000
TEST_DUTY = 0.30

adc = ADC(ADC_PIN_NUM)
raw_buffer = array.array('H', (0 for _ in range(SAMPLE_COUNT)))

def start_signal_generator():
    pwm = PWM(Pin(PWM_PIN_NUM))
    pwm.freq(TEST_FREQ)
    pwm.duty_u16(int(TEST_DUTY * 65535))
    if DEBUG_MODE: print(f"[Info] PWM Started on GP{PWM_PIN_NUM}")

def init_hardware():
    mem32[ADC_DIV] = ADC_CLK_DIV << 8 
    mem32[ADC_CS] = (1 << 0) | (0 << 12) 

def software_trigger():
    mem32[ADC_FCS] = 0 
    mem32[ADC_CS] = (1 << 0) | (1 << 3) # START_MANY + EN
    
    timeout_start = time.ticks_ms()
    while (mem32[ADC_RESULT] & 0xFFF) > TRIGGER_LEVEL_RAW:
        if time.ticks_diff(time.ticks_ms(), timeout_start) > TRIGGER_TIMEOUT_MS:
            return 
    while (mem32[ADC_RESULT] & 0xFFF) < TRIGGER_LEVEL_RAW:
        if time.ticks_diff(time.ticks_ms(), timeout_start) > TRIGGER_TIMEOUT_MS:
            return 

def capture_dma():
    # 1. STOP ADC
    mem32[ADC_CS] = 0 
    
    # 2. DRAIN FIFO
    while (mem32[ADC_FCS] & (1 << 8)) == 0: 
        _ = mem32[ADC_FIFO]

    # 3. ENABLE FIFO & DREQ
    # !!! THE FIX IS HERE !!!
    # We need Bit 24 (THRESH=1), Bit 3 (DREQ_EN), Bit 0 (EN)
    # (1 << 24) | (1 << 3) | (1 << 0) = 0x01000009
    mem32[ADC_FCS] = 0x01000009 
    
    # 4. CONFIGURE DMA
    mem32[DMA_CH0_READ_ADDR] = ADC_FIFO
    mem32[DMA_CH0_WRITE_ADDR] = uctypes.addressof(raw_buffer)
    mem32[DMA_CH0_TRANS_COUNT] = SAMPLE_COUNT
    
    dreq_adc = 36
    ctrl_val = 1 | (1 << 2) | (1 << 4) | (dreq_adc << 15)
    mem32[DMA_CH0_CTRL_TRIG] = ctrl_val 

    # 5. RESTART ADC
    mem32[ADC_CS] = 0x009 

    # 6. WAIT FOR DMA
    start_wait = time.ticks_ms()
    while mem32[DMA_CH0_CTRL_TRIG] & (1 << 24):
        if time.ticks_diff(time.ticks_ms(), start_wait) > 1000:
            if DEBUG_MODE: print("[Error] DMA Hardware Stuck!")
            break
        
    # 7. CLEANUP
    mem32[ADC_CS] = 0   
    mem32[ADC_FCS] = 0 

def analyze_and_send():
    if DEBUG_MODE: print("\n--- Step 1: Waiting for Trigger ---")
    software_trigger()
    
    if DEBUG_MODE: print("--- Step 2: Capturing DMA ---")
    start_t = time.ticks_us()
    capture_dma()
    end_t = time.ticks_us()
    
    # --- METRICS ---
    duration_s = time.ticks_diff(end_t, start_t) / 1_000_000
    if duration_s <= 0: duration_s = 0.0001
    sample_rate = SAMPLE_COUNT / duration_s
    
    v_max_raw = 0
    v_min_raw = 4095
    v_sum_raw = 0
    
    for val in raw_buffer:
        if val > v_max_raw: v_max_raw = val
        if val < v_min_raw: v_min_raw = val
        v_sum_raw += val
        
    CONV = 3.3 / 4095
    v_pp = (v_max_raw - v_min_raw) * CONV
    v_avg = (v_sum_raw / SAMPLE_COUNT) * CONV
    
    mid = (v_max_raw + v_min_raw) // 2
    edges = 0
    first_edge = 0
    last_edge = 0
    state = 0
    high_samples = 0
    
    for i in range(SAMPLE_COUNT):
        val = raw_buffer[i]
        if val > mid: high_samples += 1
        if state == 0 and val > mid:
            state = 1
            edges += 1
            if edges == 1: first_edge = i
            last_edge = i
        elif state == 1 and val < mid:
            state = 0
            
    freq = 0
    if edges > 1:
        period_samples = (last_edge - first_edge) / (edges - 1)
        period_s = period_samples / sample_rate
        if period_s > 0: freq = 1 / period_s
        
    duty = (high_samples / SAMPLE_COUNT) * 100

    if DEBUG_MODE:
        print(f"--- Step 3: Results ---")
        print(f"Captured {SAMPLE_COUNT} samples in {duration_s*1000:.3f} ms")
        print(f"Sample Rate: {sample_rate/1000:.1f} kS/s")
        print(f"Vpp:  {v_pp:.2f} V")
        print(f"Freq: {freq:.1f} Hz")
        print(f"Duty: {duty:.1f} %")
        print(f"First 5 Raw: {[raw_buffer[i] for i in range(5)]}")
        time.sleep(1)
    else:
        print(f"METRICS:{v_pp:.2f},{freq:.1f},{duty:.1f},{v_avg:.2f}|DATA:", end="")
        for i in range(SAMPLE_COUNT):
            if i > 0: print(",", end="")
            print(raw_buffer[i], end="")
        print("")

init_hardware()
start_signal_generator()
print("Pico Scope Ready.")
while True:
    analyze_and_send()