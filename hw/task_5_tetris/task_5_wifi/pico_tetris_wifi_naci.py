# ---------------------------------------------------------------
# pico_tetris_wifi.py – Raspberry Pi Pico W Wi-Fi Tetris Server
# ---------------------------------------------------------------

import machine
import time
import random
import network
import socket
import ujson

# ---------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------
WIFI_SSID = "Eren"
WIFI_PASSWORD = "19981998"
WIFI_STATIC_IP = ""
SERVER_PORT = 8080

DISPLAY_WIDTH = 16
DISPLAY_HEIGHT = 32

SPI_BUS = 0
SPI_SCK_PIN = machine.Pin(10)
SPI_MOSI_PIN = machine.Pin(11)
SPI_CS_PIN = machine.Pin(9)
NUM_MATRICES = 8

GAME_TICK_RATE = 0.5
PLAYER_1_COLOR = 1
PLAYER_2_COLOR = 2
STATIC_COLOR = 3

TETROMINOES = {
    'O': [(0,0),(1,0),(0,1),(1,1)],
    'I': [(0,1),(1,1),(2,1),(3,1)],
    'S': [(1,0),(2,0),(0,1),(1,1)],
    'Z': [(0,0),(1,0),(1,1),(2,1)],
    'L': [(0,1),(1,1),(2,1),(2,0)],
    'J': [(0,1),(1,1),(2,1),(0,0)],
    'T': [(1,1),(0,1),(2,1),(1,0)]
}
TETROMINO_KEYS = list(TETROMINOES.keys())

# ---------------------------------------------------------------
# DISPLAY DRIVER
# ---------------------------------------------------------------
class MAX7219Display:
    def __init__(self, spi, cs_pin, num_matrices):
        self.spi = spi
        self.cs = cs_pin
        self.cs.init(cs_pin.OUT, value=1)
        self.num_matrices = num_matrices
        self.buffer = bytearray(8 * num_matrices)
        self._SCAN_LIMIT, self._DECODE_MODE = 0xB, 0x9
        self._INTENSITY, self._SHUTDOWN, self._DISPLAY_TEST = 0xA, 0xC, 0xF
        self.init_display()

    def _cmd(self, reg, data):
        self.cs(0)
        for _ in range(self.num_matrices):
            self.spi.write(bytearray([reg, data]))
        self.cs(1)

    def init_display(self):
        for r, d in [
            (self._SHUTDOWN, 1), (self._DISPLAY_TEST, 0),
            (self._SCAN_LIMIT, 7), (self._DECODE_MODE, 0),
            (self._INTENSITY, 7)
        ]:
            self._cmd(r, d)
        self.clear()
        self.show()

    def clear(self):
        self.buffer[:] = b'\x00' * len(self.buffer)

    def set_pixel(self, x, y, value):
        if not (0 <= x < DISPLAY_WIDTH and 0 <= y < DISPLAY_HEIGHT):
            return
        m_x, m_y = x // 8, y // 8
        idx = m_y * 2 + m_x
        off = idx * 8 + (y % 8)
        bit = 1 << (7 - (x % 8))
        if value:
            self.buffer[off] |= bit
        else:
            self.buffer[off] &= ~bit

    def show(self):
        for row in range(8):
            self.cs(0)
            for i in reversed(range(self.num_matrices)):
                off = i * 8 + row
                self.spi.write(bytearray([row + 1, self.buffer[off]]))
            self.cs(1)

    def display_text(self, text):
        self.clear()
        if text == "WIFI":
            self.set_pixel(1, 1, 1)
            self.set_pixel(2, 2, 1)
            self.set_pixel(3, 1, 1)
        elif text == "PAUSE":
            self.set_pixel(1, 1, 1)
            self.set_pixel(2, 1, 1)
            self.set_pixel(2, 2, 1)
        self.show()

# ---------------------------------------------------------------
# GAME LOGIC
# ---------------------------------------------------------------
class TetrisGame:
    def __init__(self):
        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT
        self.grid = [[0]*self.width for _ in range(self.height)]
        self.score = 0
        self.game_over = False
        self.p1 = self.Player(self, PLAYER_1_COLOR, self.width // 2 - 4)
        self.p2 = self.Player(self, PLAYER_2_COLOR, self.width // 2 + 1)
        self.p1.next_shape = self.rand()
        self.p2.next_shape = self.rand()
        self.spawn_new()

    def rand(self):
        return random.choice(TETROMINO_KEYS)

    def spawn_new(self):
        self.p1.spawn(self.p1.next_shape)
        self.p2.spawn(self.p2.next_shape)
        self.p1.next_shape = self.rand()
        self.p2.next_shape = self.rand()
        if not self.p1.valid() or not self.p2.valid():
            self.game_over = True

    class Player:
        def __init__(self, game, color, start_x):
            self.g, self.c, self.sx = game, color, start_x
            self.shape_key = ''
            self.shape = []
            self.x = self.y = 0
            self.next_shape = ''
            self.is_placed = False

        def spawn(self, key):
            self.shape_key = key
            self.shape = TETROMINOES[key]
            self.x, self.y = self.sx, 0
            self.is_placed = False

        def valid(self, shape=None, x=None, y=None):
            shape = shape or self.shape
            x = x if x is not None else self.x
            y = y if y is not None else self.y
            for (px, py) in shape:
                nx, ny = x + px, y + py
                if not (0 <= nx < self.g.width and 0 <= ny < self.g.height):
                    return False
                if self.g.grid[ny][nx] == STATIC_COLOR:
                    return False
            return True

        def move(self, dx, dy):
            if self.is_placed:
                return False
            if self.valid(x=self.x + dx, y=self.y + dy):
                self.x += dx
                self.y += dy
                return True
            return False

        def rotate(self):
            if self.is_placed or self.shape_key == 'O':
                return
            pivot = self.shape[1]
            new = [(-(py - pivot[1]) + pivot[0], (px - pivot[0]) + pivot[1]) for (px, py) in self.shape]
            if self.valid(shape=new):
                self.shape = new

    def gravity(self):
        if self.game_over:
            return
        moved1 = self.p1.move(0, 1)
        moved2 = self.p2.move(0, 1)
        if not moved1:
            self.place(self.p1)
        if not moved2:
            self.place(self.p2)
        if self.p1.is_placed and self.p2.is_placed:
            lines = self.lines()
            if lines:
                self.clear_lines(lines)
            else:
                self.spawn_new()

    def place(self, p):
        if p.is_placed:
            return
        p.is_placed = True
        for (px, py) in p.shape:
            nx, ny = p.x + px, p.y + py
            if 0 <= nx < self.width and 0 <= ny < self.height:
                self.grid[ny][nx] = STATIC_COLOR

    def lines(self):
        lines = [y for y in range(self.height) if all(self.grid[y][x] == STATIC_COLOR for x in range(self.width))]
        if lines:
            self.score += len(lines) ** 2
        return lines

    def clear_lines(self, lines):
        for y in lines:
            del self.grid[y]
            self.grid.insert(0, [0]*self.width)

    def input(self, n, act):
        if self.game_over:
            return
        p = self.p1 if n == 1 else self.p2
        if p.is_placed:
            return
        if act == "left":
            p.move(-1, 0)
        elif act == "right":
            p.move(1, 0)
        elif act == "down":
            while p.move(0, 1):
                pass
            self.place(p)
        elif act == "rotate":
            p.rotate()

    def json(self, paused=False):
        g = [r[:] for r in self.grid]
        for p in (self.p1, self.p2):
            if not p.is_placed:
                for (px, py) in p.shape:
                    nx, ny = p.x + px, p.y + py
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        g[ny][nx] = p.c
        flat = [c for r in g for c in r]
        return ujson.dumps({
            "grid": flat,
            "score": self.score,
            "p1_next": self.p1.next_shape,
            "p2_next": self.p2.next_shape,
            "game_over": self.game_over,
            "paused": paused
        })

# ---------------------------------------------------------------
# NETWORK UTILITIES
# ---------------------------------------------------------------
def setup_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0xa11140)
    if not wlan.isconnected():
        print("Connecting to WiFi '{}'...".format(WIFI_SSID))
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        if WIFI_STATIC_IP:
            wlan.ifconfig((WIFI_STATIC_IP, '255.255.255.0', '192.168.1.1', '8.8.8.8'))
        for _ in range(10):
            if wlan.status() >= 3:
                break
            time.sleep(1)
    if wlan.status() != 3:
        raise RuntimeError("WiFi connection failed")
    ip = wlan.ifconfig()[0]
    print("Connected. IP:", ip)
    s = socket.socket()
    s.bind(("0.0.0.0", SERVER_PORT))
    s.listen(1)
    s.setblocking(False)
    print("Listening on tcp://{}:{}".format(ip, SERVER_PORT))
    return s, ip

def send_wifi_message(client_socket, message):
    if client_socket:
        try:
            client_socket.sendall((message + "\n").encode("utf-8"))
            return True
        except Exception as e:
            print("WiFi send error:", e)
            return False
    return False

def check_wifi_connection(server_socket):
    try:
        conn, addr = server_socket.accept()
        conn.setblocking(False)
        print("Client connected from:", addr)
        return conn
    except OSError:
        return None

def check_wifi_input(client_socket):
    if client_socket:
        try:
            data = client_socket.recv(64)
            if data:
                return data.decode("utf-8")
            else:
                return "DISCONNECTED"
        except OSError:
            return None
    return None

# ---------------------------------------------------------------
# GAME LOOP
# ---------------------------------------------------------------
def game_loop(display):
    game = TetrisGame()
    paused = False
    last_tick = time.ticks_ms()

    try:
        server, ip = setup_wifi()
        display.display_text("WIFI")
        print("IP:", ip)
    except Exception as e:
        print("WiFi setup failed:", e)
        return "MAIN_MENU"

    client = None
    while True:
        if not client:
            client = check_wifi_connection(server)
        if client:
            data = check_wifi_input(client)
            if data == "DISCONNECTED":
                print("Client lost, waiting...")
                client = None
            elif data:
                for c in data:
                    if c == "p":
                        paused = not paused
                    elif c in "wasdu lnr":
                        m = {
                            "w": (1, "rotate"), "a": (1, "left"),
                            "s": (1, "down"), "d": (1, "right"),
                            "u": (2, "rotate"), "l": (2, "left"),
                            "n": (2, "down"), "r": (2, "right")
                        }[c]
                        game.input(*m)

        now = time.ticks_ms()
        if not paused and not game.game_over and time.ticks_diff(now, last_tick) > GAME_TICK_RATE * 1000:
            last_tick = now
            game.gravity()

        state = game.json(paused)
        if client:
            send_wifi_message(client, state)

        if game.game_over:
            print("Game Over! Score:", game.score)
            send_wifi_message(client, state)
            send_wifi_message(client, '{"event":"GAME_OVER"}')
            time.sleep(2)
            try:
                client.close()
            except:
                pass
            try:
                server.close()
            except:
                pass
            print("Restarting new game...")
            time.sleep(2)
            return "RESTART"
        time.sleep_ms(10)

# ---------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------
def init_display():
    try:
        spi = machine.SPI(SPI_BUS, sck=SPI_SCK_PIN, mosi=SPI_MOSI_PIN)
        cs = SPI_CS_PIN
        d = MAX7219Display(spi, cs, NUM_MATRICES)
        return d
    except Exception as e:
        print("Display init failed:", e)
        class Dummy:
            def __getattr__(self, name): return lambda *a, **k: None
        return Dummy()

def main():
    d = init_display()
    while True:
        res = game_loop(d)
        print("Loop ended:", res)
        time.sleep(1)

if __name__ == "__main__":
    main()

