# ShofEL2 for T124

This is a Fusee Gelee / ShofEL2 exploit port for the Nvidia T124 (a.k.a Jetson TK1, Shield K1, etc).

Currently this code allows you to download and execute a payload to the T124, dump the fuses and memory and boot bct without apply the locks.

Mostly of my code is based on the original ShofEL2 code and Katherine Temkin research, so I cannot take that much credit for this.

See the original fail0verflow blog post: https://fail0verflow.com/blog/2018/shofel2/
See additional info at the original Katherine Temkin github: https://github.com/Qyriad/fusee-launcher/blob/master/report/fusee_gelee.md

## Obligatory disclaimer

This code is provided without any warranty, use under your own resposability.

## Usage

You need an arm-*-eabi toolkit. You can use [Crosstool-ng](https://crosstool-ng.github.io/download/) compile it.

Build the loader and payloads:

    $ cd ShofEL2-for-T124
    $ make

Usage

    $ ./shofel2_t124 ( MEM_DUMP | READ_FUSES | BOOT_BCT | PAYLOAD ) [options]
    $ MEM_DUMP address length out_file -> Dumps "length" bytes starting from "address" to "out_file".
    $ READ_FUSES out_file -> Dumps the T124 fuses to "out_file" and show them in console. 
    $ BOOT_BCT -> Boots BCT without applying locks.
    $ PAYLOAD payload.bin [arm|thumb] -> Boots "payload.bin" the entrymode mode can be specified (thumb by default)
    

## Interesting facts (maybe some of them wrong)

* RCM loads the payload to IRAM at 0x4000E000 (described on tegrarcm source code).
* RCM cmd format is sligitly different. RCM cmd header length is 0x284 bytes but the firtst 4 bytes still containing the RCM cmd length.
* RCM cmd length restrictions are different to X1 bootrom:
	* Bulk transfers need to be multiply of 0x1000 to ensure use the whole usb buffer.
	* RCM cmd length minus 0x284 (header length) must be a multiple of 0x10 (which means RCM CMD length needs to end in 4).
	* RCM cmd min length is 0x404 bytes. Due to the previous condition the minimun length would be 0x1004.
	* RCM cmd length cannot exceed avaiable IRAM for the payload (from 0x4000E000 till 0x4003FFFF).
	* With all this in mind max RCM cmd length is 0x32274 bytes.
	* Since the exploit uses usb buffer 2, only 0x31000 bytes can be used for the payload in order to avoid finishing the RCM cmd.
* A payload can still be loaded using the same path as the one used by the original shofEL2, since no validation is carried out till the whole payload is received.
* Even if the specs says that the JTAG is enabled by default, cold bootrom code disasbles it while is runnig (not as dumb as expected :D).
* RCM runs on an ARM7TDMI core, I manage to halt the CPU on uboot using a Segger J-LINK.
* When the poisoned get status is executed, 0x30C bytes will be copied before the payload. These bytes are part of the execution stack, starting with the USB status var.
* Using the original sanity_check function from shofel2, I got from the execution stack that the RCM USB buffers are located at 0x40004000 and 0x40008000.
* Two USB buffers of 0x1000 bytes still present. They still alternating on each USB txn. And odd number of USB txn will let you on the hight buffer for the next txn.
* Using the original sanity_check function from shofel2, I got from the execution stack that the memcpy return address is located at 0x4000DCD8 (0x4000DCF4 - 0xC - 2 * 4 - 2 * 4).
* The position in the RCM cmd where the entry adress need to be write to smash the memcpy return address is calculated as follow:
	* n_bytes_to_copy = 0x4000DCD8 - 0x40008000 (memcpy_ret_add_loc - usb_buf2_add) -> n_bytes_to_copy = 0x5CD8 bytes
	* pos_in_payload = n_bytes_to_copy - 0x30C (copied from the execution stack) - 0x4 -> pos_in_payload = 0x59C8
	* pos_in_rcm_cmd = pos_in_payload + 0x284 (header length) -> pos_in_rcm_cmd = 0x5C4C
* I found the following functions on the the bootrom:

| Function | IROM Address | Description |
| ------------- | ------------- | ------------- |
| void ep1_in_write_imm(void *buffer, u32 size, u32 *num_xfer) | 0x001065C0 | Writes EP1_IN |
| void ep1_out_read_imm(void *buffer, u32 size, u32 *num_xfer) | 0x00106612 | Reads EP1_OUT |
| void do_bct_boot() | 0x00100624 | Boots BCT without applying locks. |

