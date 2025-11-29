# tetris_pc.py — Two-player cooperative Tetris (Python only, no Pico/MicroPython)
# - Virtual 16×32 matrix (16 horizontal, 32 vertical) drawn with pygame
# - Shared arena is the LEFT 8 columns; columns 8–9 are empty (gap)
# - Right HUD (scores + next pieces)
# - Both players receive their pieces at the same time. Next pair spawns ONLY after both have locked.
# - Line clear flickers briefly before removal.
#
# Controls
#   Player 1: A/D = left/right, S = soft drop, E = rotate CW, Q = rotate CCW
#   Player 2: ←/→ = left/right, ↓ = soft drop, / = rotate CW, . = rotate CCW
#   Global:   P = pause menu; 1/2/3 = menu choices; Esc or Q = quit
#
# Requirements:  pip install pygame

import sys, random, time
import pygame

# ------------------------------ CONFIG --------------------------------
VIRT_W, VIRT_H = 16, 32        # virtual LED matrix size
PLAYFIELD_W, PLAYFIELD_H = 8, 32
GAP_W = 2                      # columns 8–9 reserved blank
HUD_W_PIXELS = 220             # right side HUD panel width (pixels)
SCALE = 18                     # size of each "LED" square in pixels
FPS = 60

GRAVITY_TICKS = 12             # frames per automatic drop
LINE_FLICKER_FRAMES = 8        # frames to flicker full lines

# ------------------------------ PIECES --------------------------------
PIECES = {
    'I': [
        [(0,1),(1,1),(2,1),(3,1)],
        [(2,0),(2,1),(2,2),(2,3)],
        [(0,2),(1,2),(2,2),(3,2)],
        [(1,0),(1,1),(1,2),(1,3)],
    ],
    'O': [
        [(1,1),(2,1),(1,2),(2,2)],
    ] * 4,
    'T': [
        [(1,1),(0,1),(2,1),(1,2)],
        [(1,1),(1,0),(1,2),(2,1)],
        [(1,1),(0,1),(2,1),(1,0)],
        [(1,1),(1,0),(1,2),(0,1)],
    ],
    'L': [
        [(1,1),(0,1),(2,1),(2,2)],
        [(1,1),(1,0),(1,2),(2,0)],
        [(1,1),(0,0),(0,1),(2,1)],
        [(1,1),(1,0),(1,2),(0,2)],
    ],
    'J': [
        [(1,1),(0,1),(2,1),(0,2)],
        [(1,1),(1,0),(1,2),(2,2)],
        [(1,1),(0,1),(2,1),(2,0)],
        [(1,1),(1,0),(1,2),(0,0)],
    ],
    'S': [
        [(1,1),(2,1),(0,2),(1,2)],
        [(1,1),(1,0),(2,1),(2,2)],
        [(1,0),(2,0),(0,1),(1,1)],
        [(0,0),(0,1),(1,1),(1,2)],
    ],
    'Z': [
        [(0,1),(1,1),(1,2),(2,2)],
        [(2,0),(2,1),(1,1),(1,2)],
        [(0,0),(1,0),(1,1),(2,1)],
        [(1,0),(1,1),(0,1),(0,2)],
    ],
}
PIECE_ORDER = tuple(PIECES.keys())

# ------------------------------ MODEL ---------------------------------
class Falling:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.rot = 0
        self.x = x
        self.y = y
        self.locked = False
    @property
    def cells(self):
        return PIECES[self.kind][self.rot]

class Game:
    def __init__(self):
        # arena (shared)
        self.grid = [[0]*PLAYFIELD_W for _ in range(PLAYFIELD_H)]

        # pieces / players
        self.f1 = None
        self.f2 = None
        self.next1 = self.rand_piece()
        self.next2 = self.rand_piece()
        self.score1 = 0
        self.score2 = 0

        # flow
        self.gravity_ctr = 0
        self.line_flicker = 0
        self.flicker_lines = []

        self.state = "title"  # title | playing | paused
        self.running = True

    def rand_piece(self):
        return random.choice(PIECE_ORDER)

    def reset_new(self):
        self.grid = [[0]*PLAYFIELD_W for _ in range(PLAYFIELD_H)]
        self.f1 = None; self.f2 = None
        self.next1 = self.rand_piece()
        self.next2 = self.rand_piece()
        self.score1 = 0; self.score2 = 0
        self.gravity_ctr = 0
        self.line_flicker = 0
        self.flicker_lines = []
        self.spawn_pair()
        self.state = "playing"

    def spawn_pair(self):
        # spawn near center
        self.f1 = Falling(self.next1, 2, 0)
        self.f2 = Falling(self.next2, 5, 0)
        self.next1 = self.rand_piece()
        self.next2 = self.rand_piece()
        if not self.can_place(self.f1, 0, 0) or not self.can_place(self.f2, 0, 0):
            self.state = "title"  # overflow -> back to title

    def can_place(self, f, dx, dy, drot=0):
        rot = (f.rot + drot) % 4
        cells = PIECES[f.kind][rot]
        for (cx,cy) in cells:
            x = f.x + dx + cx
            y = f.y + dy + cy
            if x < 0 or x >= PLAYFIELD_W or y < 0 or y >= PLAYFIELD_H:
                return False
            if self.grid[y][x]:
                return False
        return True

    def lock_piece(self, f, pid):
        for (cx,cy) in f.cells:
            x = f.x + cx; y = f.y + cy
            if 0 <= x < PLAYFIELD_W and 0 <= y < PLAYFIELD_H:
                self.grid[y][x] = pid  # store owner (1 or 2)
        f.locked = True

    def mark_full_lines(self):
        fulls = [y for y in range(PLAYFIELD_H) if all(self.grid[y][x] for x in range(PLAYFIELD_W))]
        if fulls:
            self.flicker_lines = fulls
            self.line_flicker = LINE_FLICKER_FRAMES
            return len(fulls)
        return 0

    def apply_line_clears(self):
        removed = 0
        for y in sorted(self.flicker_lines):
            del self.grid[y]
            self.grid.insert(0, [0]*PLAYFIELD_W)
            removed += 1
        self.flicker_lines = []
        self.line_flicker = 0
        return removed

    # -------------------------- UPDATE LOOP ---------------------------
    def update(self):
        if self.state != "playing":
            return

        # gravity
        self.gravity_ctr += 1
        if self.gravity_ctr >= GRAVITY_TICKS:
            self.gravity_ctr = 0
            for (f, pid) in ((self.f1,1), (self.f2,2)):
                if f and not f.locked:
                    if self.can_place(f, 0, +1):
                        f.y += 1
                    else:
                        self.lock_piece(f, pid)

        # coordinated advance: proceed only after both locked
        if (self.f1 and self.f1.locked) and (self.f2 and self.f2.locked):
            if self.line_flicker == 0 and not self.flicker_lines:
                n = self.mark_full_lines()
                if n == 0:
                    self.f1 = None; self.f2 = None
                    self.spawn_pair()
                # else: wait for flicker frames
            else:
                self.line_flicker -= 1
                if self.line_flicker <= 0:
                    removed = self.apply_line_clears()
                    pts = 100 * removed
                    self.score1 += pts; self.score2 += pts
                    self.f1 = None; self.f2 = None
                    self.spawn_pair()

    # ---------------------------- INPUT --------------------------------
    def handle_key(self, key):
        # quit
        if key in (pygame.K_q, pygame.K_ESCAPE):
            self.running = False
            return

        if self.state == "title":
            # any of: Enter/1/space -> start
            if key in (pygame.K_RETURN, pygame.K_1, pygame.K_SPACE):
                self.reset_new()
            return

        if self.state == "paused":
            if key == pygame.K_1:   # continue
                self.state = "playing"
            elif key == pygame.K_2: # restart
                self.reset_new()
            elif key == pygame.K_3: # back to title
                self.state = "title"
            return

        # playing:
        if key == pygame.K_p:
            self.state = "paused"
            return

        # Player 1
        if self.f1 and not self.f1.locked:
            if key == pygame.K_a and self.can_place(self.f1, -1, 0): self.f1.x -= 1
            elif key == pygame.K_d and self.can_place(self.f1, +1, 0): self.f1.x += 1
            elif key == pygame.K_s:
                if self.can_place(self.f1, 0, +1): self.f1.y += 1
                else: self.lock_piece(self.f1, 1)
            elif key == pygame.K_e and self.can_place(self.f1, 0, 0, +1): self.f1.rot = (self.f1.rot + 1) % 4
            elif key == pygame.K_q and self.can_place(self.f1, 0, 0, -1): self.f1.rot = (self.f1.rot - 1) % 4

        # Player 2
        if self.f2 and not self.f2.locked:
            if key == pygame.K_LEFT and self.can_place(self.f2, -1, 0): self.f2.x -= 1
            elif key == pygame.K_RIGHT and self.can_place(self.f2, +1, 0): self.f2.x += 1
            elif key == pygame.K_DOWN:
                if self.can_place(self.f2, 0, +1): self.f2.y += 1
                else: self.lock_piece(self.f2, 2)
            elif key == pygame.K_SLASH and self.can_place(self.f2, 0, 0, +1): self.f2.rot = (self.f2.rot + 1) % 4
            elif key == pygame.K_PERIOD and self.can_place(self.f2, 0, 0, -1): self.f2.rot = (self.f2.rot - 1) % 4

# ------------------------------ RENDER --------------------------------
def draw_virtual(surface, game):
    # background
    surface.fill((10,10,12))
    # draw 16×32 grid (only left 8 used for blocks)
    # we still show pixels for the whole grid for a faithful "matrix" feel
    for y in range(VIRT_H):
        for x in range(VIRT_W):
            # lit?
            v = 0
            # playfield blocks
            if x < PLAYFIELD_W and y < PLAYFIELD_H:
                v = 1 if game.grid[y][x] else 0
                # line flicker
                if game.line_flicker > 0 and y in game.flicker_lines:
                    if game.line_flicker % 2:
                        v = 0
            # falling pieces
            for f in (game.f1, game.f2):
                if f and not f.locked:
                    for (cx,cy) in f.cells:
                        if (f.x+cx) == x and (f.y+cy) == y:
                            v = 1
            # draw pixel
            color = (220,220,220) if v else (24,24,26)
            pygame.draw.rect(surface, color, (x*SCALE, y*SCALE, SCALE-1, SCALE-1))

    # optional: vertical separators for gap region (cols 8–9)
    gx0 = PLAYFIELD_W * SCALE
    gx1 = (PLAYFIELD_W + GAP_W) * SCALE
    pygame.draw.line(surface, (60,60,65), (gx0, 0), (gx0, VIRT_H*SCALE))
    pygame.draw.line(surface, (60,60,65), (gx1, 0), (gx1, VIRT_H*SCALE))

def draw_hud(win, game, x0):
    pygame.draw.rect(win, (35,38,45), (x0, 0, HUD_W_PIXELS, VIRT_H*SCALE))
    font = pygame.font.SysFont(None, 24)
    big  = pygame.font.SysFont(None, 28)

    win.blit(big.render("Co-op Tetris", True, (240,240,255)), (x0+12, 10))
    win.blit(font.render(f"P1 Score: {game.score1}", True, (230,230,230)), (x0+12, 48))
    win.blit(font.render(f"P2 Score: {game.score2}", True, (230,230,230)), (x0+12, 72))
    win.blit(font.render(f"Next P1: {game.next1}", True, (220,220,220)), (x0+12, 110))
    win.blit(font.render(f"Next P2: {game.next2}", True, (220,220,220)), (x0+12, 134))

    if game.state == "title":
        y = 190
        win.blit(big.render("Tetris Game", True, (255,220,120)), (x0+12, y)); y+=30
        win.blit(font.render("Press Enter/1/Space to Start", True, (220,220,220)), (x0+12, y)); y+=24
        win.blit(font.render("Q/Esc to Quit", True, (180,180,180)), (x0+12, y))
    elif game.state == "paused":
        y = 190
        win.blit(big.render("PAUSED", True, (255,210,0)), (x0+12, y)); y+=30
        win.blit(font.render("1) Continue", True, (220,220,220)), (x0+12, y)); y+=22
        win.blit(font.render("2) Restart", True, (220,220,220)), (x0+12, y)); y+=22
        win.blit(font.render("3) Main Menu", True, (220,220,220)), (x0+12, y))

# ------------------------------ MAIN ----------------------------------
def main():
    pygame.init()
    W = VIRT_W*SCALE + HUD_W_PIXELS
    H = VIRT_H*SCALE
    win = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Two-Player Co-op Tetris (Python)")
    clock = pygame.time.Clock()
    font_ready = pygame.font.SysFont(None, 24)  # warm up font cache

    random.seed()
    game = Game()

    # Auto-start after short delay to avoid confusion
    autostart_ms = pygame.time.get_ticks()
    started_auto = False

    while game.running:
        # events
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                game.running = False
            elif ev.type == pygame.KEYDOWN:
                game.handle_key(ev.key)

        # auto-start from title after 2 seconds
        if game.state == "title" and not started_auto:
            if pygame.time.get_ticks() - autostart_ms > 2000:
                game.reset_new()
                started_auto = True

        # update
        game.update()

        # draw virtual matrix
        virt = pygame.Surface((VIRT_W*SCALE, VIRT_H*SCALE))
        draw_virtual(virt, game)
        win.blit(virt, (0,0))

        # draw HUD
        draw_hud(win, game, VIRT_W*SCALE)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
