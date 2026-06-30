import pygame
import struct
import time

# ============================
# Joystick 초기화
# ============================

pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("레이싱휠을 찾을 수 없습니다.")
    exit()

wheel = pygame.joystick.Joystick(0)
wheel.init()

print("----------------------------------------")
print("Racing Wheel Connected")
print("Name :", wheel.get_name())
print("----------------------------------------")

while True:

    pygame.event.pump()

    # 핸들
    steering_axis = wheel.get_axis(0)

    # 엑셀/브레이크 공유축
    pedal_axis = wheel.get_axis(1)

    # -----------------------------
    # Steering (-135 ~ 135)
    # -----------------------------

    steering = int(steering_axis * 127)

    if abs(steering) < 3:
        steering = 0

    # -----------------------------
    # Accelerator / Brake
    # -----------------------------

    accel = 0
    brake = 0

    if pedal_axis < 0:
        accel = int((-pedal_axis) * 100)

    elif pedal_axis > 0:
        brake = int((pedal_axis) * 100)

    # -----------------------------
    # RPM (0~300)
    # -----------------------------

    target_rpm = accel * 3

    if target_rpm > 300:
        target_rpm = 300

    # -----------------------------
    # DBC Frame 생성
    # -----------------------------

    frame = bytearray(8)

    # Byte0~1 : Target_Velocity (uint16)
    frame[0:2] = struct.pack("<H", target_rpm)

    # Byte2 : Steering_Angle (int8)
    frame[2] = struct.pack("b", steering)[0]

    # Byte3 : Brake_Depth (uint8)
    frame[3] = brake

    # Byte4~7 Reserved
    frame[4] = 0
    frame[5] = 0
    frame[6] = 0
    frame[7] = 0

    # 방향 표시
    if steering < 0:
        direction = f"LEFT {-steering:3d}°"

    elif steering > 0:
        direction = f"RIGHT {steering:3d}°"

    else:
        direction = "CENTER"

    # HEX 출력
    hex_data = " ".join(f"{b:02X}" for b in frame)

    print(
        f"\rID:100 | "
        f"{direction:12} | "
        f"Accel:{accel:3d}% | "
        f"Brake:{brake:3d}% | "
        f"RPM:{target_rpm:3d} | "
        f"DATA: {hex_data}",
        end=""
    )

    time.sleep(0.02)
