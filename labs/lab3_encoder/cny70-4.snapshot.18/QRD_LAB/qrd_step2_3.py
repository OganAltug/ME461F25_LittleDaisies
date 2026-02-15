from machine import Pin
import time
import sys

# --- 1. The Class Definition (Digital Version) ---
class QrdSensor:
    def __init__(self, pin_number, debounce_ms=50):
        """
        :param pin_number: GPIO pin (e.g., 27).
        :param debounce_ms: Minimum time (ms) between counts to prevent noise.
        """
        # Configure as Digital Input with Pull-Up resistor to stabilize signal
        self.sensor_pin = Pin(pin_number, Pin.IN, Pin.PULL_UP)
        self.debounce_ms = debounce_ms
        
        # State tracking variables
        self.transition_count = 0
        self.last_transition_time = 0
        
        # ACTIVATE INTERRUPT
        # This tells the Pico: "When voltage changes (Rise or Fall), run _handle_interrupt"
        self.sensor_pin.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self._handle_interrupt)

    def _handle_interrupt(self, pin):
        """
        INTERNAL FUNCTION. Do not call manually.
        This runs automatically when the hardware detects a change.
        """
        current_time = time.ticks_ms()
        
        # Debounce Logic: Check if enough time passed since last valid signal
        if time.ticks_diff(current_time, self.last_transition_time) > self.debounce_ms:
            self.transition_count += 1
            self.last_transition_time = current_time

    def read_current_state(self):
        # Returns 1 (High) or 0 (Low)
        return self.sensor_pin.value()

    def get_count(self):
        # Returns the count tracked by the interrupt
        return self.transition_count

    def reset_count(self):
        self.transition_count = 0 

# --- 2. Function for Raw Data Mode ---
def run_raw_mode(sensor_obj):
    print("\n--- Running Raw Data Mode (Digital) ---")
    print("Press Ctrl+C to Stop and return to menu.")
    print("Adjust your Potentiometer until you see clear 0 and 1 changes!")
    
    try:
        while True:
            # Reads 0 or 1
            val = sensor_obj.read_current_state()
            
            # Interpretation depends on your wiring, but usually:
            # 1 = High Voltage (Black/Reflection Blocked)
            # 0 = Low Voltage (White/Reflection Active)
            status_text = "High (Black?)" if val == 1 else "Low (White?)"
            
            print(f"Digital State: {val} | {status_text}")
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nStopping Raw Mode...")

# --- 3. Function for Transition Counting Mode ---
def run_transition_mode(sensor_obj):
    print("\n--- Running Transition Count Mode (Interrupts) ---")
    print("Press Ctrl+C to Stop and return to menu.")
    
    sensor_obj.reset_count()
    
    try:
        while True:
            # NOTICE: We are NOT calling a detect function here.
            # We are just asking "What is the count right now?"
            # The interrupt is doing the work in the background!
            current_count = sensor_obj.get_count()
            current_state = sensor_obj.read_current_state()
            
            print(f"Transitions: {current_count} | Current State: {current_state}")
            
            # We can sleep for a long time (0.5s) and we WON'T miss counts
            # because the interrupt handles them instantly.
            time.sleep(0.1) 
            
    except KeyboardInterrupt:
        print("\nStopping Transition Mode...")

# --- 4. Main Menu Logic ---

# Initialize on Pin 27 (Digital Mode)
# debounce_ms=50 is standard. Increase to 200 if you get "double counts".
my_sensor = QrdSensor(pin_number=28, debounce_ms=1000)

while True:
    print("\n" + "="*30)
    print(" MAIN MENU (DIGITAL INTERRUPT)")
    print("="*30)
    print("1. Read Digital State (0/1)")
    print("2. Count Transitions (Interrupt)")
    print("3. Exit Program")
    
    choice = input("Enter selection (1-3): ")

    if choice == '1':
        run_raw_mode(my_sensor)
    elif choice == '2':
        run_transition_mode(my_sensor)
    elif choice == '3':
        # Disable interrupt before exiting to be clean
        my_sensor.sensor_pin.irq(handler=None)
        print("Exiting program. Goodbye!")
        break
    else:
        print("Invalid selection.")