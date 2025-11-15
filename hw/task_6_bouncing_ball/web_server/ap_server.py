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

oled_print(["Pico A: Starting AP"])

# ========== WIFI AP SETUP ==========
SSID = 'Eren'
PASSWORD = '19981998'
PORT = 5000

ap = network.WLAN(network.AP_IF)
ap.config(essid=SSID, password=PASSWORD)
ap.active(True)

oled_print(["AP starting...", SSID])
while not ap.active():
    time.sleep(0.1)

ip = ap.ifconfig()[0]
oled_print(["AP Ready:", ip])

# ========== TCP SERVER ==========
addr = socket.getaddrinfo("0.0.0.0", PORT)[0][-1]
s = socket.socket()
s.bind(addr)
s.listen(1)

oled_print(["AP Ready:", ip, "Listening..."])

while True:
    oled_print(["Waiting client..."])
    conn, client_addr = s.accept()

    oled_print(["Client:", str(client_addr[0])])
    print("Client connected:", client_addr)

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                break

            msg = data.decode()
            print("Received:", msg)

            oled_print([
                "From Client:",
                msg[:16],
                msg[16:32]
            ])

            reply = "A says: " + msg
            conn.send(reply.encode())

    except Exception as e:
        print("Error:", e)

    conn.close()
    oled_print(["Client left"])

