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

/* 슬라이드 축(리니어 스크류 액추에이터) 채널. STM32F446 1대로 TMC2208 2대를 독립 제어.
 *   SLIDE_RL = 0x120 RL_Slide_Position (기존 1축)
 *   SLIDE_RR = 0x121 RR_Slide_Position (신규 2축) */
typedef enum {
  SLIDE_RL = 0,
  SLIDE_RR,
  SLIDE_COUNT
} slide_ch_t;

/* 초기화: 두 축 모두 드라이버 비활성(정지) 상태로 둔다. */
void slide_init(void);

/* 부팅 시 1회 호출. 하드스톱까지 밀어 0점을 잡는다(블로킹). 센서 없음 가정. 두 축 모두. */
void slide_home(void);

/* 목표 위치(mm, 0~SLIDE_MAX_MM) 설정. 실제 이동은 slide_service()가 수행. */
void slide_set_target_mm(slide_ch_t ch, uint8_t mm);

/* 논블로킹: 메인 루프에서 매번 호출. 두 축을 각각 한 스텝씩 목표로 접근. */
void slide_service(void);

/* E-stop: on=1 이면 두 축 즉시 정지·래치, on=0 이면 해제. */
void slide_estop(uint8_t on);

/* 재영점: 현재 위치를 새 0점으로 선언(테스트용, 모터 안 움직임). */
void slide_rezero(slide_ch_t ch);

/* 호밍: 오른쪽 끝(시작점)까지 밀어붙여 0점을 잡는다(논블로킹, slide_service가 수행). */
void slide_seek_home(slide_ch_t ch);

/* 현재 위치(mm). 상태 보고용 피드백. */
uint8_t slide_get_pos_mm(slide_ch_t ch);

/* 이동 중이면 1(어느 축이든). FreeRTOS 태스크가 이동 중 정밀 스텝(tight-loop) 판단에 사용. */
uint8_t slide_is_moving(void);

/* 특정 축이 지금 실제로 구동(스텝) 중이면 1(드라이버 ON). 인터록 대기 축은 0. */
uint8_t slide_ch_is_moving(slide_ch_t ch);

/* 특정 축이 목표 미도달(구동 중 + 순서 대기 포함)이면 1. estop 시 0. */
uint8_t slide_ch_pending(slide_ch_t ch);

#ifdef __cplusplus
}
#endif

#endif /* __SLIDE_H__ */
