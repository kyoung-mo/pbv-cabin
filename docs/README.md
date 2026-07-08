# docs — 설계 문서 · 배선도 · 발표자료

프로젝트 설계 산출물을 모으는 디렉토리. 아키텍처 다이어그램, 노드 배선도, 인터페이스 정의,
발표자료, 회의록 등을 둔다.

## 담을 것
- **아키텍처 다이어그램** — 4노드(슈퍼바이저 + 존 ECU 3) CAN 토폴로지, 데이터 흐름
- **배선도** — MCP2515/SPI, CAN 버스 종단(120Ω 양 끝 2개), 각 ECU 액추에이터/센서 결선, 전원 분배
- **인터페이스 정의** — CAN 메시지 표(정본 DBC = `supervisor/dbc/model_car_net.dbc` 14메시지 기준)
- **발표자료 · 회의록**

## 관련 위치
- 프로젝트 전반 개요 → 루트 [`README.md`](../README.md)
- CAN/DBC 정본 → [`supervisor/dbc/model_car_net.dbc`](../supervisor/dbc/model_car_net.dbc)
- v7.0 설계-구현 대조 정리본 → [`assets/project_summery_7.md`](../assets/project_summery_7.md)

> 이미지·바이너리 산출물은 용량을 고려해 필요한 것만 커밋한다.
