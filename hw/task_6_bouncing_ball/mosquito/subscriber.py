import network
import time
from umqtt.simple import MQTTClient

WIFI_SSID = "YOUR_WIFI"
WIFI_PASS = "YOUR_PASSWORD"
BROKER_IP = "192.168.1.100"
TOPIC = b"pico/data"

# ---- WiFi ----
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    print("Connecting to WiFi", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print("\nConnected:", wlan.ifconfig())


# ---- Callback ----
def on_message(topic, msg):
    print("Received:", topic, msg)

# ---- Subscriber ----
def main():
    connect_wifi()

    client = MQTTClient("pico-subscriber", BROKER_IP)
    client.set_callback(on_message)
    client.connect()

    client.subscribe(TOPIC)
    print("Subscribed to:", TOPIC)

    while True:
        client.check_msg()   # non-blocking receive
        time.sleep(0.1)

main()
