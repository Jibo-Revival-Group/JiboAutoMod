#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include "emmc_server.h"

int main(void) {
    struct emmc_cmd_s cmd = {EMMC_CMD_READ, EMMC_RO_STORAGE_SECTORS-1, 1};
    assert(emmc_ro_command_allowed(&cmd));
    cmd.num_sectors = 2; assert(!emmc_ro_command_allowed(&cmd));
    cmd.start_sector = 0; cmd.num_sectors = EMMC_RO_MAX_READ_SECTORS;
    assert(emmc_ro_command_allowed(&cmd));
    cmd.num_sectors++; assert(!emmc_ro_command_allowed(&cmd));
    uint32_t random = 0xABCD1234;
    for (unsigned int i = 0; i < 10000; i++) {
        random ^= random << 13; random ^= random >> 17; random ^= random << 5;
        cmd.start_sector = random; cmd.num_sectors = (random >> 16) + (i % 2 ? 0 : 0xFFFF0000u);
        int expected = cmd.num_sectors > 0 && cmd.num_sectors <= 4096 &&
            (uint64_t)cmd.start_sector + cmd.num_sectors <= EMMC_RO_STORAGE_SECTORS;
        assert(emmc_ro_command_allowed(&cmd) == expected);
    }
    for (uint32_t op = 0; op <= 255; op++) {
        cmd.op = op; cmd.start_sector = 0; cmd.num_sectors = 0;
        assert(!emmc_ro_command_allowed(&cmd));
    }
    const uint32_t allowed[] = {EMMC_CMD_STATUS, EMMC_CMD_READ_EXT_CSD, EMMC_CMD_EXIT};
    for (unsigned int i = 0; i < 3; i++) {
        cmd.op = allowed[i]; cmd.start_sector = 0; cmd.num_sectors = 0; assert(emmc_ro_command_allowed(&cmd));
        cmd.num_sectors = 1; assert(!emmc_ro_command_allowed(&cmd));
    }
    puts("Read-only policy passed 10000 range cases and legacy-opcode refusal.");
    return 0;
}
