#include "servo.h"
#include "main.h"

#define SERVO_MIN_US      500U
#define SERVO_MAX_US      2500U
#define SERVO_MAX_ANGLE   180U

extern TIM_HandleTypeDef htim2;

void Servo_Init(void)
{
    /* SG90 서보 2개의 PWM 출력을 시작한다. */
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim2, TIM_CHANNEL_2);

    /* 초기 위치: 등받이 정위치로 쓸 중립 각도. */
    Servo_SetAngle(1, 90);
    Servo_SetAngle(2, 90);
}

void Servo_SetAngle(uint8_t channel, uint8_t angle)
{
    uint32_t pulse;

    /* 잘못된 채널 번호는 무시한다. */
    if (channel < 1U || channel > 2U)
    {
        return;
    }

    /* 서보 명령 범위를 0~180도로 제한한다. */
    if (angle > SERVO_MAX_ANGLE)
    {
        angle = SERVO_MAX_ANGLE;
    }

    /* CAN에서 들어오는 리클라인 값은 0~180도 각도값이다.
     * TIM2는 1카운트 = 1us이므로 SG90이 이해하는 500~2500us 펄스폭으로 변환한다.
     * 예: 0도=500us, 90도=1500us, 180도=2500us
     */
    pulse = SERVO_MIN_US + (((uint32_t)angle * (SERVO_MAX_US - SERVO_MIN_US)) / SERVO_MAX_ANGLE);

    if (channel == 1U)
    {
        /* 운전석 서보: PA0 = TIM2_CH1 */
        __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_1, pulse);
    }
    else
    {
        /* 조수석 서보: PA1 = TIM2_CH2 */
        __HAL_TIM_SET_COMPARE(&htim2, TIM_CHANNEL_2, pulse);
    }
}

void Servo_Stop(void)
{
    /* PWM 출력을 멈춘다. 주로 비상정지나 디버깅용이다. */
    HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_1);
    HAL_TIM_PWM_Stop(&htim2, TIM_CHANNEL_2);
}
