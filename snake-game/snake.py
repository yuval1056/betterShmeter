import pygame
import random
import sys

# Initialize Pygame
pygame.init()

# Constants
WIDTH, HEIGHT = 600, 400
BLOCK_SIZE = 20
SPEED = 10

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)

# Set up display
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Snake Game")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 35)

def draw_snake(snake_body):
    for segment in snake_body:
        pygame.draw.rect(screen, GREEN, (segment[0], segment[1], BLOCK_SIZE, BLOCK_SIZE))

def draw_food(food_pos):
    pygame.draw.rect(screen, RED, (food_pos[0], food_pos[1], BLOCK_SIZE, BLOCK_SIZE))

def show_score(score):
    score_text = font.render(f"Score: {score}", True, WHITE)
    screen.blit(score_text, (10, 10))

def game_over_message():
    msg = font.render("Game Over! Press Q to quit or C to play again", True, WHITE)
    screen.blit(msg, (20, HEIGHT // 2))

def main():
    x, y = WIDTH // 2, HEIGHT // 2
    dx, dy = BLOCK_SIZE, 0
    snake_body = [[x, y]]
    snake_length = 1
    food_pos = [random.randrange(0, WIDTH, BLOCK_SIZE), random.randrange(0, HEIGHT, BLOCK_SIZE)]
    score = 0
    game_over = False

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if not game_over:
                    if event.key == pygame.K_LEFT and dx == 0:
                        dx, dy = -BLOCK_SIZE, 0
                    elif event.key == pygame.K_RIGHT and dx == 0:
                        dx, dy = BLOCK_SIZE, 0
                    elif event.key == pygame.K_UP and dy == 0:
                        dx, dy = 0, -BLOCK_SIZE
                    elif event.key == pygame.K_DOWN and dy == 0:
                        dx, dy = 0, BLOCK_SIZE
                else:
                    if event.key == pygame.K_q:
                        pygame.quit()
                        sys.exit()
                    if event.key == pygame.K_c:
                        main()
                        return

        if not game_over:
            x += dx
            y += dy

            # Check wall collision
            if x < 0 or x >= WIDTH or y < 0 or y >= HEIGHT:
                game_over = True

            # Check self collision
            for segment in snake_body[:-1]:
                if segment == [x, y]:
                    game_over = True

            snake_body.append([x, y])
            if len(snake_body) > snake_length:
                del snake_body[0]

            # Check food collision
            if [x, y] == food_pos:
                food_pos = [random.randrange(0, WIDTH, BLOCK_SIZE), random.randrange(0, HEIGHT, BLOCK_SIZE)]
                snake_length += 1
                score += 10

        screen.fill(BLACK)
        draw_snake(snake_body)
        draw_food(food_pos)
        show_score(score)
        if game_over:
            game_over_message()

        pygame.display.update()
        clock.tick(SPEED)

if __name__ == "__main__":
    main()
