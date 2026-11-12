# Jibo Revival Conversion Preview

> **Practice only:** this preview uses made-up information. It cannot check,
> connect to, or change a real Jibo. Real conversion and robot checks are not
> available.

The demo walks through five example screens. They let you see the order of a
possible future journey; they are not completed steps for a real robot.

| Screen | What you will see |
| --- | --- |
| Check setup | An introduction to the sample journey |
| Connect Jibo | An example of a future connection step |
| Recovery copy | An example of where recovery fits in the journey |
| Join service | An example of a future service choice |
| Verify | A sample report, not a check of your robot |

The preview does not make or check a backup, contact a service, or confirm robot
support or readiness.

It does not ask for an account, robot address, backup, JSON file, or partition
choice. **Open demo report** shows a local report made from sample data only; no
real backup is read. The report is optional.

## Try the demo

There is no release download yet. If the project provides a candidate archive,
choose the one for your computer:

| Computer | Candidate archive | Open after extracting |
| --- | --- | --- |
| Windows, 64-bit | `JiboRevival-Conversion-Preview-Windows-x64.zip` | `JiboRevival-Conversion-Preview.exe` |
| macOS, Intel | `JiboRevival-Conversion-Preview-macOS-x64.zip` | `JiboRevival-Conversion-Preview.app` |
| macOS, Apple silicon | `JiboRevival-Conversion-Preview-macOS-arm64.zip` | `JiboRevival-Conversion-Preview.app` |
| Linux, x86-64 | `JiboRevival-Conversion-Preview-Linux-x64.tar.gz` | `JiboRevival-Conversion-Preview` inside its folder |

1. Extract the **entire** archive to a folder.
2. Open the app listed for your computer. The Windows candidate needs no separate
   Python installation.
3. Choose **Try demo** and continue through the five example screens.
4. Select **Open demo report** if you want to view the sample HTML report.

## Candidate status and help

The Windows candidate's frozen and extracted launch checks passed, including a
check without Python installed. macOS and Linux package checks are still pending.
Candidate packages are unsigned, and the macOS app is not notarized. If your
computer blocks an app or shows a security warning, stop and send the message to
the project maintainers. Do not turn off security settings or bypass the warning.

A successful demo says nothing about whether a real Jibo is supported or ready.
For technical build and operating-system coverage notes, see the
[host support matrix](host-support.md). The source GUI entry point,
`owner_preview.py`, is for developers; a source checkout is not the owner install.
