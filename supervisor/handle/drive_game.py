import pygame
import random

# ======================
# 초기화
# ======================
pygame.init()

WIDTH = 800
HEIGHT = 600

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("PBV Driving Simulator")

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 36)

# ======================
# 레이싱 휠
# ======================
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("레이싱 휠이 연결되지 않았습니다.")
    quit()

js = pygame.joystick.Joystick(0)
js.init()

# ======================
# 차량
# ======================
car_x = WIDTH // 2
car_y = HEIGHT - 100

speed = 0

MAX_SPEED = 15
MAX_STEERING_ANGLE = 150

# ======================
# 도로
# ======================
ROAD_LEFT = 250
ROAD_RIGHT = 550

# ======================
# 장애물
# ======================
obstacles = []

spawn_timer = 0
score = 0

# ======================
# 상태
# ======================
running = True
game_over = False

# ======================
# 메인 루프
# ======================
while running:

    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    pygame.event.pump()

    if not game_over:

        # ------------------
        # 핸들
        # ------------------
        steering = js.get_axis(0)

        steering_deg = steering * MAX_STEERING_ANGLE

        if abs(steering_deg) < 3:
            steering_deg = 0

        # ------------------
        # 엑셀 / 브레이크
        # ------------------
        pedal = js.get_axis(1)

        throttle = 0
        brake = 0

        if pedal < -0.02:
            throttle = abs(pedal)

        elif pedal > 0.02:
            brake = pedal

        # ------------------
        # 속도
        # ------------------
        speed += throttle * 0.25
        speed -= brake * 0.40

        speed *= 0.99

        if speed < 0:
            speed = 0

        if speed > MAX_SPEED:
            speed = MAX_SPEED

        # ------------------
        # 차량 이동
        # ------------------
        car_x += steering * speed * 0.6

        # ------------------
        # 장애물 생성
        # ------------------
        spawn_timer += 1

        if spawn_timer > 50:

            lane = random.choice([
                300,
                400,
                500
            ])

            obstacles.append({
                "x": lane,
                "y": -80
            })

            spawn_timer = 0

        # ------------------
        # 장애물 이동
        # ------------------
        for obs in obstacles:
            obs["y"] += 5 + speed

        # ------------------
        # 점수
        # ------------------
        new_obstacles = []

        for obs in obstacles:

            if obs["y"] > HEIGHT:
                score += 1
            else:
                new_obstacles.append(obs)

        obstacles = new_obstacles

        # ------------------
        # 충돌
        # ------------------
        car_rect = pygame.Rect(
            car_x - 20,
            car_y - 40,
            40,
            80
        )

        for obs in obstacles:

            obs_rect = pygame.Rect(
                obs["x"] - 20,
                obs["y"] - 40,
                40,
                80
            )

            if car_rect.colliderect(obs_rect):
                game_over = True

        # ------------------
        # 차선 이탈
        # ------------------
        if car_x < ROAD_LEFT + 20:
            game_over = True

        if car_x > ROAD_RIGHT - 20:
            game_over = True

    # ======================
    # 화면
    # ======================
    screen.fill((40, 40, 40))

    # 도로
    pygame.draw.rect(
        screen,
        (80, 80, 80),
        (
            ROAD_LEFT,
            0,
            ROAD_RIGHT - ROAD_LEFT,
            HEIGHT
        )
    )

    # 중앙선
    pygame.draw.line(
        screen,
        (255,255,255),
        (400,0),
        (400,HEIGHT),
        3
    )

    # 차량
    pygame.draw.rect(
        screen,
        (0,255,0),
        (
            car_x - 20,
            car_y - 40,
            40,
            80
        )
    )

    # 장애물
    for obs in obstacles:

        pygame.draw.rect(
            screen,
            (255,0,0),
            (
                obs["x"] - 20,
                obs["y"] - 40,
                40,
                80
            )
        )

    # ======================
    # HUD
    # ======================
    if steering_deg > 0:
        steering_text = f"오른쪽 {steering_deg:.1f}°"
    elif steering_deg < 0:
        steering_text = f"왼쪽 {abs(steering_deg):.1f}°"
    else:
        steering_text = "정면 0°"

    txt1 = font.render(
        f"속도 : {speed:.1f}",
        True,
        (255,255,255)
    )

    txt2 = font.render(
        f"조향 : {steering_text}",
        True,
        (255,255,255)
    )

    txt3 = font.render(
        f"점수 : {score}",
        True,
        (255,255,255)
    )

    screen.blit(txt1,(20,20))
    screen.blit(txt2,(20,60))
    screen.blit(txt3,(20,100))

    if game_over:

        txt4 = font.render(
            "GAME OVER",
            True,
            (255,0,0)
        )

        screen.blit(
            txt4,
            (300,250)
        )

    pygame.display.flip()

pygame.quit()
