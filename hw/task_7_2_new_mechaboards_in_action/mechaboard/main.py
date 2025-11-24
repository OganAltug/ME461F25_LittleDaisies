from machine import Pin, ADC, I2C, SPI, PWM, time_pulse_us
from utime import sleep, ticks_ms, ticks_diff
from imu import MPU6050
from max7219 import Matrix8x8
import ssd1306
import urandom
import math


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
      - 1 HC-SR04 ultrasonic sensor (trig/echo)
      - 4 external LEDs
      - 1 built-in LED
    """

    def __init__(
        self,
        # Buttons
        button_left_pin=0,      # btn1: GP0 (diagram.json line 68)
        button_right_pin=7,     # btn2: GP7 (diagram.json line 69)
        button_up_pin=1,        # btn3: GP1 (diagram.json line 70)
        button_down_pin=6,      # btn4: GP6 (diagram.json line 71)
        # Rotary encoder
        enc_clk_pin=14,
        enc_dt_pin=15,
        enc_sw_pin=4,
        # I2C for IMU + OLED
        i2c_scl_pin=13,
        i2c_sda_pin=12,
        # Buzzer
        buzzer_pin=20,
        # Potentiometer (ADC)
        pot_pin=26,
        # MAX7219 dot matrix (SPI)
        mx_cs_pin=5,
        mx_clk_pin=2,
        mx_din_pin=3,
        num_matrices=4,         # diagram.json shows chain="4" (line 18)
        # HC-SR04 Ultrasonic sensor
        trig_pin=19,
        echo_pin=18,
        # External LEDs
        led_1=16,
        led_2=17,
        led_3=21,
        led_4=22,
    ):
        # ---------- Buttons ----------
        self.button_left = Pin(button_left_pin, Pin.IN, Pin.PULL_DOWN)
        self.button_right = Pin(button_right_pin, Pin.IN, Pin.PULL_DOWN)
        self.button_up = Pin(button_up_pin, Pin.IN, Pin.PULL_DOWN)
        self.button_down = Pin(button_down_pin, Pin.IN, Pin.PULL_DOWN)

        # ---------- Encoder ----------
        self.enc_clk = Pin(enc_clk_pin, Pin.IN, Pin.PULL_UP)
        self.enc_dt = Pin(enc_dt_pin, Pin.IN, Pin.PULL_UP)
        self.enc_sw = Pin(enc_sw_pin, Pin.IN, Pin.PULL_DOWN)

        self.encoder_position = 0
        self.encoder_last_clk = self.enc_clk.value()

        # ---------- Pot ----------
        self.pot = ADC(Pin(pot_pin))

        # ---------- I2C: IMU + OLED ----------
        self.i2c = I2C(0, scl=Pin(i2c_scl_pin), sda=Pin(i2c_sda_pin), freq=400000)
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
        # num_matrices = 4 → 32x8 display
        self.matrix = Matrix8x8(self.spi, self.mx_cs, num_matrices, orientation=2)
        self.num_matrices = num_matrices
        self.matrix_width = 8 * num_matrices
        self.matrix_height = 8

        # ---------- Ultrasonic Sensor ----------
        self.trig = Pin(trig_pin, Pin.OUT)
        self.echo = Pin(echo_pin, Pin.IN)
        self.trig.low()

        # ---------- LEDs ----------
        # Built-in LED (always ON after boot)
        self.led_builtin = Pin("LED", Pin.OUT)
        self.led_builtin.value(1)

        # External game LEDs (mode B: one per game)
        self.led_ball = Pin(led_1, Pin.OUT)
        self.led_music = Pin(led_2, Pin.OUT)
        self.led_shoot = Pin(led_3, Pin.OUT)
        self.led_ultra = Pin(led_4, Pin.OUT)

        self.all_game_leds_off()

    # ---------------- LED HELPERS ----------------
    def all_game_leds_off(self):
        self.led_ball.value(0)
        self.led_music.value(0)
        self.led_shoot.value(0)
        self.led_ultra.value(0)

    # ---------------- BUTTONS ----------------
    def read_buttons(self):
        return {
            "left": self.button_left.value(),
            "right": self.button_right.value(),
            "up": self.button_up.value(),
            "down": self.button_down.value(),
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
        Reads incremental rotary encoder step.
        CW and CCW both register, direction based on wiring.
        """
        movement = 0
        clk_now = self.enc_clk.value()
        dt_now = self.enc_dt.value()

        # detect any edge
        if clk_now != self.encoder_last_clk:
            # detect falling edge
            if clk_now == 0:
                # For your wiring:
                #   CW → DT == 0
                #   CCW → DT == 1
                if dt_now == 0:
                    movement = +1   # CW
                    self.encoder_position += 1
                else:
                    movement = -1   # CCW
                    self.encoder_position -= 1

        self.encoder_last_clk = clk_now
        return movement

    def encoder_button_pressed(self):
        return self.enc_sw.value() == 1  # active high (connected to VCC)

    # ---------------- MPU6050 ----------------
    def read_imu(self):
        """
        Returns (ax, ay, az, gx, gy, gz)
        Axes remapped so:
         - ay_raw controls horizontal (x) movement
         - -ax_raw controls vertical (y) movement
        This corrects for the board mounting where:
         - Looking at the top, raw y is left, raw x is bottom.
        """
        ax_raw = self.imu.accel.x
        ay_raw = self.imu.accel.y
        az_raw = self.imu.accel.z

        # Remap axes for more intuitive gameplay
        ax = round(ay_raw, 2)     # horizontal
        ay = round(-ax_raw, 2)    # vertical
        az = round(az_raw, 2)

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
        Displays full text with automatic left-scroll
        when the text is too long for the display.
        Characters stay default size (no scaling).
        """
        self.matrix.fill(0)

        # Each 5x7 font character uses ~6 pixels including spacing
        text_len_px = len(text) * 6

        # If it fits, show directly
        if text_len_px <= self.matrix_width:
            self.matrix.text(text, 0, 0, 1)
            self.matrix.show()
            return

        # Otherwise, scroll text from right to left
        for offset in range(text_len_px - self.matrix_width + 1):
            self.matrix.fill(0)
            self.matrix.text(text, -offset, 0, 1)
            self.matrix.show()
            sleep(0.05)

    # ---------------- BUZZER ----------------
    def beep(self, freq=1000, duration_ms=100):
        self.buzzer.freq(freq)
        self.buzzer.duty_u16(20000)
        sleep(duration_ms / 1000)
        self.buzzer.duty_u16(0)

    # ---------------- ULTRASONIC ----------------
    def read_distance_cm(self):
        """
        Returns distance in cm using HC-SR04.
        Uses machine.time_pulse_us for accurate timing.
        Returns None on timeout / no echo.
        """
        # Send 10 µs trigger pulse
        self.trig.low()
        sleep(0.000002)
        self.trig.high()
        sleep(0.00001)
        self.trig.low()

        # Measure echo high pulse width in microseconds
        pulse = time_pulse_us(self.echo, 1, 30000)  # 30 ms timeout

        if pulse < 0:
            return None

        # Convert µs → cm (approx)
        distance = pulse / 58.0
        return distance


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
    Ball Game App:
    - Ball moves on OLED screen
    - IMU accelerometer controls ball direction (tilt board)
    - Potentiometer controls speed scale (0-3.5x)
    - Ball bounces on edges with buzzer feedback
    - DOWN button: Exit to menu
    """

    def __init__(self, board: MechaBoard):
        super().__init__(board, name="BALL", frame_ms=40)
        self.x = 64
        self.y = 32
        self.vx = 0.0
        self.vy = 0.0

    def on_enter(self):
        super().on_enter()
        self.board.all_game_leds_off()
        self.board.led_ball.value(1)  # LED for BALL app
        self.x = 64
        self.y = 32
        self.vx = 0
        self.vy = 0
        self.board.oled_clear()
        self.board.oled_show()

    def on_exit(self):
        super().on_exit()
        self.board.led_ball.value(0)

    def update(self):
        # 1) Read IMU + pot
        ax, ay, az, gx, gy, gz = self.board.read_imu()
        speed_scale = 0.5 + 3.0 * self.board.read_pot_norm()

        # 2) Simple physics: use ax, ay to change velocity
        self.vx += ax * 0.1 * speed_scale
        self.vy += -ay * 0.1 * speed_scale   # minus to adjust tilt sense if needed

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
    Music App:
    - LEFT button: Previous track
    - RIGHT button: Next track  
    - UP button: Play/Pause toggle
    - DOWN button: Exit to menu
    - Buzzer plays the selected melody
    - OLED shows track name and status
    """

    def __init__(self, board: MechaBoard):
        super().__init__(board, name="MUSIC", frame_ms=100)
        # simple melodies as lists of (freq, duration_ms)
        self.melodies = [
            # At Doom's Gate
            [(82,36),(0,18),(82,36),(0,18),(165,36),(0,18),(82,36),(0,18),
             (82,36),(0,18),(147,36),(0,18),(82,36),(0,18),(82,36),(0,18),
             (131,36),(0,18),(82,36),(0,18),(82,36),(0,18),(117,36),(0,18),
             (82,36),(0,18),(82,36),(0,18),(124,36),(0,18),(131,18),(0,18),
             (82,36),(0,18),(82,36),(0,18),(165,36),(0,18),(82,36),(0,18),
             (82,36),(0,18),(147,36),(0,18),(82,36),(0,18),(82,36),(0,18),
             (131,36),(0,18),(82,36),(0,18),(82,36),(0,18),(117,243),(0,18)],
            # Silver Cord by Gojira
            [(98,176),(104,176),(131,352),(131,352),(104,352),(98,352),(117,352),(131,352),(87,352),
             (87,352),(104,352),(87,352),(131,352),(104,352),(87,352),(104,352),(87,352),
             (78,352),(98,352),(78,352),(131,704),(98,704),(78,352),
             (78,352),(98,352),(78,352),(131,352),(98,352),(78,352),(98,352),(78,352),
             (98,176),(104,176),(131,352),(131,352),(104,352),(98,352),(117,352),(131,352),(87,352),
             (87,352),(104,352),(87,352),(131,352),(104,352),(87,352),(104,352),(87,352),
             (78,352),(98,352),(78,352),(131,704),(98,704),(78,352),
             (78,352),(156,352),(131,352),(156,352),(131,352),(156,352),(174,352),(156,352)]
        ]
        self.current_index = 0
        self.playing = False
        self.note_index = 0
        self.note_end_time = 0

    def on_enter(self):
        super().on_enter()
        self.board.all_game_leds_off()
        self.board.led_music.value(1)  # LED for MUSIC app
        self.playing = False
        self.note_index = 0
        self.board.oled_print_single_line("Music App")

    def on_exit(self):
        super().on_exit()
        self.board.led_music.value(0)
        self.board.buzzer.duty_u16(0)

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
        self.board.oled.text("Track: {}".format(self.current_index), 0, 16)
        self.board.oled.text("Playing" if self.playing else "Stopped", 0, 32)
        if self.current_index == 0:
            self.board.oled.text("DOOM \\m/", 0, 48)
        if self.current_index == 1:
            self.board.oled.text("Gojira <3", 0, 48)
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
                if freq == 0:
                    self.board.buzzer.duty_u16(0)
                    self.note_end_time = now + dur
                    self.note_index += 1
                else:
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

class ShooterGameApp(BaseApp):
    """
    Shooter Game App:
    - Rotate ENCODER: Aim shooter full 360° (R3)
    - Press ENCODER BUTTON: Fire bullet
    - LEFT button: Reload magazine (when out of bullets)
    - Random targets appear at the top
    - Dot matrix shows: Top row = bullets left, Bottom row = magazines left
    - OLED shows game view with shooter, bullets, and targets
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
        self.board.all_game_leds_off()
        self.board.led_shoot.value(1)  # LED for SHOOT app
        self.angle = 0
        self.shots_left = 6
        self.magazines = 3
        self.bullets = []
        self.spawn_target()

    def on_exit(self):
        super().on_exit()
        self.board.led_shoot.value(0)

    def spawn_target(self):
        # random position near top
        self.target = {
            "x": urandom.getrandbits(7) % 128,
            "y": urandom.getrandbits(6) % 20 + 5
        }

    def handle_encoder(self):
        # Read encoder rotation
        step = self.board.read_encoder_step()
        if step != 0:
            # Each encoder step = 5 degrees, full 360° (R3)
            self.angle = (self.angle + step * 5) % 360

        # Check for shooting (encoder button)
        if self.board.encoder_button_pressed():
            if self.shots_left > 0:
                self.fire_bullet()
                self.shots_left -= 1
                self.board.beep(2000, 30)
                sleep(0.2)

        # Check for reload (LEFT button) - when out of bullets
        buttons = self.board.read_buttons()
        if buttons["left"]:
            if self.shots_left == 0 and self.magazines > 0:
                # Reload: use one magazine, get 6 bullets
                self.magazines -= 1
                self.shots_left = 6
                self.board.beep(800, 100)
                sleep(0.2)

    def fire_bullet(self):
        # start at center bottom
        origin_x = 64
        origin_y = 63

        # direction based on angle (0° right, 90° up, etc.)
        rad = math.radians(self.angle)
        vx = 4 * math.cos(rad)
        vy = -4 * math.sin(rad)

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

        # Draw HUD info at top (bullet and magazine count)
        self.board.oled.text("Bullets: {}/6".format(self.shots_left), 0, 0)
        self.board.oled.text("Mags: {}".format(self.magazines), 70, 0)

        # draw shooter at bottom center: small line
        cx = 64
        cy = 63
        self.board.oled.line(cx - 5, cy, cx + 5, cy, 1)
        # direction indicator
        rad = math.radians(self.angle)
        dx = int(cx + 10 * math.cos(rad))
        dy = int(cy - 10 * math.sin(rad))
        self.board.oled.line(cx, cy, dx, dy, 1)

        # draw bullets
        for b in self.bullets:
            self.board.oled.pixel(int(b["x"]), int(b["y"]), 1)

        # draw target
        if self.target:
            self.board.oled.rect(self.target["x"] - 2, self.target["y"] - 2, 5, 5, 1)

        # Show reload hint when out of bullets
        if self.shots_left == 0 and self.magazines > 0:
            self.board.oled.text("Press LEFT", 30, 48)
            self.board.oled.text("to reload", 35, 56)

        self.board.oled.show()


# =========================
#   APP 4: ULTRASONIC SENSOR
# =========================

class UltrasonicApp(BaseApp):
    """
    Ultrasonic Sensor App:
    - Reads distance from HC-SR04 sensor (0-100cm)
    - OLED shows distance in centimeters
    - Matrix shows bar graph (0-100cm mapped to display width)
    - Buzzer alarm sounds when object < threshold
    - DOWN button: Exit to menu
    """

    def __init__(self, board: MechaBoard, threshold_cm=20):
        super().__init__(board, name="ULTRA", frame_ms=100)
        self.threshold_cm = threshold_cm

    def on_enter(self):
        super().on_enter()
        self.board.all_game_leds_off()
        self.board.led_ultra.value(1)  # LED for ULTRA app
        self.board.oled_print_single_line("Ultrasonic App")

    def on_exit(self):
        super().on_exit()
        self.board.led_ultra.value(0)

    def update(self):
        dist = self.board.read_distance_cm()

        # OLED display
        self.board.oled.fill(0)
        self.board.oled.text("Ultrasonic", 0, 0)

        if dist is None:
            self.board.oled.text("No echo", 0, 20)
        else:
            self.board.oled.text("Dist: {:.1f}cm".format(dist), 0, 20)

            # Alarm if too close
            if dist < self.threshold_cm:
                self.board.beep(2000, 50)

        self.board.oled.show()

        # Matrix bar-graph display (0–100 cm mapped to width)
        self.board.matrix.fill(0)
        if dist is not None:
            # Map 0–100 cm to 0–matrix_width
            max_dist = 100.0
            norm = dist / max_dist
            if norm > 1:
                norm = 1
            bar_length = int(norm * self.board.matrix_width)
            # Draw on middle row
            y = 3
            for x in range(bar_length):
                self.board.matrix.pixel(x, y, 1)
        self.board.matrix.show()


# =========================
#   MENU APP
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
        self.board.all_game_leds_off()
        # Small delay to let button states stabilize
        sleep(0.05)
        self.board.oled_clear()
        self.show_current_name()

    def show_current_name(self):
        name = self.apps[self.current_index][0]
        # Show menu on OLED screen
        self.board.oled.fill(0)
        self.board.oled.text("=== MENU ===", 0, 0)
        self.board.oled.text("Selected: {}".format(name), 0, 16)
        self.board.oled.text("< Left/Right >", 0, 32)
        self.board.oled.text("^ UP to select", 0, 48)
        self.board.oled.show()

        # Also show app name on matrix for visibility
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

        # select with UP or encoder button (with debounce)
        if buttons["up"]:
            sleep(0.01)
            buttons_check = self.board.read_buttons()
            if buttons_check["up"]:
                self.selected_app = self.apps[self.current_index][1]
                self.running = False  # signal main loop to switch
                self.board.beep(1200, 80)
                sleep(0.2)
        elif self.board.encoder_button_pressed():
            sleep(0.01)
            if self.board.encoder_button_pressed():
                self.selected_app = self.apps[self.current_index][1]
                self.running = False
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
    ultra_app = UltrasonicApp(board, threshold_cm=25)

    apps = [
        ("BALL", ball_app),
        ("MUSIC", music_app),
        ("SHOOT", shooter_app),
        ("ULTRA", ultra_app),
    ]

    while True:
        menu = MenuApp(board, apps)
        menu.on_enter()

        # Wait a bit for button states to stabilize and clear any initial button presses
        sleep(0.1)
        _ = board.read_buttons()
        _ = board.read_encoder_step()

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
            # Exit app with DOWN button
            buttons = board.read_buttons()
            if buttons["down"]:
                current_app.on_exit()
            sleep(0.01)


# Only run if this is the main file
if __name__ == "__main__":
    main()

