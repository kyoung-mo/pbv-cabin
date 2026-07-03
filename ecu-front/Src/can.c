#include "can.h"
#include "main.h"

extern CAN_HandleTypeDef hcan;

/* CAN 수신 인터럽트에서는 플래그만 세우고, main loop에서 Pop 함수로 꺼내 처리한다. */
static volatile SeatCommand_t rx_cmd;
static volatile uint8_t rx_cmd_pending;
static volatile GearStatus_t rx_gear_status;
static volatile uint8_t rx_gear_pending;
static volatile SafeAbort_t rx_safe_abort;
static volatile uint8_t rx_safe_abort_pending;

static uint32_t tx_mailbox;

/* STM32 HAL의 16비트 CAN 필터는 표준 ID를 왼쪽으로 5비트 밀어서 넣는다. */
static uint16_t can_std_filter_value(uint16_t std_id)
{
    return (uint16_t)(std_id << 5);
}

/* Driver_Seat_Cmd 체크섬.
 * DBC에는 Checksum 신호만 있고 계산식은 없어서,
 * 현재는 byte0 + byte1 + byte2의 하위 8비트로 검증한다.
 * 메인 제어기 체크섬 규칙이 다르면 이 함수만 바꾸면 된다.
 */
static uint8_t can_driver_cmd_checksum(const uint8_t data[4])
{
    return (uint8_t)(data[0] + data[1] + data[2]);
}

static void can_filter_init(void)
{
    CAN_FilterTypeDef f = {0};

    /* 프론트 존 ECU가 받아야 하는 명령 ID만 통과시킨다. */
    f.FilterBank = 0;
    f.FilterMode = CAN_FILTERMODE_IDLIST;
    f.FilterScale = CAN_FILTERSCALE_16BIT;
    f.FilterIdHigh = can_std_filter_value(CAN_ID_SAFE_ABORT);
    f.FilterIdLow = can_std_filter_value(CAN_ID_GEAR_STATUS);
    f.FilterMaskIdHigh = can_std_filter_value(CAN_ID_DRIVER_SEAT_CMD);
    f.FilterMaskIdLow = can_std_filter_value(CAN_ID_PASSENGER_SEAT_CMD);
    f.FilterFIFOAssignment = CAN_RX_FIFO0;
    f.FilterActivation = ENABLE;

    if (HAL_CAN_ConfigFilter(&hcan, &f) != HAL_OK)
    {
        Error_Handler();
    }
}

void CAN_AppStart(void)
{
    can_filter_init();

    if (HAL_CAN_Start(&hcan) != HAL_OK)
    {
        Error_Handler();
    }

    if (HAL_CAN_ActivateNotification(&hcan, CAN_IT_RX_FIFO0_MSG_PENDING) != HAL_OK)
    {
        Error_Handler();
    }
}

uint8_t CAN_AppPopSeatCommand(SeatCommand_t *cmd)
{
    if (rx_cmd_pending == 0U || cmd == 0)
    {
        return 0U;
    }

    __disable_irq();
    *cmd = rx_cmd;
    rx_cmd_pending = 0U;
    __enable_irq();

    return 1U;
}

uint8_t CAN_AppPopGearStatus(GearStatus_t *status)
{
    if (rx_gear_pending == 0U || status == 0)
    {
        return 0U;
    }

    __disable_irq();
    *status = rx_gear_status;
    rx_gear_pending = 0U;
    __enable_irq();

    return 1U;
}

uint8_t CAN_AppPopSafeAbort(SafeAbort_t *abort_msg)
{
    if (rx_safe_abort_pending == 0U || abort_msg == 0)
    {
        return 0U;
    }

    __disable_irq();
    *abort_msg = rx_safe_abort;
    rx_safe_abort_pending = 0U;
    __enable_irq();

    return 1U;
}

void CAN_AppSendSeatStatus(SeatId_t seat,
                           uint8_t curr_recline,
                           uint8_t curr_rotation,
                           uint8_t pinch_detected)
{
    CAN_TxHeaderTypeDef header = {0};
    uint8_t data[3] = {0};

    header.StdId = (seat == SEAT_DRIVER) ? CAN_ID_DRIVER_SEAT_STATUS : CAN_ID_PASSENGER_SEAT_STATUS;
    header.IDE = CAN_ID_STD;
    header.RTR = CAN_RTR_DATA;
    header.DLC = 3;
    header.TransmitGlobalTime = DISABLE;

    /* Driver_Seat_Status(0x210), Passenger_Seat_Status(0x211), Length 3
     * byte0 = 현재 리클라이너 각도, 즉 서보모터 각도
     * byte1 = 현재 회전 각도, 즉 스텝모터 목표 각도
     * byte2 bit0 = 끼임감지 센서값
     */
    data[0] = curr_recline;
    data[1] = curr_rotation;
    data[2] = (uint8_t)(pinch_detected & 0x01U);

    (void)HAL_CAN_AddTxMessage(&hcan, &header, data, &tx_mailbox);
}

void HAL_CAN_RxFifo0MsgPendingCallback(CAN_HandleTypeDef *can_handle)
{
    CAN_RxHeaderTypeDef header;
    uint8_t data[8];

    if (HAL_CAN_GetRxMessage(can_handle, CAN_RX_FIFO0, &header, data) != HAL_OK)
    {
        return;
    }

    if (header.IDE != CAN_ID_STD || header.RTR != CAN_RTR_DATA)
    {
        return;
    }

    if (header.StdId == CAN_ID_SAFE_ABORT && header.DLC >= 3U)
    {
        /* SafeAbort(0x010), Length 3 */
        rx_safe_abort.stop_flag = (uint8_t)(data[0] & 0x01U);
        rx_safe_abort.source_id = data[1];
        rx_safe_abort.reason_code = data[2];
        rx_safe_abort_pending = 1U;
    }
    else if (header.StdId == CAN_ID_GEAR_STATUS && header.DLC >= 1U)
    {
        /* GearStatus(0x070), Length 1 */
        rx_gear_status.gear = (uint8_t)(data[0] & 0x03U);
        rx_gear_pending = 1U;
    }
    else if (header.StdId == CAN_ID_DRIVER_SEAT_CMD && header.DLC >= 4U)
    {
        /* Driver_Seat_Cmd(0x110), Length 4 */
        rx_cmd.seat = SEAT_DRIVER;
        rx_cmd.recline_angle = data[0];
        rx_cmd.rotation_angle = data[1];
        rx_cmd.rolling_counter = (uint8_t)(data[2] & 0x0FU);
        rx_cmd.checksum_ok = (data[3] == can_driver_cmd_checksum(data)) ? 1U : 0U;
        rx_cmd_pending = 1U;
    }
    else if (header.StdId == CAN_ID_PASSENGER_SEAT_CMD && header.DLC >= 2U)
    {
        /* Passenger_Seat_Cmd(0x111), Length 2 */
        rx_cmd.seat = SEAT_PASSENGER;
        rx_cmd.recline_angle = data[0];
        rx_cmd.rotation_angle = data[1];
        rx_cmd.rolling_counter = 0U;
        rx_cmd.checksum_ok = 1U;
        rx_cmd_pending = 1U;
    }
}
