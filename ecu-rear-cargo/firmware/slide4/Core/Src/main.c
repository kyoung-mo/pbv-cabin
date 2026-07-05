/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2026 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "cmsis_os.h"
#include "can.h"
#include "i2c.h"
#include "tim.h"
#include "usart.h"
#include "gpio.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>      /* printf */
#include "slide.h"          /* 슬라이드 스텝모터 모듈 */
#include "servo.h"          /* 리클라인 서보(SG90 x2) 모듈 — TIM2 PWM */
#include "ina226.h"         /* 서보 전류센서(INA226 x2) — 안티핀치 */
#include "model_car_net.h"  /* cantools 생성 DBC 라이브러리 (프레임 ID/시그널 정식 정의) */
#include "cmsis_os.h"       /* FreeRTOS CMSIS-RTOS2 (태스크/큐/osDelay) */
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
/* 프레임 ID는 model_car_net.h(DBC)를 정식 기준으로 사용한다.
 *   HMI_Emergency        = 0x010  (기존 0x500 매직값은 폐기)
 *   Rear_Left_Seat_Cmd   = 0x120  / _Status = 0x220
 *   Rear_Right_Seat_Cmd  = 0x121  / _Status = 0x221
 */
#define STATUS_PERIOD_MS 100       /* 상태 브로드캐스트 주기 */

/* 슬라이드 위치 센티넬: RL_Slide_Position(0~100mm) 범위 밖 값으로 특수 명령 표현.
 *   255 = 재영점("여기를 0으로", 모터 안 움직임)  — cantest.py 'z'
 *   254 = 호밍("오른쪽 끝 시작점으로 가서 0점 잡기")  — cantest.py 'h'
 * 중간에서 부팅됐을 때 254로 실제 시작점까지 보낸 뒤 m<mm>를 쓰면 절대위치가 맞는다. */
#define SLIDE_REZERO_CMD 255
#define SLIDE_HOME_CMD   254
#define SLIDE_HOLD_CMD   253   /* 슬라이드 유지(안 움직임) — 리클라인 서보만 조정할 때 */

/* 안티핀치: 서보 전류센서(INA226) 7비트 주소 + 판정 파라미터.
 * 서보가 끼임으로 스톨되면 전류가 급상승(SG90 구동 ~150mA → 스톨 ~700mA). */
#define INA226_ADDR_RL    0x40     /* RL 리클라인 서보 전류 → rl_pinch_detected */
#define INA226_ADDR_RR    0x41     /* RR 리클라인 서보 전류 → rr_pinch_detected */
#define PINCH_CURRENT_MA  170      /* TODO(calibration): 끼임 판정 전류 임계값(mA) */
#define PINCH_DEBOUNCE    3        /* 연속 N회 초과 시 확정(돌입전류 오검출 방지) */
#define PINCH_PERIOD_MS   20       /* 전류 폴링 주기 */
#define PINCH_BACKOFF_DEG 15       /* 끼임 시 서보를 이 각만큼 후퇴시켜 압력 해제 */
#define PINCH_DEBUG       1        /* 1=서보 전류를 300ms마다 UART 출력(진단/임계값 보정용). 끝나면 0 */
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/

/* USER CODE BEGIN PV */
/* 리클라인 각도는 servo 모듈이 보관(servo_get_deg)하므로 별도 에코 변수 불필요 */
uint8_t  cmd_cargo_lamp = 0;       /* TODO: 램프 GPIO */
volatile uint8_t pinch_rl = 0;     /* INA226 안티핀치: 1=RL 끼임(래치). MotionTask 기록/StatusTask 읽기 */
volatile uint8_t pinch_rr = 0;     /* 1=RR 서보 끼임 감지(래치) */
static uint8_t ina_ok_rl = 0;      /* INA226(RL) 장착 여부 — 미장착이면 모니터 skip */
static uint8_t ina_ok_rr = 0;      /* INA226(RR) 장착 여부 */

/* FreeRTOS: CAN 수신 프레임 → 큐 → MotionTask 에서 디코드. ISR 부담 최소화 + 상태 단일소유. */
typedef struct { uint32_t id; uint8_t dlc; uint8_t data[8]; } can_frame_t;
static osMessageQueueId_t canRxQ;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
void MX_FREERTOS_Init(void);
/* USER CODE BEGIN PFP */
static void CAN_Config(void);
static void send_status(void);
static void pinch_service(void);
static void can_dispatch(const can_frame_t *f);   /* 큐에서 꺼낸 프레임 처리(MotionTask) */
void StartMotionTask(void *argument);             /* 액추에이터 + CAN 디스패치 */
void StartStatusTask(void *argument);             /* 상태 송신(100ms) */
void app_rtos_init(void);                          /* 큐/태스크 생성(freertos.c 에서 호출) */
#if PINCH_DEBUG
static void i2c_scan(void);
#endif
/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{

  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_CAN1_Init();
  MX_USART2_UART_Init();
  MX_TIM2_Init();
  MX_I2C1_Init();
  /* USER CODE BEGIN 2 */
  CAN_Config();
  slide_init();
  servo_init();                       /* 리클라인 서보 PWM 시작(두 채널 0°) */
  servo_set_deg(SERVO_RL, 90);        /* 부팅/리셋 시 좌석 각도 기본 90° (스케줄러 시작 후 servo_service가 램프) */
  servo_set_deg(SERVO_RR, 90);
  ina_ok_rl = ina226_init(INA226_ADDR_RL);   /* 미장착이면 0 → 해당 축 모니터 skip */
  ina_ok_rr = ina226_init(INA226_ADDR_RR);
  printf("Rear_Zone_ECU boot (INA226 RL=%u RR=%u)\r\n", ina_ok_rl, ina_ok_rr);
#if PINCH_DEBUG
  i2c_scan();                                 /* 버스에 응답하는 I2C 주소 출력(진단) */
#endif
  slide_home();                       /* 부팅 시 0점 잡기 */
  /* USER CODE END 2 */

  /* Init scheduler */
  osKernelInitialize();  /* Call init function for freertos objects (in cmsis_os2.c) */
  MX_FREERTOS_Init();

  /* Start scheduler */
  osKernelStart();

  /* We should never get here as control is now taken by the scheduler */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
    /* FreeRTOS 스케줄러가 제어를 가져가므로 이 지점(main while)엔 도달하지 않음.
     * 애플리케이션 로직은 MotionTask / StatusTask 로 이동(USER CODE 4). */
  }
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

  /** Configure the main internal regulator output voltage
  */
  __HAL_RCC_PWR_CLK_ENABLE();
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE3);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLM = 8;
  RCC_OscInitStruct.PLL.PLLN = 84;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLR = 2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
}

/* USER CODE BEGIN 4 */

/* printf → USART2 (ST-Link VCP) 리타게팅.
 * syscalls.c 의 weak _write 가 문자마다 __io_putchar 를 호출한다. */
int __io_putchar(int ch)
{
  HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
  return ch;
}

/* CAN: 필터(전부 통과) + 시작 + 수신 인터럽트 활성화.
 * NVIC enable 은 can.c 의 MspInit 에서 이미 했으므로 여기선 하지 않는다. */
static void CAN_Config(void)
{
  CAN_FilterTypeDef f = {0};
  f.FilterBank           = 0;
  f.FilterMode           = CAN_FILTERMODE_IDMASK;
  f.FilterScale          = CAN_FILTERSCALE_32BIT;
  f.FilterIdHigh         = 0x0000;
  f.FilterIdLow          = 0x0000;
  f.FilterMaskIdHigh     = 0x0000;   /* mask 0 = 전부 통과 */
  f.FilterMaskIdLow      = 0x0000;
  f.FilterFIFOAssignment = CAN_RX_FIFO0;
  f.FilterActivation     = ENABLE;

  HAL_CAN_ConfigFilter(&hcan1, &f);
  HAL_CAN_Start(&hcan1);
  HAL_CAN_ActivateNotification(&hcan1, CAN_IT_RX_FIFO0_MSG_PENDING);
}

/* 상태 브로드캐스트: 0x220(좌), 0x221(우). DBC pack 함수로 직렬화 */
static void send_status(void)
{
  CAN_TxHeaderTypeDef tx = {0};
  uint32_t mbx;
  uint8_t  d[8] = {0};

  tx.IDE = CAN_ID_STD;
  tx.RTR = CAN_RTR_DATA;

  /* 0x220 Rear_Left_Seat_Status */
  struct model_car_net_rear_left_seat_status_t rl = {
    .curr_rl_recline   = servo_get_deg(SERVO_RL),  /* RL 리클라인 서보 지령각(°) */
    .rl_pinch_detected = pinch_rl,                 /* INA226 안티핀치 결과(래치) */
  };
  tx.StdId = MODEL_CAR_NET_REAR_LEFT_SEAT_STATUS_FRAME_ID;
  tx.DLC   = (uint32_t)model_car_net_rear_left_seat_status_pack(d, &rl, sizeof(d));
  HAL_CAN_AddTxMessage(&hcan1, &tx, d, &mbx);

  /* 0x221 Rear_Right_Seat_Status */
  struct model_car_net_rear_right_seat_status_t rr = {
    .curr_rr_recline   = servo_get_deg(SERVO_RR),  /* RR 리클라인 서보 지령각(°) */
    .rr_pinch_detected = pinch_rr,
  };
  tx.StdId = MODEL_CAR_NET_REAR_RIGHT_SEAT_STATUS_FRAME_ID;
  tx.DLC   = (uint32_t)model_car_net_rear_right_seat_status_pack(d, &rr, sizeof(d));
  HAL_CAN_AddTxMessage(&hcan1, &tx, d, &mbx);
}

/* CAN 수신 콜백(ISR): 프레임만 큐에 넣고 즉시 반환 → 무거운 디코드/구동은 MotionTask 로.
 * 큐가 꽉 차면(timeout 0) 드롭. ISR 부담 최소화 + 액추에이터 접근을 단일 태스크로 일원화. */
void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
  CAN_RxHeaderTypeDef rx;
  can_frame_t f = {0};

  if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &rx, f.data) != HAL_OK) return;
  f.id  = rx.StdId;
  f.dlc = rx.DLC;
  osMessageQueuePut(canRxQ, &f, 0, 0);   /* ISR-safe(timeout 0) */
}

/* 큐에서 꺼낸 CAN 프레임을 DBC unpack 하여 slide/servo 모듈로 전달(MotionTask 문맥에서 호출).
 * unpack 의 size 인자는 소스 버퍼 크기(8). data 를 0으로 초기화했으므로 DLC 가 짧아도 0으로 읽힘. */
static void can_dispatch(const can_frame_t *f)
{
  switch (f->id) {

    case MODEL_CAR_NET_HMI_EMERGENCY_FRAME_ID: {       /* 0x010: 최고 우선 처리 */
      struct model_car_net_hmi_emergency_t m;
      if (model_car_net_hmi_emergency_unpack(&m, f->data, sizeof(f->data)) == 0)
        slide_estop(m.emergency_stop_flag);            /* 1=래치 정지, 0=해제 */
      break;
    }

    case MODEL_CAR_NET_REAR_LEFT_SEAT_CMD_FRAME_ID: {  /* 0x120: 좌석 좌 */
      struct model_car_net_rear_left_seat_cmd_t m;
      if (model_car_net_rear_left_seat_cmd_unpack(&m, f->data, sizeof(f->data)) == 0) {
        pinch_rl = 0;                                  /* 새 명령 = 끼임 해소 간주, 래치 해제 */
        servo_set_deg(SERVO_RL, m.rl_recline_angle);   /* 리클라인 SG90 서보(좌) */
        if (m.rl_slide_position == SLIDE_HOLD_CMD)
          { /* 253 = 슬라이드 유지: 이동 명령 없음(서보만 조정) */ }
        else if (m.rl_slide_position == SLIDE_REZERO_CMD)
          slide_rezero(SLIDE_RL);                       /* 255 = 현재 위치를 0점으로 재설정 */
        else if (m.rl_slide_position == SLIDE_HOME_CMD)
          slide_seek_home(SLIDE_RL);                    /* 254 = 오른쪽 끝(시작점)으로 호밍 */
        else
          slide_set_target_mm(SLIDE_RL, m.rl_slide_position);  /* RL 슬라이드 축(PB5/PB4/PB10) */
      }
      break;
    }

    case MODEL_CAR_NET_REAR_RIGHT_SEAT_CMD_FRAME_ID: { /* 0x121: 좌석 우 */
      struct model_car_net_rear_right_seat_cmd_t m;
      if (model_car_net_rear_right_seat_cmd_unpack(&m, f->data, sizeof(f->data)) == 0) {
        pinch_rr = 0;                                  /* 새 명령 = 끼임 해소 간주, 래치 해제 */
        servo_set_deg(SERVO_RR, m.rr_recline_angle);   /* 리클라인 SG90 서보(우) */
        cmd_cargo_lamp = m.cargo_lamp_status;          /* TODO 램프 GPIO */
        if (m.rr_slide_position == SLIDE_HOLD_CMD)
          { /* 253 = 슬라이드 유지: 이동 명령 없음(서보만 조정) */ }
        else if (m.rr_slide_position == SLIDE_REZERO_CMD)
          slide_rezero(SLIDE_RR);                      /* 255 = 현재 위치를 0점으로 재설정 */
        else if (m.rr_slide_position == SLIDE_HOME_CMD)
          slide_seek_home(SLIDE_RR);                   /* 254 = 오른쪽 끝(시작점)으로 호밍 */
        else
          slide_set_target_mm(SLIDE_RR, m.rr_slide_position);  /* RR 슬라이드 축(PC0/PC1/PC2) */
      }
      break;
    }

    default:
      break;
  }
}

#if PINCH_DEBUG
/* I2C1 버스 스캐너: 0x01~0x7F 주소에 ACK가 오는 장치를 출력(부팅 1회 진단).
 *   - 아무것도 안 나오면 → 전원/풀업/배선(SDA·SCL) 문제 (버스 자체가 죽음)
 *   - 0x40/0x41 아닌 다른 주소가 나오면 → 모듈 주소가 다른 것(A0/A1 핀) */
static void i2c_scan(void)
{
  printf("I2C scan:");
  uint8_t found = 0;
  for (uint8_t a = 1; a < 128; a++) {
    if (HAL_I2C_IsDeviceReady(&hi2c1, (uint16_t)(a << 1), 2, 5) == HAL_OK) {
      printf(" 0x%02X", a);
      found++;
    }
  }
  printf(found ? "\r\n" : " (없음 - 전원/풀업/배선 확인)\r\n");
}
#endif

/* 안티핀치: 두 서보의 전류를 주기적으로 읽어 스톨(끼임)을 감지한다.
 * 임계 전류를 PINCH_DEBOUNCE회 연속 넘으면 끼임 확정 → pinch 래치 ON(상태로 보고)
 * + 서보를 PINCH_BACKOFF_DEG 만큼 후퇴시켜 압력을 해제한다.
 * 미장착 센서(ina_ok=0)는 건너뛴다. 래치는 새 명령 수신 시 해제(RxCallback). */
static void pinch_service(void)
{
  static uint32_t lastTick = 0;
  static uint8_t  cntRL = 0, cntRR = 0;

  uint32_t now = HAL_GetTick();

#if PINCH_DEBUG
  /* 진단: 300ms마다 두 서보 전류·센서인식·핀치상태를 UART로 출력.
   * 막았을 때 mA가 얼마나 뛰는지 보고 PINCH_CURRENT_MA 를 그 아래로 맞춘다. */
  static uint32_t lastDbgTick = 0;
  if (now - lastDbgTick >= 300) {
    lastDbgTick = now;
    int32_t iRL = ina226_read_current_mA(INA226_ADDR_RL);
    int32_t iRR = ina226_read_current_mA(INA226_ADDR_RR);
    printf("INA RL(ok%u) %ldmA | RR(ok%u) %ldmA | pinch[%u %u]\r\n",
           ina_ok_rl, (long)iRL, ina_ok_rr, (long)iRR, pinch_rl, pinch_rr);
  }
#endif

  if (now - lastTick < PINCH_PERIOD_MS) return;       /* 폴링 주기 throttle */
  lastTick = now;

  if (ina_ok_rl) {
    int32_t i = ina226_read_current_mA(INA226_ADDR_RL);
    if (i < 0) i = -i;                                 /* 배선 방향 무관, 절대전류 */
    if (i > PINCH_CURRENT_MA) {
      if (++cntRL >= PINCH_DEBOUNCE) {
        cntRL = 0;
        pinch_rl = 1;
        servo_pinch_relief(SERVO_RL, PINCH_BACKOFF_DEG);   /* 진행 반대로 후퇴+정지 */
      }
    } else {
      cntRL = 0;
    }
  }

  if (ina_ok_rr) {
    int32_t i = ina226_read_current_mA(INA226_ADDR_RR);
    if (i < 0) i = -i;
    if (i > PINCH_CURRENT_MA) {
      if (++cntRR >= PINCH_DEBOUNCE) {
        cntRR = 0;
        pinch_rr = 1;
        servo_pinch_relief(SERVO_RR, PINCH_BACKOFF_DEG);   /* 진행 반대로 후퇴+정지 */
      }
    } else {
      cntRR = 0;
    }
  }
}

/* --------------------------------------------------------------------------
 *  FreeRTOS 태스크 (슈퍼루프 → 태스크 분리)
 * ------------------------------------------------------------------------ */

/* MotionTask(높은 우선순위): CAN 명령 소비 → 슬라이드/서보/안티핀치 서비스.
 * 액추에이터·I2C 상태를 이 태스크가 단독 소유하므로 별도 락 불필요.
 * osDelay(1)로 1ms 주기 — 스텝 타이밍은 slide.c 내부 DWT(µs) 판정 유지. */
void StartMotionTask(void *argument)
{
  (void)argument;
  for (;;) {
    can_frame_t f;
    while (osMessageQueueGet(canRxQ, &f, NULL, 0) == osOK)
      can_dispatch(&f);               /* 수신 명령 적용(디코드) */
    slide_service();                  /* 논블로킹 슬라이드 이동 */
    servo_service();                  /* 논블로킹 서보 램프 */
    pinch_service();                  /* 안티핀치(내부 20ms throttle) */
    /* 이동 중엔 tight-loop로 정밀 스텝(DWT µs) — osDelay(1) 지터가 스텝모터 탈조 유발.
     * 대기 중엔 osDelay로 StatusTask/idle 에 양보(HAL tick=TIM6·DWT는 계속 진행). */
    if (slide_is_moving()) osThreadYield();
    else                   osDelay(1);
  }
}

/* StatusTask(보통 우선순위): 0x220/0x221 상태를 100ms 주기로 송신.
 * 위치/핀치 등은 단일 int 읽기라 atomic — 별도 락 없이 스냅샷 송신. */
void StartStatusTask(void *argument)
{
  (void)argument;
  for (;;) {
    send_status();
    osDelay(STATUS_PERIOD_MS);
  }
}

/* 큐/태스크 생성. osKernelInitialize 이후(스케줄러 시작 전)에 호출되어야 하므로
 * freertos.c 의 MX_FREERTOS_Init 에서 부른다. */
void app_rtos_init(void)
{
  canRxQ = osMessageQueueNew(8, sizeof(can_frame_t), NULL);

  const osThreadAttr_t motion_attr = {
    .name = "Motion", .stack_size = 512 * 4, .priority = osPriorityHigh,
  };
  const osThreadAttr_t status_attr = {
    .name = "Status", .stack_size = 256 * 4, .priority = osPriorityNormal,
  };
  osThreadNew(StartMotionTask, NULL, &motion_attr);
  osThreadNew(StartStatusTask, NULL, &status_attr);
}

/* USER CODE END 4 */

/**
  * @brief  Period elapsed callback in non blocking mode
  * @note   This function is called  when TIM6 interrupt took place, inside
  * HAL_TIM_IRQHandler(). It makes a direct call to HAL_IncTick() to increment
  * a global variable "uwTick" used as application time base.
  * @param  htim : TIM handle
  * @retval None
  */
void HAL_TIM_PeriodElapsedCallback(TIM_HandleTypeDef *htim)
{
  /* USER CODE BEGIN Callback 0 */

  /* USER CODE END Callback 0 */
  if (htim->Instance == TIM6)
  {
    HAL_IncTick();
  }
  /* USER CODE BEGIN Callback 1 */

  /* USER CODE END Callback 1 */
}

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}
#ifdef USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
