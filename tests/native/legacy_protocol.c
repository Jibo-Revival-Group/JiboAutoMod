#include <assert.h>
#include "emmc_server.h"
int main(void) {
    assert(EMMC_CMD_READ == 1 && EMMC_CMD_WRITE == 2 && EMMC_CMD_STATUS == 3);
    assert(EMMC_CMD_READ_EXT_CSD == 4 && EMMC_CMD_ERASE == 5 && EMMC_CMD_EXIT == 255);
    assert(EMMC_CHUNK_SECTORS == 1);
    return 0;
}
