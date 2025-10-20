#for the wokwi files https://wokwi.com/projects/369228178686431233



from machine import Pin, ADC, PWM
from time import sleep, sleep_ms
import sys

#for temperature reading
import ds18x20
import onewire


# Define onboard LED (GP13 on Pico)
led_pin = 13
led = Pin(led_pin, Pin.OUT)

# Define ADC for onboard temperature sensor (ADC4)
sensor_temp = ADC(4)
conversion_factor = 3.3 / (65535)



# Define the DS18B20 data pin
DATA_PIN = machine.Pin(22)  # Use the GPIO pin you connected the sensor data pin to

# Create the onewire object
ds_sensor = ds18x20.DS18X20(onewire.OneWire(DATA_PIN))

# Scan for DS18B20 devices on the bus
roms = ds_sensor.scan()



# Heartbeat LED on GP15 (can use an external LED if you prefer)
heartbeat_led = PWM(Pin(15))
heartbeat_led.freq(1000)

def main_menu():
    print("\n==============================")
    print("      Raspberry Pi Pico")
    print("==============================")
    print("1. LED Blink")
    print("2. Heart Beat")
    print("3. Calculator")
    print("4. Display Onboard Temperature")
    print("5. Reverse the Given Text")
    print("==============================")
    selection = input("Enter your selection: ")
    return selection

def blink_led():
    try:
        num = input("Enter total number of blinks (or 'inf' for infinite): ")
        if num.lower() == 'inf':
            num = float('inf')
        else:
            num = int(num)

        dur = input("Enter duration of 1 blink in ms: ")
        dur = round(float(dur))

        print("Blinking started. Press Ctrl+C to stop.")
        count = 0
        while count < num:
            led.value(1)
            sleep_ms(dur)
            led.value(0)
            sleep_ms(dur)
            count += 1
    except KeyboardInterrupt:
        print("\nReturning to main menu...\n")
    except:
        print("Invalid input. Returning to main menu.")

def heartbeat():
    try:
        num = input("Enter total number of heartbeats (or 'inf' for infinite): ")
        if num.lower() == 'inf':
            num = float('inf')
        else:
            num = int(num)

        dur = input("Enter duration of 1 heartbeat in ms: ")
        dur = round(float(dur))

        print("Heartbeat started. Press Ctrl+C to stop.")
        count = 0
        while count < num:
            for duty in range(0, 65535, 1500):
                heartbeat_led.duty_u16(duty)
                sleep_ms(dur // 50)
            for duty in range(65535, 0, -1500):
                heartbeat_led.duty_u16(duty)
                sleep_ms(dur // 50)
            count += 1
        heartbeat_led.duty_u16(0)
    except KeyboardInterrupt:
        heartbeat_led.duty_u16(0)
        print("\nReturning to main menu...\n")
    except:
        print("Invalid input. Returning to main menu.")

def calculator():
    try:
        while True:
            expr = input("Enter an expression (Ctrl+C to exit): ")
            if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
                expr = expr[1:-1]
            try:
                result = eval(expr)
                print("Result:", result)
            except:
                print("Invalid expression.")
    except KeyboardInterrupt:
        print("\nReturning to main menu...\n")

#def temperature_display():
#    try:
#        print("Press Ctrl+C to stop.")
#        while True:
#            ds_sensor.convert_temp()
#            sleep(0.5)
#
#            for rom in roms:
#                temperature = ds_sensor.read_temp(rom)
#                print("Temperature: {:.2f}°C".format(temperature))
#            
#            sleep(1/3)  # update 3 times per second
#    except KeyboardInterrupt:
#        print("\nReturning to main menu...\n")


def temperature_display():
    try:
        print("Press Ctrl+C to stop.")
        while True:
            reading = sensor_temp.read_u16() * conversion_factor
            temperature = 27 - (reading - 0.706) / 0.001721
            print("Onboard Temperature: {:.2f} °C".format(temperature))
            sleep(1/3)  # update 3 times per second
    except KeyboardInterrupt:
        print("\nReturning to main menu...\n")
        

def reverse_text():
    try:
        while True:
            text = input("Enter text to reverse (Ctrl+C to exit): ")
            rev_text = "".join(reversed(text))
            print("Reversed:", rev_text)
    except KeyboardInterrupt:
        print("\nReturning to main menu...\n")

# ===== Main Loop =====
while True:
    choice = main_menu()
    if choice == '1':
        blink_led()
    elif choice == '2':
        heartbeat()
    elif choice == '3':
        calculator()
    elif choice == '4':
        temperature_display()
    elif choice == '5':
        reverse_text()
    else:
        print("Invalid selection. Try again.")