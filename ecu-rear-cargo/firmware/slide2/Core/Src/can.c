/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    can.c
  * @brief   This file provides code for the configuration
  *          of the CAN instances.
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
#include "can.h"
#include "stm32f4xx.h"

/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

CAN_HandleTypeDef hcan1;

/* CAN1 init function */
void MX_CAN1_Init(void)
{

  /* USER CODE BEGIN CAN1_Init 0 */

  /* USER CODE END CAN1_Init 0 */

  /* USER CODE BEGIN CAN1_Init 1 */

  /* USER CODE END CAN1_Init 1 */
  /* ── bxCAN 비트 타이밍 → 비트레이트 500 kbit/s ────────────────────────────
   *   CAN1은 APB1 버스에 물려 있고 PCLK1 = 42 MHz (SystemClock_Config 참조).
   *   1 TQ(타임 퀀텀) = Prescaler / PCLK1 = 6 / 42 MHz
   *   1 비트 = SYNC(1) + BS1(11) + BS2(2) = 14 TQ
   *   비트레이트 = 42 MHz / (6 × 14) = 500 kbit/s
   *   샘플 포인트 = (1 + 11) / 14 ≈ 85.7%  (CiA 권장 87.5% 근처, 양호)
   *   ※ 버스의 다른 노드도 반드시 동일한 500 kbit/s 여야 통신된다.
   * ----------------------------------------------------------------------- */
  hcan1.Instance = CAN1;
  hcan1.Init.Prescaler = 6;                       /* TQ 분주값 (위 계산 참조) */
  hcan1.Init.Mode = CAN_MODE_NORMAL;              /* 정상 송수신 모드 (Loopback/Silent 아님) */
  hcan1.Init.SyncJumpWidth = CAN_SJW_1TQ;         /* 재동기화 시 최대 보정폭 1 TQ */
  hcan1.Init.TimeSeg1 = CAN_BS1_11TQ;             /* 비트 세그먼트1 = 11 TQ */
  hcan1.Init.TimeSeg2 = CAN_BS2_2TQ;              /* 비트 세그먼트2 = 2 TQ */
  hcan1.Init.TimeTriggeredMode = DISABLE;         /* 시간 트리거(TTCAN) 미사용 */
  hcan1.Init.AutoBusOff = ENABLE;                 /* Bus-Off 진입 시 자동 복구(128×11비트 후) */
  hcan1.Init.AutoWakeUp = DISABLE;                /* Sleep 자동 해제 미사용 */
  hcan1.Init.AutoRetransmission = DISABLE;        /* 단발 송신(NART): ACK 없어도 재전송 안 함 */
  hcan1.Init.ReceiveFifoLocked = DISABLE;         /* FIFO 가득 차면 최신 메시지로 덮어씀 */
  hcan1.Init.TransmitFifoPriority = DISABLE;      /* 송신 우선순위: 메일박스 번호가 아닌 ID 기준 */
  if (HAL_CAN_Init(&hcan1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN CAN1_Init 2 */

  /* USER CODE END CAN1_Init 2 */

}

/* HAL_CAN_Init() 내부에서 자동 호출되는 저수준 초기화(MSP = MCU Support Package).
 * CAN 페리페럴이 실제로 쓰는 클럭·GPIO·인터럽트(NVIC)를 여기서 켠다. */
void HAL_CAN_MspInit(CAN_HandleTypeDef* canHandle)
{

  GPIO_InitTypeDef GPIO_InitStruct = {0};
  if(canHandle->Instance==CAN1)
  {
  /* USER CODE BEGIN CAN1_MspInit 0 */

  /* USER CODE END CAN1_MspInit 0 */
    /* CAN1 clock enable */
    __HAL_RCC_CAN1_CLK_ENABLE();            /* CAN1 페리페럴 클럭 공급 */

    __HAL_RCC_GPIOB_CLK_ENABLE();           /* CAN 핀이 GPIOB에 있으므로 포트 클럭도 공급 */
    /**CAN1 GPIO Configuration
    PB8     ------> CAN1_RX
    PB9     ------> CAN1_TX
    */
    /* PB8=RX, PB9=TX 를 트랜시버(예: TJA1050)에 연결. AF9 가 CAN1 대체기능. */
    GPIO_InitStruct.Pin = GPIO_PIN_8|GPIO_PIN_9;
    GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;            /* 대체기능 푸시풀 */
    GPIO_InitStruct.Pull = GPIO_NOPULL;               /* 풀업/다운 없음(트랜시버가 레벨 구동) */
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_VERY_HIGH;
    GPIO_InitStruct.Alternate = GPIO_AF9_CAN1;        /* PB8/PB9 → CAN1 기능으로 매핑 */
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    /* CAN1 interrupt Init — 두 IRQ 모두 우선순위 0(최상). 핸들러는 stm32f4xx_it.c 에 있다.
     * 여기서 NVIC를 켜므로 main.c CAN_Config()에서는 알림(Notification)만 활성화하면 된다. */
    HAL_NVIC_SetPriority(CAN1_TX_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(CAN1_TX_IRQn);                 /* 송신 완료 인터럽트 */
    HAL_NVIC_SetPriority(CAN1_RX0_IRQn, 0, 0);
    HAL_NVIC_EnableIRQ(CAN1_RX0_IRQn);                /* RX FIFO0 수신 인터럽트 → RxFifo0MsgPendingCallback */
  /* USER CODE BEGIN CAN1_MspInit 1 */

  /* USER CODE END CAN1_MspInit 1 */
  }
}

void HAL_CAN_MspDeInit(CAN_HandleTypeDef* canHandle)
{

  if(canHandle->Instance==CAN1)
  {
  /* USER CODE BEGIN CAN1_MspDeInit 0 */

  /* USER CODE END CAN1_MspDeInit 0 */
    /* Peripheral clock disable */
    __HAL_RCC_CAN1_CLK_DISABLE();

    /**CAN1 GPIO Configuration
    PB8     ------> CAN1_RX
    PB9     ------> CAN1_TX
    */
    HAL_GPIO_DeInit(GPIOB, GPIO_PIN_8|GPIO_PIN_9);

    /* CAN1 interrupt Deinit */
    HAL_NVIC_DisableIRQ(CAN1_TX_IRQn);
    HAL_NVIC_DisableIRQ(CAN1_RX0_IRQn);
  /* USER CODE BEGIN CAN1_MspDeInit 1 */

  /* USER CODE END CAN1_MspDeInit 1 */
  }
}

/* USER CODE BEGIN 1 */

/* USER CODE END 1 */
