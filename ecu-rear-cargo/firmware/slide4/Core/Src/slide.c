/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    slide.c
  * @brief   좌석 슬라이드 스텝모터 2축 구동 (논블로킹) — TMC2208 STEP/DIR/EN ×2.
  *          STM32F446 1대로 리니어 스크류 액추에이터 2대(RL/RR)를 독립 제어한다.
  ******************************************************************************
  */
/* USER CODE END Header */
#include "slide.h"

/* --------------------------------------------------------------------------
 *  채널별 TMC2208 핀 매핑 (NUCLEO-F446RE)
 *    SLIDE_RL (기존 1축): STEP=PB5(D4)  DIR=PB4(D5)  EN=PB10(D6)   ← 배선 그대로
 *    SLIDE_RR (신규 2축): STEP=PC0      DIR=PC1      EN=PC2        ← 추가 결선
 *  EN: LOW=구동 / HIGH=전류차단·프리휠. 두 드라이버 EN 독립(축별 정지 가능).
 * ------------------------------------------------------------------------ */
typedef struct {
  GPIO_TypeDef *step_port; uint16_t step_pin;
  GPIO_TypeDef *dir_port;  uint16_t dir_pin;
  GPIO_TypeDef *en_port;   uint16_t en_pin;
} slide_io_t;

static const slide_io_t IO[SLIDE_COUNT] = {
  { GPIOB, GPIO_PIN_5, GPIOB, GPIO_PIN_4, GPIOB, GPIO_PIN_10 },  /* SLIDE_RL */
  { GPIOC, GPIO_PIN_0, GPIOC, GPIO_PIN_1, GPIOC, GPIO_PIN_2  },  /* SLIDE_RR */
};

/* TMC2208 EN 극성: LOW=enable(구동), HIGH=disable(전류차단). */
#define DRV_ENABLE_LEVEL   GPIO_PIN_RESET
#define DRV_DISABLE_LEVEL  GPIO_PIN_SET

/* --------------------------------------------------------------------------
 *  튜닝 파라미터 (두 축 동일 하드웨어 가정)
 * ------------------------------------------------------------------------ */
#define MICROSTEP              2       /* TMC2208 MS1/MS2 핀 설정과 일치(여기선 1/2). MS 핀 바꾸면 이 값도 맞출 것 */
#define FULLSTEPS_PER_MM       198.4f  /* 풀스텝 실측 보정값(L298N 시절). 마이크로스텝 배수는 아래서 곱한다 */
#define STEPS_PER_MM           (FULLSTEPS_PER_MM * MICROSTEP)  /* 1/2 → 396.8 microsteps/mm */
#define SLIDE_MAX_MM           100     /* DBC 사양 0~100mm 사용(제품 좌석 행정) */

/* STEP 펄스 주기: HAL_GetTick(1ms)으론 마이크로스텝 속도를 못 내므로 DWT(µs)로 타이밍.
 * 가속 램프: 출발은 STEP_START_US(느리게)에서 시작해 한 스텝마다 STEP_ACCEL_US씩 간격을
 * 줄여 STEP_MIN_US(최고속)까지 가속한다. StealthChop 급출발 탈조 방지 + 정지마찰 극복.
 * 최고 이동속도 ≈ 1e6 / (STEP_MIN_US × STEPS_PER_MM) mm/s.
 *   예) 200µs, 396.8/mm → ≈12.6mm/s. 더 빠르게: STEP_MIN_US ↓. 탈조나면 STEP_MIN_US ↑(완만). */
#define STEP_MIN_US            800u    /* 최고속 간격(작을수록 빠름). 500→800: 토크 확보(≈3mm/s) */
#define STEP_START_US          2000u   /* 출발 간격(가속 시작점, 정지마찰 극복) */
#define STEP_ACCEL_US          5u      /* 스텝당 간격 감소량(작을수록 완만한 가속→탈조↓) */
#define HOME_INTERVAL_US       3000u   /* 호밍은 천천히(가속 없음, ≈0.84mm/s) */
#define STEP_PULSE_US          3u      /* STEP HIGH 펄스폭(µs). TMC2208 최소요구보다 넉넉 */

/* 호밍 오버드라이브 배수: 어느 위치서 시작하든 끝에 확실히 닿게 전체행정보다 더 민다. */
#define SLIDE_HOMING_OVERDRIVE 1.05f

/* 슬라이드 방향 규약: 0점 = 오른쪽 끝, +mm = 왼쪽 이동.
 * DIR_FWD_LEVEL[ch] = "+mm(왼쪽)으로 갈 때 DIR 핀 레벨". 모터/기구가 반대로 가면 해당 축 값만
 * 뒤집으면 된다(재배선 불필요). 축마다 모터 장착 방향이 달라 채널별로 둔다. */
static const GPIO_PinState DIR_FWD_LEVEL[SLIDE_COUNT] = {
  GPIO_PIN_SET,     /* SLIDE_RL — h 호밍이 반대로 가서 반전(2026-06-25) */
  GPIO_PIN_SET,     /* SLIDE_RR — EN/STEP 오배선 수정 후 원복(2026-07-02) */
};

/* 호밍 사용 여부.
 *   0 = 호밍 끔: 부팅 시 현재 위치를 0으로 간주(모터 안 움직임). 갈림 없음. 테스트용.
 *   1 = 하드스톱 호밍(센서 없음 → 끝까지 밀어 0점). 끝에서 갈림 발생.
 * 리밋 스위치/스톨 감지 붙기 전엔 0 권장. */
#define SLIDE_HOMING           0

/* --------------------------------------------------------------------------
 *  상태 (채널별 배열)
 * ------------------------------------------------------------------------ */
static int32_t  posSteps[SLIDE_COUNT]      = {0};  /* 현재 위치(microsteps, home=0) */
static int32_t  targetSteps[SLIDE_COUNT]   = {0};  /* 목표 위치(microsteps) */
static uint32_t lastStepCyc[SLIDE_COUNT]   = {0};  /* 마지막 스텝 시각(DWT 사이클) */
static uint8_t  enabled[SLIDE_COUNT]       = {0};  /* 드라이버 EN 상태 캐시(중복 GPIO write 방지) */
static int32_t  homeRemaining[SLIDE_COUNT] = {0};  /* >0 이면 호밍 중(오른쪽 끝까지 남은 스텝수) */
static uint32_t curStepUs[SLIDE_COUNT]     = {0};  /* 현재 스텝 간격(가속 중 STEP_START→STEP_MIN) */
static uint8_t  estop                      = 0;    /* 1이면 두 축 모두 정지(래치) */
static uint8_t  homed[SLIDE_COUNT]         = {0};  /* 1=원점 확정(호밍완료/재영점)→위치보고 유효. 0=미확정(0xFF 보고) */

/* --------------------------------------------------------------------------
 *  DWT 마이크로초 타이머 (Cortex-M4 사이클 카운터)
 * ------------------------------------------------------------------------ */
#define US_TO_CYC(us)  ((uint32_t)(us) * (SystemCoreClock / 1000000u))

static void dwt_init(void)
{
  CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;   /* 트레이스 유닛 enable */
  DWT->CYCCNT = 0;
  DWT->CTRL  |= DWT_CTRL_CYCCNTENA_Msk;             /* 사이클 카운터 start */
}

/* 짧은 busy-wait(µs). unsigned 차연산이라 카운터 wrap에도 안전. */
static void delay_us(uint32_t us)
{
  uint32_t t0 = DWT->CYCCNT;
  uint32_t d  = US_TO_CYC(us);
  while ((DWT->CYCCNT - t0) < d) { }
}

/* --------------------------------------------------------------------------
 *  드라이버 enable/disable (내부, 채널별)
 * ------------------------------------------------------------------------ */
static void driver_enable(slide_ch_t ch)
{
  if (!enabled[ch]) {
    HAL_GPIO_WritePin(IO[ch].en_port, IO[ch].en_pin, DRV_ENABLE_LEVEL);
    enabled[ch] = 1;
  }
}

/* 정지 시 전류 차단(발열↓). TMC2208 disable=프리휠이라 홀딩 토크는 사라진다
 * (개루프 슬라이드는 리드스크류 셀프락/마찰로 위치 유지 가정 — L298N coils_off와 동일 철학). */
static void driver_disable(slide_ch_t ch)
{
  if (enabled[ch]) {
    HAL_GPIO_WritePin(IO[ch].en_port, IO[ch].en_pin, DRV_DISABLE_LEVEL);
    enabled[ch] = 0;
  }
}

/* --------------------------------------------------------------------------
 *  한 마이크로스텝 (내부, 채널별)
 *    logical_dir: +1 = +mm 방향, -1 = -mm(home) 방향
 * ------------------------------------------------------------------------ */
static void slide_step(slide_ch_t ch, int logical_dir)
{
  GPIO_PinState fwd = DIR_FWD_LEVEL[ch];
  HAL_GPIO_WritePin(IO[ch].dir_port, IO[ch].dir_pin,
                    (logical_dir > 0) ? fwd
                                      : (fwd == GPIO_PIN_RESET ? GPIO_PIN_SET : GPIO_PIN_RESET));

  /* STEP 상승엣지에서 래치 — DIR setup 시간 확보 후 펄스 1발 */
  HAL_GPIO_WritePin(IO[ch].step_port, IO[ch].step_pin, GPIO_PIN_SET);
  delay_us(STEP_PULSE_US);
  HAL_GPIO_WritePin(IO[ch].step_port, IO[ch].step_pin, GPIO_PIN_RESET);

  posSteps[ch] += logical_dir;
}

/* 한 축의 논블로킹 모션 1틱. */
static void service_ch(slide_ch_t ch)
{
  uint32_t now = DWT->CYCCNT;

  /* 호밍 중: 오른쪽 끝(시작점)까지 -mm 방향으로 한 스텝씩 밀기 */
  if (homeRemaining[ch] > 0) {
    if ((now - lastStepCyc[ch]) < US_TO_CYC(HOME_INTERVAL_US)) return;
    lastStepCyc[ch] = now;
    driver_enable(ch);
    slide_step(ch, -1);                              /* -mm = 물리적 오른쪽 */
    if (--homeRemaining[ch] == 0) {                   /* 하드스톱 도달 → 그 위치를 0으로 */
      posSteps[ch]    = 0;
      targetSteps[ch] = 0;
      homed[ch]       = 1;                           /* 254 호밍 완료 = 원점 확정 → 위치보고 시작 */
      driver_disable(ch);                            /* 끝에서 정지 — 발열 방지 */
    }
    return;
  }

  if (posSteps[ch] == targetSteps[ch]) {            /* 목표 도달 → 전류 차단 + 가속 리셋 */
    driver_disable(ch);
    curStepUs[ch] = STEP_START_US;
    return;
  }
  if ((now - lastStepCyc[ch]) < US_TO_CYC(curStepUs[ch])) return;
  lastStepCyc[ch] = now;

  driver_enable(ch);
  slide_step(ch, posSteps[ch] < targetSteps[ch] ? +1 : -1);

  if (curStepUs[ch] > STEP_MIN_US) {                /* 가속: 간격을 최고속까지 점차 단축 */
    curStepUs[ch] = (curStepUs[ch] > STEP_MIN_US + STEP_ACCEL_US)
                    ? curStepUs[ch] - STEP_ACCEL_US : STEP_MIN_US;
  }
}

/* --------------------------------------------------------------------------
 *  공개 API
 * ------------------------------------------------------------------------ */
void slide_init(void)
{
  dwt_init();
  estop = 0;
  for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++) {
    posSteps[ch]      = 0;
    targetSteps[ch]   = 0;
    homeRemaining[ch] = 0;
    homed[ch]         = 0;          /* 부팅 원점 미확정(SLIDE_HOMING=0) → 호밍/재영점 전까지 0xFF 보고 */
    curStepUs[ch]     = STEP_START_US;
    enabled[ch]       = 1;          /* MX_GPIO_Init이 EN=LOW(enable)로 둠 → 캐시 동기화 후 끈다 */
    HAL_GPIO_WritePin(IO[ch].step_port, IO[ch].step_pin, GPIO_PIN_RESET);
    driver_disable((slide_ch_t)ch); /* 정지 상태로 시작(전류 차단) */
  }
}

void slide_set_target_mm(slide_ch_t ch, uint8_t mm)
{
  if (ch >= SLIDE_COUNT) return;
  if (mm > SLIDE_MAX_MM) mm = SLIDE_MAX_MM;          /* 범위 클램프 */
  targetSteps[ch] = (int32_t)(mm * STEPS_PER_MM);
}

/* 인터록 제거(2026-07-05): 두 축 직렬화를 supervisor가 위치 피드백 기반으로 담당한다.
 * slide_service는 두 축을 각각 서비스한다.
 * 주의: 펌웨어 레벨의 동시구동 차단 안전망은 이제 없다 — supervisor가 겹친 명령을 보내면
 *       두 축이 동시에 구동될 수 있다(드라이버 과전류 위험). 직렬화 책임은 supervisor. */
void slide_service(void)
{
  if (estop) {                                       /* E-stop: 두 축 정지 유지 */
    for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++) driver_disable((slide_ch_t)ch);
    return;
  }
  for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++) service_ch((slide_ch_t)ch);
}

/* 부팅 1회 호출. SLIDE_HOMING=1이면 하드스톱까지 밀어 0점 잡기(센서 없음 → 오버드라이브).
 * SLIDE_HOMING=0이면 현재 위치를 0으로 간주하고 즉시 복귀(모터 안 움직임). 두 축 순차 처리. */
void slide_home(void)
{
  for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++) {
#if SLIDE_HOMING
    driver_enable((slide_ch_t)ch);
    int32_t n = (int32_t)(SLIDE_MAX_MM * STEPS_PER_MM * 1.2f);  /* 120% 오버슈트 */
    for (int32_t i = 0; i < n; i++) {
      if (estop) { driver_disable((slide_ch_t)ch); break; }
      slide_step((slide_ch_t)ch, -1);              /* home = -mm 방향 */
      delay_us(HOME_INTERVAL_US);
    }
#endif
    posSteps[ch]    = 0;                            /* 여기가 0 기준 */
    targetSteps[ch] = 0;
    driver_disable((slide_ch_t)ch);
  }
}

void slide_estop(uint8_t on)
{
  estop = on ? 1 : 0;
  if (estop) {                                       /* 비상정지는 호밍도 취소 */
    for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++) {
      homeRemaining[ch] = 0;
      driver_disable((slide_ch_t)ch);
    }
  }
}

/* 재영점: 현재 물리 위치를 새 0점으로 선언한다(테스트용). 모터는 움직이지 않는다.
 * 개루프라 탈조로 위치가 틀어졌을 때 오른쪽 끝에 맞춰두고 호출하면 0이 재설정된다. */
void slide_rezero(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT) return;
  homeRemaining[ch] = 0;
  posSteps[ch]      = 0;
  targetSteps[ch]   = 0;
  homed[ch]         = 1;             /* 255 재영점 = 현위치를 원점으로 확정 → 위치보고 유효 */
}

/* 시작점(오른쪽 끝) 호밍: -mm(오른쪽) 방향으로 전체행정의 105%를 밀어 하드스톱에 붙인 뒤
 * 그 위치를 0으로 잡는다. 논블로킹 — slide_service()가 한 스텝씩 수행(호밍 중에도 CAN/서보 동작).
 * 센서가 없어 끝에 닿은 뒤 남는 스텝은 갈림(skip)이 발생한다. 방향이 반대면 DIR_FWD_LEVEL을 뒤집을 것. */
void slide_seek_home(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT) return;
  homed[ch]         = 0;             /* 호밍 시작 = 원점 무효화(완료 시 service_ch가 다시 1) */
  homeRemaining[ch] = (int32_t)(SLIDE_MAX_MM * STEPS_PER_MM * SLIDE_HOMING_OVERDRIVE);
}

uint8_t slide_get_pos_mm(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT) return 0;
  int32_t mm = (int32_t)(posSteps[ch] / STEPS_PER_MM);
  if (mm < 0) mm = 0;
  if (mm > SLIDE_MAX_MM) mm = SLIDE_MAX_MM;
  return (uint8_t)mm;
}

/* CAN 상태 보고용 위치. 원점 확정(homed) 전엔 0xFF(미확정) → 중앙이 "호밍 필요"로 인식하게 한다.
 * 호밍/재영점 전엔 절대위치를 신뢰할 수 없고(개루프), 클램프로 0이 되어 "위치0"으로 오해되는 걸 막는다. */
uint8_t slide_report_pos_mm(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT) return 0xFFu;
  return homed[ch] ? slide_get_pos_mm(ch) : 0xFFu;
}

/* 이동 중이면 1(estop 시 0). 어느 축이든 목표 미도달 또는 호밍 중이면 이동으로 본다.
 * FreeRTOS MotionTask 가 이동 중엔 tight-loop(정밀 DWT 스텝), 대기 중엔 양보하도록 판단용. */
uint8_t slide_is_moving(void)
{
  if (estop) return 0;
  for (uint8_t ch = 0; ch < SLIDE_COUNT; ch++)
    if (homeRemaining[ch] > 0 || posSteps[ch] != targetSteps[ch]) return 1;
  return 0;
}

/* 특정 축이 지금 실제로 구동(스텝) 중인가. 1=드라이버 ON(이동 중), 0=정지/순서대기.
 * 인터록으로 한 번에 한 축만 ON이므로, 명령은 받았지만 순서 대기 중인 축은 0을 반환한다.
 * (명령 접수됐으나 아직 시작 전인지까지 보려면 slide_ch_pending 사용) */
uint8_t slide_ch_is_moving(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT) return 0;
  return enabled[ch];
}

/* 특정 축이 목표 미도달(이동 중 + 순서 대기 포함)이면 1. estop 시 0. */
uint8_t slide_ch_pending(slide_ch_t ch)
{
  if (ch >= SLIDE_COUNT || estop) return 0;
  return (homeRemaining[ch] > 0 || posSteps[ch] != targetSteps[ch]);
}
