# pc_tetris_client.py
# PC Client for Pico Tetris
# Requires: pip install pygame pyserial

import pygame
import serial
import socket
import time
import sys
import json
import threading
import queue

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

# --- Serial (USB) Config ---
# Find your Pico's COM port (e.g., 'COM3' on Windows, '/dev/ttyACM0' on Linux)
SERIAL_PORT = "/dev/ttyACM0"  # CHANGE THIS
SERIAL_BAUDRATE = 115200

# --- WiFi Config ---
# This MUST match the IP your Pico gets from DHCP or its static IP
PICO_IP = ""  # CHANGE THIS
PICO_PORT = 8080

# --- Pygame Config ---
GRID_WIDTH = 16
GRID_HEIGHT = 32
BLOCK_SIZE = 20  # Size of each block in pixels
BORDER_SIZE = 1

# Calculate window size
GAME_AREA_WIDTH = (BLOCK_SIZE + BORDER_SIZE) * GRID_WIDTH + BORDER_SIZE
GAME_AREA_HEIGHT = (BLOCK_SIZE + BORDER_SIZE) * GRID_HEIGHT + BORDER_SIZE

INFO_PANEL_WIDTH = 200
WINDOW_WIDTH = GAME_AREA_WIDTH + INFO_PANEL_WIDTH
WINDOW_HEIGHT = GAME_AREA_HEIGHT

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GRID = (40, 40, 40)
COLOR_P1 = (255, 87, 34)   # Deep Orange
COLOR_P2 = (33, 150, 243)  # Blue
COLOR_STATIC = (158, 158, 158) # Grey
COLOR_BG = (10, 10, 10)

# Color map for grid values
COLOR_MAP = {
    0: COLOR_BG,
    1: COLOR_P1,
    2: COLOR_P2,
    3: COLOR_STATIC
}

# ---------------------------------------------------------------
# Tetromino Mini-Display
# ---------------------------------------------------------------

# Shapes for the "Next" display
TETROMINOES = {
    'O': [(0, 0), (1, 0), (0, 1), (1, 1)],
    'I': [(0, 1), (1, 1), (2, 1), (3, 1)],
    'S': [(1, 0), (2, 0), (0, 1), (1, 1)],
    'Z': [(0, 0), (1, 0), (1, 1), (2, 1)],
    'L': [(0, 1), (1, 1), (2, 1), (2, 0)],
    'J': [(0, 1), (1, 1), (2, 1), (0, 0)],
    'T': [(1, 1), (0, 1), (2, 1), (1, 0)]
}

def draw_mini_shape(surface, shape_key, x_offset, y_offset):
    """Draws a small shape in the info panel."""
    if not shape_key or shape_key not in TETROMINOES:
        return
        
    shape = TETROMINOES[shape_key]
    mini_block_size = 10
    
    for (px, py) in shape:
        # Center the 4x4 shape in the area
        draw_x = x_offset + px * (mini_block_size + 1)
        draw_y = y_offset + py * (mini_block_size + 1)
        pygame.draw.rect(surface, COLOR_STATIC, 
                         (draw_x, draw_y, mini_block_size, mini_block_size))

# ---------------------------------------------------------------
# Communication Thread
# ---------------------------------------------------------------

class CommunicationThread(threading.Thread):
    """Handles all serial/socket communication in a separate thread."""
    def __init__(self, mode, input_queue, output_queue):
        super().__init__(daemon=True)
        self.mode = mode
        self.input_q = input_queue  # Data from Pico (game state)
        self.output_q = output_queue # Data to Pico (key presses)
        self.connection = None
        self.running = True

    def connect(self):
        """Establish the connection."""
        if self.mode == "USB":
            try:
                # Note: The port was already opened by send_mode_to_pico
                # It should be free now.
                self.connection = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=0.1)
                print(f"Connected to {SERIAL_PORT}")
                return True
            except serial.SerialException as e:
                print(f"Error connecting to {SERIAL_PORT}: {e}")
                return False
        
        elif self.mode == "WIFI":
            try:
                self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connection.settimeout(5.0) # Longer timeout for initial connect
                self.connection.connect((PICO_IP, PICO_PORT))
                self.connection.settimeout(0.1) # Set back to non-blocking
                print(f"Connected to {PICO_IP}:{PICO_PORT}")
                return True
            except socket.error as e:
                print(f"Error connecting to {PICO_IP}: {e}")
                return False
        return False

    def run(self):
        """Main loop for the thread."""
        if not self.connect():
            self.input_q.put({"error": "Connection Failed"})
            return
            
        buffer = ""
        while self.running:
            # 1. Send data to Pico
            try:
                while not self.output_q.empty():
                    key_press = self.output_q.get_nowait()
                    if self.mode == "USB":
                        self.connection.write(key_press.encode('utf-8'))
                    elif self.mode == "WIFI":
                        self.connection.sendall(key_press.encode('utf-8'))
            except Exception as e:
                print(f"Error sending data: {e}")
                self.running = False
                break

            # 2. Receive data from Pico
            try:
                if self.mode == "USB":
                    # Read all available bytes
                    bytes_waiting = self.connection.in_waiting
                    if bytes_waiting > 0:
                        raw_data = self.connection.read(bytes_waiting)
                        buffer += raw_data.decode('utf-8', errors='ignore')
                    
                    # Process buffer line by line
                    if '\n' in buffer:
                        data, buffer = buffer.split('\n', 1)
                        data = data.strip()
                    else:
                        data = None

                elif self.mode == "WIFI":
                    # Read until newline
                    buffer += self.connection.recv(1024).decode('utf-8')
                    if '\n' in buffer:
                        data, buffer = buffer.split('\n', 1)
                        data = data.strip()
                    else:
                        data = None
                
                if data:
                    try:
                        # Pico sends JSON strings
                        game_state = json.loads(data)
                        self.input_q.put(game_state)
                    except json.JSONDecodeError:
                        # Pico might also send debug print()s. Ignore them.
                        print(f"Pico debug: {data}")
                        pass
                        
            except serial.SerialTimeoutException:
                    pass # Normal timeout
            except socket.timeout:
                pass # Normal timeout
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.running = False
        
        # Cleanup
        if self.connection:
            self.connection.close()
        print("Communication thread stopped.")

# ---------------------------------------------------------------
# Main Pygame Class
# ---------------------------------------------------------------

class PygameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pico Tetris - 2 Player")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont(None, 50)
        self.font_medium = pygame.font.SysFont(None, 30)
        self.font_small = pygame.font.SysFont(None, 25)
        
        self.comm_mode = self.show_menu()
        if self.comm_mode is None:
            sys.exit()
            
        self.error_message = None
        
        # --- NEW: Send mode to Pico first ---
        if not self.send_mode_to_pico(self.comm_mode):
            # Error message is set by the function
            self.error_message = self.error_message or "Failed to contact Pico on USB"
        # ---
        
        self.game_state_q = queue.Queue()
        self.input_q = queue.Queue()
        
        self.comm_thread = CommunicationThread(self.comm_mode, self.game_state_q, self.input_q)
        if self.error_message is None:
            self.comm_thread.start()
        
        self.current_state = {
            "grid": [0] * (GRID_WIDTH * GRID_HEIGHT),
            "score": 0,
            "p1_next": "",
            "p2_next": "",
            "game_over": False,
            "paused": False
        }

    def show_menu(self):
        """Displays a menu to select connection mode."""
        title_text = self.font_big.render("Pico Tetris", True, COLOR_WHITE)
        usb_text = self.font_medium.render("1: Play over USB", True, COLOR_WHITE)
        wifi_text = self.font_medium.render("2: Play over WiFi", True, COLOR_WHITE)
        
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_1:
                        return "USB"
                    if event.key == pygame.K_2:
                        return "WIFI"

            self.screen.fill(COLOR_BG)
            self.screen.blit(title_text, (WINDOW_WIDTH // 2 - title_text.get_width() // 2, 100))
            self.screen.blit(usb_text, (WINDOW_WIDTH // 2 - usb_text.get_width() // 2, 200))
            self.screen.blit(wifi_text, (WINDOW_WIDTH // 2 - wifi_text.get_width() // 2, 250))
            pygame.display.flip()
            self.clock.tick(15)

    def send_mode_to_pico(self, mode):
        """Sends the initial mode selection to the Pico over USB."""
        print(f"Sending {mode} command to Pico via USB...")
        try:
            # Open a temporary serial connection for the handshake
            temp_ser = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=2, write_timeout=2)
            
            if mode == "USB":
                temp_ser.write(b"MODE_USB\n")
            elif mode == "WIFI":
                temp_ser.write(b"MODE_WIFI\n")
            
            temp_ser.flush()
            time.sleep(0.5) # Give Pico time to process the command
            temp_ser.close()
            print("Mode command sent. Pico should be configured.")
            return True
        except serial.SerialException as e:
            print(f"CRITICAL: Could not send mode to Pico: {e}")
            print("Is the Pico connected and running the code?")
            self.error_message = "Failed to contact Pico on USB."
            return False
        except Exception as e:
            print(f"An unexpected error occurred during handshake: {e}")
            self.error_message = "Pico handshake error."
            return False

    def run_game(self):
        """Main game loop for Pygame."""
        running = True
        while running:
            # 1. Handle Pygame Events (Input)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)
            
            # 2. Get Game State from Pico
            try:
                while not self.game_state_q.empty():
                    new_state = self.game_state_q.get_nowait()
                    if "error" in new_state:
                        self.error_message = new_state["error"]
                    else:
                        self.current_state = new_state
            except queue.Empty:
                pass
                
            if not self.comm_thread.is_alive() and not self.error_message:
                # If the thread dies and we don't have an error, set one.
                if self.current_state.get("game_over") or self.current_state.get("paused"):
                     # If game is paused/over, thread might close normally
                     pass
                else:
                    self.error_message = "Connection Lost"
                
            # 3. Draw Everything
            self.draw()
            
            self.clock.tick(60) # Run at 60 FPS
            
        # Stop thread and quit
        self.comm_thread.running = False
        self.comm_thread.join(timeout=1)
        pygame.quit()
        if self.error_message:
            print(f"Exiting due to error: {self.error_message}")

    def handle_keydown(self, key):
        """Map pygame keys to single-char commands for Pico."""
        
        # --- NEW: Pause Menu Input ---
        if self.current_state.get("paused", False):
            if key == pygame.K_1:
                self.input_q.put('1') # Resume
                return
            if key == pygame.K_2:
                self.input_q.put('2') # Restart
                return
            if key == pygame.K_3:
                self.input_q.put('3') # Main Menu
                return
            if key == pygame.K_p:
                self.input_q.put('p') # Resume (also 'p')
                return
        
        # --- Pause Toggle ---
        if key == pygame.K_p:
            self.input_q.put('p')
            return

        # --- Player Game Input ---
        key_map = {
            # Player 1
            pygame.K_w: 'w',
            pygame.K_a: 'a',
            pygame.K_s: 's',
            pygame.K_d: 'd',
            
            # Player 2
            pygame.K_UP:    'u',
            pygame.K_LEFT:  'l',
            pygame.K_DOWN:  'n',
            pygame.K_RIGHT: 'r',
        }
        if key in key_map:
            self.input_q.put(key_map[key])

    def draw(self):
        """Draw the entire game screen."""
        self.screen.fill(COLOR_BG)
        
        self.draw_grid()
        self.draw_info_panel()
        
        # --- NEW: Handle Overlays ---
        if self.current_state.get("paused", False):
            self.draw_pause_menu()
        elif self.current_state.get("game_over", False):
            self.draw_game_over()
            
        if self.error_message:
            self.draw_error()

        pygame.display.flip()

    def draw_grid(self):
        """Draw the 16x32 game grid."""
        grid_data = self.current_state["grid"]
        
        for i in range(len(grid_data)):
            x = i % GRID_WIDTH
            y = i // GRID_WIDTH
            
            color = COLOR_MAP.get(grid_data[i], COLOR_BLACK)
            
            # Calculate position
            draw_x = (BLOCK_SIZE + BORDER_SIZE) * x + BORDER_SIZE
            draw_y = (BLOCK_SIZE + BORDER_SIZE) * y + BORDER_SIZE
            
            pygame.draw.rect(self.screen, color, 
                             (draw_x, draw_y, BLOCK_SIZE, BLOCK_SIZE))
                             
    def draw_info_panel(self):
        """Draw the side panel with score and next pieces."""
        panel_x = GAME_AREA_WIDTH
        
        # --- Score ---
        score_text = self.font_big.render("SCORE", True, COLOR_WHITE)
        score_val = self.font_big.render(str(self.current_state["score"]), True, COLOR_WHITE)
        
        self.screen.blit(score_text, (panel_x + (INFO_PANEL_WIDTH - score_text.get_width()) // 2, 50))
        self.screen.blit(score_val, (panel_x + (INFO_PANEL_WIDTH - score_val.get_width()) // 2, 100))

        # --- Player 1 Next ---
        p1_text = self.font_medium.render("P1 Next", True, COLOR_P1)
        self.screen.blit(p1_text, (panel_x + (INFO_PANEL_WIDTH - p1_text.get_width()) // 2, 200))
        draw_mini_shape(self.screen, self.current_state.get("p1_next", ""), 
                        panel_x + (INFO_PANEL_WIDTH // 2) - (2 * 11), 240) # Center shape

        # --- Player 2 Next ---
        p2_text = self.font_medium.render("P2 Next", True, COLOR_P2)
        self.screen.blit(p2_text, (panel_x + (INFO_PANEL_WIDTH - p2_text.get_width()) // 2, 350))
        draw_mini_shape(self.screen, self.current_state.get("p2_next", ""), 
                        panel_x + (INFO_PANEL_WIDTH // 2) - (2 * 11), 390) # Center shape

    def draw_game_over(self):
        """Display a 'Game Over' overlay."""
        overlay = pygame.Surface((GAME_AREA_WIDTH, 200), pygame.SRCALPHA)
        overlay.fill((50, 50, 50, 200)) # Semi-transparent grey
        
        text1 = self.font_big.render("GAME OVER", True, COLOR_WHITE)
        text2 = self.font_medium.render("Pico will restart game", True, COLOR_WHITE)
        
        overlay.blit(text1, ( (GAME_AREA_WIDTH - text1.get_width()) // 2, 50) )
        overlay.blit(text2, ( (GAME_AREA_WIDTH - text2.get_width()) // 2, 120) )
        
        self.screen.blit(overlay, (0, (GAME_AREA_HEIGHT - 200) // 2))

    def draw_pause_menu(self):
        """Display the interactive pause menu."""
        overlay = pygame.Surface((GAME_AREA_WIDTH, 300), pygame.SRCALPHA)
        overlay.fill((50, 50, 50, 220)) # Semi-transparent grey
        
        text1 = self.font_big.render("PAUSED", True, COLOR_WHITE)
        text2 = self.font_medium.render("1: Resume (or P)", True, COLOR_WHITE)
        text3 = self.font_medium.render("2: Restart", True, COLOR_WHITE)
        text4 = self.font_medium.render("3: Main Menu", True, COLOR_WHITE)
        
        overlay.blit(text1, ( (GAME_AREA_WIDTH - text1.get_width()) // 2, 50) )
        overlay.blit(text2, ( (GAME_AREA_WIDTH - text2.get_width()) // 2, 120) )
        overlay.blit(text3, ( (GAME_AREA_WIDTH - text3.get_width()) // 2, 160) )
        overlay.blit(text4, ( (GAME_AREA_WIDTH - text4.get_width()) // 2, 200) )
        
        self.screen.blit(overlay, (0, (GAME_AREA_HEIGHT - 300) // 2))

    def draw_error(self):
        """Display an error message."""
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((100, 0, 0, 220)) # Semi-transparent red
        
        text1 = self.font_big.render("ERROR", True, COLOR_WHITE)
        text2 = self.font_medium.render(self.error_message, True, COLOR_WHITE)
        text3 = self.font_small.render("Check Pico connection andSERIAL_PORT.", True, COLOR_WHITE)
        text4 = self.font_small.render("Restart both Pico and PC client.", True, COLOR_WHITE)
        
        overlay.blit(text1, ( (WINDOW_WIDTH - text1.get_width()) // 2, 100) )
        overlay.blit(text2, ( (WINDOW_WIDTH - text2.get_width()) // 2, 200) )
        overlay.blit(text3, ( (WINDOW_WIDTH - text3.get_width()) // 2, 250) )
        overlay.blit(text4, ( (WINDOW_WIDTH - text4.get_width()) // 2, 280) )
        
        self.screen.blit(overlay, (0, 0))

# ---------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------

if __name__ == "__main__":
    # --- Instructions ---
    print("--- PC Tetris Client ---")
    print(f"Ensure your Pico is connected to: {SERIAL_PORT}")
    print("Run 'pico_tetris_main.py' on the Pico FIRST.")
    print("The Pico will wait for this client to start.")
    print("-" * 26)

    client = PygameClient()
    client.run_game()