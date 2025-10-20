"""
Snake Eater
Made with PyGame
"""

import pygame, sys, random

# Difficulty (lower = slower, easier)
# Example values: Easy=5, Medium=10, Hard=25
difficulty = 5   # slowed down for easier play

# Window size
frame_size_x = 720
frame_size_y = 480

# Initialize pygame
check_errors = pygame.init()
if check_errors[1] > 0:
    print(f'[!] Had {check_errors[1]} errors when initializing game, exiting...')
    sys.exit(-1)
else:
    print('[+] Game successfully initialized')

# Game window
pygame.display.set_caption('Snake Eater')
game_window = pygame.display.set_mode((frame_size_x, frame_size_y))

# Colors (R, G, B)
black = pygame.Color(0, 0, 0)
white = pygame.Color(255, 255, 255)
red = pygame.Color(255, 0, 0)
green = pygame.Color(0, 255, 0)
blue = pygame.Color(0, 0, 255)

random_flag = False

# FPS controller
fps_controller = pygame.time.Clock()

# ---------- GAME FUNCTIONS ----------

def init_vars():
    """Initialize or reset all game variables."""
    global snake_pos, snake_body, food_pos, food_spawn, direction, change_to, score
    snake_pos = [100, 50]
    snake_body = [[100, 50], [90, 50], [80, 50]]
    food_pos = [random.randrange(1, (frame_size_x // 10)) * 10,
                random.randrange(1, (frame_size_y // 10)) * 10]
    food_spawn = True
    direction = 'RIGHT'
    change_to = direction
    score = 0
    random_flag = False

def show_score(choice, color, font, size):
    score_font = pygame.font.SysFont(font, size)
    score_surface = score_font.render('Score : ' + str(score), True, color)
    score_rect = score_surface.get_rect()
    if choice == 1:
        score_rect.midtop = (frame_size_x / 10, 15)
    else:
        score_rect.midtop = (frame_size_x / 2, frame_size_y / 1.25)
    game_window.blit(score_surface, score_rect)

def wait_for_space(message):
    """Display a message and wait for SPACE to start."""
    game_window.fill(black)
    title_font = pygame.font.SysFont('times new roman', 60)
    text_surface = title_font.render(message, True, white)
    text_rect = text_surface.get_rect(center=(frame_size_x / 2, frame_size_y / 2.5))
    game_window.blit(text_surface, text_rect)

    small_font = pygame.font.SysFont('consolas', 25)
    prompt_surface = small_font.render('Press SPACE to start, ESC to quit', True, blue)
    prompt_rect = prompt_surface.get_rect(center=(frame_size_x / 2, frame_size_y / 1.5))
    game_window.blit(prompt_surface, prompt_rect)

    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    waiting = False
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
            elif event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

def game_over():
    """Display the game-over screen and wait for SPACE to restart."""
    my_font = pygame.font.SysFont('times new roman', 90)
    game_over_surface = my_font.render('YOU DIED', True, red)
    game_over_rect = game_over_surface.get_rect(center=(frame_size_x / 2, frame_size_y / 3))

    game_window.fill(black)
    game_window.blit(game_over_surface, game_over_rect)
    show_score(0, red, 'times', 20)

    restart_font = pygame.font.SysFont('consolas', 25)
    restart_surface = restart_font.render('Press SPACE to restart or ESC to quit', True, white)
    restart_rect = restart_surface.get_rect(center=(frame_size_x / 2, frame_size_y / 1.6))
    game_window.blit(restart_surface, restart_rect)

    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:  # SPACE -> restart
                    init_vars()
                    waiting = False
                elif event.key == pygame.K_ESCAPE:  # ESC -> quit
                    pygame.quit()
                    sys.exit()
            elif event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

# ---------- MAIN GAME LOOP ----------

init_vars()
wait_for_space("Snake Eater")  # show start screen first

while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP or event.key == ord('w'):
                if not random_flag:
                    change_to = 'UP'
                else:
                    change_to = 'DOWN'
            if event.key == pygame.K_DOWN or event.key == ord('s'):
                if not random_flag:    
                    change_to = 'DOWN'
                else:
                    change_to = 'UP'
            if event.key == pygame.K_LEFT or event.key == ord('a'):
                if not random_flag:    
                    change_to = 'LEFT'
                else:
                    change_to = 'RIGHT'
            if event.key == pygame.K_RIGHT or event.key == ord('d'):
                if not random_flag:
                    change_to = 'RIGHT'
                else:
                    change_to = 'LEFT'
            if event.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    # Prevent opposite direction moves
    if change_to == 'UP' and direction != 'DOWN':
        direction = 'UP'
    if change_to == 'DOWN' and direction != 'UP':
        direction = 'DOWN'
    if change_to == 'LEFT' and direction != 'RIGHT':
        direction = 'LEFT'
    if change_to == 'RIGHT' and direction != 'LEFT':
        direction = 'RIGHT'

    # Move the snake
    if direction == 'UP':
        snake_pos[1] -= 10
    if direction == 'DOWN':
        snake_pos[1] += 10
    if direction == 'LEFT':
        snake_pos[0] -= 10
    if direction == 'RIGHT':
        snake_pos[0] += 10

    # Snake body growing mechanism
    snake_body.insert(0, list(snake_pos))
    if snake_pos[0] == food_pos[0] and snake_pos[1] == food_pos[1]:
        score += 1
        randomizer = random.randint(0,9)
        if randomizer > 2:
            if random_flag:
                random_flag = False
            else:
                random_flag = True
        food_spawn = False
    else:
        snake_body.pop()

    # Spawn food
    if not food_spawn:
        food_pos = [random.randrange(1, (frame_size_x // 10)) * 10,
                    random.randrange(1, (frame_size_y // 10)) * 10]
    food_spawn = True

    # Graphics
    game_window.fill(black)
    for pos in snake_body:
        if not random_flag:    
            pygame.draw.rect(game_window, green, pygame.Rect(pos[0], pos[1], 10, 10))
        else:
            pygame.draw.rect(game_window, blue, pygame.Rect(pos[0], pos[1], 10, 10))
    pygame.draw.rect(game_window, white, pygame.Rect(food_pos[0], food_pos[1], 10, 10))

    # Game over conditions
    if snake_pos[0] < 0 or snake_pos[0] > frame_size_x - 10:
        random_flag = False
        game_over()
        wait_for_space("Snake Eater")
    if snake_pos[1] < 0 or snake_pos[1] > frame_size_y - 10:
        random_flag = False
        game_over()
        wait_for_space("Snake Eater")
    for block in snake_body[1:]:
        if snake_pos[0] == block[0] and snake_pos[1] == block[1]:
            random_flag = False
            game_over()
            wait_for_space("Snake Eater")

    show_score(1, white, 'consolas', 20)
    pygame.display.update()
    fps_controller.tick(difficulty)
