/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    slide.c
  * @brief   좌석 슬라이드 스텝모터 1축 구동 (논블로킹).
  ******************************************************************************
  */
/* USER CODE END Header */
#include "slide.h"

/* --------------------------------------------------------------------------
 *  핀 매핑 (드라이버 IN1~IN4  ↔  NUCLEO-F446RE 아두이노 헤더 D4~D7)
 *    IN1 = D4 = PB5
 *    IN2 = D5 = PB4
 *    IN3 = D6 = PB10
 *    IN4 = D7 = PA8
 *  CubeMX에서 위 핀에 User Label(IN1~IN4)을 지정하고 재생성하면 main.h에
 *  동일한 매크로가 생긴다. 아직 라벨을 안 잡았어도 아래 fallback 으로 빌드된다
 *  (#ifndef 이라 CubeMX 라벨이 생기면 그쪽이 우선).
 * ------------------------------------------------------------------------ */
#ifndef IN1_Pin
#define IN1_Pin        GPIO_PIN_5
#define IN1_GPIO_Port  GPIOB
#define IN2_Pin        GPIO_PIN_4
#define IN2_GPIO_Port  GPIOB
#define IN3_Pin        GPIO_PIN_10
#define IN3_GPIO_Port  GPIOB
#define IN4_Pin        GPIO_PIN_8
#define IN4_GPIO_Port  GPIOA
#endif

/* --------------------------------------------------------------------------
 *  튜닝 파라미터
 * ------------------------------------------------------------------------ */
#define STEPS_PER_MM           198.4f  /* 실측 보정(8ms로 탈조 제거 후): m50→반복 42mm → 166.67×50/42≈198.4 */
#define SLIDE_MAX_MM           100     /* DBC 사양 0~100mm 사용(제품 좌석 행정). 테스트 레일은 170mm지만 앞 100mm만 씀 */
#define SLIDE_STEP_INTERVAL_MS 5       /* 6→5ms (~20% 빠름). 시작/정지 토크 한계 근처 — 더 빠르려면 가속램프 */
#define HOME_STEP_INTERVAL_MS  5       /* 호밍은 천천히 */
/* 호밍 오버드라이브 배수: 어느 위치서 시작하든 끝에 확실히 닿게 전체행정보다 더 민다.
 * 끝에 닿은 뒤 남는 양만큼 갈리므로 작을수록 갈림↓(단 끝에 못 닿으면 키워야 함).
 * ★ 갈림을 줄이는 더 큰 레버는 SLIDE_MAX_MM 을 "실제 스트로크"로 맞추는 것. */
#define SLIDE_HOMING_OVERDRIVE 1.05f

/* 슬라이드 방향 규약: 0점 = 오른쪽 끝, +mm = 왼쪽으로 이동(오른쪽에서 출발해 왼쪽으로).
 * FWD_PHASE 부호가 "+mm일 때 코일을 어느 방향으로 돌릴지"를 정한다.
 *   -1 → +mm이 왼쪽(현재 규약). 호밍(-mm 방향)은 자연히 오른쪽 끝으로 향함 → 거기가 0.
 * 실제 모터가 의도와 반대로 돌면 이 부호만 뒤집으면 된다(재배선 불필요). */
#define FWD_PHASE              (-1)    /* -1: +mm을 왼쪽으로 (0 = 오른쪽 끝) */

/* 호밍 사용 여부.
 *   0 = 호밍 끔: 부팅 시 현재 위치를 0으로 간주(모터 안 움직임). 갈림 없음. 테스트용.
 *   1 = 하드스톱 호밍(센서 없음 → 끝까지 밀어 0점). 끝에서 갈림 발생.
 * 리밋 스위치/스톨 감지 붙기 전엔 0 권장. */
#define SLIDE_HOMING           0

/* --------------------------------------------------------------------------
 *  풀스텝 시퀀스 — 드라이버 종류에 맞춰 선택
 *    L298N(바이폴라): IN1/IN2=코일A H브리지, IN3/IN4=코일B H브리지
 *    ULN2003+28BYJ-48(유니폴라): IN1~IN4 각각이 한 상(相)
 *  ※ 모터가 회전하지 않고 진동만 하면 드라이버 종류가 반대인 것 →
 *    아래 define 을 0 으로 바꿔라.
 * ------------------------------------------------------------------------ */
#define STEPPER_DRIVER_L298N   1

#if STEPPER_DRIVER_L298N
static const uint8_t PHASE[4][4] = {
  {1,0,1,0},
  {0,1,1,0},
  {0,1,0,1},
  {1,0,0,1},
};
#else  /* ULN2003 / 28BYJ-48 유니폴라 풀스텝(2상 여자) */
static const uint8_t PHASE[4][4] = {
  {1,1,0,0},
  {0,1,1,0},
  {0,0,1,1},
  {1,0,0,1},
};
#endif

/* --------------------------------------------------------------------------
 *  상태 (모듈 내부)
 * ------------------------------------------------------------------------ */
static int32_t  posSteps     = 0;   /* 현재 위치(steps, home=0) */
static int32_t  targetSteps  = 0;   /* 목표 위치(steps) */
static uint8_t  stepPhase    = 0;   /* 풀스텝 시퀀스 인덱스 0~3 */
static uint32_t lastStepTick = 0;
static uint8_t  estop        = 0;   /* 1이면 모든 모션 정지(래치) */
static int32_t  homeRemaining = 0;  /* >0 이면 호밍 중(오른쪽 끝까지 남은 스텝수) */

/* --------------------------------------------------------------------------
 *  코일 구동 (내부)
 * ------------------------------------------------------------------------ */
static void set_coils(uint8_t p)
{
  HAL_GPIO_WritePin(IN1_GPIO_Port, IN1_Pin, PHASE[p][0]);
  HAL_GPIO_WritePin(IN2_GPIO_Port, IN2_Pin, PHASE[p][1]);
  HAL_GPIO_WritePin(IN3_GPIO_Port, IN3_Pin, PHASE[p][2]);
  HAL_GPIO_WritePin(IN4_GPIO_Port, IN4_Pin, PHASE[p][3]);
}

/* 정지 시 코일 전류 차단(발열↓). L298N/ULN2003 모두 정지 중 가열 주의 */
static void coils_off(void)
{
  HAL_GPIO_WritePin(IN1_GPIO_Port, IN1_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(IN2_GPIO_Port, IN2_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(IN3_GPIO_Port, IN3_Pin, GPIO_PIN_RESET);
  HAL_GPIO_WritePin(IN4_GPIO_Port, IN4_Pin, GPIO_PIN_RESET);
}

/* logical_dir: +1 = +mm 방향, -1 = -mm(home) 방향 */
static void slide_step(int logical_dir)
{
  int pstep = (logical_dir > 0) ? FWD_PHASE : -FWD_PHASE;
  stepPhase = (uint8_t)((stepPhase + pstep + 4) & 0x03);
  set_coils(stepPhase);
  posSteps += logical_dir;
}

/* --------------------------------------------------------------------------
 *  공개 API
 * ------------------------------------------------------------------------ */
void slide_init(void)
{
  posSteps    = 0;
  targetSteps = 0;
  stepPhase   = 0;
  estop       = 0;
  coils_off();
}

void slide_set_target_mm(uint8_t mm)
{
  if (mm > SLIDE_MAX_MM) mm = SLIDE_MAX_MM;          /* 범위 클램프 */
  targetSteps = (int32_t)(mm * STEPS_PER_MM);
}

void slide_service(void)
{
  if (estop) { coils_off(); return; }               /* E-stop: 정지 유지 */

  uint32_t now = HAL_GetTick();

  /* 호밍 중: 오른쪽 끝(시작점)까지 -mm 방향으로 한 스텝씩 밀기(논블로킹) */
  if (homeRemaining > 0) {
    if (now - lastStepTick < HOME_STEP_INTERVAL_MS) return;
    lastStepTick = now;
    slide_step(-1);                                 /* -mm = 물리적 오른쪽 */
    if (--homeRemaining == 0) {                      /* 하드스톱 도달 → 그 위치를 0으로 */
      posSteps    = 0;
      targetSteps = 0;
      coils_off();                                   /* 끝에서 정지 — 발열 방지 */
    }
    return;
  }

  if (posSteps == targetSteps) return;
  if (now - lastStepTick < SLIDE_STEP_INTERVAL_MS) return;
  lastStepTick = now;

  slide_step(posSteps < targetSteps ? +1 : -1);
}

/* 부팅 1회 호출. SLIDE_HOMING=1이면 하드스톱까지 밀어 0점 잡기(센서 없음 → 오버드라이브).
 * SLIDE_HOMING=0이면 현재 위치를 0으로 간주하고 즉시 복귀(모터 안 움직임). */
void slide_home(void)
{
#if SLIDE_HOMING
  int32_t n = (int32_t)(SLIDE_MAX_MM * STEPS_PER_MM * 1.2f);  /* 120% 오버슈트 */
  for (int32_t i = 0; i < n; i++) {
    if (estop) { coils_off(); return; }
    slide_step(-1);                                 /* home = -mm 방향 */
    HAL_Delay(HOME_STEP_INTERVAL_MS);
  }
#endif
  posSteps    = 0;                                  /* 여기가 0 기준 */
  targetSteps = 0;
  coils_off();
}

void slide_estop(uint8_t on)
{
  estop = on ? 1 : 0;
  if (estop) { homeRemaining = 0; coils_off(); }    /* 비상정지는 호밍도 취소 */
}

/* 재영점: 현재 물리 위치를 새 0점으로 선언한다(테스트용). 모터는 움직이지 않는다.
 * 개루프라 탈조로 위치가 틀어졌을 때 오른쪽 끝에 맞춰두고 호출하면 0이 재설정된다. */
void slide_rezero(void)
{
  homeRemaining = 0;
  posSteps    = 0;
  targetSteps = 0;
}

/* 시작점(오른쪽 끝) 호밍: -mm(오른쪽) 방향으로 전체행정의 120%를 밀어 하드스톱에 붙인 뒤
 * 그 위치를 0으로 잡는다. 논블로킹 — slide_service()가 한 스텝씩 수행(호밍 중에도 CAN/서보 동작).
 * 센서가 없어 끝에 닿은 뒤 남는 스텝은 갈림(skip)이 발생한다. 방향이 반대면 FWD_PHASE 부호를 뒤집을 것. */
void slide_seek_home(void)
{
  homeRemaining = (int32_t)(SLIDE_MAX_MM * STEPS_PER_MM * SLIDE_HOMING_OVERDRIVE);
}

uint8_t slide_get_pos_mm(void)
{
  int32_t mm = (int32_t)(posSteps / STEPS_PER_MM);
  if (mm < 0) mm = 0;
  if (mm > SLIDE_MAX_MM) mm = SLIDE_MAX_MM;
  return (uint8_t)mm;
}
