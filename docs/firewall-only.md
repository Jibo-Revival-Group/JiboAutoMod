# Firewall-only conversion path

The `--firewall-only` path opens the existing SSH service without changing
`/var/jibo/mode.json`. It patches both bootable root filesystem slots and
always verifies the exact sector payload by reading it back through ShofEL.

```bash
python3 jibo_automod.py --firewall-only
```

To restore the original assignment on both slots:

```bash
python3 jibo_automod.py --firewall-only --restore-firewall
```

## Why the control flow leaves the firewall open

The validated script calls `flush_rules` before it reads the mode. That
function flushes the filter table and sets INPUT, FORWARD, and OUTPUT policy to
ACCEPT for both `iptables` and `ip6tables`. A literal shell assignment succeeds,
so the following `$?` test is false. The `int-developer` branch only prints a
status line; it does not call `normal_rules`. Execution then leaves `start`.

The result is local to `S21firewall`. Other startup scripts still see the real
value returned by `jibo-getmode`. This conclusion assumes `flush_rules`
completes successfully. The script has `set -e`, so an iptables failure can
still stop the init script and must be treated as a boot-time error.

## Byte signature and validation

The standalone assignment is deliberately not a valid signature. It occurs in
several unrelated init scripts in the supplied firmware. The actual profile is
the complete 3,225-byte known file, with only the assignment allowed to be in
its original or patched form. The control-flow excerpt around the edit is:

```sh
start() {
    echo -n "Configuring firewall: "
    flush_rules
    my_mode=$(/usr/bin/jibo-getmode)
    if [ $? -ne 0 ]; then
        echo "Unspecified mode. SKIP"
    elif [ "$my_mode" == "identified" ]; then
        echo "IDENTIFIED"
    elif [ "$my_mode" == "int-developer" ]; then
        echo "INT-DEVELOPER"
    elif [ "$my_mode" == "developer" ]; then
        developer_rules
```

Only the assignment bytes change:

```text
original: "    my_mode=$(/usr/bin/jibo-getmode)\n"
patched:  "    my_mode=\"int-developer\"         \n"
```

Both byte strings are 37 bytes. The nine trailing spaces preserve the line and
file length; the terminating LF is unchanged.

Validation rules are intentionally strict:

1. Parse GPT from a bounded 2 MiB read.
2. Require exactly one GPT partition named `rootfsA` and one named `rootfsB`.
3. Require a sector-aligned ext filesystem image for each slot.
4. Scan only those two bounded partition images.
5. Require exactly one complete original-or-patched firewall signature in each
   image. Missing, duplicated, mixed, or structurally changed context aborts.
6. Validate both slots before the first eMMC write.
7. Construct the smallest sector-aligned payload containing the assignment.
8. Save the complete rootfs reads and original sector payloads before writing.
9. Read every written sector back and require an exact byte-for-byte match.

For the supplied images, both `S21firewall` files are 3,225 bytes, SHA-256
`cb34db864fee2e6725fa09a293c60fff003b87348a16553419926ee7cc1a1cc8`, and
the patched-file SHA-256 is
`323141f5483d25f08ea7c17dd79e033074c9a34538ed51cbe687c33cbfb6e223`.
The assignment is at file offset 2,160. In both 1,000 MiB rootfs images, the
validated assignment is at partition byte offset 140,327,024 and fits in one
512-byte sector. These offsets are observations only; the tool never uses them
as discovery constants.

## Firmware and filesystem variations

Partition order, start sector, filesystem block placement, and the observed
byte offset are not trusted. GPT names define the scan bounds and content
defines the candidate. A firmware version with changed shell context is unknown
until its complete control flow is reviewed and a new explicit signature
profile is added with tests. Size-only, partition-number-only, and
nearest-offset fallbacks are intentionally forbidden.

The audit log is `jibo_work/firewall_patch_log.jsonl`. It records the GPT slot,
partition bounds, partition image SHA-256 identity, partition and absolute eMMC
byte offsets, before/after sector hashes, read-back hash, and result. Full slot
images and original patch sectors remain in `jibo_work` for recovery.

## Post-boot verification

After a successful verified write:

1. Boot normally and confirm the robot completes its usual normal-mode startup.
2. Confirm it receives the expected LAN address (DHCP lease or router client
   list) and responds to ARP/ping where the LAN permits it.
3. Test TCP port 22 from the same LAN (`nc -vz <ip> 22` or equivalent).
4. Start SSH and verify the server host key fingerprint before accepting it.
5. After login, record `cat /var/jibo/mode.json`, `/usr/bin/jibo-getmode`,
   `iptables -S`, `ip6tables -S`, and the SSH service/process status.
6. Reboot once more and repeat the port and rules checks to prove persistence
   and exercise the alternate rootfs slot if the firmware selects it.

If either slot or either read-back fails, do not boot as though conversion was
complete. Keep the robot in RCM, preserve the audit log, and run the restore
path. The saved `.firewall-sector.backup.bin` files are the exact recovery
payloads for the eMMC sectors recorded in the log.
