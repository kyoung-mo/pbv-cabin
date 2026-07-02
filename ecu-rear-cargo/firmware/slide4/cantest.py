import can

PORT = "COM6"   # ← CANable 포트 (Nucleo VCP COM 아님!)
bus = can.Bus(interface="slcan", channel=PORT, bitrate=500000)

last = {}     # ID별 마지막 데이터 (바뀔 때만 출력)
count = {}    # ID별 수신 개수 (링크 살아있는지 확인용)
def on_rx(m):
    aid = m.arbitration_id
    count[aid] = count.get(aid, 0) + 1
    h = m.data.hex()
    if last.get(aid) == h:
        return
    last[aid] = h
    line = f"\nRX  0x{aid:03X}  {h}"
    d = m.data
    # 좌석 상태 프레임 디코드: [0]=리클라인각, [1]=끼임플래그(bit0)
    if aid == 0x220 and len(d) >= 2:        # Rear_Left_Seat_Status
        p = d[1] & 1
        line += f"  | RL recline={d[0]} pinch={p}" + ("   <<<< 끼임! STOP >>>>" if p else "")
    elif aid == 0x221 and len(d) >= 2:      # Rear_Right_Seat_Status
        p = d[1] & 1
        line += f"  | RR recline={d[0]} pinch={p}" + ("   <<<< 끼임! STOP >>>>" if p else "")
    print(line)
can.Notifier(bus, [on_rx])

def tx(arb, data):
    try:
        bus.send(can.Message(arbitration_id=arb, is_extended_id=False, data=bytes(data)))
        print(f"TX> 0x{arb:03X}  {bytes(data).hex()}")   # 보낸 것 확인
    except Exception as ex:
        print(f"!! TX 실패: {ex}")                        # 송신 에러면 여기 뜸

# 한 CAN 프레임에 여러 축이 같이 들어간다(DBC 바이트 배치).
#   0x120 Rear_Left_Seat_Cmd  : [0]=RL 리클라인각, [1]=RL 슬라이드 위치
#   0x121 Rear_Right_Seat_Cmd : [0]=RR 리클라인각, [1]=RR 슬라이드, [2]=카고램프
# 상태를 들고 있다가 "바뀐 바이트만" 갱신해 보내야 다른 축을 0으로 덮어쓰지 않는다.
rl = [0, 0]      # 0x120 : [RL_Recline(0~180°), RL_Slide(0~100mm)]
rr = [0, 0, 0]   # 0x121 : [RR_Recline(0~180°), RR_Slide(0~100mm), Cargo_Lamp]

def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v

HELP = ("명령:  [RL] h=호밍 m<mm>슬라이드(0~100) z=재영점  "
        "[RR] H=호밍 n<mm>슬라이드(0~100) Z=재영점  "
        "a<각>RL서보  b<각>RR서보(0~180)  e=Estop  r=해제  s=수신통계  q=종료")
print(HELP)
try:
    while True:
        c = input("> ").strip()
        if not c:
            continue
        try:
            if c == "q":
                break
            elif c == "s":
                print("수신누적:", {f"0x{k:03X}": v for k, v in count.items()} or "없음")
            elif c == "h":
                # 호밍: 슬라이드 바이트만 254로 보내 "오른쪽 끝(시작점)으로 가서 0점 잡기".
                # 리클라인([0])은 유지. 보낸 뒤 상태를 0으로(호밍 끝나면 현위치가 0).
                rl[1] = 254; tx(0x120, rl); rl[1] = 0
            elif c == "z":
                # 재영점: 슬라이드 바이트만 255(범위밖 센티넬)로 보내 "여기를 0으로".
                # 리클라인([0])은 유지 → 서보는 안 움직임. 보낸 뒤 상태를 0으로(현위치가 0이 됨).
                rl[1] = 255; tx(0x120, rl); rl[1] = 0
            elif c == "H":
                rr[1] = 254; tx(0x121, rr); rr[1] = 0              # RR 슬라이드 호밍(0x121 [1]=254)
            elif c == "Z":
                rr[1] = 255; tx(0x121, rr); rr[1] = 0              # RR 슬라이드 재영점(0x121 [1]=255)
            elif c.startswith("m"):
                rl[1] = clamp(int(c[1:]), 0, 100); tx(0x120, rl)   # RL 슬라이드 위치
            elif c.startswith("n"):
                rr[1] = clamp(int(c[1:]), 0, 100); tx(0x121, rr)   # RR 슬라이드 위치
            elif c.startswith("a"):
                rl[0] = clamp(int(c[1:]), 0, 180); tx(0x120, rl)   # RL 리클라인 서보
            elif c.startswith("b"):
                rr[0] = clamp(int(c[1:]), 0, 180); tx(0x121, rr)   # RR 리클라인 서보
            elif c == "e":
                tx(0x010, [1])   # HMI_Emergency (DBC 0x010): 1=래치 정지
            elif c == "r":
                tx(0x010, [0])   # 0=해제
            else:
                print(HELP)
        except ValueError:
            print("숫자 형식 오류. 예)  m50   a90   b120")
except KeyboardInterrupt:
    pass
bus.shutdown()
