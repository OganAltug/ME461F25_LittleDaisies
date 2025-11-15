import network
import time
from umqtt.simple import MQTTClient
from machine import Pin, I2C
import ssd1306

# ---- OLED SETUP ----
i2c = I2C(1, scl=Pin(11), sda=Pin(10), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

def show(text1, text2):
    oled.fill(0)
    oled.text(text1, 0, 0)
    oled.text(text2, 0, 20)
    oled.show()

# ---- USER SETTINGS ----
WIFI_SSID = "YOUR_WIFI"
WIFI_PASS = "YOUR_PASSWORD"
BROKER_IP = "192.168.1.100"

MY_ID = "PICO_B"
MY_TOPIC = b"pico/B"
OTHER_TOPIC = b"pico/A"

# ---- WIFI ----
def wifi_connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    print("Connecting to WiFi", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print("\nConnected:", wlan.ifconfig())

# ---- CALLBACK ----
other_id = "WAITING..."

def on_msg(topic, msg):
    global other_id
    other_id = msg.decode()
    show("Me: " + MY_ID, "Other: " + other_id)

# ---- MAIN ----
def main():
    wifi_connect()

    client = MQTTClient("picoB", BROKER_IP)
    client.set_callback(on_msg)
    client.connect()
    client.subscribe(OTHER_TOPIC)

    while True:
        client.publish(MY_TOPIC, MY_ID)
        client.check_msg()
        show("Me: " + MY_ID, "Other: " + other_id)
        time.sleep(2)

main()
