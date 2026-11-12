# Jibo Revival Conversion Preview

> **Preview only:** this app checks its sample files and local results folder.
> The rest of the journey uses made-up information. It cannot check, connect to,
> or change a real Jibo. Real conversion is unavailable.

The demo walks through five example screens. They let you see the order of a
possible future journey; they are not completed steps for a real robot.

| Screen | What you will see |
| --- | --- |
| Check setup | Checks the bundled example files, the app's results folder, and space for a sample report. This is a local preview check only; it does not check your Jibo or space for a real backup. |
| Connect Jibo | An example of a future connection step |
| Recovery copy | An example of where recovery fits in the journey |
| Join service | An example of a future service choice |
| Verify | A sample report, not a check of your robot |

The first screen checks only whether this computer can create the sample preview.
The remaining screens are examples. The preview does not make or check a backup,
contact a service, or confirm robot support or readiness.

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
3. On the first screen, choose **Check preview** and wait for the local check to
   finish. Choose **Continue** only after it passes. The report step checks setup
   again before creating a sample report.
4. Continue through the four example screens. They do not connect to a Jibo or
   perform real recovery, service, or compatibility checks.
5. Select **Open demo report** if you want to view the sample HTML report.

## Candidate status and help

The Windows candidate's frozen and extracted checks passed using its bundled
Python runtime. Other platform candidates are offered only after their matching
build and launch checks pass. These checks cover the sample app, not a robot.
Candidate packages are unsigned, and the macOS app is not notarized. If your
computer blocks an app or shows a security warning, stop and send the message to
the project maintainers. Do not turn off security settings or bypass the warning.

A successful demo says nothing about whether a real Jibo is supported or ready.
For technical build and operating-system coverage notes, see the
[host support matrix](host-support.md). The source GUI entry point,
`owner_preview.py`, is for developers; a source checkout is not the owner install.
