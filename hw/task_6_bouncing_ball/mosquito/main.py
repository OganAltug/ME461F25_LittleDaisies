import network
import time
import json
import machine
from simple import MQTTClient
from machine import Pin, I2C
import ssd1306

# ============================================================
# 1. CONFIGURATION
# ============================================================

# !!! SET THIS DIFFERENT ON EACH PICO !!!
MY_ID = 0     # For Pico 1
# MY_ID = 1   # For Pico 2
# MY_ID = 2   # For Pico 3

WIFI_SSID = "Eren"
WIFI_PASS = "19981998"

# CHANGE THIS → your laptop/PC/IP running mosquitto
MQTT_SERVER = "10.42.0.1"

MQTT_CLIENT_ID = f"pico_display_{MY_ID}"

TOPIC_HEARTBEAT = "pico/heartbeat"
TOPIC_BALL_POS = "pico/ball_pos"

# Screen config (logical game grid)
SCREEN_HEIGHT = 16
SCREEN_WIDTH = 8

HEARTBEAT_INTERVAL_S = 1
PICO_TIMEOUT_S = 3.5
GAME_TICK_S = 0.1

# ============================================================
# 2. HARDWARE: OLED SETUP
# ============================================================

i2c = I2C(1, scl=Pin(11), sda=Pin(10), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

def oled_print(lines):
    oled.fill(0)
    
    oled.text(lines, 0, 12)
        
    oled.show()

def oled_draw_ball(global_x, global_y, order):
    oled.fill(0)

    if MY_ID not in order:
        oled.text("Inactive", 0, 0)
        oled.show()
        return

    my_index = order.index(MY_ID)
    my_min_col = my_index * SCREEN_WIDTH
    my_max_col = my_min_col + SCREEN_WIDTH - 1

    is_local = (my_min_col <= global_x <= my_max_col)
    local_x = global_x - my_min_col

    # convert grid coords to OLED coords
    if is_local:
        px = int((local_x / (SCREEN_WIDTH - 1)) * 120)
        py = int((global_y / 15) * 56)
        oled.fill_rect(px, py, 6, 6, 1)

    oled.text(f"ID:{MY_ID}", 0, 0)
    oled.text("Main" if i_am_main else "Follow", 70, 0)
    oled.show()

# ============================================================
# 3. GLOBAL STATE
# ============================================================

mqtt_client = None
led = machine.Pin("LED", machine.Pin.OUT)

active_picos = {}
i_am_main = False
last_drawn_state = {}

current_ball_state = {
    "pos": [0, 0],
    "vel": [1, 1],
    "total_size": [SCREEN_HEIGHT, SCREEN_WIDTH],
    "order": [MY_ID]
}

# ============================================================
# 4. NETWORK & MQTT FUNCTIONS
# ============================================================

def connect_wifi():
    oled_print(f"Connecting to Wi-Fi {WIFI_SSID} ...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)

    while not wlan.isconnected():
        oled_print("Waiting...")
        time.sleep(1)

    oled_print(f"WiFi connected:{wlan.ifconfig()}")

def mqtt_callback(topic, msg):
    global current_ball_state

    topic = topic.decode()
    data = json.loads(msg.decode())

    if topic == TOPIC_HEARTBEAT:
        active_picos[data["id"]] = time.time()

    elif topic == TOPIC_BALL_POS:
        current_ball_state = data


def connect_mqtt():
    global mqtt_client
    mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER)
    mqtt_client.set_callback(mqtt_callback)
    mqtt_client.connect()
    mqtt_client.subscribe(TOPIC_HEARTBEAT)
    mqtt_client.subscribe(TOPIC_BALL_POS)
    oled_print("MQTT connected.")

# ============================================================
# 5. GAME PHYSICS (MAIN PICO)
# ============================================================

def main_physics_loop():
    global current_ball_state

    active_ids = sorted(active_picos.keys())
    if not active_ids:
        return

    total_width = len(active_ids) * SCREEN_WIDTH
    total_height = SCREEN_HEIGHT

    pos = current_ball_state["pos"]
    vel = current_ball_state["vel"]

    # Move ball
    pos[0] = (pos[0] + vel[0]) % total_width
    pos[1] += vel[1]

    # Bounce vertically
    if pos[1] <= 0:
        pos[1] = 0
        vel[1] = -vel[1]

    if pos[1] >= total_height - 1:
        pos[1] = total_height - 1
        vel[1] = -vel[1]

    new_state = {
        "total_size": [total_height, total_width],
        "pos": pos,
        "vel": vel,
        "order": active_ids
    }

    mqtt_client.publish(TOPIC_BALL_POS, json.dumps(new_state))
    current_ball_state = new_state

# ============================================================
# 6. HEARTBEAT + PRUNE
# ============================================================

def publish_heartbeat():
    mqtt_client.publish(TOPIC_HEARTBEAT, json.dumps({"id": MY_ID}))

def prune_picos():
    now = time.time()
    for pid in list(active_picos.keys()):
        if now - active_picos[pid] > PICO_TIMEOUT_S:
            del active_picos[pid]

# ============================================================
# 7. DISPLAY LOGIC
# ============================================================

def update_display(ball_state):
    order = ball_state["order"]
    pos = ball_state["pos"]

    # Draw on OLED
    oled_draw_ball(pos[0], pos[1], order)


# ============================================================
# 8. MAIN LOOP
# ============================================================

def run():
    global i_am_main, last_drawn_state

    connect_wifi()
    connect_mqtt()

    last_hb = time.time()
    last_tick = time.time()

    while True:
        mqtt_client.check_msg()
        now = time.time()

        if now - last_hb > HEARTBEAT_INTERVAL_S:
            publish_heartbeat()
            last_hb = now

        prune_picos()

        if active_picos:
            active_ids = sorted(active_picos.keys())
            i_am_main = (MY_ID == active_ids[0])

            if i_am_main:
                if now - last_tick > GAME_TICK_S:
                    main_physics_loop()
                    last_tick = now

        if current_ball_state != last_drawn_state:
            update_display(current_ball_state)
            last_drawn_state = current_ball_state.copy()

        time.sleep(0.01)

# ============================================================
# 9. START
# ============================================================

run()

