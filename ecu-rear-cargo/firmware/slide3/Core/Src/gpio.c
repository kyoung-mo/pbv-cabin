/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    gpio.c
  * @brief   This file provides code for the configuration
  *          of all used GPIO pins.
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
#include "gpio.h"

/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/*----------------------------------------------------------------------------*/
/* Configure GPIO                                                             */
/*----------------------------------------------------------------------------*/
/* USER CODE BEGIN 1 */

/* USER CODE END 1 */

/** Configure pins as
        * Analog
        * Input
        * Output
        * EVENT_OUT
        * EXTI
*/
/* 슬라이드 스텝모터 드라이버 입력(IN1~IN4)을 출력 GPIO로 설정한다.
 * 핀 ↔ 의미 매핑(slide.c 와 동일):
 *   PB5  = IN1 (D4)   PB4  = IN2 (D5)
 *   PB10 = IN3 (D6)   PA8  = IN4 (D7)
 * 실제 코일 구동 시퀀스는 slide.c 의 set_coils()/PHASE[][] 가 담당. */
void MX_GPIO_Init(void)
{

  GPIO_InitTypeDef GPIO_InitStruct = {0};

  /* GPIO Ports Clock Enable — 사용하는 포트의 클럭을 켜야 레지스터 접근 가능 */
  __HAL_RCC_GPIOH_CLK_ENABLE();   /* HSE/OSC 핀 등 시스템용(직접 사용 안 함) */
  __HAL_RCC_GPIOA_CLK_ENABLE();   /* PA8(예비), PA2/3(USART2), PA0/1(서보) */
  __HAL_RCC_GPIOB_CLK_ENABLE();   /* PB4/5/10(RL TMC2208 DIR/STEP/EN), PB6/7(I2C), PB8/9(CAN) */
  __HAL_RCC_GPIOC_CLK_ENABLE();   /* PC0/1/2(RR TMC2208 STEP/DIR/EN — 신규 2축) */

  /* 초기 출력 레벨 = LOW: 부팅 직후 STEP=LOW. EN은 slide_init()이 곧 HIGH(비활성)로 정리한다. */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_8, GPIO_PIN_RESET);

  /* RR 2축 TMC2208 핀 초기 LOW (PC0=STEP2 / PC1=DIR2 / PC2=EN2) */
  HAL_GPIO_WritePin(GPIOC, GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2, GPIO_PIN_RESET);

  /*Configure GPIO pins : PB10 PB4 PB5 — RL TMC2208 EN/DIR/STEP */
  GPIO_InitStruct.Pin = GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;     /* 푸시풀 출력 */
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;    /* 스텝 토글은 수 ms 주기 → 저속이면 충분 */
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PA8 — 예비(구 IN4) */
  GPIO_InitStruct.Pin = GPIO_PIN_8;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

  /*Configure GPIO pins : PC0 PC1 PC2 — RR TMC2208 STEP2/DIR2/EN2 (신규 2축) */
  GPIO_InitStruct.Pin = GPIO_PIN_0|GPIO_PIN_1|GPIO_PIN_2;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

}

/* USER CODE BEGIN 2 */

/* USER CODE END 2 */
