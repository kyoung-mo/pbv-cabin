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

/* CAN 송수신 하드웨어 핸들러 및 헤더 */
CAN_RxHeaderTypeDef rx_header;
CAN_TxHeaderTypeDef tx_header;
uint8_t rx_data[8];
uint8_t tx_data[8];
uint32_t tx_mailbox;

/* 세이프티 및 페일세이프 관련 변수 */
uint32_t supervisor_wd_timer = 0; // 하트비트 무응답 시간 누적용 (ms 단위 카운트)
uint8_t last_alive_counter = 0;   // 이전 하트비트 카운트 값 백업
bool is_emergency_active = false; // 현재 비상 정지 상태 여부 플래그

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

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */
	  tx_drive_status.drive_motor_current = 0; // 실제로는 안쓰지만 dbc 구조 유지용
	  /* 1. 절충안 세이프티: 하트비트(사령탑) 두절 감시 (300ms 초과 시) */
	  if (supervisor_wd_timer >= 300) {
		  is_emergency_active = true;
		  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0); // 좌측 모터 차단
		  __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0); // 우측 모터 차단
		  // 필요 시 비상 정지 상태임을 알리는 로그를 출력하거나 디버그 LED 점등
	  }

	  /* 2. 실제 바퀴 RPM 측정 (엔코더 타이머 값 파싱) */
	  // 4체배 모드이므로 한 주기 동안 변화한 펄스 카운트를 받아 RPM 계산 공식 대입
	  left_encoder_count = (int16_t)__HAL_TIM_GET_COUNTER(&htim2);
	  right_encoder_count = (int16_t)__HAL_TIM_GET_COUNTER(&htim3);

	  // 카운터 레지스터 클리어 (다음 주기의 변화량을 알기 위함)
	  __HAL_TIM_SET_COUNTER(&htim2, 0);
	  __HAL_TIM_SET_COUNTER(&htim3, 0);

	  // 두 전륜 바퀴의 평균 회전 속도 계산 (예시 물리식)
	  current_rpm = calculate_actual_rpm(left_encoder_count, right_encoder_count);

	  /* 3. 사령탑(D3-G)으로 데이터 주기 보고 (Drive_Status 0x200 브로드캐스트) */
	  tx_drive_status.current_velocity = model_car_net_drive_status_current_velocity_encode(current_rpm);
	  //tx_drive_status.drive_motor_current = get_motor_current_ma(); // INA226 센서 값 매핑
	  tx_drive_status.current_gear_status = rx_drive_cmd.gear_status; // 기어 상태 에코백 피드백

	  // 라이브러리를 사용해 8바이트 데이터 필드 일렬 패킹 수행
	  model_car_net_drive_status_pack(tx_data, &tx_drive_status, MODEL_CAR_NET_DRIVE_STATUS_LENGTH);

	  // CAN 캔 버스 고속도로로 전송 메시지 쏘기
	  tx_header.StdId = MODEL_CAR_NET_DRIVE_STATUS_FRAME_ID;
	  tx_header.RTR = CAN_RTR_DATA;
	  tx_header.IDE = CAN_ID_STD;
	  tx_header.DLC = MODEL_CAR_NET_DRIVE_STATUS_LENGTH;
	  tx_header.TransmitGlobalTime = DISABLE;

	  HAL_CAN_AddTxMessage(&hcan1, &tx_header, tx_data, &tx_mailbox);

	  /* 4. 루프 주기 동기화 및 타임아웃 누적 (10ms 주기 가정) */
	  HAL_Delay(10);
	  if (!is_emergency_active) {
		  supervisor_wd_timer += 10; // 10ms씩 타이머 누적
	  }
    /* USER CODE BEGIN 3 */

  /* USER CODE END 3 */
  }
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
  HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : LD2_Pin */
  GPIO_InitStruct.Pin = LD2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);

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

	// 1. 최우선순위: 비상 정지 (0x010)
	if(rx_header.StdId == MODEL_CAR_NET_HMI_EMERGENCY_FRAME_ID){
		model_car_net_hmi_emergency_unpack(NULL, rx_data, rx_header.DLC);

		// 비상 정지 플래그 활성화 및 하드웨어 즉각 차단
		is_emergency_active = true;
		__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0); // 왼쪽 모터 정지
		__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0); // 오른쪽 모터 정지
		return;
	}

	// 2. 제어기 생존 신호 (0x050) 감지
	if (rx_header.StdId == MODEL_CAR_NET_HEARTBEAT_FRAME_ID){
		model_car_net_heartbeat_unpack(&rx_heartbeat, rx_data, rx_header.DLC);

		// Alive_Counter 값이 정상적으로 변하고 있다면 중앙 제어기가 살아있다고 판단
		if(rx_heartbeat.alive_counter != last_alive_counter){
			supervisor_wd_timer = 0;
			last_alive_counter = rx_heartbeat.alive_counter;
		}
		return;
	}

	// 3. 일반 주행 명령 신호 (0x100) 수신 처리
	if (rx_header.StdId == MODEL_CAR_NET_HEARTBEAT_FRAME_ID){
		model_car_net_drive_cmd_unpack(&rx_drive_cmd, rx_data, rx_header.DLC);
		// 물리 주소 범위 검증 후 하드웨어 적용 (예외 처리)
		if (model_car_net_drive_cmd_target_velocity_is_in_range(rx_drive_cmd.target_velocity)) {
			/* * [모터 속도 제어 로직 기술 부하 부분]
			 * 물리 RPM 수치를 PWM 듀티비(0~999)로 환산하는 알고리즘을 거쳐 적용합니다.
			 * 기어 상태(rx_drive_cmd.gear_status)가 Drive(1)일 때만 모터를 구동하는 인터록 적용.
			 */
			if (rx_drive_cmd.gear_status == 1) { // Drive 모드
				// 간단 매핑 예시 (실제 제어 시 PID 제어 알고리즘이나 변환식 적용 필요)
				uint32_t duty_cycle = (rx_drive_cmd.target_velocity * 999) / 3000;
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, duty_cycle);
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, duty_cycle);
			} else {
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, 0);
				__HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, 0);
			}
		}
		/* [조향 제어 로직 기술 부하 부분]
		 * rx_drive_cmd.steering_angle (-135 ~ 135도) 값을
		 * 조향 서보모터용 PWM 타이머 비교 레지스터 값으로 매핑하여 서보 축을 꺾어줍니다.
		 */
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
