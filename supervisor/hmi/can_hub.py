"""can_hub — Central_Supervisor 의 CAN 입출력 허브 (스텝2: 실제 can0 양방향).

이 노드는 DBC 상 **Central_Supervisor** 다.
  · 송신(TX) = Central_Supervisor 가 sender 인 메시지
        Drive_Cmd, Driver/Passenger/Rear_Left/Rear_Right_Seat_Cmd, GearStatus
  · 수신(RX) = Central_Supervisor 가 receiver 인 메시지
        Driver/Passenger/Rear_Left/Rear_Right_Seat_Status, Drive_Status

설계:
  · 메시지 정의는 절대 임시로 만들지 않는다 — supervisor/dbc/model_car_net.dbc 를
    cantools 로 로드해 encode/decode 한다. (.h/.c 는 ECU 펌웨어용, 여기선 안 쓴다.)
  · 송신은 GUI 스레드(좌석 Cmd)와 휠 스레드(Drive_Cmd) 양쪽에서 호출되므로 Lock 으로 직렬화.
  · 수신은 전용 RX 스레드에서 recv→decode 후 **Qt Signal** 로 GUI 스레드에 넘긴다.
    (RX 스레드에서 QML/State 를 직접 건드리지 않는다 — QueuedConnection 으로 스레드 안전.)
"""

import os
import threading
import time

import can
import cantools
from PySide6.QtCore import QObject, Signal


# ── 인터페이스 이름은 이 상수 하나로 (나중에 한 줄 교체 가능) ──────────────────
CAN_IFACE = "can0"
CAN_BITRATE = 500000  # 참고용(socketcan 은 ip link 에서 이미 설정됨)

DBC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "dbc", "model_car_net.dbc")


# ── 좌석 UI(키) → 좌석 Cmd 메시지/시그널 매핑 ────────────────────────────────
#   HMI 좌석키            DBC 메시지              recline 시그널        axis2 시그널(앞=회전/뒤=슬라이드)
SEAT_CMD_DEF = {
    "driver":     ("Driver_Seat_Cmd",     "Drv_Recline_Angle",  "Drv_Rotation_Angle"),
    "passenger":  ("Passenger_Seat_Cmd",  "Psgr_Recline_Angle", "Psgr_Rotation_Angle"),
    "rear_left":  ("Rear_Left_Seat_Cmd",  "RL_Recline_Angle",   "RL_Slide_Position"),
    "rear_right": ("Rear_Right_Seat_Cmd", "RR_Recline_Angle",   "RR_Slide_Position"),
}

# ── 좌석 Status 메시지 → (좌석키, recline 시그널, rotate 시그널|None, pinch 시그널) ──
#   · 앞좌석(0x210/0x211)은 DLC3 — Curr_*_Rotate(회전 현재값)까지 피드백한다(closed-loop).
#   · 뒷좌석(0x220/0x221)은 DLC2 — 슬라이드 현재값 피드백이 없다(rotate=None, open-loop).
#   파싱은 전부 cantools decode 로 통일(수동 비트 추출 없음). 핀치 비트 위치(byte1→byte2)
#   변경도 DBC 기준으로 cantools 가 알아서 처리한다.
SEAT_STATUS_DEF = {
    "Driver_Seat_Status":     ("driver",     "Curr_Drv_Recline",  "Curr_Drv_Rotate",  "Drv_Pinch_Detected"),
    "Passenger_Seat_Status":  ("passenger",  "Curr_Psgr_Recline", "Curr_Psgr_Rotate", "Psgr_Pinch_Detected"),
    "Rear_Left_Seat_Status":  ("rear_left",  "Curr_RL_Recline",   None,               "RL_Pinch_Detected"),
    "Rear_Right_Seat_Status": ("rear_right", "Curr_RR_Recline",   None,               "RR_Pinch_Detected"),
}


def _clamp_signal(msg, name, value):
    """시그널의 '인코딩 가능한 실제 범위' 로 클램프.

    DBC 의 선언 min/max 와, 비트폭·signed·scale·offset 으로 물리적으로 표현 가능한
    범위를 교집합한다. (예: Drive_Cmd.Steering_Angle 은 8bit signed 라 물리적으로
    -128..127 만 가능 — 선언값 -135..135 를 그대로 쓰면 cantools 인코딩이 오버플로한다.)
    """
    s = msg.get_signal_by_name(name)
    scale = s.scale if s.scale is not None else 1
    offset = s.offset if s.offset is not None else 0
    if s.is_signed:
        raw_lo, raw_hi = -(1 << (s.length - 1)), (1 << (s.length - 1)) - 1
    else:
        raw_lo, raw_hi = 0, (1 << s.length) - 1
    phys_a, phys_b = raw_lo * scale + offset, raw_hi * scale + offset
    lo, hi = min(phys_a, phys_b), max(phys_a, phys_b)   # scale 음수 대비
    if s.minimum is not None:
        lo = max(lo, s.minimum)
    if s.maximum is not None:
        hi = min(hi, s.maximum)
    return max(lo, min(hi, value))


class CanHub(QObject):
    """can0 송수신 허브. 생성 시 DBC 로드 + 버스 오픈(실패 시 예외)."""

    # RX 스레드 → GUI 스레드 (QueuedConnection 으로 연결할 것)
    #   rotate = 앞좌석 Curr_*_Rotate(회전 현재값). 뒷좌석은 피드백 없어 -1.
    seatStatusReceived = Signal(str, int, int, bool)   # (seat, curr_recline, curr_rotate|-1, pinch)
    driveStatusReceived = Signal(float, int, int)      # (velocity_rpm, motor_mA, gear)
    busError = Signal(str)

    def __init__(self, iface=CAN_IFACE, dbc_path=DBC_PATH, parent=None):
        super().__init__(parent)
        self._db = cantools.database.load_file(dbc_path)
        self._bus = can.interface.Bus(channel=iface, interface="socketcan",
                                      receive_own_messages=False)

        self._send_lock = threading.Lock()
        self._tx_err_last = 0.0            # busError 스로틀(마지막 방출 시각, monotonic)
        self._tx_err_count = 0            # 스로틀 창 동안 누적 드롭 수
        self._rolling = 0                  # Driver_Seat_Cmd 의 Rolling_Counter (0~15 순환)
        self._running = False
        self._rx_thread = None

        # 자주 쓰는 메시지 핸들 캐시
        self._drive_cmd = self._db.get_message_by_name("Drive_Cmd")
        self._gear_status = self._db.get_message_by_name("GearStatus")
        self._drive_status_id = self._db.get_message_by_name("Drive_Status").frame_id

        # 수신 디스패치 테이블: frame_id → (seat_key, recline_sig, rotate_sig|None, pinch_sig)
        self._status_by_id = {}
        for msg_name, mapping in SEAT_STATUS_DEF.items():
            fid = self._db.get_message_by_name(msg_name).frame_id
            self._status_by_id[fid] = mapping

    # =====================================================================
    # 송신 헬퍼 (encode → can0 send)
    # =====================================================================
    def _send(self, frame_id, data):
        """프레임 1개 송신. 실패해도 예외를 올리지 않고 드롭 후 False 반환.

        ENOBUFS(105) 등 커널 TX 큐 포화는 보통 버스에서 프레임이 ACK 되지 않아(다른 노드
        부재·종단저항 미설치·비트레이트 불일치) 송신 큐가 안 빠지는 상태다. 좌석/기어/모드
        프리셋 같은 단발 송신 경로가 여기서 예외를 그대로 올리면 QML 슬롯(selectMode 등)이
        통째로 죽는다. 주기 브로드캐스트 버스에서는 프레임을 조용히 버리고(다음 틱에 재송신)
        앱을 살려두는 편이 옳다. 스팸 방지를 위해 busError 는 1초에 한 번만 방출한다.
        반환: 송신 성공 True / 드롭 False.
        """
        msg = can.Message(arbitration_id=frame_id, data=bytes(data),
                          is_extended_id=False)
        with self._send_lock:
            try:
                self._bus.send(msg, timeout=0.1)
                return True
            except (can.CanError, OSError) as e:
                self._tx_err_count += 1
                now = time.monotonic()
                if now - self._tx_err_last >= 1.0:
                    self.busError.emit(
                        f"TX 드롭 {self._tx_err_count}건 (최근 frame 0x{frame_id:03X}: {e}) "
                        "— can0 TX 큐 포화(버스 ACK 부재/종단·비트레이트 확인)")
                    self._tx_err_last = now
                    self._tx_err_count = 0
                return False

    def _next_rolling(self):
        v = self._rolling
        self._rolling = (self._rolling + 1) & 0x0F   # 15 → 0 wrap
        return v

    def send_seat_cmd(self, seat, recline, axis2, cargo_lamp=0):
        """좌석 UI 1개의 목표포즈(recline + 회전/슬라이드)를 해당 *_Seat_Cmd 로 송신.

        한 프레임에 두 축을 모두 싣는다(DBC 구조). 좌석↔메시지 매핑은 SEAT_CMD_DEF.
        Driver_Seat_Cmd 만 Rolling_Counter/Checksum 을 앱에서 채운다(cantools 자동 X).
        """
        msg_name, recline_sig, axis2_sig = SEAT_CMD_DEF[seat]
        msg = self._db.get_message_by_name(msg_name)

        sig = {
            recline_sig: int(_clamp_signal(msg, recline_sig, recline)),
            axis2_sig:   int(_clamp_signal(msg, axis2_sig, axis2)),
        }
        if seat == "driver":
            sig["Rolling_Counter"] = self._next_rolling()
            sig["Checksum"] = 0                       # XOR 계산 전 자리 비움
        if seat == "rear_right":
            sig["Cargo_Lamp_Status"] = int(cargo_lamp)

        data = bytearray(msg.encode(sig, strict=True))

        if seat == "driver":
            # ── Checksum 방식: ecu-front can.c 와 동일 — 8비트 합 ──
            #   can_driver_cmd_checksum() == (data[0]+data[1]+data[2]) & 0xFF 로 검증하므로
            #   송신 체크섬도 정확히 같은 식이어야 실물 STM32 에서 checksum_ok=1 이 된다.
            #   Driver_Seat_Cmd(DLC=4) 바이트 배치:
            #     byte0 = Drv_Recline_Angle
            #     byte1 = Drv_Rotation_Angle
            #     byte2 = Rolling_Counter (하위 4비트)
            #     byte3 = Checksum  ← 여기에 (byte0+byte1+byte2) & 0xFF 를 채운다
            data[3] = (data[0] + data[1] + data[2]) & 0xFF

        self._send(msg.frame_id, data)
        return data

    def send_drive_cmd(self, steering, velocity=0.0, brake=0):
        """Drive_Cmd 송신. steering(-135..135), velocity(RPM,0..300), brake(%,0..100)."""
        m = self._drive_cmd
        sig = {
            "Target_Velocity": _clamp_signal(m, "Target_Velocity", velocity),
            "Steering_Angle":  int(_clamp_signal(m, "Steering_Angle", steering)),
            "Brake_Depth":     int(_clamp_signal(m, "Brake_Depth", brake)),
        }
        self._send(m.frame_id, m.encode(sig, strict=True))

    def send_gear_status(self, gear_idx):
        """GearStatus 송신. (HMI GearSlider 순서 R/P/D = 0/1/2 그대로 매핑 — ECU 합의 시 조정)"""
        m = self._gear_status
        gear_idx = int(_clamp_signal(m, "Gear", gear_idx))
        self._send(m.frame_id, m.encode({"Gear": gear_idx}, strict=True))

    # =====================================================================
    # 수신 (전용 RX 스레드 → Qt Signal)
    # =====================================================================
    def start_rx(self):
        if self._running:
            return
        self._running = True
        self._rx_thread = threading.Thread(target=self._rx_loop,
                                           name="can-rx", daemon=True)
        self._rx_thread.start()

    def _rx_loop(self):
        while self._running:
            try:
                msg = self._bus.recv(timeout=0.2)
            except Exception as e:        # 종료 중 버스 close → recv 예외 → 조용히 탈출
                if self._running:
                    self.busError.emit(f"RX recv 오류: {e}")
                continue
            if msg is None:
                continue

            info = self._status_by_id.get(msg.arbitration_id)
            if info:
                seat, recline_sig, rotate_sig, pinch_sig = info
                try:
                    d = self._db.decode_message(msg.arbitration_id, msg.data)
                except Exception:
                    continue
                rotate = int(round(d[rotate_sig])) if rotate_sig else -1
                self.seatStatusReceived.emit(
                    seat, int(round(d[recline_sig])), rotate, bool(d[pinch_sig]))
            elif msg.arbitration_id == self._drive_status_id:
                try:
                    d = self._db.decode_message(msg.arbitration_id, msg.data)
                except Exception:
                    continue
                self.driveStatusReceived.emit(
                    float(d["Current_Velocity"]),
                    int(d["Drive_Motor_Current"]),
                    int(d["Current_Gear_Status"]))

    # =====================================================================
    # 종료 (휠/CAN RX/GUI 스레드 정리 — 멱등)
    # =====================================================================
    def stop(self):
        if not self._running and self._bus is None:
            return
        self._running = False
        if self._rx_thread is not None and self._rx_thread.is_alive():
            self._rx_thread.join(timeout=1.0)
            self._rx_thread = None
        if self._bus is not None:
            try:
                self._bus.shutdown()
            except Exception:
                pass
            self._bus = None
