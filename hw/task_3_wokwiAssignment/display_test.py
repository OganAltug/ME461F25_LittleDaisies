import machine
import max7219
from machine import Pin
import _thread
import utime

onboard_led = Pin(25, Pin.OUT)
onboard_led.toggle()
def blink():
   while True:
       onboard_led.toggle()
       utime.sleep(0.5)
thread2 = _thread.start_new_thread(blink, ())

# Initialize SPI
spi = machine.SPI(0, baudrate=10000000, polarity=1, phase=0, sck=machine.Pin(2), mosi=machine.Pin(3))
# Initialize Chip Select
cs = machine.Pin(5, machine.Pin.OUT)
# Initialize the MAX7219 driver
display = max7219.Matrix8x8(spi, cs, 4)
# Clear the display
display.fill(0)
display.show()

# Display a single character
display.text('A', 0, 0, 1)
display.show()
