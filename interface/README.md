# interface — 공용 약속 (모든 노드가 공유)

5개 노드가 **똑같이** 합의해서 쓰는 단 하나의 약속. 여기 있는 파일은
보드별 브랜치가 아니라 **반드시 `main`에서만 수정**한다.
(브랜치마다 따로 고치면 통합 날 "DBC가 서로 다르네" 사고가 난다.)

| 폴더 | 내용 |
|---|---|
| `dbc/` | CAN 메시지 정의 (`model_car_net.dbc`) + cantools 생성물(`.c`/`.h`) |
| `interlock-matrix/` | 인터록 매트릭스 (어떤 조건에서 승인/거부하는지 표) |
| `fsm/` | System Mode FSM 전이도 (주행/회의/차박/짐칸 전이 규칙) |

## 인터페이스가 바뀌면 (5명 전원)
```bash
git switch main && git pull      # 최신 공용 약속 받기
git switch 내브랜치
git merge main                   # 내 브랜치에 반영
```
