from machine import Pin, PWM, ADC
import time

# --- Setup Motor Pins (Direction) ---
# Left Side (Motor A / LED Group 1)
in1 = Pin(0, Pin.OUT)
in2 = Pin(1, Pin.OUT)
# Right Side (Motor B / LED Group 2)
in3 = Pin(17, Pin.OUT)
in4 = Pin(16, Pin.OUT)


# --- Setup Switch Pins (Internal Pull-Up) ---
# When pressed, value is 0. When released, value is 1.
btn_forward = Pin(2, Pin.IN, Pin.PULL_UP)
btn_backward = Pin(3, Pin.IN, Pin.PULL_UP)


def stop_all():
    in1.low()
    in2.low()
    in3.low()
    in4.low()

def move_forward():
    # Polarity: Positive
    in1.high()
    in2.low()
    in3.high()
    in4.low()

def move_backward():
    # Polarity: Negative (Reversed)
    in1.low()
    in2.high()
    in3.low()
    in4.high()

# --- Main Loop ---
print("System Ready. Press buttons to control direction.")

while True:
    # Check if Button 1 (Forward) is pressed (Logic 0)
    if btn_forward.value() == 0:
        move_forward()
        print("Moving Forward (Red LEDs)")
        
    # Check if Button 2 (Backward) is pressed (Logic 0)
    elif btn_backward.value() == 0:
        move_backward()
        print("Moving Backward (Blue LEDs)")
        
    # If no button is pressed
    else:
        stop_all()

    time.sleep(0.1) # Short delay to prevent CPU overload