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
#include "model_car_net.h"
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
CAN_HandleTypeDef hcan1;

TIM_HandleTypeDef htim1;
TIM_HandleTypeDef htim2;
TIM_HandleTypeDef htim3;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */
/* CAN 통신용 구조체 변수 */
struct model_car_net_drive_cmd_t rx_drive_cmd;       // 수신된 주행 명령 저장용
struct model_car_net_drive_status_t tx_drive_status; // 송신할 구동 상태 저장용
struct model_car_net_heartbeat_t rx_heartbeat;       // 수신된 하트비트 저장용
struct model_car_net_gear_status_t rx_gear_status;   // 0x070 기어 상태 추가
struct model_car_net_safe_abort_t rx_safe_abort;     // 0x010 세이프 어보트 확장

/* CAN 송수신 하드웨어 핸들러 및 헤더 */
CAN_RxHeaderTypeDef rx_header;
CAN_TxHeaderTypeDef tx_header;
uint8_t rx_data[8];
uint8_t tx_data[8];
uint32_t tx_mailbox;

/* 하드웨어 테스트용 CAN 송신 변수 */
CAN_TxHeaderTypeDef test_tx_header;
uint8_t test_tx_data[8];
uint32_t test_mailbox;

/* 세이프티 및 페일세이프 관련 변수 */
uint32_t supervisor_wd_timer = 0; // 하트비트 무응답 시간 누적용 (ms 단위 카운트)
uint8_t last_alive_counter = 0;   // 이전 하트비트 카운트 값 백업
bool is_emergency_active = false; // 현재 비상 정지 상태 여부 플래그
uint8_t current_gear = 0;         // 0=P, 1=D, 2=R 로컬 백업용

/* 엔코더 측정 및 속도 계산 변수 */
int16_t left_encoder_count = 0;
int16_t right_encoder_count = 0;
double current_rpm = 0.0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_CAN1_Init(void);
static void MX_TIM1_Init(void);
static void MX_TIM2_Init(void);
static void MX_TIM3_Init(void);
/* USER CODE BEGIN PFP */
double calculate_actual_rpm(int16_t left_counts, int16_t right_counts);
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
  MX_USART2_UART_Init();
  MX_CAN1_Init();
  MX_TIM1_Init();
  MX_TIM2_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */
  /* ====================================================================
 * 1. CAN 하드웨어 활성화 및 필터 마스터 세팅 (PCAN-View 통신 개통용)
 * ==================================================================== */


// 모든 CAN ID를 필터링 없이 다 받아들이는 '마스터 오픈 필터' 설정
CAN_FilterTypeDef canFilter;
canFilter.FilterBank = 0;
canFilter.FilterMode = CAN_FILTERMODE_IDMASK;
canFilter.FilterScale = CAN_FILTERSCALE_32BIT;
canFilter.FilterIdHigh = 0x0000;
canFilter.FilterIdLow = 0x0000;
canFilter.FilterMaskIdHigh = 0x0000;
canFilter.FilterMaskIdLow = 0x0000;
canFilter.FilterFIFOAssignment = CAN_RX_FIFO0;
canFilter.FilterActivation = ENABLE;
canFilter.SlaveStartFilterBank = 14;

if (HAL_CAN_ConfigFilter(&hcan1, &canFilter) != HAL_OK) {
	Error_Handler(); // 필터 설정 실패 시 잠금
}

// CAN 외장 하드웨어 선로 전격 개통! (이게 켜져야 PCAN Receive가 뚫립니다)
if (HAL_CAN_Start(&hcan1) != HAL_OK) {
	Error_Handler();
}

// CAN 수신 인터럽트(FIFO0 Pending) 활성화
if (HAL_CAN_ActivateNotification(&hcan1, CAN_IT_RX_FIFO0_MSG_PENDING) != HAL_OK) {
	Error_Handler();
}

// 송신 헤더 설정
//tx_header.StdId = 0x102; // F446용 테스트 ID
//tx_header.RTR = CAN_RTR_DATA;
//tx_header.IDE = CAN_ID_STD;
//tx_header.DLC = 8;
//tx_header.TransmitGlobalTime = DISABLE;

/* ====================================================================
 * 2. 타이머 하드웨어 기동 (좌/우 모터 및 엔코더 작동 시작)
 * ==================================================================== */
// (1) TIM1 PWM 출력 채널 가동 (모터 속도 제어선 활성화)
HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1); // PA8 (PWMA)
HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2); // PA9 (PWMB)

// (2) TIM2, TIM3 엔코더 카운터 하드웨어 감시 기동
HAL_TIM_Encoder_Start(&htim2, TIM_CHANNEL_ALL); // 왼쪽 바퀴 엔코더 감시 시작
HAL_TIM_Encoder_Start(&htim3, TIM_CHANNEL_ALL); // 오른쪽 바퀴 엔코더 감시 시작
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
//	  // 1. 테스트용 CAN 메시지 헤더 설정 (Drive_Status ID: 0x200)
//	      test_tx_header.StdId = 0x200;           // 16진수 ID 200h로 송신
//	      test_tx_header.RTR = CAN_RTR_DATA;      // 데이터 프레임
//	      test_tx_header.IDE = CAN_ID_STD;        // 표준 ID (11비트)
//	      test_tx_header.DLC = 8;                 // 8바이트 데이터 꽉 채움
//	      test_tx_header.TransmitGlobalTime = DISABLE;
//
//	      // 2. 더미 데이터 채우기 (확인하기 쉽게 0xAA, 0xBB 등으로 채웁니다)
//	      test_tx_data[0] = 0xAA;
//	      test_tx_data[1] = 0xBB;
//	      test_tx_data[2] = 0xCC;
//	      test_tx_data[3] = 0xDD;
//	      test_tx_data[4] = 0x11;
//	      test_tx_data[5] = 0x22;
//	      test_tx_data[6] = 0x33;
//	      test_tx_data[7] = 0x44;
//
//	      // 3. CAN 버스에 강제로 메시지 쏘기!
//	      // 하드웨어 사정상 사서함(Mailbox)이 비어있을 때만 신호를 밀어 넣습니다.
//	      if (HAL_CAN_GetTxMailboxesFreeLevel(&hcan1) > 0) {
//	          HAL_CAN_AddTxMessage(&hcan1, &test_tx_header, test_tx_data, &test_mailbox);
//	      }
//
//	      // 4. 1초(1000ms) 동안 대기하며 무한 반복
//	      HAL_Delay(1000);
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
  __HAL_PWR_VOLTAGESCALING_CONFIG(PWR_REGULATOR_VOLTAGE_SCALE1);

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLM = 4;
  RCC_OscInitStruct.PLL.PLLN = 180;
  RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
  RCC_OscInitStruct.PLL.PLLQ = 2;
  RCC_OscInitStruct.PLL.PLLR = 2;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Activate the Over-Drive mode
  */
  if (HAL_PWREx_EnableOverDrive() != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV4;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV2;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_5) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief CAN1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_CAN1_Init(void)
{

  /* USER CODE BEGIN CAN1_Init 0 */

  /* USER CODE END CAN1_Init 0 */

  /* USER CODE BEGIN CAN1_Init 1 */

  /* USER CODE END CAN1_Init 1 */
  hcan1.Instance = CAN1;
  hcan1.Init.Prescaler = 9;
  hcan1.Init.Mode = CAN_MODE_NORMAL;
  hcan1.Init.SyncJumpWidth = CAN_SJW_1TQ;
  hcan1.Init.TimeSeg1 = CAN_BS1_7TQ;
  hcan1.Init.TimeSeg2 = CAN_BS2_2TQ;
  hcan1.Init.TimeTriggeredMode = DISABLE;
  hcan1.Init.AutoBusOff = ENABLE;
  hcan1.Init.AutoWakeUp = ENABLE;
  hcan1.Init.AutoRetransmission = DISABLE;
  hcan1.Init.ReceiveFifoLocked = DISABLE;
  hcan1.Init.TransmitFifoPriority = DISABLE;
  if (HAL_CAN_Init(&hcan1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN1_Init 2 */

  /* USER CODE END CAN1_Init 2 */

}

/**
  * @brief TIM1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM1_Init(void)
{

  /* USER CODE BEGIN TIM1_Init 0 */

  /* USER CODE END TIM1_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};
  TIM_OC_InitTypeDef sConfigOC = {0};
  TIM_BreakDeadTimeConfigTypeDef sBreakDeadTimeConfig = {0};

  /* USER CODE BEGIN TIM1_Init 1 */

  /* USER CODE END TIM1_Init 1 */
  htim1.Instance = TIM1;
  htim1.Init.Prescaler = 8;
  htim1.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim1.Init.Period = 999;
  htim1.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim1.Init.RepetitionCounter = 0;
  htim1.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim1) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim1, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_Init(&htim1) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim1, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sConfigOC.OCMode = TIM_OCMODE_PWM1;
  sConfigOC.Pulse = 0;
  sConfigOC.OCPolarity = TIM_OCPOLARITY_HIGH;
  sConfigOC.OCNPolarity = TIM_OCNPOLARITY_HIGH;
  sConfigOC.OCFastMode = TIM_OCFAST_DISABLE;
  sConfigOC.OCIdleState = TIM_OCIDLESTATE_RESET;
  sConfigOC.OCNIdleState = TIM_OCNIDLESTATE_RESET;
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_1) != HAL_OK)
  {
    Error_Handler();
  }
  if (HAL_TIM_PWM_ConfigChannel(&htim1, &sConfigOC, TIM_CHANNEL_2) != HAL_OK)
  {
    Error_Handler();
  }
  sBreakDeadTimeConfig.OffStateRunMode = TIM_OSSR_DISABLE;
  sBreakDeadTimeConfig.OffStateIDLEMode = TIM_OSSI_DISABLE;
  sBreakDeadTimeConfig.LockLevel = TIM_LOCKLEVEL_OFF;
  sBreakDeadTimeConfig.DeadTime = 0;
  sBreakDeadTimeConfig.BreakState = TIM_BREAK_DISABLE;
  sBreakDeadTimeConfig.BreakPolarity = TIM_BREAKPOLARITY_HIGH;
  sBreakDeadTimeConfig.AutomaticOutput = TIM_AUTOMATICOUTPUT_DISABLE;
  if (HAL_TIMEx_ConfigBreakDeadTime(&htim1, &sBreakDeadTimeConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM1_Init 2 */

  /* USER CODE END TIM1_Init 2 */
  HAL_TIM_MspPostInit(&htim1);

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

  TIM_Encoder_InitTypeDef sConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM2_Init 1 */

  /* USER CODE END TIM2_Init 1 */
  htim2.Instance = TIM2;
  htim2.Init.Prescaler = 0;
  htim2.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim2.Init.Period = 65535;
  htim2.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim2.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  sConfig.EncoderMode = TIM_ENCODERMODE_TI1;
  sConfig.IC1Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC1Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC1Filter = 0;
  sConfig.IC2Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC2Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC2Filter = 0;
  if (HAL_TIM_Encoder_Init(&htim2, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim2, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM2_Init 2 */

  /* USER CODE END TIM2_Init 2 */

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_Encoder_InitTypeDef sConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 0;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 65535;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  sConfig.EncoderMode = TIM_ENCODERMODE_TI1;
  sConfig.IC1Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC1Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC1Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC1Filter = 0;
  sConfig.IC2Polarity = TIM_ICPOLARITY_RISING;
  sConfig.IC2Selection = TIM_ICSELECTION_DIRECTTI;
  sConfig.IC2Prescaler = TIM_ICPSC_DIV1;
  sConfig.IC2Filter = 0;
  if (HAL_TIM_Encoder_Init(&htim3, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_RESET;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

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
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOH_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, LD2_Pin|GPIO_PIN_10, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_2|GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : LD2_Pin PA10 */
  GPIO_InitStruct.Pin = LD2_Pin|GPIO_PIN_10;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PB2 PB10 PB4 PB5 */
  GPIO_InitStruct.Pin = GPIO_PIN_2|GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /* USER CODE BEGIN MX_GPIO_Init_2 */

  /* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */
double calculate_actual_rpm(int16_t left_counts, int16_t right_counts)
{
    // 두 바퀴의 평균 펄스 변화량
    double avg_counts = (double)(left_counts + right_counts) / 2.0;

    /* [RPM 계산 가이드라인]
     * JBG37-520 모터의 감속비가 예를 들어 1:30이고 홀센서가 한 바퀴에 11펄스를 뿜는다면,
     * 4체배 시 바퀴 1회전당 총 펄스(PPR) = 11 * 4 * 30 = 1320 펄스입니다.
     * 10ms(0.01초) 주기로 셈하므로: RPM = (avg_counts / 1320) * (60초 / 0.01초)
     */
    double ppr = 1320.0; // 팀의 모터 상세 스펙에 맞춰 수정 가능
    double actual_rpm = (avg_counts / ppr) * 6000.0;

    return actual_rpm;
}

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *hcan)
{
	// can 메시지 잡기
	if (HAL_CAN_GetRxMessage(hcan, CAN_RX_FIFO0, &rx_header, rx_data) != HAL_OK){
		return;
	}
	// can 신호 들어오면 무조건 ld2 on
	HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);

	/* ====================================================================
	 * 1. 최우선순위 안전 대역: 비상 정지 (0x010 SafeAbort) ─ 확장 반영
	 * ==================================================================== */
	if (rx_header.StdId == MODEL_CAR_NET_SAFE_ABORT_FRAME_ID) {
		model_car_net_safe_abort_unpack(&rx_safe_abort, rx_data, rx_header.DLC);

		if (rx_safe_abort.stop_flag == 1) {
			is_emergency_active = true;

			// 전원 차단 및 Short Brake용 방향 핀 HIGH 락 발동
			HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);   // IN1 = HIGH
			HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4, GPIO_PIN_SET);   // IN2 = HIGH
			HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_SET);  // IN3 = HIGH
			HAL_GPIO_WritePin(GPIOA, GPIO_PIN_10, GPIO_PIN_SET);  // IN4 = HIGH

			__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0); // 왼쪽 모터 정지 (PWMA)
			__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0); // 오른쪽 모터 정지 (PWMB)
		}
		return;
	}

	/* ====================================================================
	 * 2. 안전 대역: 제어기 생존 신호 (0x050 Heartbeat)
	 * ==================================================================== */
	if (rx_header.StdId == MODEL_CAR_NET_HEARTBEAT_FRAME_ID) {
		model_car_net_heartbeat_unpack(&rx_heartbeat, rx_data, rx_header.DLC);

		if (rx_heartbeat.alive_counter != last_alive_counter) {
			supervisor_wd_timer = 0; // 와치독 카운터 리셋
			last_alive_counter = rx_heartbeat.alive_counter;
		}
		return;
	}

	/* ====================================================================
	 * 3. 안전 대역: 신규 기어 상태 수신 (0x070 GearStatus)
	 * ==================================================================== */
	if (rx_header.StdId == MODEL_CAR_NET_GEAR_STATUS_FRAME_ID) {
		model_car_net_gear_status_unpack(&rx_gear_status, rx_data, rx_header.DLC);
		current_gear = rx_gear_status.gear; // 0=P, 1=D, 2=R 전역 동기화
		return;
	}

	/* ====================================================================
	 * 4. 명령 대역: 일반 주행 명령 신호 (0x100 Drive_Cmd) ─ 판정 버그 수정 완료
	 * ==================================================================== */
	if (rx_header.StdId == MODEL_CAR_NET_DRIVE_CMD_FRAME_ID && !is_emergency_active) {
		model_car_net_drive_cmd_unpack(&rx_drive_cmd, rx_data, rx_header.DLC);

		// 물리 범위 검증
		if (model_car_net_drive_cmd_target_velocity_is_in_range(rx_drive_cmd.target_velocity)) {

			// 분리된 독립 0x070 기어 상태 변수(current_gear)를 인터록으로 사용합니다.
			if (current_gear == 1) { // 1 = Drive(D)

				// (1) 브레이크 깊이 반영 베이스 속도 연산
				double brake_factor = (100.0 - (double)rx_drive_cmd.brake_depth) / 100.0;
				double v_base = (double)rx_drive_cmd.target_velocity * brake_factor;

				// (2) 차동 조향(좌우 속도차) 연산
				double K = 0.5;
				double v_steer = (double)rx_drive_cmd.steering_angle * K;

				// (3) 좌/우 바퀴 최종 목표 RPM 산출 (왼쪽 음수/오른쪽 양수 부호 법칙)
				double target_left_rpm  = v_base + v_steer;
				double target_right_rpm = v_base - v_steer;

				// (4) 브레이크 100% 만땅 예외 처리
				if (rx_drive_cmd.brake_depth >= 100) {
					target_left_rpm = 0;
					target_right_rpm = 0;
				}

				// 음수 방지 가드 레일
				if (target_left_rpm < 0)  target_left_rpm = 0;
				if (target_right_rpm < 0) target_right_rpm = 0;

				// (5) 물리 RPM 값을 20kHz TIM1 PWM 레지스터 해상도(0~999)로 스케일 매핑
				uint32_t left_duty  = ((uint32_t)target_left_rpm * 999) / 3000;
				uint32_t right_duty = ((uint32_t)target_right_rpm * 999) / 3000;

				if (left_duty > 999)  left_duty = 999;
				if (right_duty > 999) right_duty = 999;

				// 모터 드라이버 L298N에 전진 방향 인가 (IN1=1, IN2=0 / IN3=1, IN4=0)
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);   // IN1 = HIGH
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4, GPIO_PIN_RESET); // IN2 = LOW
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_SET);  // IN3 = HIGH
				HAL_GPIO_WritePin(GPIOA, GPIO_PIN_10, GPIO_PIN_RESET); // IN4 = LOW

				// 최종 레지스터 하드웨어 투하
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, left_duty);  // PWMA
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, right_duty); // PWMB

			} else {
				// D기어가 아니거나 주차(P) 모드일 경우 모터 정지 및 축 잠금
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_5, GPIO_PIN_SET);
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_4, GPIO_PIN_SET);
				HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10, GPIO_PIN_SET);
				HAL_GPIO_WritePin(GPIOA, GPIO_PIN_10, GPIO_PIN_SET);

				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
			}
		}
	}
}
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
