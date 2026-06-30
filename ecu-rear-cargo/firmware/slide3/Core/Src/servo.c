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

/* 서보 속도 제한(소프트 램프): 목표각으로 한 번에 안 가고 조금씩 따라간다.
 * SG90은 속도 입력이 없어, 출력각을 천천히 올려 느린 모션을 흉내낸다.
 *   속도 ≈ SERVO_RAMP_STEP_DEG / SERVO_RAMP_INTERVAL_MS
 *   예) 1° / 20ms = 50°/s  (SG90 최대 ~600°/s보다 훨씬 느림)
 *   더 느리게: INTERVAL_MS ↑ (예 40ms→25°/s).  더 빠르게: INTERVAL_MS ↓. */
#define SERVO_RAMP_INTERVAL_MS 20
#define SERVO_RAMP_STEP_DEG    1

/* 채널 인덱스 → TIM2 채널 */
static const uint32_t SERVO_TIM_CH[SERVO_COUNT] = {
  TIM_CHANNEL_1,   /* SERVO_RL → PA0 */
  TIM_CHANNEL_2,   /* SERVO_RR → PA1 */
};

static uint8_t  curDeg[SERVO_COUNT] = {0, 0};  /* 현재 출력각(PWM에 반영) */
static uint8_t  tgtDeg[SERVO_COUNT] = {0, 0};  /* 목표각(지령) — service가 여기로 램프 */
static uint32_t lastRampTick = 0;

static uint32_t deg_to_us(uint8_t deg)
{
  if (deg > SERVO_MAX_DEG) deg = SERVO_MAX_DEG;
  return SERVO_MIN_US +
         ((uint32_t)deg * (SERVO_MAX_US - SERVO_MIN_US)) / SERVO_MAX_DEG;
}

void servo_init(void)
{
  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++) {
    curDeg[ch] = 0;
    tgtDeg[ch] = 0;
    __HAL_TIM_SET_COMPARE(&htim2, SERVO_TIM_CH[ch], deg_to_us(0));
    HAL_TIM_PWM_Start(&htim2, SERVO_TIM_CH[ch]);
  }
}

void servo_set_deg(servo_ch_t ch, uint8_t deg)
{
  if (ch >= SERVO_COUNT) return;
  if (deg > SERVO_MAX_DEG) deg = SERVO_MAX_DEG;
  tgtDeg[ch] = deg;          /* 목표만 갱신. 실제 이동(PWM)은 servo_service()가 램프로 수행 */
}

/* 논블로킹: 메인 루프에서 매번 호출. 각 서보 출력각을 목표각으로 조금씩 접근(속도 제한). */
void servo_service(void)
{
  uint32_t now = HAL_GetTick();
  if (now - lastRampTick < SERVO_RAMP_INTERVAL_MS) return;
  lastRampTick = now;

  for (uint8_t ch = 0; ch < SERVO_COUNT; ch++) {
    if (curDeg[ch] == tgtDeg[ch]) continue;

    int16_t diff = (int16_t)tgtDeg[ch] - (int16_t)curDeg[ch];
    if (diff >  SERVO_RAMP_STEP_DEG)      curDeg[ch] += SERVO_RAMP_STEP_DEG;
    else if (diff < -SERVO_RAMP_STEP_DEG) curDeg[ch] -= SERVO_RAMP_STEP_DEG;
    else                                  curDeg[ch]  = tgtDeg[ch];   /* 남은 각이 한 스텝 이내 → 스냅 */

    __HAL_TIM_SET_COMPARE(&htim2, SERVO_TIM_CH[ch], deg_to_us(curDeg[ch]));
  }
}

/* 안티핀치 후퇴: 현재 '진행 방향의 반대'로 deg만큼 물러나 압력을 해제하고,
 * 동시에 원래 목표를 그 위치로 덮어써 더 이상 장애물 쪽으로 밀지 않게 한다.
 * (예: 150→0로 내려가다 75에서 막히면 진행=감소 → 후퇴=+15 → 90으로 물러남) */
void servo_pinch_relief(servo_ch_t ch, uint8_t deg)
{
  if (ch >= SERVO_COUNT) return;
  int16_t dir  = (tgtDeg[ch] >= curDeg[ch]) ? 1 : -1;       /* 진행 방향 */
  int16_t back = (int16_t)curDeg[ch] - dir * (int16_t)deg;  /* 반대로 후퇴 */
  if (back < 0)             back = 0;
  if (back > SERVO_MAX_DEG) back = SERVO_MAX_DEG;
  tgtDeg[ch] = (uint8_t)back;
}

uint8_t servo_get_deg(servo_ch_t ch)
{
  if (ch >= SERVO_COUNT) return 0;
  return curDeg[ch];   /* 현재 출력각(램프 진행 중이면 이동 중 값) */
}
