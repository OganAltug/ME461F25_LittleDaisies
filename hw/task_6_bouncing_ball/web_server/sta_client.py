from machine import Pin, I2C
import network, socket, time
import ssd1306

# ========== OLED SETUP ==========
i2c = I2C(1, scl=Pin(11), sda=Pin(10), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

def oled_print(lines):
    oled.fill(0)
    y = 0
    for line in lines:
        oled.text(line, 0, y)
        y += 10
    oled.show()

oled_print(["Pico B:", "Connecting..."])

# ========== WIFI CLIENT SETUP ==========
SSID = 'Eren'
PASSWORD = '19981998'
PORT = 5000

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(SSID, PASSWORD)

while not wlan.isconnected():
    oled_print(["Pico B:", "Connecting..."])
    time.sleep(0.3)

ip, mask, gw, dns = wlan.ifconfig()
oled_print(["Connected!", "IP: " + ip])

server_ip = gw  # gateway = Pico A

# ========== TCP CLIENT ==========
addr = socket.getaddrinfo(server_ip, PORT)[0][-1]
s = socket.socket()

oled_print(["Connecting", "to server..."])
s.connect(addr)

# Send initial message
message = "Hello from Pico B!"
s.send(message.encode())
oled_print(["Sent:", "Hello from B"])

# Receive reply
data = s.recv(1024)
reply = data.decode()
oled_print(["Received:", reply[:16], reply[16:32]])

# Optional: Send periodic messages
count = 0
while True:
    txt = f"Msg {count} from B"
    s.send(txt.encode())
    data = s.recv(1024)

    oled_print([
        "Sent:",
        txt,
        "Recv:",
        data.decode()[:16]
    ])

    count += 1
    time.sleep(1)

