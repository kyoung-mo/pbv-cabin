#!/usr/bin/env python3
"""
라즈베리파이 슈퍼바이저 흉내 스크립트
==========================================
가변 실내(Reconfigurable Cabin) 프로젝트 — 감시 노드(STM32) 검증용

역할:
  1. 100ms 주기로 Heartbeat(ID 0x050, DLC=1, data[0]=Alive Counter 0~255 순환) 송신
  2. 감시 노드가 응답하는 Heartbeat_Ack(ID 0x060) 수신 확인
  3. 감시 노드가 발동하는 SafeAbort(ID 0x010) 수신 시 경보 출력

사전 준비 (라즈베리파이):
  pip3 install python-can
  sudo ip link set can0 up type can bitrate 500000
  (USB-CAN-A를 SocketCAN으로 쓰는 경우 canusb 데몬이 이미 can0을 만들어줌)

실행:
  python3 rpi_supervisor_sim.py
  python3 rpi_supervisor_sim.py --interface can0 --period 0.1
  python3 rpi_supervisor_sim.py --freeze     # Alive Counter를 일부러 고정 (Alive Stuck 시나리오 재현)
  python3 rpi_supervisor_sim.py --silent     # Heartbeat 아예 안 보냄 (Timeout 시나리오 재현)
"""

import argparse
import threading
import time
import sys

try:
    import can
except ImportError:
    print("python-can이 설치되어 있지 않습니다. 다음 명령으로 설치하세요:")
    print("    pip3 install python-can")
    sys.exit(1)

# ---------------------------------------------------------------------------
# CAN ID / 상수 — STM32 감시 노드(main.c)와 반드시 일치해야 함
# ---------------------------------------------------------------------------
CAN_ID_HEARTBEAT = 0x050
CAN_ID_HEARTBEAT_ACK = 0x060
CAN_ID_SAFEABORT = 0x010

REASON_NAMES = {
    0x00: "NONE",
    0x01: "HB_TIMEOUT (하트비트 타임아웃)",
    0x02: "ALIVE_STUCK (Alive Counter 정체)",
    0x03: "LOCAL_ESTOP",
    0x04: "CAN_ERROR",
}


class SupervisorSim:
    def __init__(self, interface: str, period: float, freeze: bool, silent: bool):
        self.interface = interface
        self.period = period
        self.freeze = freeze
        self.silent = silent

        self.bus = can.interface.Bus(channel=interface, bustype="socketcan")
        self.alive_counter = 0
        self.running = True

        # 마지막으로 보낸 counter와, 그에 대한 ack가 왔는지 추적
        self._last_sent_counter = None
        self._lock = threading.Lock()

    # -----------------------------------------------------------------
    # 송신 스레드 — Heartbeat 주기 전송
    # -----------------------------------------------------------------
    def _tx_loop(self):
        while self.running:
            if self.silent:
                # 아무것도 안 보냄 — 감시 노드 타임아웃 시나리오 재현용
                time.sleep(self.period)
                continue

            counter = self.alive_counter if self.freeze else self.alive_counter

            msg = can.Message(
                arbitration_id=CAN_ID_HEARTBEAT,
                data=[counter],
                is_extended_id=False,
            )
            try:
                self.bus.send(msg)
                with self._lock:
                    self._last_sent_counter = counter
                print(f"[TX] Heartbeat  id=0x{CAN_ID_HEARTBEAT:03X}  counter={counter}")
            except can.CanError as e:
                print(f"[TX ERROR] {e}")

            if not self.freeze:
                self.alive_counter = (self.alive_counter + 1) % 256

            time.sleep(self.period)

    # -----------------------------------------------------------------
    # 수신 스레드 — Ack / SafeAbort 감시
    # -----------------------------------------------------------------
    def _rx_loop(self):
        while self.running:
            msg = self.bus.recv(timeout=0.5)
            if msg is None:
                continue

            if msg.arbitration_id == CAN_ID_HEARTBEAT_ACK:
                ack_counter = msg.data[0] if len(msg.data) >= 1 else None
                with self._lock:
                    matched = (ack_counter == self._last_sent_counter)
                tag = "OK" if matched else "MISMATCH"
                print(f"[RX] Heartbeat_Ack  counter={ack_counter}  ({tag})")

            elif msg.arbitration_id == CAN_ID_SAFEABORT:
                data = msg.data
                stop_flag = data[0] if len(data) >= 1 else None
                source_id = data[1] if len(data) >= 2 else None
                reason_code = data[2] if len(data) >= 3 else None
                reason_str = REASON_NAMES.get(reason_code, f"UNKNOWN(0x{reason_code:02X})")
                print(
                    f"\n🚨 [RX] SafeAbort 수신! "
                    f"stop={stop_flag} source=0x{source_id:02X} reason={reason_str}\n"
                )

    def start(self):
        print(f"인터페이스: {self.interface}, 주기: {self.period*1000:.0f}ms, "
              f"freeze={self.freeze}, silent={self.silent}")
        print("Ctrl+C로 종료\n")

        tx_thread = threading.Thread(target=self._tx_loop, daemon=True)
        rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        tx_thread.start()
        rx_thread.start()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n종료 중...")
            self.running = False
            time.sleep(0.2)
            self.bus.shutdown()


def main():
    parser = argparse.ArgumentParser(description="감시 노드 검증용 슈퍼바이저 흉내 스크립트")
    parser.add_argument("--interface", default="can0", help="SocketCAN 인터페이스 이름 (기본: can0)")
    parser.add_argument("--period", type=float, default=0.1, help="Heartbeat 전송 주기(초), 기본 0.1(=100ms)")
    parser.add_argument("--freeze", action="store_true", help="Alive Counter를 고정해서 Alive Stuck 시나리오 재현")
    parser.add_argument("--silent", action="store_true", help="Heartbeat를 아예 안 보내서 Timeout 시나리오 재현")
    args = parser.parse_args()

    sim = SupervisorSim(args.interface, args.period, args.freeze, args.silent)
    sim.start()


if __name__ == "__main__":
    main()
