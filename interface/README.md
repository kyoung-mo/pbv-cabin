# interface — 공용 약속 (legacy placeholder)

프로젝트 초기, 5개 노드가 공유하는 공용 계약(DBC·인터록 매트릭스·System Mode FSM)을 한곳에
모으려던 디렉토리. **현재는 빈 placeholder(`.gitkeep`)** 만 남아 있다.

## 현재 상태
| 폴더 | 원래 의도 | 현재 |
|---|---|---|
| `dbc/` | CAN 메시지 정의(`model_car_net.dbc`) + cantools 생성물 | 비어 있음 — **정본은 `supervisor/dbc/model_car_net.dbc`** 로 이관 |
| `interlock-matrix/` | 인터록 매트릭스(승인/거부 조건표) | 비어 있음 — 인터록은 `supervisor/hmi/vehicle_state.py`에 코드로 구현 |
| `fsm/` | System Mode FSM 전이도 | 비어 있음 — 좌석 상태 FSM enum은 미구현(후속 과제) |

## 단일 소스 오브 트루스
- **CAN/DBC 정본** = `supervisor/dbc/model_car_net.dbc` (14메시지, Vector CANdb++). 각 ECU는 이
  DBC에서 생성한 C 코덱(`model_car_net.c/.h`)을 공유한다.
- 인터페이스가 바뀌면 이 DBC를 고치고 ECU 코덱을 재생성하는 것이 기준 흐름이다.

> 실제 계약이 코드/DBC로 이동한 뒤 비게 된 자리다. 신규 문서는 이 디렉토리가 아니라
> 정본 위치(`supervisor/dbc/`, `docs/`)에 둘 것.
