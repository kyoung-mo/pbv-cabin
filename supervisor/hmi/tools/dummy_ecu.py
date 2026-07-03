#!/usr/bin/env python3
"""더미 존 ECU — STM32 펌웨어가 붙기 전의 can0 자체 검증용 시뮬레이터.

can0 에서 Central_Supervisor 가 쏘는 좌석 Cmd 를 받아, 대응하는 *_Seat_Status 를
흉내내 송신한다. 좌석 모터가 목표까지 서서히 움직이는 것처럼 50ms 마다 현재값을
한 스텝씩 보낸다 → HMI 디지털 트윈이 그 Status 를 따라 움직인다(closed-loop).

  · 앞좌석(Driver/Passenger) : recline + rotation 두 축 모두 Status 로 피드백(DLC3).
  · 뒷좌석(Rear L/R)         : recline 만 피드백(DLC2, 슬라이드 피드백 없음).

실물 ECU(Front/Rear Zone)가 붙으면 이 스크립트만 끄면 된다(HMI 코드 변경 없음).

실행:
    python3 tools/dummy_ecu.py
    DUMMY_PINCH=driver python3 tools/dummy_ecu.py   # driver 끼임(Pinch=1) 강제 — UI 테스트
종료: Ctrl-C
"""

import os
import sys
import threading
import time

import can
import cantools

CAN_IFACE = "can0"
DBC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "..", "dbc", "model_car_net.dbc")

# 좌석 Cmd → 시뮬레이션/응답 정의. cmd_rotate/st_rotate=None 이면 회전 피드백 없음(뒷좌석).
SEATS = {
    "Driver_Seat_Cmd": dict(
        seat="driver", cmd_recline="Drv_Recline_Angle", cmd_rotate="Drv_Rotation_Angle",
        status="Driver_Seat_Status", st_recline="Curr_Drv_Recline",
        st_rotate="Curr_Drv_Rotate", pinch="Drv_Pinch_Detected"),
    "Passenger_Seat_Cmd": dict(
        seat="passenger", cmd_recline="Psgr_Recline_Angle", cmd_rotate="Psgr_Rotation_Angle",
        status="Passenger_Seat_Status", st_recline="Curr_Psgr_Recline",
        st_rotate="Curr_Psgr_Rotate", pinch="Psgr_Pinch_Detected"),
    "Rear_Left_Seat_Cmd": dict(
        seat="rear_left", cmd_recline="RL_Recline_Angle", cmd_rotate=None,
        status="Rear_Left_Seat_Status", st_recline="Curr_RL_Recline",
        st_rotate=None, pinch="RL_Pinch_Detected"),
    "Rear_Right_Seat_Cmd": dict(
        seat="rear_right", cmd_recline="RR_Recline_Angle", cmd_rotate=None,
        status="Rear_Right_Seat_Status", st_recline="Curr_RR_Recline",
        st_rotate=None, pinch="RR_Pinch_Detected"),
}

STEP = 4          # 50ms 당 이동량(도) — 모터 속도 흉내
TICK = 0.05       # 50ms


class DummyEcu:
    def __init__(self):
        self._db = cantools.database.load_file(DBC_PATH)
        self._bus = can.interface.Bus(channel=CAN_IFACE, interface="socketcan",
                                      receive_own_messages=False)
        self._lock = threading.Lock()
        # 좌석별 현재/목표 (recline + 앞좌석 rotate). 초기 recline=90, rotate=0.
        self._state = {}
        self._by_seat = {}
        self._cmd_by_id = {}
        for cmd_name, d in SEATS.items():
            self._state[d["seat"]] = {
                "recline": {"cur": 90, "tgt": 90},
                "rotate":  {"cur": 0,  "tgt": 0} if d["cmd_rotate"] else None,
            }
            self._by_seat[d["seat"]] = d
            self._cmd_by_id[self._db.get_message_by_name(cmd_name).frame_id] = d
        self._pinch_seat = os.environ.get("DUMMY_PINCH", "").strip() or None
        self._running = False

    def start(self):
        self._running = True
        threading.Thread(target=self._rx_loop, name="dummy-rx", daemon=True).start()
        threading.Thread(target=self._tick_loop, name="dummy-tick", daemon=True).start()
        print("DUMMY-ECU: can0 시작. 좌석 Cmd 수신 → *_Seat_Status 응답"
              " (앞좌석 recline+rotate / 뒷좌석 recline)"
              + (f" PINCH={self._pinch_seat}" if self._pinch_seat else ""))
        for seat in self._state:        # 시작 시 초기 Status 1회(트윈 동기)
            self._send_status(seat)

    def _rx_loop(self):
        while self._running:
            try:
                msg = self._bus.recv(timeout=0.2)
            except Exception:
                continue
            if msg is None:
                continue
            d = self._cmd_by_id.get(msg.arbitration_id)
            if not d:
                continue
            try:
                dec = self._db.decode_message(msg.arbitration_id, msg.data)
            except Exception:
                continue
            with self._lock:
                st = self._state[d["seat"]]
                st["recline"]["tgt"] = int(round(dec[d["cmd_recline"]]))
                if d["cmd_rotate"] and st["rotate"] is not None:
                    st["rotate"]["tgt"] = int(round(dec[d["cmd_rotate"]]))
            roll = f" Rolling={int(dec['Rolling_Counter'])}" if "Rolling_Counter" in dec else ""
            rot = f" rotate={int(dec[d['cmd_rotate']])}" if d["cmd_rotate"] else ""
            print(f"DUMMY-ECU: {d['seat']} Cmd → recline={int(round(dec[d['cmd_recline']]))}{rot}{roll}")

    def _tick_loop(self):
        while self._running:
            time.sleep(TICK)
            for seat, st in self._state.items():
                moved = False
                with self._lock:
                    for axis in ("recline", "rotate"):
                        a = st[axis]
                        if a is None or a["cur"] == a["tgt"]:
                            continue
                        if a["cur"] < a["tgt"]:
                            a["cur"] = min(a["tgt"], a["cur"] + STEP)
                        else:
                            a["cur"] = max(a["tgt"], a["cur"] - STEP)
                        moved = True
                if moved:
                    self._send_status(seat)

    def _send_status(self, seat):
        d = self._by_seat[seat]
        msg = self._db.get_message_by_name(d["status"])
        with self._lock:
            st = self._state[seat]
            sig = {d["st_recline"]: st["recline"]["cur"]}
            if d["st_rotate"] and st["rotate"] is not None:
                sig[d["st_rotate"]] = st["rotate"]["cur"]
        sig[d["pinch"]] = 1 if (self._pinch_seat == seat) else 0
        try:
            data = msg.encode(sig, strict=True)
            self._bus.send(can.Message(arbitration_id=msg.frame_id, data=data,
                                       is_extended_id=False), timeout=0.1)
        except Exception as e:
            print(f"DUMMY-ECU: status 송신 실패({seat}): {e}", file=sys.stderr)

    def stop(self):
        self._running = False
        try:
            self._bus.shutdown()
        except Exception:
            pass


def main():
    ecu = DummyEcu()
    ecu.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        ecu.stop()
        print("\nDUMMY-ECU: 종료")


if __name__ == "__main__":
    main()
