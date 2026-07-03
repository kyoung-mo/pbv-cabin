#ifndef INC_CAN_H_
#define INC_CAN_H_

#include <stdint.h>

/* 프론트 존 ECU에서 사용하는 CAN ID */
#define CAN_ID_SAFE_ABORT             0x010U
#define CAN_ID_GEAR_STATUS            0x070U
#define CAN_ID_DRIVER_SEAT_CMD        0x110U
#define CAN_ID_PASSENGER_SEAT_CMD     0x111U
#define CAN_ID_DRIVER_SEAT_STATUS     0x210U
#define CAN_ID_PASSENGER_SEAT_STATUS  0x211U

typedef enum
{
    SEAT_DRIVER = 0,
    SEAT_PASSENGER = 1
} SeatId_t;

/* Driver_Seat_Cmd(0x110), Length 4
 * byte0 = Drv_Recline_Angle     start 0,  length 8
 * byte1 = Drv_Rotation_Angle    start 8,  length 8
 * byte2 bit0~3 = Rolling_Counter start 16, length 4
 * byte3 = Checksum              start 24, length 8
 *
 * Passenger_Seat_Cmd(0x111), Length 2
 * byte0 = Psgr_Recline_Angle    start 0, length 8
 * byte1 = Psgr_Rotation_Angle   start 8, length 8
 */
typedef struct
{
    SeatId_t seat;
    uint8_t recline_angle;
    uint8_t rotation_angle;
    uint8_t rolling_counter;
    uint8_t checksum_ok;
} SeatCommand_t;

/* GearStatus(0x070), Length 1
 * byte0 bit0~1 = Gear, start 0, length 2
 * 현재 약속: 0=P, 1=D, 2=R
 */
typedef struct
{
    uint8_t gear;
} GearStatus_t;

/* SafeAbort(0x010), Length 3
 * byte0 bit0 = Stop_Flag, start 0, length 1
 * byte1 = Source_Id, start 8, length 8
 * byte2 = Reason_Code, start 16, length 8
 */
typedef struct
{
    uint8_t stop_flag;
    uint8_t source_id;
    uint8_t reason_code;
} SafeAbort_t;

/* Driver_Seat_Status(0x210), Passenger_Seat_Status(0x211), Length 3
 * byte0 = 현재 리클라이너 각도, 즉 서보모터 각도
 * byte1 = 현재 회전 각도, 즉 스텝모터 목표 각도
 * byte2 bit0 = 끼임감지 센서값
 */
void CAN_AppStart(void);
uint8_t CAN_AppPopSeatCommand(SeatCommand_t *cmd);
uint8_t CAN_AppPopGearStatus(GearStatus_t *status);
uint8_t CAN_AppPopSafeAbort(SafeAbort_t *abort_msg);

void CAN_AppSendSeatStatus(SeatId_t seat,
                           uint8_t curr_recline,
                           uint8_t curr_rotation,
                           uint8_t pinch_detected);

#endif /* INC_CAN_H_ */
