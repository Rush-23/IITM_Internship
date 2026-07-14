"""
run_rx.py  — RX PC
------------------
Records raw IQ from HackRF to rx_capture.bin.
Start this FIRST, then immediately run run_tx.py on the TX PC.

Just run it: python run_rx.py
"""

import subprocess
import os
import sys

# ── Full path to hackrf_transfer.exe ─────────────────────────────────────────
HACKRF_PATH = r"D:\IITM_INTERNSHIP_MATERIALS\GNU_RADIO\Library\bin\hackrf_transfer.exe"

# ── Your RX HackRF serial ────────────────────────────────────────────────────
RX_SERIAL   = "0000000000000000a32868dc344a9a47"

# ── Settings ──────────────────────────────────────────────────────────────────
OUTPUT_FILE    = "rx_capture.bin"
CENTER_FREQ_HZ = 1_575_420_000
SAMPLE_RATE    = 4_092_000
LNA_GAIN       = 40
VGA_GAIN       = 32
RECORD_SECS    = 35

# ─────────────────────────────────────────────────────────────────────────────

if not os.path.exists(HACKRF_PATH):
    print(f"ERROR: hackrf_transfer.exe not found at:\n  {HACKRF_PATH}")
    print("Update HACKRF_PATH at the top of this script.")
    sys.exit(1)

n_samples = RECORD_SECS * SAMPLE_RATE

cmd = [
    HACKRF_PATH,
    "-d", RX_SERIAL,
    "-r", OUTPUT_FILE,
    "-f", str(CENTER_FREQ_HZ),
    "-s", str(SAMPLE_RATE),
    "-l", str(LNA_GAIN),
    "-g", str(VGA_GAIN),
    "-n", str(n_samples),
]

print("=" * 55)
print("  GPS Spoofing RX - Recording")
print(f"  Serial : {RX_SERIAL[:16]}...")
print(f"  File   : {OUTPUT_FILE}")
print(f"  Freq   : {CENTER_FREQ_HZ/1e6:.3f} MHz")
print(f"  Gains  : LNA={LNA_GAIN}dB  VGA={VGA_GAIN}dB")
print(f"  Record : {RECORD_SECS}s")
print("=" * 55)
print()
print(">>> RX is RECORDING. Go run run_tx.py on TX PC NOW <<<")
print()

ret = subprocess.run(cmd)

if ret.returncode == 0:
    sz = os.path.getsize(OUTPUT_FILE)
    print(f"\nCapture complete: {OUTPUT_FILE}  ({sz/1e6:.0f} MB)")
    print(f"\nNext: python receiver_dll.py")
else:
    print(f"\nERROR: hackrf_transfer failed (code {ret.returncode})")
    sys.exit(1)
