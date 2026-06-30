/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    ina226.h
  * @brief   INA226 전류/전압 센서 드라이버 (I2C1). 순수 센서 읽기만 담당한다.
  *          CAN·서보·안티핀치 판단 로직은 이 모듈에 넣지 않는다(상위 main.c가 조합).
  *          여러 개를 7비트 주소로 구분해 사용한다(예: 0x40=RL, 0x41=RR).
  ******************************************************************************
  */
/* USER CODE END Header */
#ifndef __INA226_H__
#define __INA226_H__

#ifdef __cplusplus
extern "C" {
#endif

#include "main.h"

/* 션트 저항(mΩ). 보드에 실제 장착한 값으로 맞춰야 전류 환산이 맞다.
 * TODO(calibration): 실측 션트 값으로 교체. SG90 스톨(~700mA)이 측정 범위 안이어야 함.
 *   INA226 션트 측정 한계 ±81.92mV → 0.1Ω이면 ±819mA, 0.05Ω이면 ±1.6A. */
#define INA226_SHUNT_MOHM   100

/* 센서 초기화: 연속 변환(shunt+bus) + 16회 평균으로 설정.
 * @return 1=응답 있음(장착됨), 0=없음(미장착이면 상위에서 모니터 건너뛰기). */
uint8_t ina226_init(uint8_t addr7);

/* 해당 주소가 INA226인지 확인(Manufacturer ID=0x5449 'TI' 레지스터 0xFE).
 * @return 1=존재, 0=없음. */
uint8_t ina226_present(uint8_t addr7);

/* 션트 전압 레지스터(0x01) 원시값(signed). LSB=2.5µV. */
int16_t ina226_read_shunt_raw(uint8_t addr7);

/* 션트값(INA226_SHUNT_MOHM)으로 환산한 전류(mA). 음수면 0으로 클램프하지 않고
 * 절대치 비교는 상위에서. 통신 실패 시 0 반환. */
int32_t ina226_read_current_mA(uint8_t addr7);

#ifdef __cplusplus
}
#endif

#endif /* __INA226_H__ */
