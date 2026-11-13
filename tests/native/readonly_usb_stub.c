/* Test-only link replacement: this executable cannot access real USB. */
#include "mini_libusb.h"
#include "emmc_server.h"
#include "t124.h"

static uint32_t op, cursor, remaining;
static int phase;
static unsigned status_commands, read_commands, exit_commands, full_storage_reads;
#ifndef READONLY_FIXTURE_DEFAULT_MODE
#define READONLY_FIXTURE_DEFAULT_MODE ""
#endif
static const char *active_mode(void) {
    const char *current = getenv("READONLY_FIXTURE_MODE");
    return current && *current ? current : READONLY_FIXTURE_DEFAULT_MODE;
}
static int mode(const char *value) { return !strcmp(active_mode(), value); }
static void check(int condition) { if (!condition) { fputs("Fixture protocol violation.\n", stderr); exit(91); } }

int usb_open_by_vid_pid(uint16_t vid, uint16_t pid, uint8_t wait) {
    check(vid == JIBO_TK1_VID && pid == JIBO_TK1_PID && wait == 1);
    fputs("USB_FIXTURE_OPEN\n", stderr); return 1;
}
int usb_close(int usb) {
    check(usb == 1);
    fprintf(stderr, "USB_FIXTURE_COUNTS status=%u reads=%u exits=%u\n", status_commands, read_commands, exit_commands);
    if (!strncmp(active_mode(), "full-", 5)) fprintf(stderr, "USB_FIXTURE_FULL_STORAGE_READS=%u\n", full_storage_reads);
    return 0;
}
int usb_clear_halt(int usb, uint32_t ep) { check(usb == 1 && ep == 1); return 0; }
int send_rcm_cmd(int usb, char *payload, uint32_t thumb, int debug) {
    check(usb == 1 && !strcmp(payload, "emmc_server_readonly.bin") && thumb == 1 && debug == 0); return 0;
}
int usb_send_control_txn(int usb, uint8_t type, uint8_t request, uint16_t value, uint16_t index,
                         uint16_t len, uint8_t *data, int32_t timeout) { return mode("control-zero") ? 0 : -1; }
int usb_send_bulk_txn(int usb, uint32_t ep, uint32_t length, void *bytes, int debug) {
    check(usb == 1 && debug == 0);
    if (ep == RCM_EP1_OUT) {
        check(length == sizeof(struct emmc_cmd_s));
        struct emmc_cmd_s *cmd = bytes; check(emmc_ro_command_allowed(cmd));
        op = cmd->op; cursor = cmd->start_sector; remaining = cmd->num_sectors; phase = 1;
        if (op == EMMC_CMD_STATUS) ++status_commands;
        if (op == EMMC_CMD_READ || op == EMMC_CMD_READ_EXT_CSD) ++read_commands;
        if (op == EMMC_CMD_READ) ++full_storage_reads;
        if (op == EMMC_CMD_READ_EXT_CSD && mode("full-capacity-command-failure")) return -1;
        if (op == EMMC_CMD_READ && mode("full-read-command-failure")) return -1;
        if (op == EMMC_CMD_EXIT) ++exit_commands;
        if (op == EMMC_CMD_STATUS && mode("handshake-command-failure")) return -1;
        return op == EMMC_CMD_EXIT && (mode("exit-failure") || mode("full-exit-failure") || mode("handshake-reply-and-exit-failure")) ? -1 : 0;
    }
    check(ep == RCM_EP1_IN);
    if (!op) { check(length == RCM_CHIP_ID_LEN); memset(bytes, 0xA5, length); return 0; }
    if (op == EMMC_CMD_STATUS) {
        check(length == 512);
        if (mode("handshake-reply-failure") || mode("handshake-reply-and-exit-failure")) return -1;
        memset(bytes, 0, length);
        uint32_t *status = bytes;
        status[0] = mode("legacy-payload") ? 0xCAFE0000 : EMMC_RO_STATUS_MAGIC;
        status[1] = mode("clock-warning") ? 0xD0000001 : mode("clock-failure") ? 0xD0000002 : 0;
        status[2] = mode("init-failure") ? 0 : 1;
        status[13] = mode("sector-zero-failure") ? 1 : 0;
        status[56] = mode("wrong-version") ? 2 : 1;
        status[57] = mode("wrong-limits") ? 8192 : EMMC_RO_MAX_READ_SECTORS;
        status[58] = mode("wrong-storage-limit") ? EMMC_RO_STORAGE_SECTORS-1 : EMMC_RO_STORAGE_SECTORS;
        return 0;
    }
    check(op == EMMC_CMD_READ || op == EMMC_CMD_READ_EXT_CSD);
    uint32_t batch = op == EMMC_CMD_READ_EXT_CSD ? 1 : (remaining > EMMC_CHUNK_SECTORS_READ ? EMMC_CHUNK_SECTORS_READ : remaining);
    if (phase == 1) {
        check(length == sizeof(struct emmc_ro_result_s));
        struct emmc_ro_result_s *reply = bytes;
        reply->magic = mode("wrong-frame") ? 0 : EMMC_RO_DATA_MAGIC;
        reply->status = mode("read-failure") || (mode("late-read-failure") && remaining == 1) || (op == EMMC_CMD_READ_EXT_CSD && mode("full-capacity-frame-failure")) || (op == EMMC_CMD_READ && mode("full-read-frame-failure")) ? 1 : 0;
        reply->start_sector = cursor + (mode("wrong-sector") ? 1 : 0);
        reply->num_sectors = batch + (mode("wrong-count") ? 1 : 0);
        phase = 2; return mode("short-header") ? -1 : 0;
    }
    check(phase == 2 && length == batch * EMMC_SECTOR_SIZE);
    memset(bytes, 0x5A, length);
    if (op == EMMC_CMD_READ_EXT_CSD && !strncmp(active_mode(), "full-", 5)) {
        uint32_t measured = mode("full-capacity-zero") ? 0 : mode("full-capacity-too-large") ? EMMC_RO_STORAGE_SECTORS + 1u : 4105u;
        uint8_t *data = bytes;
        data[212] = measured & 0xff; data[213] = (measured >> 8) & 0xff;
        data[214] = (measured >> 16) & 0xff; data[215] = (measured >> 24) & 0xff;
    }
    if ((op == EMMC_CMD_READ_EXT_CSD && mode("full-capacity-data-failure")) ||
        (op == EMMC_CMD_READ && mode("full-read-data-failure"))) return -1;
    if (op == EMMC_CMD_READ) { cursor += batch; remaining -= batch; }
    phase = 1;
    return mode("short-data") ? -1 : 0;
}
