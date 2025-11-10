# ---------------------------------------------------------------
# pc_client_unified.py – Unified PC Client for Pico Tetris
# ---------------------------------------------------------------
# Handles:
# 1. USB serial connection (primary)
# 2. Wi-Fi fallback
# 3. Manual Wi-Fi credentials entry
#
# Requirements:
#   pip install pygame pyserial
# ---------------------------------------------------------------

import pygame
import socket
import serial
import sys
import json
import threading
import queue
import time

# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------
DEFAULT_PICO_IP = "192.168.97.210"
PICO_PORT = 8080
USB_PORTS = ["/dev/ttyACM0", "COM3", "COM4"]

GRID_WIDTH = 16
GRID_HEIGHT = 32
BLOCK_SIZE = 20
BORDER_SIZE = 1
INFO_PANEL_WIDTH = 250
GAME_AREA_WIDTH = (BLOCK_SIZE + BORDER_SIZE) * GRID_WIDTH + BORDER_SIZE
GAME_AREA_HEIGHT = (BLOCK_SIZE + BORDER_SIZE) * GRID_HEIGHT + BORDER_SIZE
WINDOW_WIDTH = GAME_AREA_WIDTH + INFO_PANEL_WIDTH
WINDOW_HEIGHT = GAME_AREA_HEIGHT

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GRID = (60, 60, 60)
COLOR_P1 = (255, 87, 34)
COLOR_P2 = (33, 150, 243)
COLOR_STATIC = (158, 158, 158)
COLOR_BG = (10, 10, 10)
COLOR_ERROR = (120, 0, 0)
COLOR_OK = (0, 150, 0)
COLOR_MAP = {0: COLOR_BG, 1: COLOR_P1, 2: COLOR_P2, 3: COLOR_STATIC}

TETROMINOES = {
    'O': [(0,0),(1,0),(0,1),(1,1)],
    'I': [(0,1),(1,1),(2,1),(3,1)],
    'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)],
    'L': [(0,1),(1,1),(2,1),(2,0)],
    'J': [(0,1),(1,1),(2,1),(0,0)],
    'T': [(1,1),(0,1),(2,1),(1,0)]
}

# ---------------------------------------------------------------
# Communication Threads
# ---------------------------------------------------------------
class USBThread(threading.Thread):
    """Handles serial USB communication."""
    def __init__(self, in_q, out_q):
        super().__init__(daemon=True)
        self.in_q, self.out_q = in_q, out_q
        self.ser = None
        self.running = True

    def connect(self):
        for port in USB_PORTS:
            try:
                self.ser = serial.Serial(port, 115200, timeout=1)
                print(f"Connected via USB: {port}")
                return True
            except serial.SerialException:
                continue
        return False

    def run(self):
        if not self.connect():
            self.in_q.put({"error": "USB_FAILED"})
            return

        while self.running:
            try:
                # Read data
                if self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8").strip()
                    if not line:
                        continue
                    if line in ["USB_FAILED", "WIFI_FAILED"]:
                        self.in_q.put({"error": line})
                    else:
                        try:
                            js = json.loads(line)
                            self.in_q.put(js)
                        except json.JSONDecodeError:
                            print("Pico debug:", line)
            except Exception as e:
                print("USB error:", e)
                self.in_q.put({"error": "USB_FAILED"})
                break
            # Send queued inputs
            try:
                while not self.out_q.empty():
                    msg = self.out_q.get_nowait()
                    self.ser.write(msg.encode("utf-8"))
            except Exception:
                pass
        if self.ser:
            self.ser.close()
        print("USBThread stopped.")

class WiFiThread(threading.Thread):
    """Handles Wi-Fi TCP communication."""
    def __init__(self, ip, port, in_q, out_q):
        super().__init__(daemon=True)
        self.ip, self.port = ip, port
        self.in_q, self.out_q = in_q, out_q
        self.sock = None
        self.running = True

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((self.ip, self.port))
            self.sock.settimeout(0.1)
            print(f"Wi-Fi connected: {self.ip}:{self.port}")
            return True
        except Exception as e:
            print("Wi-Fi connection failed:", e)
            return False

    def run(self):
        if not self.connect():
            self.in_q.put({"error": "WIFI_FAILED"})
            return
        buffer = ""
        while self.running:
            try:
                while not self.out_q.empty():
                    msg = self.out_q.get_nowait()
                    self.sock.sendall(msg.encode("utf-8"))
            except Exception:
                break
            try:
                data = self.sock.recv(1024).decode("utf-8")
                buffer += data
                if "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if line in ["USB_FAILED", "WIFI_FAILED"]:
                        self.in_q.put({"error": line})
                        continue
                    try:
                        js = json.loads(line)
                        self.in_q.put(js)
                    except json.JSONDecodeError:
                        print("Pico debug:", line)
            except socket.timeout:
                pass
            except Exception:
                break
        if self.sock:
            self.sock.close()
        print("Wi-Fi thread stopped.")

# ---------------------------------------------------------------
# Main GUI
# ---------------------------------------------------------------
class TetrisClient:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Pico Tetris – Unified Client")
        self.font_big = pygame.font.SysFont(None, 50)
        self.font_med = pygame.font.SysFont(None, 30)
        self.font_small = pygame.font.SysFont(None, 22)
        self.clock = pygame.time.Clock()

        self.state = {"grid":[0]*(GRID_WIDTH*GRID_HEIGHT),"score":0,"p1_next":"","p2_next":"","paused":False,"game_over":False}
        self.in_q, self.out_q = queue.Queue(), queue.Queue()
        self.comm = None
        self.error = None
        self.phase = "usb_try"   # usb_try → wifi_try → wifi_manual → game

    # ---------- GUI Phases ----------
    def usb_phase(self):
        """Try USB connection first."""
        self.comm = USBThread(self.in_q, self.out_q)
        self.comm.start()
        start = time.time()
        while time.time()-start < 3:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
            self.screen.fill(COLOR_BG)
            self.draw_text("Connecting via USB...", COLOR_WHITE, WINDOW_WIDTH//2, WINDOW_HEIGHT//2)
            pygame.display.flip()
            self.clock.tick(30)
            while not self.in_q.empty():
                msg = self.in_q.get()
                if "error" in msg and msg["error"] == "USB_FAILED":
                    self.phase = "wifi_try"
                    return
        # timeout
        self.phase = "wifi_try"

    def wifi_phase(self):
        """Try connecting over Wi-Fi."""
        self.comm = WiFiThread(DEFAULT_PICO_IP, PICO_PORT, self.in_q, self.out_q)
        self.comm.start()
        start = time.time()
        while time.time()-start < 4:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
            self.screen.fill(COLOR_BG)
            self.draw_text("Connecting via Wi-Fi...", COLOR_WHITE, WINDOW_WIDTH//2, WINDOW_HEIGHT//2)
            pygame.display.flip()
            self.clock.tick(30)
            while not self.in_q.empty():
                msg = self.in_q.get()
                if "error" in msg and msg["error"] == "WIFI_FAILED":
                    self.phase = "wifi_manual"
                    return
        # success (if no fail)
        self.phase = "game"

    def wifi_manual_phase(self):
        """Manual Wi-Fi credentials entry."""
        ssid, password = "", ""
        active = "ssid"
        while True:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_TAB:
                        active = "pass" if active=="ssid" else "ssid"
                    elif e.key == pygame.K_RETURN:
                        # Send credentials
                        cred_msg = f"SSID={ssid},PASS={password}\n"
                        try:
                            if self.comm and self.comm.sock:
                                self.comm.sock.sendall(cred_msg.encode())
                        except Exception:
                            pass
                        self.phase = "wifi_try"
                        return
                    elif e.key == pygame.K_BACKSPACE:
                        if active=="ssid": ssid=ssid[:-1]
                        else: password=password[:-1]
                    else:
                        ch = e.unicode
                        if active=="ssid": ssid += ch
                        else: password += ch
            self.screen.fill(COLOR_BG)
            self.draw_text("Wi-Fi Connection Failed", COLOR_ERROR, WINDOW_WIDTH//2, 150)
            self.draw_text("Enter Wi-Fi Credentials", COLOR_WHITE, WINDOW_WIDTH//2, 250)
            self.draw_text(f"SSID: {ssid}{'_' if active=='ssid' else ''}", COLOR_WHITE, WINDOW_WIDTH//2, 350)
            self.draw_text(f"PASS: {password if active!='pass' else '*'*len(password)}{'_' if active=='pass' else ''}", COLOR_WHITE, WINDOW_WIDTH//2, 400)
            self.draw_text("Press Enter to Retry", COLOR_OK, WINDOW_WIDTH//2, 480)
            pygame.display.flip()
            self.clock.tick(30)

    # ---------- Game Phase ----------
    def game_phase(self):
        running=True
        while running:
            for e in pygame.event.get():
                if e.type==pygame.QUIT: running=False
                if e.type==pygame.KEYDOWN: self.key(e.key)
            while not self.in_q.empty():
                msg=self.in_q.get()
                if "error" in msg:
                    self.error=msg["error"]; running=False
                else: self.state=msg
            self.draw_game()
            self.clock.tick(60)
        self.phase="wifi_try" if self.error=="WIFI_FAILED" else "usb_try"

    # ---------- Drawing ----------
    def draw_text(self, text, color, x, y):
        surf=self.font_med.render(text,True,color)
        rect=surf.get_rect(center=(x,y))
        self.screen.blit(surf,rect)

    def draw_game(self):
        self.screen.fill(COLOR_BG)
        grid=self.state["grid"]
        for i,v in enumerate(grid):
            if v:
                x=i%GRID_WIDTH; y=i//GRID_HEIGHT
                pygame.draw.rect(self.screen,COLOR_MAP[v],
                    ((BLOCK_SIZE+BORDER_SIZE)*(i%GRID_WIDTH)+BORDER_SIZE,
                     (BLOCK_SIZE+BORDER_SIZE)*(i//GRID_WIDTH)+BORDER_SIZE,
                     BLOCK_SIZE,BLOCK_SIZE))
        self.draw_text(f"Score: {self.state['score']}",COLOR_WHITE,WINDOW_WIDTH-120,80)
        pygame.display.flip()

    def key(self,k):
        m={pygame.K_w:'w',pygame.K_a:'a',pygame.K_s:'s',pygame.K_d:'d',
           pygame.K_UP:'u',pygame.K_LEFT:'l',pygame.K_DOWN:'n',pygame.K_RIGHT:'r',
           pygame.K_p:'p'}
        if k in m:self.out_q.put(m[k])

    # ---------- Run Controller ----------
    def run(self):
        while True:
            if self.phase=="usb_try": self.usb_phase()
            elif self.phase=="wifi_try": self.wifi_phase()
            elif self.phase=="wifi_manual": self.wifi_manual_phase()
            elif self.phase=="game": self.game_phase()

# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------
if __name__=="__main__":
    print("Unified PC Client for Pico Tetris")
    TetrisClient().run()
