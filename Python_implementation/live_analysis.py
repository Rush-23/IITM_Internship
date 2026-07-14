"""
live_analysis.py
----------------
Runs a real-time DLL tracking loop on the live RX HackRF stream
WHILE TX1 and TX2 are transmitting.

Shows a live updating plot of:
  - Correlation peak position (chip offset) over time
  - DLL discriminator error
  - Position error in metres

This makes the post-processing visual happen DURING the experiment.

Run AFTER starting run_experiment.py in another terminal.
Or pipe hackrf_transfer stdout directly:
  hackrf_transfer -d <RX_SERIAL> -r - -f 1575420000 -s 2046000 -l 40 -g 32 | python live_analysis.py

Requirements: pip install matplotlib numpy
"""

import numpy as np
import sys
import time
import threading
import collections
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os

# ── Settings ──────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 2_046_000
CHIP_RATE        = 1_023_000
SAMPLES_PER_CHIP = SAMPLE_RATE // CHIP_RATE        # 2
CODE_PERIOD      = 1023
SAMPLES_PER_CODE = CODE_PERIOD * SAMPLES_PER_CHIP  # 2046
CHIP_TO_METRES   = 293.0

PRN_SV           = 1           # Which GPS PRN to track
CODES_PER_WINDOW = 5           # 5ms integration window
WINDOW_SIZE      = CODES_PER_WINDOW * SAMPLES_PER_CODE
DLL_GAIN         = 0.3
EL_SPACING       = 0.5
SEARCH_BW        = 50          # ±50 chip search — large enough to follow 30-chip drag
                               # (2 chips/sec drift × 5ms window = 0.01 chips/window, but
                               #  initial lock may be off by up to ±50 chips from noise)
HISTORY_S        = 40          # Seconds of history to display
MAX_WINDOWS      = HISTORY_S * SAMPLE_RATE // WINDOW_SIZE

# ── Input mode ───────────────────────────────────────────────────────────────
# Mode 1: python live_analysis.py rx_capture.bin   → read finished file
# Mode 2: python live_analysis.py --live            → tail rx_capture.bin as it grows
# Mode 3: hackrf_transfer -r - ... | python live_analysis.py  → stdin pipe (Linux/cmd only)

if len(sys.argv) > 1 and sys.argv[1] == "--live":
    USE_FILE   = False
    TAIL_FILE  = True
    INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rx_capture.bin")
elif len(sys.argv) > 1:
    USE_FILE   = True
    TAIL_FILE  = False
    INPUT_FILE = sys.argv[1]
else:
    USE_FILE   = False
    TAIL_FILE  = False   # stdin pipe mode
    INPUT_FILE = None

# ── PRN Gold Code Generator ───────────────────────────────────────────────────
def generate_prn(sv_id):
    G2_TAPS = {
        1:(2,6),2:(3,7),3:(4,8),4:(5,9),5:(1,9),6:(2,10),7:(1,8),
        8:(2,9),9:(3,10),10:(2,3),11:(3,4),12:(5,6),13:(6,7),14:(7,8),
        15:(8,9),16:(9,10),17:(1,4),18:(2,5),19:(3,6),20:(4,7),
        21:(5,8),22:(6,9),23:(1,3),24:(4,6),25:(5,7),26:(6,8),
        27:(7,9),28:(8,10),29:(1,6),30:(2,7),31:(3,8),32:(4,9),
    }
    def lfsr(taps, n=1023):
        reg=[1]*10; out=[]
        for _ in range(n):
            out.append(reg[-1])
            fb=0
            for t in taps: fb^=reg[t-1]
            reg=[fb]+reg[:-1]
        return np.array(out, dtype=np.int8)
    g1  = lfsr([3,10])
    g2f = lfsr([2,3,6,8,9,10])
    ta, tb = G2_TAPS[sv_id]
    g2d = np.array([(g2f[(i+1023-(ta-1))%1023]^g2f[(i+1023-(tb-1))%1023])
                    for i in range(1023)], dtype=np.int8)
    return 1.0 - 2.0*((g1^g2d)&1).astype(np.float32)

# ── Pre-compute PRN FFT (done once) ──────────────────────────────────────────
PRN       = generate_prn(PRN_SV)
PRN_UP    = np.repeat(PRN, SAMPLES_PER_CHIP).astype(np.complex64)
PRN_CONJ  = np.conj(np.fft.fft(PRN_UP))

def correlate_window(iq_window):
    """
    Correlate one window of IQ samples against PRN.
    Returns 1023 correlation values (one per chip offset).
    """
    codes = iq_window[:CODES_PER_WINDOW * SAMPLES_PER_CODE]
    mat   = codes.reshape(CODES_PER_WINDOW, SAMPLES_PER_CODE)
    corr  = np.abs(np.fft.ifft(np.fft.fft(mat, axis=1) * PRN_CONJ, axis=1))
    avg   = corr.mean(axis=0)
    # Collapse 2 samples/chip to 1 value per chip
    return avg.reshape(CODE_PERIOD, SAMPLES_PER_CHIP).max(axis=1)

# ── Shared state (thread-safe via deques) ─────────────────────────────────────
lock           = threading.Lock()
timestamps_buf = collections.deque(maxlen=MAX_WINDOWS)
chip_buf       = collections.deque(maxlen=MAX_WINDOWS)
disc_buf       = collections.deque(maxlen=MAX_WINDOWS)
err_m_buf      = collections.deque(maxlen=MAX_WINDOWS)
init_chip      = [None]   # Set after first acquisition
tau_state      = [0.0]    # Current DLL code phase estimate

# ── Reader + DLL thread ───────────────────────────────────────────────────────
def reader_thread():
    if TAIL_FILE:
        # Wait for rx_capture.bin to appear (run_experiment.py creates it)
        print(f"[Reader] Waiting for {INPUT_FILE} to appear...")
        while not os.path.exists(INPUT_FILE):
            time.sleep(0.2)
        fh = open(INPUT_FILE, 'rb')
        print(f"[Reader] Tailing live file: {INPUT_FILE}")
    elif USE_FILE:
        fh = open(INPUT_FILE, 'rb')
        print(f"[Reader] Reading from file: {INPUT_FILE}")
    else:
        fh = sys.stdin.buffer
        print("[Reader] Reading from stdin pipe")

    raw_buf  = bytearray()
    t_start  = time.time()
    win_idx  = 0
    acquired = False
    stall_count = 0
    # Real-time window duration (how long each window represents in real life)
    WINDOW_DUR_S = CODES_PER_WINDOW * SAMPLES_PER_CODE / SAMPLE_RATE  # ~0.005s per window

    while True:
        needed = WINDOW_SIZE * 2
        chunk  = fh.read(needed - len(raw_buf))

        if not chunk:
            if TAIL_FILE:
                # File not done yet — wait for more data
                stall_count += 1
                if stall_count > 50:   # 5 seconds of no data
                    print("[Reader] No new data for 5s. Stream ended.")
                    break
                time.sleep(0.1)
                continue
            else:
                print("[Reader] Stream ended.")
                break

        stall_count = 0
        raw_buf.extend(chunk)
        if len(raw_buf) < needed:
            continue

        # Convert to complex IQ
        raw_arr = np.frombuffer(bytes(raw_buf[:needed]), dtype=np.int8)
        raw_buf  = raw_buf[needed:]
        iq_win   = (raw_arr[0::2].astype(np.float32)
                    + 1j * raw_arr[1::2].astype(np.float32)).astype(np.complex64)

        # Correlate
        corr = correlate_window(iq_win)

        # First window: acquire (find the dominant peak)
        if not acquired:
            init_chip[0] = int(np.argmax(corr))
            tau_state[0] = float(init_chip[0])
            acquired = True
            print(f"[DLL] Acquired at chip {init_chip[0]}")

        # ── Correct DLL order ───────────────────────────────────────────────────
        tau = tau_state[0]   # Read current DLL code phase estimate

        # Step 1: Measure E, L, P at CURRENT tau position
        P = float(corr[round(tau) % CODE_PERIOD])
        E = float(corr[round(tau - EL_SPACING / 2) % CODE_PERIOD])
        L = float(corr[round(tau + EL_SPACING / 2) % CODE_PERIOD])

        # Step 2: Compute discriminator (nonzero when peak is off-centre)
        discriminator = (E - L) / (E + L + 1e-9)

        # Step 3: Apply feedback to track the peak smoothly
        tau = (tau - DLL_GAIN * discriminator) % CODE_PERIOD

        # Step 4: Re-acquire only if signal is LOST (P drops below noise)
        # This is separate from normal tracking — do NOT do this every window.
        noise_floor = corr.mean()
        if P < noise_floor * 2.5:
            # Signal lost — search \u00b1SEARCH_BW chips from current position
            best_val, best_idx = -1.0, round(tau) % CODE_PERIOD
            for offset in range(-SEARCH_BW, SEARCH_BW + 1):
                idx = (round(tau) + offset) % CODE_PERIOD
                v = float(corr[idx])
                if v > best_val:
                    best_val, best_idx = v, idx
            if best_val > noise_floor * 2.5:
                tau = float(best_idx)
                discriminator = 0.0   # Reset discriminator after re-lock

        tau_state[0] = tau

        # Compute position error relative to initial chip
        raw_err = tau - init_chip[0]
        if raw_err > CODE_PERIOD / 2:   raw_err -= CODE_PERIOD
        elif raw_err < -CODE_PERIOD / 2: raw_err += CODE_PERIOD
        err_m = raw_err * CHIP_TO_METRES

        # Simulation time: how far into the experiment this window represents.
        # Using wall-clock time (time.time()) is WRONG when reading a completed
        # file — the reader runs at disk speed (~100ms for 37s of data) causing
        # all timestamps to be compressed into 0-0.1 seconds on the plot.
        t_now = win_idx * WINDOW_DUR_S

        with lock:
            timestamps_buf.append(t_now)
            chip_buf.append(tau)
            disc_buf.append(discriminator)
            err_m_buf.append(err_m)

        win_idx += 1

        # ── Rate-limit to real time ─────────────────────────────────────────
        # Slows down file reading so the animation plot updates smoothly.
        # Without this the reader finishes in <1s and only 1-2 frames are drawn.
        if USE_FILE or TAIL_FILE:
            expected_wall = win_idx * WINDOW_DUR_S
            elapsed_wall  = time.time() - t_start
            if elapsed_wall < expected_wall:
                time.sleep(expected_wall - elapsed_wall)

    if USE_FILE:
        fh.close()


# ── Live plot ─────────────────────────────────────────────────────────────────
BG = "#0d1117"
fig, axes = plt.subplots(3, 1, figsize=(14, 9), facecolor=BG)
fig.suptitle(f"LIVE GPS DLL Tracking — PRN SV{PRN_SV} | "
             f"{SAMPLE_RATE/1e6:.3f} Msps | "
             f"Gain={DLL_GAIN}  EL={EL_SPACING}chips",
             color="white", fontsize=12, fontweight="bold")

for ax in axes:
    ax.set_facecolor(BG)
    ax.tick_params(colors="#aaaaaa")
    for sp in ax.spines.values(): sp.set_color("#333333")

axes[0].set_ylabel("Chip Offset", color="#aaaaaa")
axes[0].set_title("DLL Tracked Code Phase — Flat = locked, Drifting = being dragged",
                  color="white", fontsize=9)
axes[1].set_ylabel("Discriminator", color="#aaaaaa")
axes[1].set_title("E-L Discriminator — Persistent nonzero = spoofer pulling",
                  color="white", fontsize=9)
axes[2].set_ylabel("Position Error (m)", color="#aaaaaa")
axes[2].set_title("Injected Position Error — Grows during drag phase",
                  color="white", fontsize=9)
axes[2].set_xlabel("Time (s)", color="#aaaaaa")

line_chip, = axes[0].plot([], [], color="#ff6b35", lw=1.5)
line_disc, = axes[1].plot([], [], color="#ff9900", lw=1.0, alpha=0.8)
line_err,  = axes[2].plot([], [], color="#ff3344", lw=1.5)
hline_zero = axes[2].axhline(0, color="#00d4ff", ls="--", lw=0.7, alpha=0.5)

def init_plot():
    for line in [line_chip, line_disc, line_err]:
        line.set_data([], [])
    return line_chip, line_disc, line_err

def update_plot(_frame):
    with lock:
        if len(timestamps_buf) < 2:
            return line_chip, line_disc, line_err
        ts   = list(timestamps_buf)
        chip = list(chip_buf)
        disc = list(disc_buf)
        errm = list(err_m_buf)

    line_chip.set_data(ts, chip)
    line_disc.set_data(ts, disc)
    line_err.set_data(ts, errm)

    for ax, data in [(axes[0], chip), (axes[1], disc), (axes[2], errm)]:
        ax.set_xlim(max(0, ts[-1] - HISTORY_S), ts[-1] + 1)
        margin = max(1.0, (max(data) - min(data)) * 0.15)
        ax.set_ylim(min(data) - margin, max(data) + margin)

    # Annotate current position error
    axes[2].set_title(
        f"Injected Position Error — Current: {errm[-1]:+.0f} m  ({errm[-1]/CHIP_TO_METRES:+.2f} chips)",
        color="white", fontsize=9)

    return line_chip, line_disc, line_err

# ── Start reader thread ───────────────────────────────────────────────────────
t = threading.Thread(target=reader_thread, daemon=True)
t.start()

print("[Live Analysis] Starting. Waiting for first acquisition...")

ani = animation.FuncAnimation(fig, update_plot, init_func=init_plot,
                              interval=200, blit=True, cache_frame_data=False)
plt.tight_layout(rect=[0, 0, 1, 0.95])
plt.show()
