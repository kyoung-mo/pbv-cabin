/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    servo.h
  * @brief   Rear_Zone_ECU 좌석 리클라인 서보(SG90 x2) 각도 구동 모듈.
  *          PWM 구동만 담당한다. CAN 송수신은 이 모듈에 넣지 않는다.
  *          TIM2 CH1/CH2(PA0/PA1)를 50Hz PWM 으로 쓴다(CubeMX 설정 필요).
  ******************************************************************************
  */
/* USER CODE END Header */
#ifndef __SERVO_H__
#define __SERVO_H__

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"

/* 서보 채널: 좌석 좌(RL) / 우(RR) 리클라인 각도 */
typedef enum {
  SERVO_RL = 0,   /* TIM2_CH1, PA0 (아두이노 A0) */
  SERVO_RR = 1,   /* TIM2_CH2, PA1 (아두이노 A1) */
  SERVO_COUNT
} servo_ch_t;

/* PWM 시작 + 두 채널 모두 0°로. MX_TIM2_Init() 이후(USER CODE 2)에 1회 호출. */
void servo_init(void);

/* 목표 각도(0~180°) 지정. 범위 밖은 클램프. SG90은 하드웨어로 위치를 유지하므로
 * 슬라이드와 달리 service 루프가 필요 없다(설정 즉시 PWM 반영). */
void servo_set_deg(servo_ch_t ch, uint8_t deg);

/* 현재 지령각(상태 보고용 피드백). */
uint8_t servo_get_deg(servo_ch_t ch);

#ifdef __cplusplus
}
#endif

#endif /* __SERVO_H__ */
