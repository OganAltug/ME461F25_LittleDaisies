from machine import Pin, ADC, SPI
from utime import sleep, ticks_ms, ticks_diff
from max7219 import Matrix8x8
import urandom

class GameSystem:
    # (Hardware Abstraction - This class is unchanged)
    def __init__(self,
                 num_displays=4,
                 button_pin_left=13,
                 button_pin_down=12,
                 button_pin_right=11,
                 button_pin_up=10,
                 pot_pin_left=26,
                 pot_pin_right=27,
                 cs_pin=5, clk_pin=2, din_pin=3):
        self.cs = Pin(cs_pin, Pin.OUT)
        self.spi = SPI(0, baudrate=10_000_000, sck=Pin(clk_pin), mosi=Pin(din_pin))
        self.display = Matrix8x8(self.spi, self.cs, num_displays, orientation=2)
        self.num_displays = num_displays
        self.display_width = 8 * num_displays
        self.display_height = 8
        self.button_left = Pin(button_pin_left, Pin.IN, Pin.PULL_UP)
        self.button_down = Pin(button_pin_down, Pin.IN, Pin.PULL_UP)
        self.button_right = Pin(button_pin_right, Pin.IN, Pin.PULL_UP)
        self.button_up = Pin(button_pin_up, Pin.IN, Pin.PULL_UP)
        self.pot_left = ADC(Pin(pot_pin_left))
        self.pot_right = ADC(Pin(pot_pin_right))
        self.last_update = ticks_ms()
        self.frame_delay = 80
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
        pass # This will be overridden by GunGame

    def run(self):
        while self.running:
            now = ticks_ms()
            if ticks_diff(now, self.last_update) >= self.frame_delay:
                self.last_update = now
                self.update()
            sleep(0.01)


class GunGame(GameSystem):
    
    # 3x5 Pixel Font
    FONT = {
        '0': [7, 5, 5, 5, 7], '1': [2, 6, 2, 2, 7], '2': [7, 1, 7, 4, 7],
        '3': [7, 1, 3, 1, 7], '4': [5, 5, 7, 1, 1], '5': [7, 4, 7, 1, 7],
        '6': [7, 4, 7, 5, 7], '7': [7, 1, 1, 1, 1], '8': [7, 5, 7, 5, 7],
        '9': [7, 5, 7, 1, 7],
        'A': [7, 5, 7, 5, 5], 'B': [6, 5, 6, 5, 6], 'C': [7, 4, 4, 4, 7],
        'D': [6, 5, 5, 5, 6], 'E': [7, 4, 6, 4, 7], 'F': [7, 4, 6, 4, 4],
        'G': [7, 4, 5, 5, 7], 'H': [5, 5, 7, 5, 5], 'I': [7, 2, 2, 2, 7],
        'J': [1, 1, 1, 5, 7], 'K': [5, 6, 4, 6, 5], 'L': [4, 4, 4, 4, 7],
        'M': [5, 7, 7, 5, 5], 'N': [5, 7, 6, 5, 5], 'O': [7, 5, 5, 5, 7],
        'P': [7, 5, 7, 4, 4], 'Q': [7, 5, 5, 3, 7], 'R': [7, 5, 6, 5, 5],
        'S': [7, 4, 7, 1, 7], 'T': [7, 2, 2, 2, 2], 'U': [5, 5, 5, 5, 7],
        'V': [5, 5, 5, 3, 2], 'W': [5, 5, 7, 7, 5], 'X': [5, 5, 2, 5, 5],
        'Y': [5, 5, 7, 1, 1], 'Z': [7, 1, 2, 4, 7],
        '?': [7, 1, 2, 1, 0], '>': [1, 2, 4, 2, 1], ' ': [0, 0, 0, 0, 0],
    }
    
    # 5x8 Pixel "Big" Font
    BIG_FONT = {
        'W': [17, 17, 17, 17, 21, 14, 10, 0], # 0b10001
        'I': [31, 4, 4, 4, 4, 4, 4, 31],      # 0b11111
        'N': [17, 25, 29, 21, 19, 17, 17, 0], # 0b10001
        'L': [16, 16, 16, 16, 16, 16, 16, 31], # 0b10000 <- FIXED
        'O': [14, 17, 17, 17, 17, 17, 14, 0], # 0b01110
        'S': [14, 17, 8, 14, 1, 17, 14, 0],  # 0b01110
        'E': [31, 8, 8, 28, 8, 8, 31, 0],     # 0b11111
        '?': [14, 17, 1, 2, 4, 0, 4, 0],     # 0b01110
    }

    def __init__(self):
        super().__init__()
        
        # State machine
        self.game_state = "MENU" # MENU, GAME, GAME_WON, GAME_OVER
        self.menu_selection = 0
        self.difficulty_levels = ["EASY", "MECH", "HARD", "MEDIUM"] # NITE = Nightmare
        self.difficulty_map = {
            "EASY": "easy", "MEDIUM": "medium", 
            "HARD": "hard", "MECH": "nightmare"
        }
        
        # Button debouncing
        self.button_last_time = {"left":0,"right":0,"up":0,"down":0}
        self.button_debounce = 200 # Longer debounce for menu
        
        # End screen timer
        self.end_screen_start = 0
        self.end_screen_delay = 3000 # 3 seconds
        
        # Placeholder for game vars
        self.player_x = 0
        self.player_y = 0
        self.bullets_in_mag = 0
        self.magazines_left = 0
        self.bullets = []
        self.targets = []
        self.targets_spawned_count = 0
        self.targets_destroyed_count = 0
        self._last_target_spawn = 0
        self.is_reloading = False
        self.reload_start_time = 0
        self.slowdown_budget = 0
        self.slowdown_budget_max = 1
        self.slowdown_factor = 1.0
        self.slowdown_recharge_rate = 0.5
        self.slowdown_warning_threshold = 0.25
        self.game_over = False
        self.win = False 
        self.lose_message = ""
        
    def _start_new_game(self, difficulty_choice_str):
        print(f"Starting game with difficulty: {difficulty_choice_str}")
        difficulty_settings = {
            "easy":   {"mags": 8, "cap": 8, "height": 2, "h_delay": 500, "v_delay": 700, "spawn_delay": 10000, "total_targets": 10, "reload_time": 250, "slow_budget": 10000},
            "medium": {"mags": 5, "cap": 6, "height": 3, "h_delay": 350, "v_delay": 500, "spawn_delay": 8000, "total_targets": 8, "reload_time": 500, "slow_budget": 7000},
            "hard":   {"mags": 3, "cap": 4, "height": 4, "h_delay": 200, "v_delay": 300, "spawn_delay": 6000, "total_targets": 5, "reload_time": 750, "slow_budget": 4000},
            "nightmare": {"mags": 1, "cap": 3, "height": 5, "h_delay": 80, "v_delay": 120, "spawn_delay": 99999, "total_targets": 1, "reload_time": 1000, "slow_budget": 1000},
        }

        settings = difficulty_settings[difficulty_choice_str]
        self.magazines_total = settings["mags"]
        self.mag_capacity = settings["cap"]
        self.target_height = settings["height"]
        self.target_move_delay_h = settings["h_delay"]
        self.target_move_delay_v = settings["v_delay"]
        self.target_spawn_delay = settings["spawn_delay"]
        self.total_targets_to_spawn = settings["total_targets"]
        self.reload_duration = settings["reload_time"]
        self.slowdown_budget_max = settings["slow_budget"]

        # === Initialize game state ===
        self.player_x = 8 
        self.player_y = self.display_height // 2
        self.bullets_in_mag = self.mag_capacity
        self.magazines_left = self.magazines_total - 1
        self.bullets = []
        self.targets = []
        self.targets_spawned_count = 0
        self.targets_destroyed_count = 0
        self._last_target_spawn = ticks_ms()
        self.is_reloading = False
        self.reload_start_time = 0
        self.slowdown_budget = self.slowdown_budget_max
        self.slowdown_recharge_rate = 0.5
        self.slowdown_warning_threshold = self.slowdown_budget_max * 0.25
        self.slowdown_factor = 1.0
        self.game_over = False
        self.win = False 
        self.lose_message = ""
        
        self.spawn_new_target() 
        self.game_state = "GAME"
        self.button_debounce = 150 # Faster debounce for gameplay

    # === Drawing Helpers ===
    def get_char_width(self, font=None):
        return 5 if font == self.BIG_FONT else 3

    def get_text_width(self, text, font=None):
        if not text:
            return 0
        char_width = self.get_char_width(font)
        spacing = 1
        return (len(text) * char_width) + (len(text) - 1) * spacing

    def draw_char(self, char, x_offset, y_offset, font=None):
        if font is None:
            font = self.FONT
        bitmap = font.get(char.upper(), font.get('?', [7, 5, 7, 5, 7]))
        
        char_width = self.get_char_width(font)

        for y, row in enumerate(bitmap):
            for x in range(char_width):
                if (row >> (char_width - 1 - x)) & 1:
                    self.draw_pixel(x_offset + x, y_offset + y, 1)
        return char_width

    def draw_text(self, text, x_offset, y_offset, font=None):
        x = x_offset
        char_width = self.get_char_width(font)
        spacing = 1
        for char in text:
            self.draw_char(char, x, y_offset, font)
            x += char_width + spacing
            
    def draw_centered_text(self, text, y_offset, font=None):
        width = self.get_text_width(text, font)
        x_start = (self.display_width - width) // 2
        self.draw_text(text, x_start, y_offset, font)

    # === State: MENU ===
    def update_menu(self, buttons):
        if self.button_pressed("up", buttons['up']):
            self.menu_selection = (self.menu_selection - 1) % len(self.difficulty_levels)
        
        if self.button_pressed("down", buttons['down']):
            self.menu_selection = (self.menu_selection + 1) % len(self.difficulty_levels)
            
        if self.button_pressed("right", buttons['right']):
            selected_diff_key = self.difficulty_levels[self.menu_selection]
            self._start_new_game(self.difficulty_map[selected_diff_key])
            
    def draw_menu(self):
        # Draw centered difficulty
        level_text = self.difficulty_levels[self.menu_selection]
        self.draw_centered_text(level_text, 2)
        
        # (Button labels removed for minimalism)

    # === State: GAME (All the previous game logic) ===
    def update_game(self, now, buttons, pots_raw):
        # --- Check Win Condition ---
        if self.targets_destroyed_count == self.total_targets_to_spawn:
            self.game_state = "GAME_WON"
            self.end_screen_start = now # Start timer
            return

        # --- Check Lose Condition (Out of Ammo) ---
        no_bullets = self.bullets_in_mag == 0
        no_mags = self.magazines_left == 0
        targets_remain = len(self.targets) > 0
        if no_bullets and no_mags and targets_remain and not self.is_reloading:
            self.game_state = "GAME_OVER"
            self.lose_message = "NO AMMO"
            self.end_screen_start = now # Start timer
            return
        
        # --- Handle Spawning ---
        time_to_spawn = ticks_diff(now, self._last_target_spawn) >= self.target_spawn_delay
        screen_is_clear = len(self.targets) == 0
        more_targets_to_spawn = self.targets_spawned_count < self.total_targets_to_spawn
        if more_targets_to_spawn and (time_to_spawn or screen_is_clear):
            self.spawn_new_target()

        # --- Handle Inputs ---
        raw_y = pots_raw['left']
        self.player_y = int((raw_y / 65535) * (self.display_height - 1))

        pot_val = pots_raw['right']
        desired_factor = 1.0 + ((pot_val) / 65535) * 2.0
        
        if self.slowdown_budget <= 0 and desired_factor > 1.0:
            self.slowdown_factor = 1.0
            self.slowdown_budget = 0
        else:
            self.slowdown_factor = desired_factor
        
        if self.slowdown_factor > 1.0:
            drain = self.frame_delay * (self.slowdown_factor - 1.0)
            self.slowdown_budget = max(0, self.slowdown_budget - drain)
        else:
            recharge = self.frame_delay * self.slowdown_recharge_rate
            self.slowdown_budget = min(self.slowdown_budget_max, self.slowdown_budget + recharge)

        if self.button_pressed("left", buttons['left']):
            self.player_x = max(8, self.player_x - 1) 
        elif self.button_pressed("right", buttons['right']):
            self.player_x = min(15, self.player_x + 1)

        if self.button_pressed("up", buttons['up']):
            if not self.is_reloading and self.magazines_left > 0:
                self.is_reloading = True
                self.reload_start_time = ticks_ms()
                self.magazines_left -= 1
                self.bullets_in_mag = 0 
                print("Reloading...")
            elif self.is_reloading:
                print("Already reloading!")
            else:
                print("No spare magazines.")

        if self.button_pressed("down", buttons['down']):
            if self.is_reloading:
                print("Reloading! Can't shoot.")
            elif self.bullets_in_mag > 0:
                self.spawn_bullet(self.player_x, self.player_y)
                self.bullets_in_mag -= 1
            else:
                print("No bullets left.")

        # --- Update Game State ---
        self.update_targets(self.slowdown_factor) 
        self.update_bullets()
        self.update_reload_status(self.slowdown_factor)
        
    def draw_game(self, now):
        if self.is_reloading:
            self.draw_reloading_numerical()
        else:
            self.draw_ammo_numerical()
            
        # Draw Player (with blink logic)
        draw_player = True
        is_running_low = self.slowdown_budget < self.slowdown_warning_threshold
        if is_running_low and (now // 200) % 2 == 0:
            draw_player = False
        
        if draw_player:
            self.draw_pixel(self.player_x, self.player_y, 1)
        
        for b in self.bullets:
            self.draw_pixel(b['x'], b['y'], 1) 
        self.draw_targets()

    # === State: END SCREENS (MODIFIED) ===
    def update_end_screen(self, now):
        # Wait for a delay, then automatically go back to menu
        if ticks_diff(now, self.end_screen_start) > self.end_screen_delay:
            self.game_state = "MENU"
            self.button_debounce = 200 # Back to menu debounce

    def draw_end_screen(self, win=True):
        if win:
            # "WIN" = 3 chars * 5px wide + 2 * 1px space = 17px
            # (32 - 17) // 2 = 7
            self.draw_text("WIN", 7, 0, self.BIG_FONT)
        else:
            # "LOSE" = 4 chars * 5px wide + 3 * 1px space = 23px
            # (32 - 23) // 2 = 4 (rounds down)
            self.draw_text("LOSE", 4, 0, self.BIG_FONT)

    # === Main Game Loop (Router) ===
    def update(self):
        now = ticks_ms()
        self.clear()
        buttons = self.read_buttons()
        pots_raw = self.read_pots()

        if self.game_state == "MENU":
            self.update_menu(buttons)
            self.draw_menu()
            
        elif self.game_state == "GAME":
            self.update_game(now, buttons, pots_raw)
            self.draw_game(now)
            
        elif self.game_state == "GAME_WON":
            self.update_end_screen(now)
            self.draw_end_screen(win=True)
            
        elif self.game_state == "GAME_OVER":
            self.update_end_screen(now)
            self.draw_end_screen(win=False)

        # REPLAY state is removed

        self.show()
        
    # === Button Debouncer ===
    def button_pressed(self, name, state):
        now = ticks_ms()
        if not state:
            return False
        if ticks_diff(now, self.button_last_time[name]) > self.button_debounce:
            self.button_last_time[name] = now
            return True
        return False
        
    # === Game Logic Helpers (copied from previous version) ===
    def draw_ammo_numerical(self):
        for x in range(8):
            for y in range(8):
                self.draw_pixel(x, y, 0)
        # We need to convert int to str for the draw_char helper
        self.draw_char(str(self.magazines_left), 0, 2)
        self.draw_char(str(self.bullets_in_mag), 4, 2)
            
    def draw_reloading_numerical(self):
        for x in range(8):
            for y in range(8):
                self.draw_pixel(x, y, 0)
        now = ticks_ms()
        elapsed = ticks_diff(now, self.reload_start_time)
        if (elapsed // 100) % 2 == 0:
            self.draw_char(str(self.magazines_left), 0, 2)
            self.draw_char('0', 4, 2)

    def draw_targets(self):
        for t in self.targets:
            for seg_index in range(t['height']):
                y = t['top'] + seg_index
                if 0 <= y < self.display_height:
                    alive = not t['hits'][seg_index]
                    self.draw_pixel(t['x'], y, 1 if alive else 0)

    def spawn_new_target(self):
        if self.targets_spawned_count >= self.total_targets_to_spawn:
            return 
        spawn_y = urandom.randint(0, self.display_height - self.target_height)
        new_target = {
            "x": self.display_width, "top": spawn_y, "height": self.target_height,
            "hits": [False] * self.target_height, "dir": 1,
            "_last_move_h": ticks_ms(), "_last_move_v": ticks_ms(), "destroyed": False
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

    def update_targets(self, current_slowdown_factor):
        now = ticks_ms()
        effective_h_delay = self.target_move_delay_h * current_slowdown_factor
        effective_v_delay = self.target_move_delay_v * current_slowdown_factor

        for t in self.targets:
            if ticks_diff(now, t['_last_move_h']) >= effective_h_delay:
                t['_last_move_h'] = now
                t['x'] -= 1
                if t['x'] < 8:
                    self.game_state = "GAME_OVER"
                    self.lose_message = "BREACH"
                    self.end_screen_start = now # Start timer
                    return
                player_collides_y = t['top'] <= self.player_y < (t['top'] + t['height'])
                if t['x'] == self.player_x and player_collides_y:
                    self.game_state = "GAME_OVER"
                    self.lose_message = "HIT"
                    self.end_screen_start = now # Start timer
                    return
            if ticks_diff(now, t['_last_move_v']) >= effective_v_delay:
                t['_last_move_v'] = now
                next_top = t['top'] + t['dir']
                if next_top < 0 or next_top + t['height'] > self.display_height:
                    t['dir'] *= -1
                    next_top = t['top'] + t['dir']
                t['top'] = next_top

    def update_reload_status(self, current_slowdown_factor):
        if not self.is_reloading:
            return
        effective_reload_duration = self.reload_duration * current_slowdown_factor
        now = ticks_ms()
        if ticks_diff(now, self.reload_start_time) >= effective_reload_duration:
            self.is_reloading = False
            self.bullets_in_mag = self.mag_capacity
            print("Reload complete!")

# Run the game
game = GunGame()
game.run()