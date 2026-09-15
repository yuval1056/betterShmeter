import pygame
import sys
import random

# Initialize Pygame
pygame.init()

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)

# Paddle settings
PADDLE_WIDTH = 100
PADDLE_HEIGHT = 15
PADDLE_SPEED = 10

# Ball settings
BALL_SIZE = 10
BALL_SPEED_X = 5
BALL_SPEED_Y = -5

# Brick settings
BRICK_ROWS = 5
BRICK_COLS = 8
BRICK_WIDTH = 80
BRICK_HEIGHT = 25
BRICK_PADDING = 10
BRICK_OFFSET_TOP = 60
BRICK_OFFSET_LEFT = 45

# Brick colors for each row
BRICK_COLORS = [RED, ORANGE, YELLOW, GREEN, CYAN]


class Paddle:
    def __init__(self):
        self.width = PADDLE_WIDTH
        self.height = PADDLE_HEIGHT
        self.x = (SCREEN_WIDTH - self.width) // 2
        self.y = SCREEN_HEIGHT - 40
        self.speed = PADDLE_SPEED
        self.rect = pygame.Rect(self.x, self.y, self.width, self.height)

    def move(self, dx):
        self.x += dx
        # Keep paddle within screen bounds
        if self.x < 0:
            self.x = 0
        if self.x > SCREEN_WIDTH - self.width:
            self.x = SCREEN_WIDTH - self.width
        self.rect.x = self.x

    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, self.rect)
        pygame.draw.rect(screen, BLUE, self.rect, 2)


class Ball:
    def __init__(self):
        self.size = BALL_SIZE
        self.reset()

    def reset(self):
        self.x = SCREEN_WIDTH // 2
        self.y = SCREEN_HEIGHT // 2
        self.dx = BALL_SPEED_X * random.choice([-1, 1])
        self.dy = BALL_SPEED_Y
        self.rect = pygame.Rect(self.x, self.y, self.size, self.size)

    def move(self):
        self.x += self.dx
        self.y += self.dy
        self.rect.x = self.x
        self.rect.y = self.y

    def draw(self, screen):
        pygame.draw.ellipse(screen, WHITE, self.rect)

    def bounce_x(self):
        self.dx = -self.dx

    def bounce_y(self):
        self.dy = -self.dy


class Brick:
    def __init__(self, x, y, color):
        self.rect = pygame.Rect(x, y, BRICK_WIDTH, BRICK_HEIGHT)
        self.color = color
        self.alive = True

    def draw(self, screen):
        if self.alive:
            pygame.draw.rect(screen, self.color, self.rect)
            pygame.draw.rect(screen, WHITE, self.rect, 1)


class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Brick Breaker")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        self.reset()

    def reset(self):
        self.paddle = Paddle()
        self.ball = Ball()
        self.bricks = []
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.game_won = False
        self.create_bricks()

    def create_bricks(self):
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                x = BRICK_OFFSET_LEFT + col * (BRICK_WIDTH + BRICK_PADDING)
                y = BRICK_OFFSET_TOP + row * (BRICK_HEIGHT + BRICK_PADDING)
                brick = Brick(x, y, BRICK_COLORS[row])
                self.bricks.append(brick)

    def handle_collisions(self):
        # Ball-wall collisions
        if self.ball.x <= 0 or self.ball.x >= SCREEN_WIDTH - self.ball.size:
            self.ball.bounce_x()
        if self.ball.y <= 0:
            self.ball.bounce_y()

        # Ball-paddle collision
        if self.ball.rect.colliderect(self.paddle.rect) and self.ball.dy > 0:
            self.ball.bounce_y()
            # Add some angle based on where the ball hits the paddle
            offset = (self.ball.x + self.ball.size / 2) - (self.paddle.x + self.paddle.width / 2)
            self.ball.dx = offset * 0.15

        # Ball-brick collisions
        for brick in self.bricks:
            if brick.alive and self.ball.rect.colliderect(brick.rect):
                brick.alive = False
                self.ball.bounce_y()
                self.score += 10
                break

        # Ball falls below screen
        if self.ball.y > SCREEN_HEIGHT:
            self.lives -= 1
            if self.lives > 0:
                self.ball.reset()
            else:
                self.game_over = True

    def check_win(self):
        if all(not brick.alive for brick in self.bricks):
            self.game_won = True

    def draw_ui(self):
        # Score
        score_text = self.font.render(f"Score: {self.score}", True, WHITE)
        self.screen.blit(score_text, (10, 10))

        # Lives
        lives_text = self.font.render(f"Lives: {self.lives}", True, WHITE)
        lives_rect = lives_text.get_rect()
        lives_rect.topright = (SCREEN_WIDTH - 10, 10)
        self.screen.blit(lives_text, lives_rect)

        # Game Over / Win messages
        if self.game_over:
            game_over_text = self.font.render("GAME OVER - Press R to Restart", True, RED)
            text_rect = game_over_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(game_over_text, text_rect)
        elif self.game_won:
            win_text = self.font.render("YOU WIN! - Press R to Restart", True, GREEN)
            text_rect = win_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            self.screen.blit(win_text, text_rect)

    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r and (self.game_over or self.game_won):
                        self.reset()

            if not self.game_over and not self.game_won:
                # Paddle movement
                keys = pygame.key.get_pressed()
                if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                    self.paddle.move(-self.paddle.speed)
                if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                    self.paddle.move(self.paddle.speed)

                # Ball movement
                self.ball.move()
                self.handle_collisions()
                self.check_win()

            # Drawing
            self.screen.fill(BLACK)
            self.paddle.draw(self.screen)
            self.ball.draw(self.screen)
            for brick in self.bricks:
                brick.draw(self.screen)
            self.draw_ui()

            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    game = Game()
    game.run()
