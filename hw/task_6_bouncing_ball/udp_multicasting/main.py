import network
import time
import json
import machine
import socket
import struct

# --- 1. CORE CONFIGURATION ---
# !!! CHANGE THIS ON EACH PICO !!!
MY_ID = 0  # Pico 0
# MY_ID = 1  # Pico 1
# MY_ID = 2  # Pico 2

# -- Wi-Fi Config --
WIFI_SSID = "Eren"
WIFI_PASS = "19981998"

# -- UDP Multicast "Topics" --
# We use one IP and two different ports
MULTICAST_GROUP = "239.1.1.1"
HEARTBEAT_PORT = 12345
BALL_POS_PORT = 12346

# -- Hardware & Physics --
SCREEN_HEIGHT = 16
SCREEN_WIDTH = 8

# -- Timing --
HEARTBEAT_INTERVAL_S = 1.0
PICO_TIMEOUT_S = 3.5
GAME_TICK_S = 0.1

# --- 2. GLOBAL STATE VARIABLES ---
led = machine.Pin("LED", machine.Pin.OUT)

# Sockets
send_sock = None
heartbeat_listen_sock = None
ball_pos_listen_sock = None

# State
active_picos = {}
i_am_main = False
last_drawn_state = {} 

# This state is now updated by *all* picos when they
# receive a ball_pos message. This is how state
# handover works without a "retain" flag.
current_ball_state = {
    "pos": [0, 0],
    "vel": [1, 1],
    "total_size": [SCREEN_HEIGHT, SCREEN_WIDTH],
    "order": [MY_ID]
}

# --- 3. NETWORK & SOCKET FUNCTIONS ---

def connect_wifi():
    print(f"Connecting to Wi-Fi: {WIFI_SSID}...")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    while not wlan.isconnected():
        print("...waiting for connection")
        led.toggle()
        time.sleep(1)
    
    ip_address = wlan.ifconfig()[0]
    print(f"Wi-Fi Connected! IP: {ip_address}")
    led.on()
    return ip_address

def setup_sockets(my_ip):
    global send_sock, heartbeat_listen_sock, ball_pos_listen_sock
    
    # 1. Create the sending socket
    print("Creating sending socket...")
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    # --- THIS IS THE FIX ---
    # Enable Multicast Loopback (IPPROTO_IP=0, IP_MULTICAST_LOOP=11, value=1)
    # This allows the Pico to receive its own sent packets, which is
    # crucial for the leader election to start.
    send_sock.setsockopt(socket.IPPROTO_IP, 11, 1)
    # --- END OF FIX ---
    
    # --- Manually create the mreq struct ---
    mcast_parts = [int(x) for x in MULTICAST_GROUP.split('.')]
    mcast_bytes = struct.pack("!4B", *mcast_parts)
    
    if_parts = [int(x) for x in my_ip.split('.')]
    if_bytes = struct.pack("!4B", *if_parts)

    mreq = mcast_bytes + if_bytes

    # 2. Create and configure the HEARTBEAT listening socket
    print(f"Binding to heartbeat group ({MULTICAST_GROUP}:{HEARTBEAT_PORT})")
    heartbeat_listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    heartbeat_listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    heartbeat_listen_sock.bind(("", HEARTBEAT_PORT))
    
    heartbeat_listen_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    heartbeat_listen_sock.setblocking(False) # NON-BLOCKING

    # 3. Create and configure the BALL POSITION listening socket
    print(f"Binding to ball position group ({MULTICAST_GROUP}:{BALL_POS_PORT})")
    ball_pos_listen_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ball_pos_listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    ball_pos_listen_sock.bind(("", BALL_POS_PORT))

    ball_pos_listen_sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    ball_pos_listen_sock.setblocking(False) # NON-BLOCKING

    print("Sockets configured successfully.")

def check_sockets():
    """Replaces the MQTT callback. Reads from all listening sockets."""
    global current_ball_state, active_picos
    
    # Check for Heartbeats
    try:
        data, addr = heartbeat_listen_sock.recvfrom(1024)
        msg = json.loads(data.decode('utf-8'))
        pico_id = msg.get("id")
        if pico_id is not None:
            active_picos[pico_id] = time.time()
            
    except OSError as e:
        if e.args[0] != 11: # 11 = EWOULDBLOCK (no data)
            print(f"Heartbeat socket error: {e}")
    except Exception as e:
        print(f"Error processing heartbeat: {e}")
        
    # Check for Ball Positions
    try:
        data, addr = ball_pos_listen_sock.recvfrom(1024)
        msg = json.loads(data.decode('utf-8'))
        # This is the core of the follower logic and state handover
        # Everyone updates their state from the main's message
        current_ball_state = msg
        
    except OSError as e:
        if e.args[0] != 11: # 11 = EWOULDBLOCK (no data)
            print(f"Ball position socket error: {e}")
    except Exception as e:
        print(f"Error processing ball position: {e}")


# --- 4. LOGIC & DISPLAY FUNCTIONS ---

def print_terminal_display(ball_state, is_on_my_screen, local_x, global_y):
    """Prints a 16x8 text representation of the screen to the terminal."""
    buf = [['.' for _ in range(SCREEN_WIDTH)] for _ in range(SCREEN_HEIGHT)]
    
    if is_on_my_screen:
        local_x = max(0, min(local_x, SCREEN_WIDTH - 1))
        global_y = max(0, min(global_y, SCREEN_HEIGHT - 1))
        buf[global_y][local_x] = 'O'
    
    print(f"\n--- PICO {MY_ID} (Role: {'Main' if i_am_main else 'Follower'}) ---")
    for row in buf:
        print("".join(row))
        
    order = ball_state.get("order", [])
    pos = ball_state.get("pos", [])
    print(f"Pos: {pos} Order: {order}")
    print("--------------------------------")

def update_display(ball_state):
    """Calculates positions and prints to terminal."""
    try:
        order = ball_state.get("order", [])
        if MY_ID not in order:
            return
            
        global_x, global_y = ball_state.get("pos", [0, 0])
        my_index = order.index(MY_ID)
        
        my_min_col = my_index * SCREEN_WIDTH
        my_max_col = (my_index * SCREEN_WIDTH) + (SCREEN_WIDTH - 1)
        
        is_on_my_screen = (my_min_col <= global_x <= my_max_col)
        local_x = global_x - my_min_col
        
        print_terminal_display(ball_state, is_on_my_screen, local_x, global_y)
            
    except Exception as e:
        print(f"Error updating display: {e}")

def main_physics_loop():
    """MAIN PICO logic: Calculates and SENDS the new state."""
    global current_ball_state
    
    active_ids = sorted(active_picos.keys())
    if not active_ids: return 

    total_width = len(active_ids) * SCREEN_WIDTH
    total_height = SCREEN_HEIGHT
    
    # Read the last known state (which was set by check_sockets)
    pos = current_ball_state["pos"]
    vel = current_ball_state["vel"]
    
    # Update Physics
    pos[0] = (pos[0] + vel[0]) % total_width
    pos[1] = pos[1] + vel[1]
    
    if pos[1] <= 0:
        pos[1] = 0
        vel[1] = -vel[1]
    elif pos[1] >= (total_height - 1):
        pos[1] = total_height - 1
        vel[1] = -vel[1]
        
    # Create the new state message
    new_state = {
        "total_size": [total_height, total_width],
        "pos": pos,
        "vel": vel,
        "order": active_ids
    }
    
    # "Publish" the new state to the multicast group
    try:
        message = json.dumps(new_state)
        send_sock.sendto(message.encode('utf-8'), (MULTICAST_GROUP, BALL_POS_PORT))
        
        # Since we are main, we also update our own state
        # immediately so we don't have to wait for the
        # message to loop back.
        current_ball_state = new_state
        
    except Exception as e:
        print(f"Error sending ball position: {e}")

def send_heartbeat():
    """Sends our heartbeat to the multicast group."""
    try:
        message = json.dumps({"id": MY_ID})
        send_sock.sendto(message.encode('utf-8'), (MULTICAST_GROUP, HEARTBEAT_PORT))
    except Exception as e:
        print(f"Error sending heartbeat: {e}")

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
    
    led.on()
    
    try:
        my_ip = connect_wifi()
        setup_sockets(my_ip)
    except Exception as e:
        print(f"Fatal network error: {e}. Rebooting in 5s.")
        time.sleep(5)
        machine.reset()
    
    last_heartbeat_time = 0
    last_physics_tick = 0
    
    print("--- Starting Main Loop (UDP Multicast) ---")

    while True:
        try:
            # 1. Always check for incoming messages
            check_sockets()
            
            now = time.time()
            
            # 2. Send heartbeat
            if now - last_heartbeat_time > HEARTBEAT_INTERVAL_S:
                send_heartbeat()
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
                led.on()
                if now - last_physics_tick > GAME_TICK_S:
                    main_physics_loop()
                    last_physics_tick = now
            else:
                led.off()
            
            # 6. Display Logic (Everyone does this)
            if current_ball_state != last_drawn_state:
                update_display(current_ball_state)
                last_drawn_state = current_ball_state.copy() 

            time.sleep(0.01)

        except Exception as e:
            print(f"Main loop error: {e}. Rebooting in 5s.")
            time.sleep(5)
            machine.reset()

if __name__ == "__main__":
    run()