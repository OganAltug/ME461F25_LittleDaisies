from machine import Pin, I2C
import ssd1306
import time

# Initialize I2C0 on GP4=SDA, GP5=SCL
i2c = I2C(1, scl=Pin(11), sda=Pin(10), freq=400000)

# Scan to confirm address (usually 0x3C)
print("I2C devices:", i2c.scan())

# Create display instance
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

# Clear screen
oled.fill(0)
oled.text("Hello, Pico W!", 0, 0)
oled.text("SSD1306 works!", 0, 16)
oled.show()

while True:
    for i in range(64):
        oled.scroll(0, 1)
        oled.show()
        time.sleep(0.05)

