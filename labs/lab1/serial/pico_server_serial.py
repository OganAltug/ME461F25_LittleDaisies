from machine import Pin, PWM
import sys
import select

# --- Setup Motor Pins with PWM ---
# We use PWM to control speed. 
# Frequency of 1000Hz is standard for DC motors.

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
        # If motor not selected, stop it
        set_motor_speed(in1, in2, 0, "STOP")
        
    # Motor B Logic
    if active_motors in ["B", "BOTH"]:
        set_motor_speed(in3, in4, current_speed_percent, current_direction)
    else:
        set_motor_speed(in3, in4, 0, "STOP")

def parse_command(cmd_str):
    """
    Expected format: "CMD:VALUE"
    Examples: "SPD:50", "DIR:FWD", "MOT:A", "ACT:START", "ACT:STOP"
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
            # Only update direction if we are currently moving? 
            # Or just set state. Let's set state, logic handles it.
            if current_direction != "STOP":
                current_direction = val
        elif key == "ACT":
            if val == "STOP":
                current_direction = "STOP"
            elif val == "START":
                # Default to forward if just starting
                current_direction = "FWD" 
                
        update_motors()
        print(f"ACK:{key}={val}") # Send acknowledgement back to PC
        
    except Exception as e:
        print(f"ERR:{e}")

# --- Main Loop ---
print("Pico Ready. Waiting for Serial Commands...")

# Polling loop for Serial Data
while True:
    # Check if data is available on stdin (USB Serial)
    if select.select([sys.stdin], [], [], 0)[0]:
        line = sys.stdin.readline()
        if line:
            parse_command(line)
            
    # No sleep needed here as select is non-blocking but efficient







    