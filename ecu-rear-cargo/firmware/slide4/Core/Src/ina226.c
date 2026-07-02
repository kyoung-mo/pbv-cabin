/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file    ina226.c
  * @brief   INA226 전류센서 드라이버 (I2C1). 션트 전압을 읽어 전류로 환산한다.
  ******************************************************************************
  */
/* USER CODE END Header */
#include "ina226.h"
#include "i2c.h"     /* hi2c1 — CubeMX I2C1 핸들 */

/* --------------------------------------------------------------------------
 *  INA226 레지스터 맵 / 상수
 * ------------------------------------------------------------------------ */
#define INA226_REG_CONFIG    0x00
#define INA226_REG_SHUNT_V   0x01   /* 션트 전압, signed, LSB = 2.5µV */
#define INA226_REG_MANUF_ID  0xFE   /* 제조사 ID = 0x5449 ('TI') */

#define INA226_MANUF_ID      0x5449
#define INA226_I2C_TIMEOUT   5       /* ms — 미장착 센서에서 메인루프 안 멈추게 짧게 */

/* Config: AVG=16회 평균(노이즈↓), VBUS/VSH 변환 1.1ms, MODE=연속 shunt+bus(111).
 * 0x4527 = 0100 0101 0010 0111 */
#define INA226_CONFIG_VALUE  0x4527

/* 16비트 레지스터 1개 읽기(MSB first). 실패 시 0 반환. */
static uint16_t ina226_read16(uint8_t addr7, uint8_t reg)
{
  uint8_t b[2] = {0};
  if (HAL_I2C_Mem_Read(&hi2c1, (uint16_t)(addr7 << 1), reg,
                       I2C_MEMADD_SIZE_8BIT, b, 2, INA226_I2C_TIMEOUT) != HAL_OK)
    return 0;
  return (uint16_t)((b[0] << 8) | b[1]);
}

/* 16비트 레지스터 1개 쓰기(MSB first). */
static HAL_StatusTypeDef ina226_write16(uint8_t addr7, uint8_t reg, uint16_t val)
{
  uint8_t b[2] = { (uint8_t)(val >> 8), (uint8_t)(val & 0xFF) };
  return HAL_I2C_Mem_Write(&hi2c1, (uint16_t)(addr7 << 1), reg,
                           I2C_MEMADD_SIZE_8BIT, b, 2, INA226_I2C_TIMEOUT);
}

uint8_t ina226_present(uint8_t addr7)
{
  return (ina226_read16(addr7, INA226_REG_MANUF_ID) == INA226_MANUF_ID) ? 1 : 0;
}

uint8_t ina226_init(uint8_t addr7)
{
  if (!ina226_present(addr7)) return 0;        /* 미장착이면 설정도 생략 */
  ina226_write16(addr7, INA226_REG_CONFIG, INA226_CONFIG_VALUE);
  return 1;
}

int16_t ina226_read_shunt_raw(uint8_t addr7)
{
  return (int16_t)ina226_read16(addr7, INA226_REG_SHUNT_V);   /* signed 재해석 */
}

int32_t ina226_read_current_mA(uint8_t addr7)
{
  /* I[mA] = Vshunt / Rshunt = (raw × 2.5µV) / (shunt_mΩ × 1e-3) = raw × 2.5 / shunt_mΩ
   * 정수연산: (raw × 25) / (shunt_mΩ × 10).  예) raw=28000, 100mΩ → 700mA */
  int32_t raw = ina226_read_shunt_raw(addr7);
  return (raw * 25) / ((int32_t)INA226_SHUNT_MOHM * 10);
}
