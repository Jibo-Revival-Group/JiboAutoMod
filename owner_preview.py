"""A guided, synthetic-only preview of the Jibo Revival conversion journey."""

from __future__ import annotations

import argparse
import json
import os
import queue
import stat
import sys
import threading
import webbrowser
from pathlib import Path

STEPS = (
    ("Check setup", "See how the journey works", "This is a demo using made-up information. It does not check your computer or Jibo. Real conversion is not available in this preview."),
    ("Connect Jibo", "Imagine connecting your Jibo", "For this demo, nothing is connected. A future supported tool would guide you through connecting your Jibo and checking compatibility."),
    ("Recovery copy", "See the recovery step", "The demo does not make or check a backup. Before any future changes, you would need a verified recovery copy for your own Jibo."),
    ("Join service", "Choose a service later", "No account is created and no service is contacted. A future conversion would let you choose a compatible service or your own setup."),
    ("Verify", "Create your demo report", "Create a private report using sample data. It cannot tell you whether your Jibo is supported or ready to convert."),
)


class PreviewError(ValueError):
    """A preview result did not meet the synthetic-only contract."""


def validate_result(result, output_parent=None):
    """Accept only an existing local report explicitly marked as synthetic."""
    if not isinstance(result, dict) or result.get("syntheticDemo") is not True or result.get("readyForApply") is not False:
        raise PreviewError("The demo report could not be verified.")
    value = result.get("reviewFile")
    output_dir = result.get("outputDir")
    if not isinstance(value, (str, Path)) or not isinstance(output_dir, (str, Path)):
        raise PreviewError("The demo report could not be verified.")
    path, directory = Path(value), Path(output_dir)
    if not path.is_absolute() or not directory.is_absolute() or path.name != "review.html" or not path.is_file() or not directory.is_dir():
        raise PreviewError("The demo report could not be verified.")
    resolved, resolved_dir = path.resolve(strict=True), directory.resolve(strict=True)
    if resolved.parent != resolved_dir:
        raise PreviewError("The demo report could not be verified.")
    if output_parent is not None:
        parent = Path(output_parent).resolve(strict=True)
        if resolved_dir == parent or not resolved_dir.is_relative_to(parent):
            raise PreviewError("The demo report could not be verified.")
    summary = result.get("summary")
    if not isinstance(summary, str):
        raise PreviewError("The demo report could not be verified.")
    return {"reviewFile": str(resolved), "outputDir": str(resolved_dir), "summary": summary,
            "syntheticDemo": True, "readyForApply": False}


def prepare_preview(output_parent=None, backend=None):
    validation_parent = output_parent
    if backend is None:
        from owner_preview_support import default_output_parent, prepare_demo
        backend = prepare_demo
        if output_parent is None:
            validation_parent = default_output_parent()
    result = backend(output_parent=output_parent)
    return validate_result(result, validation_parent)


class PreviewController:
    """Small state machine; independent of Tk and real hardware."""

    def __init__(self):
        self.step = 0
        self.busy = False
        self.result = None
        self.failed = False

    def next(self):
        if not self.busy and self.step < len(STEPS) - 1:
            self.step += 1
            self.failed = False

    def back(self):
        if not self.busy and self.step > 0:
            self.step -= 1
            self.failed = False

    def begin(self):
        if self.busy or self.step != len(STEPS) - 1:
            raise PreviewError("Finish the demo steps first.")
        self.busy = True
        self.failed = False
        self.result = None

    def complete(self, result, output_parent=None):
        if not self.busy:
            raise PreviewError("No demo is running.")
        try:
            self.result = validate_result(result, output_parent)
        except (ValueError, OSError, RuntimeError):
            self.failed = True
            self.result = None
        finally:
            self.busy = False

    def fail(self):
        if self.busy:
            self.busy = False
            self.failed = True
            self.result = None


def launch():
    # Importing this module never initializes a display or device tooling.
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Jibo Revival — Conversion Preview")
    root.geometry("820x620")
    root.minsize(650, 510)
    root.configure(bg="#f4f6f9")
    state = PreviewController()
    messages = queue.Queue()
    alive = True

    style = ttk.Style(root)
    style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 10))
    style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(12, 9))

    top = tk.Frame(root, bg="#17243d", padx=30, pady=20)
    top.pack(fill="x")
    tk.Label(top, text="JIBO REVIVAL", bg="#17243d", fg="#b8d0ed", font=("Segoe UI", 10, "bold")).pack(anchor="w")
    tk.Label(top, text="Conversion preview", bg="#17243d", fg="white", font=("Segoe UI", 23, "bold")).pack(anchor="w", pady=(4, 0))
    tk.Label(top, text="A guided demo with sample information", bg="#17243d", fg="#d5e0ed", font=("Segoe UI", 11)).pack(anchor="w", pady=(3, 0))

    body = tk.Frame(root, bg="#f4f6f9", padx=30, pady=22)
    body.pack(fill="both", expand=True)
    progress = tk.Label(body, bg="#f4f6f9", fg="#3c5f88", font=("Segoe UI", 10, "bold"), anchor="w")
    progress.pack(fill="x")
    card = tk.Frame(body, bg="white", padx=26, pady=24, highlightbackground="#dce3ec", highlightthickness=1)
    card.pack(fill="both", expand=True, pady=(12, 18))
    step_label = tk.Label(card, bg="white", fg="#4a698c", font=("Segoe UI", 10, "bold"), anchor="w")
    step_label.pack(fill="x")
    title = tk.Label(card, bg="white", fg="#17243d", font=("Segoe UI", 20, "bold"), anchor="w", justify="left", wraplength=650)
    title.pack(fill="x", pady=(10, 12))
    description = tk.Label(card, bg="white", fg="#35465c", font=("Segoe UI", 12), anchor="nw", justify="left", wraplength=650)
    description.pack(fill="x")
    status = tk.Label(card, bg="white", fg="#3c5f88", font=("Segoe UI", 11), anchor="w", justify="left", wraplength=650)
    status.pack(fill="x", pady=(18, 0))

    def resize_text(event):
        width = max(220, event.width - 54)
        for label in (title, description, status):
            label.configure(wraplength=width)

    card.bind("<Configure>", resize_text)
    nav = tk.Frame(body, bg="#f4f6f9")
    nav.pack(fill="x")
    back = ttk.Button(nav, text="Back", style="Secondary.TButton", command=lambda: move(-1))
    back.pack(side="left")
    forward = ttk.Button(nav, style="Primary.TButton", command=lambda: advance())
    forward.pack(side="right")
    report = ttk.Button(nav, text="Open demo report", style="Secondary.TButton", command=lambda: open_report())

    def show():
        label, heading, detail = STEPS[state.step]
        progress.configure(text=f"STEP {state.step + 1} OF {len(STEPS)}    •    DEMO ONLY")
        step_label.configure(text=label.upper())
        title.configure(text=heading)
        description.configure(text=detail)
        back.configure(state="disabled" if state.step == 0 or state.busy else "normal")
        if state.busy:
            status.configure(text="Creating the sample report…")
            forward.configure(text="Please wait", state="disabled")
        elif state.failed:
            status.configure(text="The demo could not be created. Please try again or ask for help. Your Jibo was not changed.")
            forward.configure(text="Try again", state="normal")
        elif state.result and state.step == len(STEPS) - 1:
            status.configure(text="Demo report ready. This is sample data; your Jibo was not checked or changed. Keep the report private.")
            forward.configure(text="Create another demo", state="normal")
        else:
            status.configure(text="")
            forward.configure(text=("Try demo" if state.step == 0 else "Create demo report" if state.step == len(STEPS) - 1 else "Continue"), state="normal")
        if state.result and state.step == len(STEPS) - 1 and not state.busy:
            report.pack(side="right", padx=(0, 10))
        else:
            report.pack_forget()

    def move(direction):
        state.back() if direction < 0 else state.next()
        show()

    def advance():
        if state.step < len(STEPS) - 1:
            state.next()
            show()
            return
        state.begin()
        show()
        def worker():
            try:
                messages.put((True, prepare_preview()))
            except Exception:
                messages.put((False, None))
        threading.Thread(target=worker, daemon=True).start()

    def open_report():
        if state.result:
            try:
                if not webbrowser.open(Path(state.result["reviewFile"]).as_uri()):
                    status.configure(text="The report could not be opened. Please ask for help.")
            except (OSError, ValueError):
                status.configure(text="The report could not be opened. Please ask for help.")

    def poll():
        if not alive:
            return
        try:
            while True:
                ok, result = messages.get_nowait()
                state.complete(result) if ok else state.fail()
                show()
        except queue.Empty:
            pass
        root.after(100, poll)

    def close():
        nonlocal alive
        alive = False
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    show()
    root.after(100, poll)
    root.mainloop()



def write_smoke_receipt(path, result):
    """Create a new receipt in an existing, ordinary directory."""
    path = Path(path).absolute()
    parent = path.parent
    for component in (parent, *parent.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise PreviewError("The receipt location is not available.")
    if not parent.is_dir():
        raise PreviewError("The receipt location is not available.")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_BINARY", 0) | getattr(os, "O_NOINHERIT", 0) | getattr(os, "O_NOFOLLOW", 0)
    payload = {"syntheticDemo": True, "readyForApply": False,
               "reviewFile": result["reviewFile"], "outputDir": result["outputDir"]}
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(payload, stream)
        stream.write("\n")


def safe_message(message, stream):
    if stream is not None:
        print(message, file=stream)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Jibo Revival synthetic conversion preview")
    parser.add_argument("--smoke", action="store_true", help="create a synthetic report without opening a window")
    parser.add_argument("--output-parent", help="existing folder for a synthetic smoke report")
    parser.add_argument("--receipt", help="new file for the synthetic smoke result")
    args = parser.parse_args(argv)
    if (args.output_parent or args.receipt) and not args.smoke:
        parser.error("--output-parent and --receipt require --smoke")
    if args.smoke:
        try:
            result = prepare_preview(output_parent=args.output_parent)
            if args.receipt:
                write_smoke_receipt(args.receipt, result)
        except Exception:
            safe_message("The synthetic preview could not be created. Please ask for help.", sys.stderr)
            return 1
        safe_message(json.dumps({"syntheticDemo": True, "readyForApply": False, "reviewFile": result["reviewFile"]}), sys.stdout)
        return 0
    try:
        launch()
    except (ImportError, RuntimeError):
        safe_message("The preview window could not be opened. Please use a supported desktop or ask for help.", sys.stderr)
        return 1
    except Exception:
        safe_message("The preview window could not be opened. Please use a supported desktop or ask for help.", sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
