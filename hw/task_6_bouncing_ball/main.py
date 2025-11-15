import network
import time
import json
import machine
from umqtt.simple import MQTTClient

# --- 1. CORE CONFIGURATION ---
# !!! CHANGE THIS ON EACH PICO !!!
MY_ID = 0  # Pico 0
# MY_ID = 1  # Pico 1
# MY_ID = 2  # Pico 2

# -- Wi-Fi & MQTT Config --
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"
MQTT_SERVER = "YOUR_MOSQUITTO_BROKER_IP"
MQTT_CLIENT_ID = f"pico_display_{MY_ID}"

# -- MQTT Topics --
TOPIC_HEARTBEAT = "pico/heartbeat"
TOPIC_BALL_POS = "pico/ball_pos"

# -- Hardware & Physics --
# Back to your original 16x8 design
SCREEN_HEIGHT = 16
SCREEN_WIDTH = 8

# -- Timing --
HEARTBEAT_INTERVAL_S = 1.0
PICO_TIMEOUT_S = 3.5
GAME_TICK_S = 0.1

# --- 2. GLOBAL STATE VARIABLES ---
mqtt_client = None
led = machine.Pin("LED", machine.Pin.OUT)

active_picos = {}
i_am_main = False
# We use this to only print when the state changes
last_drawn_state = {} 

current_ball_state = {
    "pos": [0, 0],
    "vel": [1, 1],
    "total_size": [SCREEN_HEIGHT, SCREEN_WIDTH],
    "order": [MY_ID]
}

# --- 3. NETWORK & MQTT FUNCTIONS ---
def connect_wifi():
    print(f"Connecting to Wi-Fi: {WIFI_SSID}...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        print("...waiting for connection")
        led.toggle()
        time.sleep(1)
    print("Wi-Fi Connected!")
    print(f"IP: {wlan.ifconfig()[0]}")
    led.on()

def mqtt_callback(topic, msg):
    """
    Handles all incoming MQTT messages.
    This is kept as fast as possible. It only updates state variables.
    """
    global current_ball_state, active_picos
    
    topic_str = topic.decode('utf-8')
    
    try:
        data = json.loads(msg.decode('utf-8'))
        
        if topic_str == TOPIC_HEARTBEAT:
            pico_id = data.get("id")
            if pico_id is not None:
                active_picos[pico_id] = time.time()
                
        elif topic_str == TOPIC_BALL_POS:
            # Update the global state. The main loop will handle drawing.
            current_ball_state = data
            
    except Exception as e:
        print(f"Error in MQTT callback: {e}")

def connect_mqtt():
    global mqtt_client
    print("Connecting to MQTT server...")
    try:
        mqtt_client = MQTTClient(MQTT_CLIENT_ID, MQTT_SERVER, keepalive=60)
        mqtt_client.set_callback(mqtt_callback)
        mqtt_client.connect()
        mqtt_client.subscribe(TOPIC_HEARTBEAT)
        mqtt_client.subscribe(TOPIC_BALL_POS)
        print("MQTT Connected and Subscribed!")
    except Exception as e:
        print(f"MQTT Connection Failed: {e}. Rebooting in 5s.")
        time.sleep(5)
        machine.reset()

# --- 4. LOGIC & DISPLAY FUNCTIONS ---

def print_terminal_display(ball_state, is_on_my_screen, local_x, global_y):
    """
    Prints a 16x8 text representation of the screen to the terminal.
    """
    # Create a 16x8 buffer
    buf = [['.' for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]
    
    if is_on_my_screen:
        # Clamp coordinates just in case
        local_x = max(0, min(local_x, SCREEN_WIDTH - 1))
        global_y = max(0, min(global_y, SCREEN_HEIGHT - 1))
        buf[global_y][local_x] = 'O'
    
    # --- Print the display ---
    print(f"\n--- PICO {MY_ID} (Role: {'Main' if i_am_main else 'Follower'}) ---")
    for row in buf:
        print("".join(row))
        
    order = ball_state.get("order", [])
    pos = ball_state.get("pos", [])
    print(f"Pos: {pos} Order: {order}")
    print("--------------------------------")


def update_display(ball_state):
    """
    This is the FOLLOWER logic.
    It's called by the main loop when new ball data arrives.
    It calculates positions and prints to terminal.
    """
    try:
        order = ball_state.get("order", [])
        if MY_ID not in order:
            # We are not in the active list, do nothing
            return
            
        global_x, global_y = ball_state.get("pos", [0, 0])
        my_index = order.index(MY_ID)
        
        # Calculate our slice of the global screen
        my_min_col = my_index * SCREEN_WIDTH
        my_max_col = (my_index * SCREEN_WIDTH) + (SCREEN_WIDTH - 1)
        
        is_on_my_screen = (my_min_col <= global_x <= my_max_col)
        local_x = global_x - my_min_col
        
        # Always print to terminal
        print_terminal_display(ball_state, is_on_my_screen, local_x, global_y)
            
    except Exception as e:
        print(f"Error updating display: {e}")

def main_physics_loop():
    """
    This is the MAIN PICO logic.
    It reads the global state, updates it, and publishes.
    """
    global current_ball_state
    
    active_ids = sorted(active_picos.keys())
    if not active_ids: return 

    # Calculate total screen size based on active picos
    total_width = len(active_ids) * SCREEN_WIDTH
    total_height = SCREEN_HEIGHT # This is now 16
    
    # Read the last known state
    pos = current_ball_state["pos"]
    vel = current_ball_state["vel"]
    
    # Update Physics
    pos[0] = (pos[0] + vel[0]) % total_width # X wrap-around
    pos[1] = pos[1] + vel[1]                # Y move
    
    # Y-axis (with bounce at row 0 and 15)
    if pos[1] <= 0:
        pos[1] = 0
        vel[1] = -vel[1]
    elif pos[1] >= (total_height - 1): # Bounce at row 15
        pos[1] = total_height - 1
        vel[1] = -vel[1]
        
    # Create the new state message
    new_state = {
        "total_size": [total_height, total_width],
        "pos": pos,
        "vel": vel,
        "order": active_ids
    }
    
    try:
        mqtt_client.publish(
            TOPIC_BALL_POS,
            json.dumps(new_state),
            retain=True
        )
        # Immediately update our own state to avoid lag
        current_ball_state = new_state
        
    except Exception as e:
        print(f"Error publishing: {e}")

def publish_heartbeat():
    try:
        mqtt_client.publish(
            TOPIC_HEARTBEAT,
            json.dumps({"id": MY_ID})
        )
    except Exception as e:
        print(f"Error publishing heartbeat: {e}")

def prune_picos():
    global active_picos
    now = time.time()
    for pico_id in list(active_picos.keys()):
        if now - active_picos[pico_id] > PICO_TIMEOUT_S:
            print(f"Pico {pico_id} timed out. Removing.")
            del active_picos[pico_id]

# --- 5. MAIN EXECUTION ---
def run():
    global i_am_main, last_drawn_state
    
    led.on() # LED on during setup
    
    connect_wifi()
    connect_mqtt()
    
    last_heartbeat_time = 0
    last_physics_tick = 0
    
    print("--- Starting Main Loop ---")

    while True:
        try:
            # 1. Always check for incoming MQTT messages
            mqtt_client.check_msg()
            now = time.time()
            
            # 2. Publish heartbeat at a fixed interval
            if now - last_heartbeat_time > HEARTBEAT_INTERVAL_S:
                publish_heartbeat()
                last_heartbeat_time = now
                
            # 3. Prune disconnected picos
            prune_picos()
            
            # 4. Leader Election
            if not active_picos:
                time.sleep(0.1)
                continue
                
            active_ids = sorted(active_picos.keys())
            main_pico_id = active_ids[0]
            i_am_main = (MY_ID == main_pico_id)
            
            # 5. Act based on role
            if i_am_main:
                led.on() # Main pico has LED on
                # Run the physics loop if it's time
                if now - last_physics_tick > GAME_TICK_S:
                    main_physics_loop()
                    last_physics_tick = now
            else:
                led.off() # Follower pico has LED off
            
            # 6. Display Logic (Everyone does this)
            # Only update the terminal if the state has changed
            if current_ball_state != last_drawn_state:
                update_display(current_ball_state)
                # We must use a copy or it's just a reference
                last_drawn_state = current_ball_state.copy() 

            time.sleep(0.01)

        except Exception as e:
            print(f"Main loop error: {e}. Rebooting in 5s.")
            time.sleep(5)
            machine.reset()

if __name__ == "__main__":
    run()