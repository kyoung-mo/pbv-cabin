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
  __HAL_RCC_GPIOA_CLK_ENABLE();   /* PA8(IN4), PA2/3(USART2) */
  __HAL_RCC_GPIOB_CLK_ENABLE();   /* PB4/5/10(IN1/2/3), PB8/9(CAN) */

  /* 초기 출력 레벨 = LOW: 부팅 직후 코일 전부 OFF(무여자). slide_init()도 동일하게 정리한다. */
  HAL_GPIO_WritePin(GPIOB, GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOA, GPIO_PIN_8, GPIO_PIN_RESET);

  /*Configure GPIO pins : PB10 PB4 PB5 — 스텝모터 IN3/IN2/IN1 */
  GPIO_InitStruct.Pin = GPIO_PIN_10|GPIO_PIN_4|GPIO_PIN_5;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;     /* 푸시풀 출력 */
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;    /* 스텝 토글은 수 ms 주기 → 저속이면 충분 */
  HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

  /*Configure GPIO pin : PA8 — 스텝모터 IN4 */
  GPIO_InitStruct.Pin = GPIO_PIN_8;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

}

/* USER CODE BEGIN 2 */

/* USER CODE END 2 */
