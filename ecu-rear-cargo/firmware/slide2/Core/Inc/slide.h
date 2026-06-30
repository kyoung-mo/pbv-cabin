/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    slide.h
  * @brief   Rear_Zone_ECU 좌석 슬라이드(스텝모터 1축) 구동 모듈.
  *          모터 구동만 담당한다. CAN 송수신은 이 모듈에 넣지 않는다.
  ******************************************************************************
  */
/* USER CODE END Header */
#ifndef __SLIDE_H__
#define __SLIDE_H__

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"

/* 초기화: 코일 전류 차단(정지) 상태로 둔다. */
void slide_init(void);

/* 부팅 시 1회 호출. 하드스톱까지 밀어 0점을 잡는다(블로킹). 센서 없음 가정. */
void slide_home(void);

/* 목표 위치(mm, 0~SLIDE_MAX_MM) 설정. 실제 이동은 slide_service()가 수행. */
void slide_set_target_mm(uint8_t mm);

/* 논블로킹: 메인 루프에서 매번 호출. 한 번에 최대 한 스텝씩 목표로 접근. */
void slide_service(void);

/* E-stop: on=1 이면 즉시 정지하고 래치, on=0 이면 해제. */
void slide_estop(uint8_t on);

/* 재영점: 현재 위치를 새 0점으로 선언(테스트용, 모터 안 움직임). */
void slide_rezero(void);

/* 호밍: 오른쪽 끝(시작점)까지 밀어붙여 0점을 잡는다(논블로킹, slide_service가 수행). */
void slide_seek_home(void);

/* 현재 위치(mm). 상태 보고용 피드백. */
uint8_t slide_get_pos_mm(void);

#ifdef __cplusplus
}
#endif

#endif /* __SLIDE_H__ */
