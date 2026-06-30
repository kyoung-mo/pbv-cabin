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

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "can.h"
#include "servo.h"
#include "step.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
CAN_HandleTypeDef hcan;

TIM_HandleTypeDef htim2;

/* USER CODE BEGIN PV */
/* 메인 제어기에 다시 보고할 현재 좌석 상태값. */
static uint8_t curr_driver_recline = 90U;
static uint8_t curr_passenger_recline = 90U;
static uint8_t curr_driver_rotation = 0U;
static uint8_t curr_passenger_rotation = 0U;
static uint8_t current_gear = 0;
static uint8_t safe_abort_latched;
static uint32_t last_status_tick;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_CAN_Init(void);
static void MX_TIM2_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */
/* 서보모터 단독 테스트 모드.
 * 1로 두면 CAN/스텝 제어를 잠시 멈추고 PA0, PA1 서보 PWM만 반복 테스트한다.
 * 테스트가 끝나면 0으로 바꿔서 원래 CAN 좌석 제어 모드로 돌리면 된다.
 */
#define SERVO_PWM_SELF_TEST  0U

/* CAN 서보 단독 테스트 모드.
 * 1로 두면 CAN 좌석 명령에서 리클라인 각도만 사용하고 서보만 움직인다.
 * 스텝모터 회전 각도 byte는 무시하며 Step_SetTarget()도 호출하지 않는다.
 *
 * - 0x110 Driver_Seat_Cmd    byte0 = 운전석 서보 각도
 * - 0x111 Passenger_Seat_Cmd byte0 = 조수석 서보 각도
 *
 * 서보 CAN 테스트가 끝나고 실제 전체 좌석 동작으로 넘어갈 때는 0으로 바꾸면 된다.
 */
#define CAN_SERVO_ONLY_TEST_MODE  0U

/* 기구 튜닝값.
 * 28BYJ-48은 홈 센서가 없으므로 전원 켤 때 위치를 회전각 0도로 가정한다.
 * 180도 명령 시 스텝 수가 부족하거나 많으면 *_ROTATION_180_STEPS 값을 조정한다.
 * 조수석 회전 방향이 반대로 나오면 PASSENGER_ROTATION_180_STEPS의 부호만 바꾸면 된다.
 */
#define DRIVER_ROTATION_180_STEPS       2048L
#define PASSENGER_ROTATION_180_STEPS   (-2048L)

#if SERVO_PWM_SELF_TEST
static void Servo_PwmSelfTestProcess(void)
{
    /* TIM2 설정이 Prescaler=71, Period=19999라서 1카운트 = 1us이다.
     * SG90 확인용으로 500us, 1500us, 2500us 펄스를 직접 넣는다.
     * PA0 = TIM2_CH1, PA1 = TIM2_CH2.
     */
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 500);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, 500);
    HAL_Delay(1000);

    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 1500);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, 1500);
    HAL_Delay(1000);

    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 2500);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, 2500);
    HAL_Delay(1000);

    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, 1500);
    __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, 1500);
    HAL_Delay(1000);
}
#endif

/* 논리 좌석 번호를 실제 스텝모터 번호로 변환한다. */
static uint8_t seat_to_motor(SeatId_t seat)
{
    return (seat == SEAT_DRIVER) ? 1U : 2U;
}

/* 논리 좌석 번호를 실제 서보 채널 번호로 변환한다. */
static uint8_t seat_to_servo(SeatId_t seat)
{
    return (seat == SEAT_DRIVER) ? 1U : 2U;
}

/* 선택한 좌석의 현재 리클라인 값 주소를 돌려준다. */
static uint8_t *seat_recline_ptr(SeatId_t seat)
{
    return (seat == SEAT_DRIVER) ? &curr_driver_recline : &curr_passenger_recline;
}

/* 선택한 좌석의 현재 회전 각도 값 주소를 돌려준다. */
static uint8_t *seat_rotation_ptr(SeatId_t seat)
{
    return (seat == SEAT_DRIVER) ? &curr_driver_rotation : &curr_passenger_rotation;
}

/* 회전각 0~180도를 스텝모터 절대 목표 위치로 변환한다. */
static int32_t rotation_angle_to_steps(SeatId_t seat, uint8_t rotation_angle)
{
    int32_t steps_180 = (seat == SEAT_DRIVER) ? DRIVER_ROTATION_180_STEPS : PASSENGER_ROTATION_180_STEPS;

    if (rotation_angle > 180U)
    {
        rotation_angle = 180U;
    }

    return (steps_180 * (int32_t)rotation_angle) / 180L;
}

static void FrontSeat_ApplyCommand(const SeatCommand_t *cmd)
{
    uint8_t recline = cmd->recline_angle;
    uint8_t rotation = cmd->rotation_angle;
    uint8_t *curr_recline = seat_recline_ptr(cmd->seat);
    uint8_t *curr_rotation = seat_rotation_ptr(cmd->seat);

    if (recline > 180U)
    {
        recline = 180U;
    }

    if (rotation > 180U)
    {
        rotation = 180U;
    }

#if CAN_SERVO_ONLY_TEST_MODE
    /* 서보 단독 테스트 모드:
     * CAN 명령을 받을 때마다 리클라인 각도를 바로 서보에 넣는다.
     * 스텝모터는 건드리지 않으므로 서보 문제만 따로 볼 수 있다.
     */
    Servo_SetAngle(seat_to_servo(cmd->seat), recline);
    *curr_recline = recline;

    /* rotation 값은 일부러 무시한다.
     * 사용하지 않는 지역 변수 경고를 막기 위해 현재값으로 유지만 한다.
     */
    (void)rotation;
    (void)curr_rotation;
#else
    /* 실제 제어 모드:
     * CAN 명령을 받으면 서보 리클라인과 스텝 회전을 모두 목표값으로 갱신한다.
     */
    Servo_SetAngle(seat_to_servo(cmd->seat), recline);
    *curr_recline = recline;

    Step_SetTarget(seat_to_motor(cmd->seat), rotation_angle_to_steps(cmd->seat, rotation));
    *curr_rotation = rotation;
#endif
}

static void FrontSeat_StopAll(void)
{
    /* 스텝모터를 멈추고 PB2를 로컬 SafeAbort/Stop 표시용으로 켠다. */
    Step_StopAll();
    HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2, GPIO_PIN_SET);
}

static uint8_t FrontSeat_ReadPinchDetected(SeatId_t seat)
{
    /* 끼임감지 센서 자리.
     * 아직 실제 센서가 연결되지 않았으므로 현재는 항상 0, 즉 끼임 없음으로 보낸다.
     * 나중에 센서를 GPIO에 연결하면 여기에서 HAL_GPIO_ReadPin()으로 읽어서
     * 운전석/조수석별 값을 return하면 된다.
     */
    (void)seat;
    return 0U;
}

static void FrontSeat_SendStatusNow(void)
{
    CAN_AppSendSeatStatus(SEAT_DRIVER,
                          curr_driver_recline,
                          curr_driver_rotation,
                          FrontSeat_ReadPinchDetected(SEAT_DRIVER));
    CAN_AppSendSeatStatus(SEAT_PASSENGER,
                          curr_passenger_recline,
                          curr_passenger_rotation,
                          FrontSeat_ReadPinchDetected(SEAT_PASSENGER));
}

static void FrontSeat_SendStatusIfDue(void)
{
    uint32_t now = HAL_GetTick();

    /* 운전석/조수석 상태를 5초마다 송신한다. */
    if ((now - last_status_tick) < 5000U)
    {
        return;
    }
    last_status_tick = now;

    FrontSeat_SendStatusNow();
}

static void FrontSeat_ProcessCanEvents(void)
{
    SeatCommand_t cmd;
    GearStatus_t gear_status;
    SafeAbort_t safe_abort;

    /* SafeAbort가 최우선이다. Stop_Flag가 1이면 MCU 리셋 전까지 정지 상태를 유지한다. */
    if (CAN_AppPopSafeAbort(&safe_abort))
    {
        if (safe_abort.stop_flag != 0U)
        {
            safe_abort_latched = 1U;
            FrontSeat_StopAll();
            FrontSeat_SendStatusNow();
        }
    }

    if (CAN_AppPopGearStatus(&gear_status))
    {
        /* GearStatus는 2비트 신호다. 현재 약속은 0=P, 1=D, 2=R. */
        current_gear = gear_status.gear;
    }

    while (CAN_AppPopSeatCommand(&cmd))
    {
        /* 체크섬이 틀린 좌석 명령은 무시한다. */
        if (cmd.checksum_ok == 0U)
        {
            continue;
        }

        /* SafeAbort 이후에는 모든 좌석 이동 명령을 무시한다. */
        if (safe_abort_latched != 0U)
        {
            continue;
        }

        /* 좌석 재배치, 즉 리클라인/회전 명령은 P 기어에서만 허용한다. */
        if (current_gear == 0)
        {
            FrontSeat_ApplyCommand(&cmd);
            FrontSeat_SendStatusNow();
        }
    }
}
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
  MX_CAN_Init();
  MX_TIM2_Init();
  /* USER CODE BEGIN 2 */
  /* CubeMX가 생성한 주변장치 초기화가 끝난 뒤 각 기능 블록을 시작한다. */
  Servo_Init();
  Step_Init();
  CAN_AppStart();

  /* 전원 켜진 직후 기본값: 운전석/조수석 모두 정위치. */
  Servo_SetAngle(1, curr_driver_recline);
  Servo_SetAngle(2, curr_passenger_recline);
  Step_SetTarget(1, 0);
  Step_SetTarget(2, 0);
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
#if SERVO_PWM_SELF_TEST
    Servo_PwmSelfTestProcess();
    continue;
#endif

    /* CAN 수신 이벤트는 인터럽트 안이 아니라 main loop에서 처리한다. */
    FrontSeat_ProcessCanEvents();

    /* 스텝모터 제어는 논블로킹 방식이다. SafeAbort 상태면 이동하지 않는다. */
    if (safe_abort_latched == 0U)
    {
      Step_Process();
    }

    /* 메인 제어기로 보내는 주기 상태 보고. */
    FrontSeat_SendStatusIfDue();
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

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
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

/**
  * @brief CAN Initialization Function
  * @param None
  * @retval None
  */
static void MX_CAN_Init(void)
{

  /* USER CODE BEGIN CAN_Init 0 */

  /* USER CODE END CAN_Init 0 */

  /* USER CODE BEGIN CAN_Init 1 */

  /* USER CODE END CAN_Init 1 */
  hcan.Instance = CAN1;
  hcan.Init.Prescaler = 4;
  hcan.Init.Mode = CAN_MODE_NORMAL;
  hcan.Init.SyncJumpWidth = CAN_SJW_1TQ;
  hcan.Init.TimeSeg1 = CAN_BS1_14TQ;
  hcan.Init.TimeSeg2 = CAN_BS2_3TQ;
  hcan.Init.TimeTriggeredMode = DISABLE;
  hcan.Init.AutoBusOff = ENABLE;
  hcan.Init.AutoWakeUp = DISABLE;
  hcan.Init.AutoRetransmission = ENABLE;
  hcan.Init.ReceiveFifoLocked = DISABLE;
  hcan.Init.TransmitFifoPriority = DISABLE;
  if (HAL_CAN_Init(&hcan) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN_Init 2 */

  /* USER CODE END CAN_Init 2 */

}

/**
  * @brief TIM2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM2_Init(void)
{

  /* USER CODE BEGIN TIM2_Init 0 */

  /* USER CODE END TIM2_Init 0 */

  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 71;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 19999;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_PWM_Init(&htim2) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim2, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */
  HAL_TIM_MspPostInit(&htim2);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
  /* USER CODE BEGIN MX_GPIO_Init_1 */

  /* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_3|GPIO_PIN_4|GPIO_PIN_5|GPIO_PIN_6, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2|GPIO_PIN_12|GPIO_PIN_13|GPIO_PIN_14
                          |GPIO_PIN_15, GPIO_PIN_RESET);

  /*Configure GPIO pins : PA3 PA4 PA5 PA6 */
  GPIO_InitStruct.Pin = GPIO_PIN_3|GPIO_PIN_4|GPIO_PIN_5|GPIO_PIN_6;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PB2 PB12 PB13 PB14
                           PB15 */
  GPIO_InitStruct.Pin = GPIO_PIN_2|GPIO_PIN_12|GPIO_PIN_13|GPIO_PIN_14
                          |GPIO_PIN_15;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

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
  * @brief  Reports the name of the source file name and line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
