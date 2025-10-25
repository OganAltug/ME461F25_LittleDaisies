from machine import Pin, ADC, SPI
from utime import sleep, ticks_ms, ticks_diff
from max7219 import Matrix8x8
import urandom

class GameSystem:
    def __init__(self,
                 num_displays=4,
                 button_pin_left=13,
                 button_pin_down=12,
                 button_pin_right=11,
                 button_pin_up=10,
                 pot_pin_left=26,
                 pot_pin_right=27,
                 cs_pin=5, clk_pin=2, din_pin=3):
        # SPI + display
        self.cs = Pin(cs_pin, Pin.OUT)
        self.spi = SPI(0, baudrate=10_000_000, sck=Pin(clk_pin), mosi=Pin(din_pin))
        self.display = Matrix8x8(self.spi, self.cs, num_displays, orientation=2)
        self.num_displays = num_displays
        self.display_width = 8 * num_displays
        self.display_height = 8

        # Buttons
        self.button_left = Pin(button_pin_left, Pin.IN, Pin.PULL_UP)
        self.button_down = Pin(button_pin_down, Pin.IN, Pin.PULL_UP)
        self.button_right = Pin(button_pin_right, Pin.IN, Pin.PULL_UP)
        self.button_up = Pin(button_pin_up, Pin.IN, Pin.PULL_UP)

        # Pots
        self.pot_left = ADC(Pin(pot_pin_left))
        self.pot_right = ADC(Pin(pot_pin_right))

        # Timing
        self.last_update = ticks_ms()
        self.frame_delay = 80  # Aim for ~12.5 FPS
        self.running = True

    def clear(self):
        self.display.fill(0)

    def draw_pixel(self, x, y, val=1):
        if 0 <= x < self.display_width and 0 <= y < self.display_height:
            self.display.pixel(x, y, val)

    def show(self):
        self.display.show()

    def read_buttons(self):
        return {
            "left":  not self.button_left.value(),
            "down":  not self.button_down.value(),
            "right": not self.button_right.value(),
            "up":    not self.button_up.value()
        }

    def read_pots(self):
        return {
            "left": self.pot_left.read_u16(),
            "right": self.pot_right.read_u16()
        }

    def update(self):
        pass

    def run(self):
        while self.running:
            now = ticks_ms()
            if ticks_diff(now, self.last_update) >= self.frame_delay:
                self.last_update = now
                self.update()
            sleep(0.01)


class GunGame(GameSystem):
    def __init__(self):
        # 3x5 Pixel Font (bitmaps for digits 0-9)
        self.TINY_FONT = {
            0: [7, 5, 5, 5, 7], # 0b111, 0b101, 0b101, 0b101, 0b111
            1: [2, 6, 2, 2, 7], # 0b010, 0b110, 0b010, 0b010, 0b111
            2: [7, 1, 7, 4, 7], # 0b111, 0b001, 0b111, 0b100, 0b111
            3: [7, 1, 3, 1, 7], # 0b111, 0b001, 0b011, 0b001, 0b111
            4: [5, 5, 7, 1, 1], # 0b101, 0b101, 0b111, 0b001, 0b001
            5: [7, 4, 7, 1, 7], # 0b111, 0b100, 0b111, 0b001, 0b111
            6: [7, 4, 7, 5, 7], # 0b111, 0b100, 0b111, 0b101, 0b111
            7: [7, 1, 1, 1, 1], # 0b111, 0b001, 0b001, 0b001, 0b001
            8: [7, 5, 7, 5, 7], # 0b111, 0b101, 0b111, 0b101, 0b111
            9: [7, 5, 7, 1, 7], # 0b111, 0b101, 0b111, 0b001, 0b111
        }
        super().__init__()
        self.initialize_game()

    def initialize_game(self):
        print("Welcome to GunGame!")
        
        difficulty_settings = {
            "easy":   {"mags": 8, "cap": 8, "height": 2, "h_delay": 500, "v_delay": 700, "spawn_delay": 10000, "total_targets": 10, "reload_time": 250, "slow_budget": 10000},
            "medium": {"mags": 5, "cap": 6, "height": 3, "h_delay": 350, "v_delay": 500, "spawn_delay": 8000, "total_targets": 8, "reload_time": 500, "slow_budget": 7000},
            "hard":   {"mags": 3, "cap": 4, "height": 4, "h_delay": 200, "v_delay": 300, "spawn_delay": 6000, "total_targets": 5, "reload_time": 750, "slow_budget": 4000},
            "nightmare": {"mags": 1, "cap": 3, "height": 5, "h_delay": 80, "v_delay": 120, "spawn_delay": 99999, "total_targets": 1, "reload_time": 1000, "slow_budget": 1000},
        }

        # Select difficulty
        while True:
            try:
                choice = input("Enter difficulty (easy, medium, hard, nightmare): ").lower()
                if choice in difficulty_settings:
                    settings = difficulty_settings[choice]
                    self.magazines_total = settings["mags"]
                    self.mag_capacity = settings["cap"]
                    self.target_height = settings["height"]
                    self.target_move_delay_h = settings["h_delay"]
                    self.target_move_delay_v = settings["v_delay"]
                    self.target_spawn_delay = settings["spawn_delay"]
                    self.total_targets_to_spawn = settings["total_targets"]
                    self.reload_duration = settings["reload_time"]
                    self.slowdown_budget_max = settings["slow_budget"] # Added
                    print(f"Difficulty set to: {choice.upper()}")
                    break
                else:
                    print("Invalid input, try again.")
            except:
                print("Invalid input, try again.")

        print("Game started!")

        # === Initialize game state ===
        self.player_x = 8 
        self.player_y = self.display_height // 2

        # Ammo
        self.bullets_in_mag = self.mag_capacity
        self.magazines_left = self.magazines_total - 1
        self.bullets = []

        # Target Management
        self.targets = []
        self.targets_spawned_count = 0
        self.targets_destroyed_count = 0
        self._last_target_spawn = ticks_ms()
        self.spawn_new_target() 

        # Button timing / debouncing
        self.button_last_time = {"left":0,"right":0,"up":0,"down":0}
        self.button_debounce = 150

        # Reloading State
        self.is_reloading = False
        self.reload_start_time = 0

        # Slowdown State
        self.slowdown_budget = self.slowdown_budget_max
        self.slowdown_recharge_rate = 0.5 # 50% recharge rate
        self.slowdown_warning_threshold = self.slowdown_budget_max * 0.25
        self.slowdown_factor = 1.0 # Current slowdown (1.0 = normal)

        # Game running flag
        self.game_over = False
        self.win = False 
        self.lose_message = ""

    # === Drawing ===
    def draw_number(self, number, x_offset, y_offset):
        if number < 0 or number > 9:
            bitmap = [7, 4, 6, 4, 7] # 'E'
        else:
            bitmap = self.TINY_FONT[number]
        
        for y, row in enumerate(bitmap):
            for x in range(3): # Font is 3 pixels wide
                if (row >> (2 - x)) & 1:
                    self.draw_pixel(x_offset + x, y_offset + y, 1)

    def draw_ammo_numerical(self):
        # Clear first 8x8 matrix
        for x in range(8):
            for y in range(8):
                self.draw_pixel(x, y, 0)
        
        self.draw_number(self.magazines_left, 0, 2)
        self.draw_number(self.bullets_in_mag, 4, 2)
            
    def draw_reloading_numerical(self):
        for x in range(8):
            for y in range(8):
                self.draw_pixel(x, y, 0)
                
        now = ticks_ms()
        elapsed = ticks_diff(now, self.reload_start_time)
        
        if (elapsed // 100) % 2 == 0:
            self.draw_number(self.magazines_left, 0, 2)
            self.draw_number(0, 4, 2)

    def draw_targets(self):
        for t in self.targets:
            for seg_index in range(t['height']):
                y = t['top'] + seg_index
                if 0 <= y < self.display_height:
                    alive = not t['hits'][seg_index]
                    self.draw_pixel(t['x'], y, 1 if alive else 0)

    # === Spawning / Bullets ===
    def spawn_new_target(self):
        if self.targets_spawned_count >= self.total_targets_to_spawn:
            return 
        
        spawn_y = urandom.randint(0, self.display_height - self.target_height)
        
        new_target = {
            "x": self.display_width,
            "top": spawn_y,
            "height": self.target_height,
            "hits": [False] * self.target_height,
            "dir": 1,
            "_last_move_h": ticks_ms(),
            "_last_move_v": ticks_ms(),
            "destroyed": False
        }
        self.targets.append(new_target)
        self.targets_spawned_count += 1
        self._last_target_spawn = ticks_ms()
        print(f"New target spawned! ({self.targets_spawned_count}/{self.total_targets_to_spawn})")

    def spawn_bullet(self, x, y):
        self.bullets.append({"x": x, "y": y})

    def update_bullets(self):
        new_bullets = []
        for b in self.bullets:
            b['x'] += 1
            hit_a_target = False
            
            for t in self.targets:
                if b['x'] == t['x']:
                    rel = b['y'] - t['top']
                    if 0 <= rel < t['height'] and not t['hits'][rel]:
                        t['hits'][rel] = True
                        print(f"Bullet hit target at segment {rel}!")
                        hit_a_target = True 
                        
                        num_hits = sum(t['hits'])
                        if num_hits >= (t['height'] / 2):
                            t['destroyed'] = True
                            self.targets_destroyed_count += 1
                            print("Target destroyed!")
                        
                        break 
            
            if hit_a_target:
                continue 
            
            if b['x'] < self.display_width:
                new_bullets.append(b)
        
        self.bullets = new_bullets
        self.targets = [t for t in self.targets if not t['destroyed']]


    # === Target movement (MODIFIED) ===
    def update_targets(self, current_slowdown_factor):
        now = ticks_ms()
        # Calculate effective delays
        effective_h_delay = self.target_move_delay_h * current_slowdown_factor
        effective_v_delay = self.target_move_delay_v * current_slowdown_factor

        for t in self.targets:
            if ticks_diff(now, t['_last_move_h']) >= effective_h_delay:
                t['_last_move_h'] = now
                t['x'] -= 1
                
                if t['x'] < 8:
                    self.game_over = True
                    self.win = False
                    self.lose_message = "☠️ Target breached your defense!"
                    return

                player_collides_y = t['top'] <= self.player_y < (t['top'] + t['height'])
                if t['x'] == self.player_x and player_collides_y:
                    self.game_over = True
                    self.win = False
                    self.lose_message = "☠️ Direct hit on player!"
                    return

            if ticks_diff(now, t['_last_move_v']) >= effective_v_delay:
                t['_last_move_v'] = now
                next_top = t['top'] + t['dir']
                if next_top < 0 or next_top + t['height'] > self.display_height:
                    t['dir'] *= -1
                    next_top = t['top'] + t['dir']
                t['top'] = next_top

    # === Reloading (MODIFIED) ===
    def update_reload_status(self, current_slowdown_factor):
        if not self.is_reloading:
            return
        
        effective_reload_duration = self.reload_duration * current_slowdown_factor
        
        now = ticks_ms()
        if ticks_diff(now, self.reload_start_time) >= effective_reload_duration:
            self.is_reloading = False
            self.bullets_in_mag = self.mag_capacity
            print("Reload complete!")

    # === Pot & buttons ===
    def button_pressed(self, name, state):
        now = ticks_ms()
        if not state:
            return False
        if ticks_diff(now, self.button_last_time[name]) > self.button_debounce:
            self.button_last_time[name] = now
            return True
        return False

    # === Main update ===
    def update(self):
        now = ticks_ms()
        
        # --- Check Game Over Conditions ---
        if self.game_over:
            self.clear()
            self.show()
            
            if self.win:
                print("🎯 All targets destroyed! You win!")
            else:
                print(self.lose_message) 

            print("------------------------------------")
            
            while True:
                try:
                    again = input("Play again? (y/n): ").lower()
                    if again == "y":
                        self.initialize_game()
                        return
                    elif again == "n":
                        print("Game over. Thanks for playing!")
                        self.running = False
                        return
                    else:
                        print("Invalid input. Please enter 'y' or 'n'.")
                except:
                    print("Invalid input. Please enter 'y' or 'n'.")
        
        # --- Check Win Condition ---
        if self.targets_destroyed_count == self.total_targets_to_spawn:
            self.game_over = True
            self.win = True
            return

        # --- Check Lose Condition (Out of Ammo) ---
        no_bullets = self.bullets_in_mag == 0
        no_mags = self.magazines_left == 0
        targets_remain = len(self.targets) > 0
        
        if no_bullets and no_mags and targets_remain and not self.is_reloading:
            self.game_over = True
            self.win = False
            self.lose_message = "☠️ Out of ammo! Target remains."
            return
        
        # --- Handle Spawning ---
        time_to_spawn = ticks_diff(now, self._last_target_spawn) >= self.target_spawn_delay
        screen_is_clear = len(self.targets) == 0
        more_targets_to_spawn = self.targets_spawned_count < self.total_targets_to_spawn
        
        if more_targets_to_spawn and (time_to_spawn or screen_is_clear):
            self.spawn_new_target()

        # --- Handle Inputs ---
        self.clear()
        buttons = self.read_buttons()
        pots_raw = self.read_pots()

        # Left pot (Player Y)
        raw_y = pots_raw['left']
        self.player_y = int((raw_y / 65535) * (self.display_height - 1))

        # --- Right pot (Slowdown) ---
        pot_val = pots_raw['right']
        # Map 0-65535 to a 3.0x - 1.0x factor
        # (65535 -> 1.0x, 0 -> 3.0x)
        desired_factor = 1.0 + ((65535 - pot_val) / 65535) * 2.0
        
        if self.slowdown_budget <= 0 and desired_factor > 1.0:
            self.slowdown_factor = 1.0 # Force normal speed, out of budget
            self.slowdown_budget = 0
        else:
            self.slowdown_factor = desired_factor
        
        # Update budget
        if self.slowdown_factor > 1.0:
            # Drain budget proportional to slowdown amount
            drain = self.frame_delay * (self.slowdown_factor - 1.0)
            self.slowdown_budget = max(0, self.slowdown_budget - drain)
        else:
            # Recharge budget
            recharge = self.frame_delay * self.slowdown_recharge_rate
            self.slowdown_budget = min(self.slowdown_budget_max, self.slowdown_budget + recharge)
        # --- End Slowdown Logic ---

        # Player X movement
        if self.button_pressed("left", buttons['left']):
            self.player_x = max(8, self.player_x - 1) 
        elif self.button_pressed("right", buttons['right']):
            self.player_x = min(15, self.player_x + 1)

        # Up: reload
        if self.button_pressed("up", buttons['up']):
            if self.is_reloading:
                print("Already reloading!")
            elif self.magazines_left > 0:
                self.is_reloading = True
                self.reload_start_time = ticks_ms()
                self.magazines_left -= 1
                self.bullets_in_mag = 0 
                print("Up button pressed! Reloading...")
            else:
                print("Up button pressed! No spare magazines.")

        # Down: shoot
        if self.button_pressed("down", buttons['down']):
            if self.is_reloading:
                print("Reloading! Can't shoot.")
            elif self.bullets_in_mag > 0:
                self.spawn_bullet(self.player_x, self.player_y)
                self.bullets_in_mag -= 1
                print("Down button pressed! Bullet shot.")
            else:
                print("Down button pressed! No bullets left.")

        # --- Update Game State ---
        self.update_targets(self.slowdown_factor) 
        self.update_bullets()
        self.update_reload_status(self.slowdown_factor) 

        # --- Draw Everything ---
        if self.is_reloading:
            self.draw_reloading_numerical()
        else:
            self.draw_ammo_numerical()
            
        # Draw Player (with blink logic)
        draw_player = True
        is_running_low = self.slowdown_budget < self.slowdown_warning_threshold
        if is_running_low and (now // 200) % 2 == 0: # Blink every 200ms
            draw_player = False
        
        if draw_player:
            self.draw_pixel(self.player_x, self.player_y, 1)
        
        for b in self.bullets:
            self.draw_pixel(b['x'], b['y'], 1) # Draw bullets
        self.draw_targets() # Draw all active targets
        
        self.show()

# Run the game
game = GunGame()
game.run()