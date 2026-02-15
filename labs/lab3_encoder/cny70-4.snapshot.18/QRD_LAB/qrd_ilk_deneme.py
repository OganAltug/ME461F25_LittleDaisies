from machine import ADC
import time
import sys

# --- 1. The Class Definition ---
class QrdSensor:
    def __init__(self, pin_number, threshold=30000, debounce_ms=50):
        # Initialize the sensor
        self.sensor = ADC(pin_number)
        self.threshold = threshold
        self.debounce_ms = debounce_ms
        
        # State tracking variables
        self.transition_count = 0
        self.last_state = False # Default assumption
        self.last_transition_time = 0
        
    def read_raw(self):
        return self.sensor.read_u16()

    def is_line(self):
        # Returns True for White (Line), False for Black
        return self.read_raw() < self.threshold

    def detect_transitions(self):
        current_state = self.is_line()
        current_time = time.ticks_ms()

        # Check if state changed
        if current_state != self.last_state:
            time_diff = time.ticks_diff(current_time, self.last_transition_time)
            
            if time_diff > self.debounce_ms:
                self.transition_count += 1
                self.last_transition_time = current_time
                self.last_state = current_state
        
        return self.transition_count

    def reset_count(self):
        self.transition_count = 0 

# --- 2. Function for Raw Data Mode ---
def run_raw_mode(sensor_obj):
    print("\n--- Running Raw Data Mode ---")
    print("Press Ctrl+C to Stop.")
    
    try:
        while True:
            raw_value = sensor_obj.read_raw()
            line_status = sensor_obj.is_line()
            status_text = "Line (White)" if line_status else "No Line (Black)"
            print(f"Raw: {raw_value:<5} | Status: {status_text}")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping...")

# --- 3. Function for Transition Counting Mode ---
def run_transition_mode(sensor_obj):
    print("\n--- Running Transition Count Mode ---")
    print("Press Ctrl+C to Stop.")
    
    sensor_obj.reset_count()
    
    try:
        while True:
            # We call this FAST (no sleep) to catch every edge
            count = sensor_obj.detect_transitions()
            
            # Print occasionally so we don't slow down the processor
            # (Only printing every 1000th loop or just continuously with a small delay)
            print(f"Transitions: {count} | Raw: {sensor_obj.read_raw()}")
            time.sleep(0.01) 
            
    except KeyboardInterrupt:
        print("\nStopping...")

# --- 4. Main Menu Logic ---
# Note: I changed debounce to 50ms and Threshold to 30000
my_sensor = QrdSensor(pin_number=28, threshold=30000, debounce_ms=50)

while True:
    print("\n=== MAIN MENU ===")
    print("1. Read Raw Sensor Data")
    print("2. Count Transitions")
    print("3. Exit")
    
    choice = input("Select (1-3): ")

    if choice == '1':
        run_raw_mode(my_sensor)
    elif choice == '2':
        run_transition_mode(my_sensor)
    elif choice == '3':
        break