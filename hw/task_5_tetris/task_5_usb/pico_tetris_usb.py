# pico_tetris_usb.py
# MicroPython code for Raspberry Pi Pico W
# Runs the Tetris game logic and acts as a server for the PC client.
# --- USB-ONLY VERSION ---

import machine
import time
import sys
import select
import random
# import network # No longer needed
# import socket # No longer needed
import ujson

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

# --- WiFi Config (REMOVED) ---

# --- Display Config ---
DISPLAY_WIDTH = 16
DISPLAY_HEIGHT = 32

# --- SPI Config for MAX7219 ---
SPI_BUS = 0
SPI_SCK_PIN = machine.Pin(10)
SPI_MOSI_PIN = machine.Pin(11)
SPI_CS_PIN = machine.Pin(9) # Use GP9 for CS
NUM_MATRICES = 8 

# --- Game Config ---
GAME_TICK_RATE = 0.5 
PLAYER_1_COLOR = 1 
PLAYER_2_COLOR = 2 
STATIC_COLOR = 3 

# Tetromino shapes (O, I, S, Z, L, J, T)
TETROMINOES = {
    'O': [(0, 0), (1, 0), (0, 1), (1, 1)],
    'I': [(0, 1), (1, 1), (2, 1), (3, 1)],
    'S': [(1, 0), (2, 0), (0, 1), (1, 1)],
    'Z': [(0, 0), (1, 0), (1, 1), (2, 1)],
    'L': [(0, 1), (1, 1), (2, 1), (2, 0)],
    'J': [(0, 1), (1, 1), (2, 1), (0, 0)],
    'T': [(1, 1), (0, 1), (2, 1), (1, 0)]
}
TETROMINO_KEYS = list(TETROMINOES.keys())

# ---------------------------------------------------------------
# Minimal MAX7219 Driver
# (Code is identical, snipped for brevity)
# ---------------------------------------------------------------
class MAX7219Display:
    def __init__(self, spi, cs_pin, num_matrices):
        self.spi = spi
        self.cs = cs_pin
        self.cs.init(cs_pin.OUT, value=1)
        self.num_matrices = num_matrices
        self.buffer = bytearray(8 * num_matrices)
        self._NOOP = 0x0
        self._DECODE_MODE = 0x9
        self._INTENSITY = 0xA
        self._SCAN_LIMIT = 0xB
        self._SHUTDOWN = 0xC
        self._DISPLAY_TEST = 0xF
        self.init_display()

    def _write_cmd(self, register, data):
        self.cs(0)
        for _ in range(self.num_matrices):
            self.spi.write(bytearray([register, data]))
        self.cs(1)

    def init_display(self):
        self._write_cmd(self._SHUTDOWN, 0x01)
        self._write_cmd(self._DISPLAY_TEST, 0x00)
        self._write_cmd(self._SCAN_LIMIT, 0x07)
        self._write_cmd(self._DECODE_MODE, 0x00)
        self._write_cmd(self._INTENSITY, 0x07)
        self.clear()
        self.show()

    def set_pixel(self, x, y, value):
        if not (0 <= x < DISPLAY_WIDTH and 0 <= y < DISPLAY_HEIGHT):
            return
        matrix_x = x // 8
        matrix_y = y // 8
        matrix_index = matrix_y * 2 + matrix_x
        local_x = x % 8
        local_y = y % 8
        byte_offset = matrix_index * 8 + local_y
        bit_mask = 1 << (7 - local_x)
        if value:
            self.buffer[byte_offset] |= bit_mask
        else:
            self.buffer[byte_offset] &= ~bit_mask

    def clear(self):
        for i in range(len(self.buffer)):
            self.buffer[i] = 0x00

    def show(self):
        for row in range(8):
            self.cs(0)
            for matrix_index in reversed(range(self.num_matrices)):
                byte_offset = matrix_index * 8 + row
                self.spi.write(bytearray([row + 1, self.buffer[byte_offset]]))
            self.cs(1)
            
    def display_text(self, text):
        self.clear()
        if text == "USB":
            self.set_pixel(1, 1, 1); self.set_pixel(1, 2, 1); self.set_pixel(1, 3, 1)
            self.set_pixel(2, 3, 1); self.set_pixel(3, 1, 1); self.set_pixel(3, 2, 1)
            self.set_pixel(3, 3, 1)
        elif text == "PAUSE":
            self.set_pixel(1, 1, 1); self.set_pixel(1, 2, 1); self.set_pixel(1, 3, 1)
            self.set_pixel(2, 1, 1); self.set_pixel(3, 1, 1); self.set_pixel(2, 2, 1)
        # Removed WAIT and WIFI
        self.show()

# ---------------------------------------------------------------
# Game Logic
# (Code is identical, snipped for brevity)
# ---------------------------------------------------------------
class TetrisGame:
    def __init__(self):
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.score = 0
        self.game_over = False
        self.p1 = self.Player(self, PLAYER_1_COLOR, self.width // 2 - 4)
        self.p2 = self.Player(self, PLAYER_2_COLOR, self.width // 2 + 1)
        self.p1.next_shape = self.get_random_shape()
        self.p2.next_shape = self.get_random_shape()
        self.spawn_new_pieces()

    def get_random_shape(self):
        return random.choice(TETROMINO_KEYS)

    def spawn_new_pieces(self):
        self.p1.spawn(self.p1.next_shape)
        self.p2.spawn(self.p2.next_shape)
        self.p1.next_shape = self.get_random_shape()
        self.p2.next_shape = self.get_random_shape()
        if not self.p1.is_valid_position() or not self.p2.is_valid_position():
            self.game_over = True

    class Player:
        def __init__(self, game, color, start_x):
            self.game = game
            self.color = color
            self.start_x = start_x
            self.shape = None
            self.shape_key = ''
            self.x = 0
            self.y = 0
            self.next_shape = ''
            self.is_placed = False

        def spawn(self, shape_key):
            self.shape_key = shape_key
            self.shape = TETROMINOES[shape_key]
            self.x = self.start_x
            self.y = 0
            self.is_placed = False

        def is_valid_position(self, shape=None, x=None, y=None):
            shape = shape if shape is not None else self.shape
            x = x if x is not None else self.x
            y = y if y is not None else self.y
            for (px, py) in shape:
                nx, ny = x + px, y + py
                if not (0 <= nx < self.game.width and 0 <= ny < self.game.height):
                    return False
                if self.game.grid[ny][nx] == STATIC_COLOR:
                    return False
                other_player = self.game.p2 if self.color == PLAYER_1_COLOR else self.game.p1
                if not other_player.is_placed:
                    for (opx, opy) in other_player.shape:
                        if (other_player.x + opx == nx and other_player.y + opy == ny):
                            return False
            return True

        def move(self, dx, dy):
            if self.is_placed: return False
            if self.is_valid_position(x=self.x + dx, y=self.y + dy):
                self.x += dx
                self.y += dy
                return True
            return False

        def rotate(self):
            if self.is_placed or self.shape_key == 'O': return
            pivot = self.shape[1]
            new_shape = []
            if self.shape_key == 'I':
                pivot = (1, 1)
                for (px, py) in self.shape:
                    new_shape.append((-(py - pivot[1]) + pivot[0], (px - pivot[0]) + pivot[1]))
            else:
                 for (px, py) in self.shape:
                    new_shape.append((-(py - pivot[1]) + pivot[0], (px - pivot[0]) + pivot[1]))
            if self.is_valid_position(shape=new_shape): self.shape = new_shape
            elif self.is_valid_position(shape=new_shape, x=self.x + 1): self.shape = new_shape; self.x += 1
            elif self.is_valid_position(shape=new_shape, x=self.x - 1): self.shape = new_shape; self.x -= 1
            elif self.is_valid_position(shape=new_shape, x=self.x + 2): self.shape = new_shape; self.x += 2
            elif self.is_valid_position(shape=new_shape, x=self.x - 2): self.shape = new_shape; self.x -= 2

    def step_gravity(self):
        if self.game_over: return
        p1_can_move = True
        p2_can_move = True
        if not self.p1.is_placed:
            if not self.p1.move(0, 1): p1_can_move = False
        if not self.p2.is_placed:
            if not self.p2.move(0, 1): p2_can_move = False
        if not p1_can_move and not self.p1.is_placed: self.place_piece(self.p1)
        if not p2_can_move and not self.p2.is_placed: self.place_piece(self.p2)
        if self.p1.is_placed and self.p2.is_placed:
            cleared_lines = self.check_for_lines()
            if cleared_lines == 0:
                self.spawn_new_pieces()
            
    def place_piece(self, player):
        if player.is_placed: return
        player.is_placed = True
        for (px, py) in player.shape:
            nx, ny = player.x + px, player.y + py
            if 0 <= ny < self.height and 0 <= nx < self.width:
                self.grid[ny][nx] = STATIC_COLOR

    def check_for_lines(self):
        lines_to_clear = []
        for y in range(self.height):
            if all(self.grid[y][x] == STATIC_COLOR for x in range(self.width)):
                lines_to_clear.append(y)
        if lines_to_clear:
            self.score += len(lines_to_clear) ** 2
            return lines_to_clear
        return 0
        
    def finish_line_clear(self, cleared_lines):
        for y_to_clear in cleared_lines:
            del self.grid[y_to_clear]
            self.grid.insert(0, [0 for _ in range(self.width)])
        self.spawn_new_pieces()

    def handle_input(self, player_num, action):
        if self.game_over: return
        player = self.p1 if player_num == 1 else self.p2
        if player.is_placed: return
        if action == 'left': player.move(-1, 0)
        elif action == 'right': player.move(1, 0)
        elif action == 'down':
            while player.move(0, 1): pass
            self.place_piece(player)
        elif action == 'rotate': player.rotate()
            
    def get_game_state(self, is_paused=False):
        temp_grid = [row[:] for row in self.grid]
        if not self.p1.is_placed:
            for (px, py) in self.p1.shape:
                nx, ny = self.p1.x + px, self.p1.y + py
                if 0 <= ny < self.height and 0 <= nx < self.width:
                    temp_grid[ny][nx] = self.p1.color
        if not self.p2.is_placed:
            for (px, py) in self.p2.shape:
                nx, ny = self.p2.x + px, self.p2.y + py
                if 0 <= ny < self.height and 0 <= nx < self.width:
                    temp_grid[ny][nx] = self.p2.color
        flat_grid = [cell for row in temp_grid for cell in row]
        state = {
            "grid": flat_grid,
            "score": self.score,
            "p1_next": self.p1.next_shape,
            "p2_next": self.p2.next_shape,
            "game_over": self.game_over,
            "paused": is_paused
        }
        return ujson.dumps(state)

# ---------------------------------------------------------------
# Display Drawing Function
# (Code is identical, snipped for brevity)
# ---------------------------------------------------------------

def draw_game_to_display(display, game_state_json):
    try:
        state = ujson.loads(game_state_json)
        grid_flat = state["grid"]
        display.clear()
        for i in range(len(grid_flat)):
            x = i % DISPLAY_WIDTH
            y = i // DISPLAY_WIDTH
            if grid_flat[i] != 0:
                display.set_pixel(x, y, 1)
        display.show()
    except Exception as e:
        print("Error drawing to display:", e)

def display_line_flicker(display, game, lines_to_clear):
    for _ in range(3):
        for y in lines_to_clear:
            for x in range(DISPLAY_WIDTH):
                display.set_pixel(x, y, 0)
        display.show()
        time.sleep(0.1)
        for y in lines_to_clear:
            for x in range(DISPLAY_WIDTH):
                display.set_pixel(x, y, 1)
        display.show()
        time.sleep(0.1)

# ---------------------------------------------------------------
# Communication Handlers
# ---------------------------------------------------------------

# --- USB (STDIO) ---
usb_poller = select.poll()
usb_poller.register(sys.stdin, select.POLLIN)

def check_usb_input():
    """Check for non-blocking input from USB."""
    if usb_poller.poll(0):
        try:
            char = sys.stdin.read(1)
            if char:
                return char
        except Exception as e:
            print("USB read error:", e)
    return None

def send_usb_message(message):
    """Send a message over USB (just print it)."""
    print(message)

# --- WiFi (Socket) (REMOVED) ---

# ---------------------------------------------------------------
# Input Mapping
# (Code is identical)
# ---------------------------------------------------------------

PLAYER_INPUT_MAP = {
    'w': (1, 'rotate'), 'a': (1, 'left'), 's': (1, 'down'), 'd': (1, 'right'),
    'u': (2, 'rotate'), 'l': (2, 'left'), 'n': (2, 'down'), 'r': (2, 'right'),
}
SYSTEM_INPUT_MAP = {
    'p': "pause_toggle", '1': "menu_resume",
    '2': "menu_restart", '3': "menu_main_menu",
}

# ---------------------------------------------------------------
# Main Menu (REMOVED)
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Main Game Loop
# ---------------------------------------------------------------

def game_loop(display):
    """
    The main game loop for USB mode.
    Returns:
        "RESTART" or "MAIN_MENU" (both will trigger a restart)
    """
    
    game = TetrisGame()
    is_paused = False
    
    last_tick_time = time.ticks_ms()
    flicker_info = None 
    
    # --- Comms setup ---
    display.display_text("USB")
    print("Game Started. Go!")

    while True:
        
        # --- 1. Handle Flicker Effect ---
        if flicker_info:
            start_time, lines_to_clear = flicker_info
            if time.ticks_diff(time.ticks_ms(), start_time) > 700:
                game.finish_line_clear(lines_to_clear)
                flicker_info = None
        
        # --- 2. Handle Gravity (Game Tick) ---
        if not is_paused and not game.game_over and not flicker_info:
            current_time = time.ticks_ms()
            if time.ticks_diff(current_time, last_tick_time) > (GAME_TICK_RATE * 1000):
                last_tick_time = current_time
                game.step_gravity()
                
                lines_to_clear = game.check_for_lines()
                if lines_to_clear:
                    flicker_info = (time.ticks_ms(), lines_to_clear)
                    display_line_flicker(display, game, lines_to_clear)

        # --- 3. Handle Inputs ---
        raw_input_data = check_usb_input() # Always check USB

        if raw_input_data:
            for char in raw_input_data:
                if char in SYSTEM_INPUT_MAP:
                    command = SYSTEM_INPUT_MAP[char]
                    
                    if command == "pause_toggle":
                        is_paused = not is_paused
                        print("Pause Toggled:", is_paused)
                    
                    elif is_paused:
                        if command == "menu_resume":
                            is_paused = False
                        elif command == "menu_restart":
                            print("Restarting game...")
                            return "RESTART"
                        elif command == "menu_main_menu":
                            print("Returning to main menu...")
                            return "MAIN_MENU" # Will be caught by main() as a restart
                            
                elif char in PLAYER_INPUT_MAP:
                    if not is_paused and not game.game_over:
                        player_num, action = PLAYER_INPUT_MAP[char]
                        game.handle_input(player_num, action)

        # --- 4. Send State to Client ---
        game_state_json = game.get_game_state(is_paused)
        send_usb_message(game_state_json) # Always send USB
        
        # --- 5. Draw to Pico Display ---
        if is_paused:
            display.display_text("PAUSE")
        elif not flicker_info:
            draw_game_to_display(display, game_state_json)
            
        # --- 7. Game Over ---
        if game.game_over:
            print("Game Over! Final Score: {}".format(game.score))
            time.sleep(5) # PC client will show message
            return "RESTART"

        time.sleep_ms(10)

# ---------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------

def init_display():
    """Initialize SPI and Display, return display object."""
    try:
        spi = machine.SPI(SPI_BUS, 
                          sck=SPI_SCK_PIN, 
                          mosi=SPI_MOSI_PIN)
        cs = SPI_CS_PIN
        display = MAX7219Display(spi, cs, NUM_MATRICES)
        display.init_display()
        print("MAX7219 Display Initialized.")
        return display
    except Exception as e:
        print("Error initializing display:", e)
        print("Continuing without display (REPL only)...")
        class DummyDisplay:
            def __getattr__(self, name):
                return lambda *args, **kwargs: None
        return DummyDisplay()

def main():
    display = init_display()
    
    while True:
        # Always run the USB game loop
        print("Pico debug: Starting USB game loop...")
        result = game_loop(display)
        
        # Both MAIN_MENU and RESTART will just restart the loop
        print(f"Pico debug: Game loop ended with {result}. Restarting...")
        time.sleep(1) # Brief delay

if __name__ == "__main__":
    main()