from machine import Pin, ADC, I2C, SPI, PWM
from utime import sleep, ticks_ms, ticks_diff
from imu import MPU6050
from max7219 import Matrix8x8
import ssd1306


# =========================
#  LOW-LEVEL: BOARD WRAPPER
# =========================

class MechaBoard:
    """
    Wraps:
      - 4 buttons
      - 1 rotary encoder + push button
      - 1 potentiometer
      - 1 MPU6050 IMU
      - 1 SSD1306 OLED
      - 4x daisy-chained MAX7219 8x8 matrices
      - 1 buzzer (PWM)
    """

    def __init__(
        self,
        # Buttons
        button_left_pin=16,
        button_right_pin=19,
        button_up_pin=18,
        button_down_pin=17,
        # Rotary encoder
        enc_clk_pin=14,
        enc_dt_pin=15,
        enc_sw_pin=13,
        # I2C for IMU + OLED
        i2c_scl_pin=11,
        i2c_sda_pin=10,
        # Buzzer
        buzzer_pin=6,
        # Potentiometer (ADC)
        pot_pin=28,
        # MAX7219 dot matrix (SPI)
        mx_cs_pin=5,
        mx_clk_pin=2,
        mx_din_pin=3,
        num_matrices=4
    ):
        # ---------- Buttons ----------
        self.button_left = Pin(button_left_pin, Pin.IN, Pin.PULL_UP)
        self.button_right = Pin(button_right_pin, Pin.IN, Pin.PULL_UP)
        self.button_up = Pin(button_up_pin, Pin.IN, Pin.PULL_UP)
        self.button_down = Pin(button_down_pin, Pin.IN, Pin.PULL_UP)

        # ---------- Encoder ----------
        self.enc_clk = Pin(enc_clk_pin, Pin.IN, Pin.PULL_UP)
        self.enc_dt = Pin(enc_dt_pin, Pin.IN, Pin.PULL_UP)
        self.enc_sw = Pin(enc_sw_pin, Pin.IN, Pin.PULL_UP)

        self.encoder_position = 0
        self.encoder_last_clk = self.enc_clk.value()

        # ---------- Pot ----------
        self.pot = ADC(Pin(pot_pin))

        # ---------- I2C: IMU + OLED ----------
        self.i2c = I2C(1, scl=Pin(i2c_scl_pin), sda=Pin(i2c_sda_pin), freq=400000)
        self.oled = ssd1306.SSD1306_I2C(128, 64, self.i2c)
        self.imu = MPU6050(self.i2c)

        # ---------- Buzzer ----------
        self.buzzer = PWM(Pin(buzzer_pin))
        self.buzzer.duty_u16(0)  # off

        # ---------- MAX7219 Matrices ----------
        self.spi = SPI(
            0,
            baudrate=10_000_000,
            polarity=0,
            phase=0,
            sck=Pin(mx_clk_pin),
            mosi=Pin(mx_din_pin)
        )
        self.mx_cs = Pin(mx_cs_pin, Pin.OUT)
        self.matrix = Matrix8x8(self.spi, self.mx_cs, num_matrices)
        self.num_matrices = num_matrices
        self.matrix_width = 8 * num_matrices
        self.matrix_height = 8

    # ---------------- BUTTONS ----------------
    def read_buttons(self):
        return {
            "left": not self.button_left.value(),
            "right": not self.button_right.value(),
            "up": not self.button_up.value(),
            "down": not self.button_down.value(),
        }

    # ---------------- POT ----------------
    def read_pot_raw(self):
        return self.pot.read_u16()

    def read_pot_norm(self):
        """Return 0.0–1.0 from pot."""
        return self.pot.read_u16() / 65535.0

    # ---------------- ENCODER ----------------
    def read_encoder_step(self):
        """
        Returns:
         +1 : if rotated one step CW
         -1 : if rotated one step CCW
          0 : if no change
        """
        movement = 0
        clk_now = self.enc_clk.value()

        if clk_now != self.encoder_last_clk:
            if clk_now == 0:  # falling edge
                if self.enc_dt.value() != clk_now:
                    movement = +1
                    self.encoder_position += 1
                else:
                    movement = -1
                    self.encoder_position -= 1

        self.encoder_last_clk = clk_now
        return movement

    def encoder_button_pressed(self):
        return self.enc_sw.value() == 0  # active low

    # ---------------- MPU6050 ----------------
    def read_imu(self):
        ax = round(self.imu.accel.x, 2)
        ay = round(self.imu.accel.y, 2)
        az = round(self.imu.accel.z, 2)
        gx = round(self.imu.gyro.x)
        gy = round(self.imu.gyro.y)
        gz = round(self.imu.gyro.z)
        return ax, ay, az, gx, gy, gz

    # ---------------- OLED ----------------
    def oled_clear(self):
        self.oled.fill(0)

    def oled_text(self, text, x=0, y=0):
        self.oled.text(text, x, y)

    def oled_show(self):
        self.oled.show()

    def oled_print_single_line(self, text):
        self.oled.fill(0)
        self.oled.text(text, 0, 0)
        self.oled.show()

    # ---------------- MAX7219 MATRIX ----------------
    def matrix_clear(self):
        self.matrix.fill(0)

    def matrix_pixel(self, x, y, v=1):
        if 0 <= x < self.matrix_width and 0 <= y < self.matrix_height:
            self.matrix.pixel(x, y, v)

    def matrix_show(self):
        self.matrix.show()

    def matrix_draw_text_simple(self, text):
        """
        Very simple: just write text starting at (0,0).
        For real app you’ll probably scroll it.
        """
        self.matrix.fill(0)
        # Matrix8x8 inherits from framebuf.FrameBuffer → has text()
        self.matrix.text(text[:8*self.num_matrices // 8], 0, 0, 1)
        self.matrix.show()

    # ---------------- BUZZER ----------------
    def beep(self, freq=1000, duration_ms=100):
        self.buzzer.freq(freq)
        self.buzzer.duty_u16(20000)
        sleep(duration_ms / 1000)
        self.buzzer.duty_u16(0)


# =========================
#   BASE APP CLASS
# =========================

class BaseApp:
    def __init__(self, board: MechaBoard, name="App", frame_ms=50):
        self.board = board
        self.name = name
        self.frame_ms = frame_ms
        self.last_update = ticks_ms()
        self.running = False

    def on_enter(self):
        """Called when app becomes active."""
        self.running = True

    def on_exit(self):
        """Called when app is deactivated."""
        self.running = False

    def update(self):
        """Override in child classes."""
        pass

    def step_if_due(self):
        """Call this in main loop; it runs update at frame_ms rate."""
        now = ticks_ms()
        if ticks_diff(now, self.last_update) >= self.frame_ms:
            self.last_update = now
            self.update()


# =========================
#   APP 1: BALL GAME
# =========================

class BallGameApp(BaseApp):
    """
    - Ball on OLED.
    - IMU accelerometer controls direction.
    - Pot controls speed scale.
    - Hitting edges → buzzer beep.
    """

    def __init__(self, board: MechaBoard):
        super().__init__(board, name="BALL", frame_ms=40)
        self.x = 64
        self.y = 32
        self.vx = 0.0
        self.vy = 0.0

    def on_enter(self):
        super().on_enter()
        self.x = 64
        self.y = 32
        self.vx = 0
        self.vy = 0
        self.board.oled_clear()
        self.board.oled_show()

    def update(self):
        # 1) Read IMU + pot
        ax, ay, az, gx, gy, gz = self.board.read_imu()
        speed_scale = 0.5 + 3.0 * self.board.read_pot_norm()

        # 2) Simple physics: use ax, ay to change velocity
        self.vx += ax * 0.1 * speed_scale
        self.vy += -ay * 0.1 * speed_scale   # minus so tilt forward goes down

        # 3) Update position
        self.x += self.vx
        self.y += self.vy

        # 4) Bounce on OLED edges (0–127, 0–63)
        hit = False
        if self.x < 0:
            self.x = 0
            self.vx = -self.vx * 0.7
            hit = True
        if self.x > 127:
            self.x = 127
            self.vx = -self.vx * 0.7
            hit = True
        if self.y < 0:
            self.y = 0
            self.vy = -self.vy * 0.7
            hit = True
        if self.y > 63:
            self.y = 63
            self.vy = -self.vy * 0.7
            hit = True

        if hit:
            self.board.beep(freq=1500, duration_ms=50)

        # 5) Draw ball
        self.board.oled.fill(0)
        # draw a 3x3 ball
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                xx = int(self.x) + dx
                yy = int(self.y) + dy
                if 0 <= xx < 128 and 0 <= yy < 64:
                    self.board.oled.pixel(xx, yy, 1)
        self.board.oled.show()


# =========================
#   APP 2: MUSIC APP
# =========================

class MusicApp(BaseApp):
    """
    - Use buttons to select track.
    - Buzzer plays the melody.
    - OLED shows which track is playing + maybe small animation.
    """

    def __init__(self, board: MechaBoard):
        super().__init__(board, name="MUSIC", frame_ms=100)
        # simple melodies as lists of (freq, duration_ms)
        self.melodies = [
            [(880, 150), (988, 150), (1046, 300)],  # melody 0
            [(440, 200), (660, 200), (880, 400)],   # melody 1
        ]
        self.current_index = 0
        self.playing = False
        self.note_index = 0
        self.note_end_time = 0

    def on_enter(self):
        super().on_enter()
        self.playing = False
        self.note_index = 0
        self.board.oled_print_single_line("Music App")

    def update(self):
        buttons = self.board.read_buttons()

        # change selected track
        if buttons["left"]:
            self.current_index = (self.current_index - 1) % len(self.melodies)
            sleep(0.15)
        if buttons["right"]:
            self.current_index = (self.current_index + 1) % len(self.melodies)
            sleep(0.15)

        # start/stop playing with UP button
        if buttons["up"]:
            self.playing = not self.playing
            self.note_index = 0
            self.board.buzzer.duty_u16(0)
            sleep(0.15)

        # OLED status
        self.board.oled.fill(0)
        self.board.oled.text("Music App", 0, 0)
        self.board.oled.text(f"Track: {self.current_index}", 0, 16)
        self.board.oled.text("Playing" if self.playing else "Stopped", 0, 32)
        self.board.oled.show()

        # play melody
        if self.playing and self.melodies:
            now = ticks_ms()
            if self.note_index >= len(self.melodies[self.current_index]):
                # restart
                self.note_index = 0

            freq, dur = self.melodies[self.current_index][self.note_index]

            if now >= self.note_end_time:
                # start next note
                self.board.buzzer.freq(freq)
                self.board.buzzer.duty_u16(20000)
                self.note_end_time = now + dur
                self.note_index += 1
        else:
            # make sure buzzer is off
            self.board.buzzer.duty_u16(0)


# =========================
#   APP 3: SHOOTER GAME
# =========================

import urandom


class ShooterGameApp(BaseApp):
    """
    - Shooter in the center bottom of OLED.
    - Encoder rotates shooter (angle).
    - Encoder button shoots.
    - Random targets appear.
    - Dot matrix shows magazine & bullets.
    """

    def __init__(self, board: MechaBoard):
        super().__init__(board, name="SHOOT", frame_ms=50)
        self.angle = 0  # degrees
        self.shots_left = 6
        self.magazines = 3
        self.bullets = []  # list of dicts {x, y, vx, vy}
        self.target = None

    def on_enter(self):
        super().on_enter()
        self.angle = 0
        self.shots_left = 6
        self.magazines = 3
        self.bullets = []
        self.spawn_target()

    def spawn_target(self):
        # random position near top
        self.target = {
            "x": urandom.getrandbits(7) % 128,
            "y": urandom.getrandbits(6) % 20 + 5
        }

    def handle_encoder(self):
        step = self.board.read_encoder_step()
        if step != 0:
            self.angle += step * 5   # 5 degrees per step
            if self.angle < -80:
                self.angle = -80
            if self.angle > 80:
                self.angle = 80

        # shooting
        if self.board.encoder_button_pressed():
            if self.shots_left > 0:
                self.fire_bullet()
                self.shots_left -= 1
                self.board.beep(2000, 30)
                sleep(0.2)
            elif self.magazines > 0:
                # reload with DOWN button for example
                buttons = self.board.read_buttons()
                if buttons["down"]:
                    self.magazines -= 1
                    self.shots_left = 6
                    self.board.beep(800, 100)
                    sleep(0.2)

    def fire_bullet(self):
        # start at center bottom
        origin_x = 64
        origin_y = 63

        # simple direction
        rad = 3.14159 * self.angle / 180.0
        vx = 4 * (math.cos(rad))
        vy = -4 * (math.sin(rad))

        self.bullets.append({
            "x": origin_x,
            "y": origin_y,
            "vx": vx,
            "vy": vy
        })

    def update_bullets(self):
        new_bullets = []
        for b in self.bullets:
            b["x"] += b["vx"]
            b["y"] += b["vy"]

            # check bounds
            if 0 <= b["x"] < 128 and 0 <= b["y"] < 64:
                new_bullets.append(b)
        self.bullets = new_bullets

    def check_hit(self):
        if not self.target:
            return
        tx = self.target["x"]
        ty = self.target["y"]
        for b in self.bullets:
            if abs(b["x"] - tx) < 3 and abs(b["y"] - ty) < 3:
                # hit!
                self.board.beep(1200, 80)
                self.spawn_target()
                return

    def update_matrix_hud(self):
        self.board.matrix.fill(0)
        # simple representation: bullets on top row, mags on bottom
        for i in range(self.shots_left):
            if i < self.board.matrix_width:
                self.board.matrix.pixel(i, 0, 1)
        for j in range(self.magazines):
            if j < self.board.matrix_width:
                self.board.matrix.pixel(j, 7, 1)
        self.board.matrix.show()

    def update(self):
        self.handle_encoder()
        self.update_bullets()
        self.check_hit()
        self.update_matrix_hud()

        # draw on OLED
        self.board.oled.fill(0)
        # draw shooter at bottom center: small triangle / line
        cx = 64
        cy = 63
        self.board.oled.line(cx - 5, cy, cx + 5, cy, 1)
        # direction indicator
        dx = int(cx + 10 * math.cos(3.14159 * self.angle / 180.0))
        dy = int(cy - 10 * math.sin(3.14159 * self.angle / 180.0))
        self.board.oled.line(cx, cy, dx, dy, 1)

        # draw bullets
        for b in self.bullets:
            self.board.oled.pixel(int(b["x"]), int(b["y"]), 1)

        # draw target
        if self.target:
            self.board.oled.rect(self.target["x"] - 2, self.target["y"] - 2, 5, 5, 1)

        self.board.oled.show()


# =========================
#   MENU APP (ON MATRIX)
# =========================

class MenuApp(BaseApp):
    """
    - Lives on dot matrix.
    - Use buttons or encoder to switch between apps.
    - When selected, shows app name on matrix, OLED cleared.
    """

    def __init__(self, board: MechaBoard, apps):
        super().__init__(board, name="MENU", frame_ms=150)
        self.apps = apps  # list of (name, app_instance)
        self.current_index = 0
        self.selected_app = None

    def on_enter(self):
        super().on_enter()
        self.selected_app = None
        self.board.oled_print_single_line("Select App")
        self.show_current_name()

    def show_current_name(self):
        name = self.apps[self.current_index][0]
        # very simple non-scrolling display
        self.board.matrix_draw_text_simple(name)

    def update(self):
        buttons = self.board.read_buttons()
        step = self.board.read_encoder_step()

        # navigate with left/right or encoder
        if buttons["left"] or step < 0:
            self.current_index = (self.current_index - 1) % len(self.apps)
            self.show_current_name()
            sleep(0.15)
        if buttons["right"] or step > 0:
            self.current_index = (self.current_index + 1) % len(self.apps)
            self.show_current_name()
            sleep(0.15)

        # select with UP or encoder button
        if buttons["up"] or self.board.encoder_button_pressed():
            self.selected_app = self.apps[self.current_index][1]
            self.running = False  # signal main loop to switch
            self.board.beep(1200, 80)
            sleep(0.2)


# =========================
#   MAIN LOOP
# =========================

def main():
    board = MechaBoard()

    # Instantiate apps
    ball_app = BallGameApp(board)
    music_app = MusicApp(board)
    shooter_app = ShooterGameApp(board)

    apps = [
        ("BALL", ball_app),
        ("MUSIC", music_app),
        ("SHOOT", shooter_app),
    ]

    while True:
        menu = MenuApp(board, apps)
        menu.on_enter()

        # Run menu until user selects an app
        while menu.running:
            menu.step_if_due()
            sleep(0.01)

        # Get selected app and run it
        current_app = menu.selected_app
        if current_app is None:
            continue

        current_app.on_enter()
        while current_app.running:
            current_app.step_if_due()
            # you can add: exit app with DOWN button etc.
            buttons = board.read_buttons()
            if buttons["down"]:
                current_app.on_exit()
            sleep(0.01)


# Only run if this is the main file
if __name__ == "__main__":
    main()
