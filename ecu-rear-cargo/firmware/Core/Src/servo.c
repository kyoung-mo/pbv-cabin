/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    servo.c
  * @brief   좌석 리클라인 서보(SG90 x2) 각도 구동. TIM2 CH1/CH2 PWM.
  ******************************************************************************
  */
/* USER CODE END Header */
#include "servo.h"
#include "tim.h"     /* htim2 — CubeMX 에서 TIM2 활성화 후 재생성하면 생긴다 */

/* --------------------------------------------------------------------------
 *  SG90 펄스폭(µs) ↔ 각도 매핑
 *    SG90: 50Hz, 0.5ms(0°) ~ 2.5ms(180°).
 *    양 끝에서 떨림(버징)이 나면 600 / 2400 으로 좁혀라.
 *
 *  타이머 전제 (CubeMX TIM2 설정값과 일치해야 함):
 *    APB1 Timer clock = 84MHz, PSC=83  → 1 tick = 1µs
 *    ARR(Counter Period)=19999         → 20ms 주기 = 50Hz
 *    ⇒ CCR(Pulse) 값 = 펄스폭(µs) 그대로.
 * ------------------------------------------------------------------------ */
#define SERVO_MIN_US   500     /* 0°   */
#define SERVO_MAX_US   2500    /* 180° */
#define SERVO_MAX_DEG  180

/* 채널 인덱스 → TIM2 채널 */
static const uint32_t SERVO_TIM_CH[SERVO_COUNT] = {
  TIM_CHANNEL_1,   /* SERVO_RL → PA0 */
  TIM_CHANNEL_2,   /* SERVO_RR → PA1 */
};

static uint8_t curDeg[SERVO_COUNT] = {0, 0};   /* 현재 지령각 */

static uint32_t deg_to_us(uint8_t deg)
{
  if (deg > SERVO_MAX_DEG) deg = SERVO_MAX_DEG;
  return SERVO_MIN_US +
         ((uint32_t)deg * (SERVO_MAX_US - SERVO_MIN_US)) / SERVO_MAX_DEG;
}

void servo_init(void)
{
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++) {
    __HAL_TIM_SET_COMPARE(&htim2, SERVO_TIM_CH[ch], deg_to_us(0));
    HAL_TIM_PWM_Start(&htim2, SERVO_TIM_CH[ch]);
    curDeg[ch] = 0;
  }
}

void servo_set_deg(servo_ch_t ch, uint8_t deg)
{
  if (ch >= SERVO_COUNT) return;
  if (deg > SERVO_MAX_DEG) deg = SERVO_MAX_DEG;
  curDeg[ch] = deg;
  __HAL_TIM_SET_COMPARE(&htim2, SERVO_TIM_CH[ch], deg_to_us(deg));
}

uint8_t servo_get_deg(servo_ch_t ch)
{
  if (ch >= SERVO_COUNT) return 0;
  return curDeg[ch];
}
