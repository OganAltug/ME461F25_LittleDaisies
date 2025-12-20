from machine import Pin, PWM
import sys
import select

# --- Hardware Setup (Based on Script A) ---

# MOTOR 1 (Left)
# dig_8, dig_9 are direction pins. dig_10 is PWM speed.
m1_dir_a = Pin(12, Pin.OUT)
m1_dir_b = Pin(13, Pin.OUT)
m1_pwm = PWM(Pin(14))
m1_pwm.freq(50)        # Using 50Hz as established in your working code
m1_pwm.duty_u16(0)     # Ensure it starts off

# MOTOR 2 (Right)
# dig_19, dig_20 are direction pins. dig_21 is PWM speed.
m2_dir_a = Pin(19, Pin.OUT)
m2_dir_b = Pin(20, Pin.OUT)
m2_pwm = PWM(Pin(21))
m2_pwm.freq(50)        # Using 50Hz
m2_pwm.duty_u16(0)     # Ensure it starts off

# --- Global State Variables ---
current_speed_percent = 0
current_direction = "STOP" # STOP, FWD, BWD
active_motors = "BOTH"     # A, B, BOTH

def set_motor_state(dir_pin_a, dir_pin_b, pwm_pin, speed_percent, direction):
    """
    Controls the 3-pin motor driver logic.
    """
    # Convert percent (0-100) to u16 duty (0-65535)
    duty = int((speed_percent / 100) * 65535)
    
    if direction == "STOP":
        # Stop PWM and set logical low
        dir_pin_a.value(0)
        dir_pin_b.value(0)
        pwm_pin.duty_u16(0)
        
    elif direction == "FWD":
        # Direction Logic: A=1, B=0 (Adjust if wheel spins backwards)
        dir_pin_a.value(1)
        dir_pin_b.value(0)
        pwm_pin.duty_u16(duty)
        
    elif direction == "BWD":
        # Direction Logic: A=0, B=1
        dir_pin_a.value(0)
        dir_pin_b.value(1)
        pwm_pin.duty_u16(duty)

def update_motors():
    """
    Applies global state variables to physical motors
    """
    # --- Motor A Logic ---
    if active_motors in ["A", "BOTH"]:
        set_motor_state(m1_dir_a, m1_dir_b, m1_pwm, current_speed_percent, current_direction)
    else:
        # If motor not selected, force stop
        set_motor_state(m1_dir_a, m1_dir_b, m1_pwm, 0, "STOP")
        
    # --- Motor B Logic ---
    if active_motors in ["B", "BOTH"]:
        set_motor_state(m2_dir_a, m2_dir_b, m2_pwm, current_speed_percent, current_direction)
    else:
        set_motor_state(m2_dir_a, m2_dir_b, m2_pwm, 0, "STOP")

def parse_command(cmd_str):
    """
    Parses Serial commands from PC
    Expected format: "CMD:VALUE"
    """
    global current_speed_percent, current_direction, active_motors
    
    try:
        parts = cmd_str.strip().split(':')
        if len(parts) != 2:
            return

        key, val = parts[0], parts[1]

        if key == "SPD":
            current_speed_percent = int(val)
        
        elif key == "MOT":
            active_motors = val # A, B, or BOTH
        
        elif key == "DIR":
            # Update direction state
            if current_direction != "STOP":
                current_direction = val
        
        elif key == "ACT":
            if val == "STOP":
                current_direction = "STOP"
            elif val == "START":
                # Default to forward if just starting
                current_direction = "FWD" 
                
        # Apply changes immediately
        update_motors()
        print(f"ACK:{key}={val}") # Send acknowledgement back to PC
        
    except Exception as e:
        print(f"ERR:{e}")

# --- Main Loop ---
# Ensure motors are off at boot
update_motors()
print("Pico Ready. Waiting for Serial Commands...")

# Polling loop for Serial Data
while True:
    # Check if data is available on stdin (USB Serial)
    # This effectively waits for your PC Python script to send data
    if select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if line:
            parse_command(line)