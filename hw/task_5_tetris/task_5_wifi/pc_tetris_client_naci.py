# pc_client_wifi.py
# PC Client for Pico Tetris
# --- WIFI-ONLY VERSION ---
# Requires: pip install pygame

import pygame
import socket
import time
import sys
import json
import threading
import queue

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

# --- WiFi Config ---
PICO_IP = "192.168.97.210"  # CHANGE THIS to your Pico's IP
PICO_PORT = 8080

# --- Pygame Config ---
GRID_WIDTH = 16
GRID_HEIGHT = 32
BLOCK_SIZE = 20
BORDER_SIZE = 1
GAME_AREA_WIDTH = (BLOCK_SIZE + BORDER_SIZE) * GRID_WIDTH + BORDER_SIZE
GAME_AREA_HEIGHT = (BLOCK_SIZE + BORDER_SIZE) * GRID_HEIGHT + BORDER_SIZE
INFO_PANEL_WIDTH = 250
WINDOW_WIDTH = GAME_AREA_WIDTH + INFO_PANEL_WIDTH
WINDOW_HEIGHT = GAME_AREA_HEIGHT

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GRID = (60, 60, 60)
COLOR_P1 = (255, 87, 34)
COLOR_P2 = (33, 150, 243)
COLOR_STATIC = (158, 158, 158)
COLOR_BG = (10, 10, 10)
COLOR_MAP = {0: COLOR_BG, 1: COLOR_P1, 2: COLOR_P2, 3: COLOR_STATIC}
GRID_LINE_COLOR = (60, 60, 60)
GRID_W, GRID_H = GRID_WIDTH, GRID_HEIGHT
WIN_W = WINDOW_WIDTH
WIN_H = WINDOW_HEIGHT

# ---------------------------------------------------------------
# Tetromino Mini-Display
# ---------------------------------------------------------------
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
    if not shape_key or shape_key not in TETROMINOES:
        return
    shape = TETROMINOES[shape_key]
    mini_block_size = 10
    for (px, py) in shape:
        draw_x = x_offset + px * (mini_block_size + 1)
        draw_y = y_offset + py * (mini_block_size + 1)
        pygame.draw.rect(
            surface,
            COLOR_STATIC,
            (draw_x, draw_y, mini_block_size, mini_block_size)
        )

# ---------------------------------------------------------------
# Communication Thread
# ---------------------------------------------------------------
class CommunicationThread(threading.Thread):
    """Handles all socket communication in a separate thread."""
    def __init__(self, input_queue, output_queue):
        super().__init__(daemon=True)
        self.input_q = input_queue
        self.output_q = output_queue
        self.connection = None
        self.running = True

    def connect(self):
        try:
            self.connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.connection.settimeout(5.0)
            self.connection.connect((PICO_IP, PICO_PORT))
            self.connection.settimeout(0.1)
            print(f"Connected to {PICO_IP}:{PICO_PORT}")
            return True
        except socket.error as e:
            print(f"Error connecting to {PICO_IP}: {e}")
            return False

    def run(self):
        if not self.connect():
            self.input_q.put({"error": "Connection Failed"})
            return
        buffer = ""
        while self.running:
            # Send data to Pico
            try:
                while not self.output_q.empty():
                    key_press = self.output_q.get_nowait()
                    self.connection.sendall(key_press.encode('utf-8'))
            except Exception as e:
                print(f"Error sending data: {e}")
                self.running = False
                break

            # Receive data from Pico
            try:
                buffer += self.connection.recv(1024).decode('utf-8')
                if '\n' in buffer:
                    data, buffer = buffer.split('\n', 1)
                    data = data.strip()
                else:
                    data = None
                if data:
                    try:
                        game_state = json.loads(data)
                        self.input_q.put(game_state)
                    except json.JSONDecodeError:
                        print(f"Pico debug: {data}")
                        pass
            except socket.timeout:
                pass
            except Exception as e:
                print(f"Error receiving data: {e}")
                self.running = False
        if self.connection:
            self.connection.close()
        print("Communication thread stopped.")

# ---------------------------------------------------------------
# Main Pygame Client
# ---------------------------------------------------------------
class PygameClient:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pico Tetris - 2 Player (WiFi Mode)")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_big = pygame.font.SysFont(None, 50)
        self.font_medium = pygame.font.SysFont(None, 30)
        self.font_small = pygame.font.SysFont(None, 25)

        self.comm_mode = "WIFI"
        self.error_message = None
        self.game_state_q = queue.Queue()
        self.input_q = queue.Queue()
        self.comm_thread = CommunicationThread(self.game_state_q, self.input_q)
        self.comm_thread.start()

        self.current_state = {
            "grid": [0] * (GRID_WIDTH * GRID_HEIGHT),
            "score": 0,
            "p1_next": "",
            "p2_next": "",
            "game_over": False,
            "paused": False
        }

    def run_game(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    self.handle_keydown(event.key)
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
                if not (self.current_state.get("game_over") or self.current_state.get("paused")):
                    self.error_message = "Connection Lost"
            self.draw()
            self.clock.tick(60)
        self.comm_thread.running = False
        self.comm_thread.join(timeout=1)
        pygame.quit()
        if self.error_message:
            print(f"Exiting due to error: {self.error_message}")

    def handle_keydown(self, key):
        if self.current_state.get("paused", False):
            if key == pygame.K_1: self.input_q.put('1'); return
            if key == pygame.K_2: self.input_q.put('2'); return
            if key == pygame.K_3: self.input_q.put('3'); return
            if key == pygame.K_p: self.input_q.put('p'); return
        if key == pygame.K_p: self.input_q.put('p'); return
        key_map = {
            pygame.K_w: 'w', pygame.K_a: 'a', pygame.K_s: 's', pygame.K_d: 'd',
            pygame.K_UP: 'u', pygame.K_LEFT: 'l', pygame.K_DOWN: 'n', pygame.K_RIGHT: 'r',
        }
        if key in key_map:
            self.input_q.put(key_map[key])

    def draw(self):
        self.screen.fill(COLOR_BG)
        self.draw_grid()
        self.draw_grid_lines()
        # Draw border frame
        pygame.draw.rect(self.screen, (80, 80, 80), pygame.Rect(0, 0, GAME_AREA_WIDTH, GAME_AREA_HEIGHT), 2)
        self.draw_info_panel()
        if self.current_state.get("paused", False):
            self.draw_pause_menu()
        elif self.current_state.get("game_over", False):
            self.draw_game_over()
        if self.error_message:
            self.draw_error()
        pygame.display.flip()

    def draw_grid_lines(self):
        """Draw better aligned, visible background grid lines."""
        for x in range(GRID_WIDTH + 1):
            xpos = x * (BLOCK_SIZE + BORDER_SIZE)
            pygame.draw.line(self.screen, GRID_LINE_COLOR, (xpos, 0), (xpos, GAME_AREA_HEIGHT))
        for y in range(GRID_HEIGHT + 1):
            ypos = y * (BLOCK_SIZE + BORDER_SIZE)
            pygame.draw.line(self.screen, GRID_LINE_COLOR, (0, ypos), (GAME_AREA_WIDTH, ypos))

    def draw_grid(self):
        grid_data = self.current_state["grid"]
        for i in range(len(grid_data)):
            x = i % GRID_WIDTH
            y = i // GRID_WIDTH
            color = COLOR_MAP.get(grid_data[i], COLOR_BLACK)
            draw_x = (BLOCK_SIZE + BORDER_SIZE) * x + BORDER_SIZE
            draw_y = (BLOCK_SIZE + BORDER_SIZE) * y + BORDER_SIZE
            pygame.draw.rect(self.screen, color, (draw_x, draw_y, BLOCK_SIZE, BLOCK_SIZE))

    def draw_info_panel(self):
        panel_x = GAME_AREA_WIDTH
        score_text = self.font_big.render("SCORE", True, COLOR_WHITE)
        score_val = self.font_big.render(str(self.current_state["score"]), True, COLOR_WHITE)
        self.screen.blit(score_text, (panel_x + (INFO_PANEL_WIDTH - score_text.get_width()) // 2, 50))
        self.screen.blit(score_val, (panel_x + (INFO_PANEL_WIDTH - score_val.get_width()) // 2, 100))
        p1_text = self.font_medium.render("P1 Next", True, COLOR_P1)
        self.screen.blit(p1_text, (panel_x + (INFO_PANEL_WIDTH - p1_text.get_width()) // 2, 200))
        draw_mini_shape(self.screen, self.current_state.get("p1_next", ""), panel_x + (INFO_PANEL_WIDTH // 2) - (2 * 11), 240)
        p2_text = self.font_medium.render("P2 Next", True, COLOR_P2)
        self.screen.blit(p2_text, (panel_x + (INFO_PANEL_WIDTH - p2_text.get_width()) // 2, 350))
        draw_mini_shape(self.screen, self.current_state.get("p2_next", ""), panel_x + (INFO_PANEL_WIDTH // 2) - (2 * 11), 390)

    def draw_game_over(self):
        overlay = pygame.Surface((GAME_AREA_WIDTH, 200), pygame.SRCALPHA)
        overlay.fill((50, 50, 50, 200))
        text1 = self.font_big.render("GAME OVER", True, COLOR_WHITE)
        text2 = self.font_medium.render("Pico will restart game", True, COLOR_WHITE)
        overlay.blit(text1, ((GAME_AREA_WIDTH - text1.get_width()) // 2, 50))
        overlay.blit(text2, ((GAME_AREA_WIDTH - text2.get_width()) // 2, 120))
        self.screen.blit(overlay, (0, (GAME_AREA_HEIGHT - 200) // 2))

    def draw_pause_menu(self):
        overlay = pygame.Surface((GAME_AREA_WIDTH, 300), pygame.SRCALPHA)
        overlay.fill((50, 50, 50, 220))
        text1 = self.font_big.render("PAUSED", True, COLOR_WHITE)
        text2 = self.font_medium.render("1: Resume (or P)", True, COLOR_WHITE)
        text3 = self.font_medium.render("2: Restart", True, COLOR_WHITE)
        text4 = self.font_medium.render("3: Main Menu", True, COLOR_WHITE)
        overlay.blit(text1, ((GAME_AREA_WIDTH - text1.get_width()) // 2, 50))
        overlay.blit(text2, ((GAME_AREA_WIDTH - text2.get_width()) // 2, 120))
        overlay.blit(text3, ((GAME_AREA_WIDTH - text3.get_width()) // 2, 160))
        overlay.blit(text4, ((GAME_AREA_WIDTH - text4.get_width()) // 2, 200))
        self.screen.blit(overlay, (0, (GAME_AREA_HEIGHT - 300) // 2))

    def draw_error(self):
        overlay = pygame.Surface((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((100, 0, 0, 220))
        text1 = self.font_big.render("ERROR", True, COLOR_WHITE)
        text2 = self.font_medium.render(self.error_message, True, COLOR_WHITE)
        text3 = self.font_small.render(f"Check Pico WiFi connection and PICO_IP ({PICO_IP}).", True, COLOR_WHITE)
        text4 = self.font_small.render("Restart both Pico and PC client.", True, COLOR_WHITE)
        overlay.blit(text1, ((WINDOW_WIDTH - text1.get_width()) // 2, 100))
        overlay.blit(text2, ((WINDOW_WIDTH - text2.get_width()) // 2, 200))
        overlay.blit(text3, ((WINDOW_WIDTH - text3.get_width()) // 2, 250))
        overlay.blit(text4, ((WINDOW_WIDTH - text4.get_width()) // 2, 280))
        self.screen.blit(overlay, (0, 0))

# ---------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------
if __name__ == "__main__":
    print("--- PC Tetris Client (WiFi Mode) ---")
    print(f"Ensure your Pico is running 'pico_tetris_wifi.py'")
    print(f"Attempting to connect to: {PICO_IP}:{PICO_PORT}")
    print("-" * 26)
    client = PygameClient()
    client.run_game()
