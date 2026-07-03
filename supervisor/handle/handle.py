import pygame
import time

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("레이싱 휠이 연결되지 않았습니다.")
    exit()

js = pygame.joystick.Joystick(0)
js.init()

MAX_STEERING_ANGLE = 130

while True:

    pygame.event.pump()

    # ======================
    # Steering
    # ======================
    steering = js.get_axis(0)

    steering_deg = steering * MAX_STEERING_ANGLE

    if abs(steering_deg) < 3:
        steering_deg = 0

    if steering_deg > 0:
        steering_text = f"오른쪽 {steering_deg:.1f}°"

    elif steering_deg < 0:
        steering_text = f"왼쪽 {abs(steering_deg):.1f}°"

    else:
        steering_text = "정면 0°"

    # ======================
    # Pedal
    # ======================
    pedal = js.get_axis(1)

    if pedal < -0.02:
        throttle = abs(pedal) * 100
        brake = 0

    elif pedal > 0.02:
        throttle = 0
        brake = pedal * 100

    else:
        throttle = 0
        brake = 0

    print(
        f"조향 : {steering_text:15} | "
        f"엑셀 : {throttle:5.1f}% | "
        f"브레이크 : {brake:5.1f}%"
    )

    time.sleep(0.1)
