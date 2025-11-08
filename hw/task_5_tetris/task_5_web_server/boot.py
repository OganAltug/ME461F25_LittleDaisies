# boot.py - Simple Wi-Fi connection setup
import network
import time

# --- Configuration ---
# Your Wi-Fi network name
ssid = 'YOUR_WIFI_NAME'
# Your Wi-Fi password
password = 'YOUR_WIFI_PASSWORD'
# ---------------------

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

print('Waiting for Wi-Fi connection...')
max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    time.sleep(1)

if wlan.status() != 3:
    print('Wi-Fi connection failed!')
else:
    status = wlan.ifconfig()
    print('Connected! Pico IP:', status[0])

# Do not run main.py automatically if it exists, let the user start the server manually
# exec(open('main.py').read())