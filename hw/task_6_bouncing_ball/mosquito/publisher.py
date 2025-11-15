import network
import time
from umqtt.simple import MQTTClient
import machine

WIFI_SSID = "YOUR_WIFI"
WIFI_PASS = "YOUR_PASSWORD"
BROKER_IP = "192.168.1.100"   # your Mosquitto broker
TOPIC = b"pico/data"

# ----- Connect to WiFi -----
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    print("Connecting to WiFi", end="")
    while not wlan.isconnected():
        print(".", end="")
        time.sleep(0.3)
    print("\nConnected:", wlan.ifconfig())


# ----- Publisher -----
def main():
    connect_wifi()
    client = MQTTClient("pico-publisher", BROKER_IP)
    client.connect()
    print("Connected to MQTT broker!")

    counter = 0
    while True:
        msg = "value:" + str(counter)
        client.publish(TOPIC, msg)
        print("Published:", msg)
        counter += 1
        time.sleep(2)

main()
