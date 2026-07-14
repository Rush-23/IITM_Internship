"""
analyze_spoofing.py
-------------------
Full spoofing attack analyzer — tracks TWO correlation peaks separately
by accounting for hardware clock drift to show the true magnitude crossover.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import argparse
import os
import csv
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 2_046_000
CHIP_RATE        = 1_023_000
SAMPLES_PER_CHIP = SAMPLE_RATE // CHIP_RATE  # 2
CODE_PERIOD      = 1023
SAMPLES_PER_CODE = CODE_PERIOD * SAMPLES_PER_CHIP   # 2046


def generate_prn_chips(sv_id: int) -> np.ndarray:
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
    g2d = np.array([(g2f[(i+1023-(ta-1))%1023] ^ g2f[(i+1023-(tb-1))%1023])
                    for i in range(1023)], dtype=np.int8)
    return 1.0 - 2.0 * ((g1 ^ g2d) & 1).astype(np.float32)


def load_iq(path: str) -> np.ndarray:
    raw = np.fromfile(path, dtype=np.int8)
    if len(raw) % 2: raw = raw[:-1]
    return (raw[0::2].astype(np.float32) + 1j*raw[1::2].astype(np.float32)).astype(np.complex64)


def analyze(filepath: str, sv_id: int, window_ms: float,
            rx_lead_s: float, min_peak_sep: int,
            out_csv: str, out_plot: str):

    print(f"\n[Spoofing Analyzer] Loading {filepath} ...")
    if not os.path.exists(filepath):
        print(f"ERROR: {filepath} not found"); return

    iq = load_iq(filepath)
    print(f"  Total samples : {len(iq):,}  ({len(iq)/SAMPLE_RATE:.2f}s)")

    # PRN reference
    prn_chips   = generate_prn_chips(sv_id)
    prn_ups     = np.repeat(prn_chips, SAMPLES_PER_CHIP).astype(np.complex64)
    PRN_FFT_CONJ = np.conj(np.fft.fft(prn_ups))

    # Skip RX lead time
    skip = int(rx_lead_s * SAMPLE_RATE)
    iq_data = iq[skip:]

    n_codes_per_win  = max(1, round(window_ms))
    samples_per_win  = n_codes_per_win * SAMPLES_PER_CODE

    n_codes_total = len(iq_data) // SAMPLES_PER_CODE
    iq_trimmed    = iq_data[:n_codes_total * SAMPLES_PER_CODE]
    iq_matrix     = iq_trimmed.reshape(n_codes_total, SAMPLES_PER_CODE)

    print(f"  Running batch FFT ({n_codes_total} code periods) ...")
    SIG_FFT  = np.fft.fft(iq_matrix, axis=1)
    CORR_ALL = np.abs(np.fft.ifft(SIG_FFT * PRN_FFT_CONJ, axis=1))

    n_windows  = n_codes_total // n_codes_per_win
    CORR_WIN   = (CORR_ALL[:n_windows * n_codes_per_win]
                  .reshape(n_windows, n_codes_per_win, SAMPLES_PER_CODE)
                  .mean(axis=1))
    CORR_CHIPS = (CORR_WIN
                  .reshape(n_windows, CODE_PERIOD, SAMPLES_PER_CHIP)
                  .max(axis=2))

    timestamps = np.arange(n_windows) * samples_per_win / SAMPLE_RATE

    # ── 1. Find initial chip positions ────────────────────────────────────────
    # Clock chain eliminates drift — peaks are stationary.
    n_init    = min(20, n_windows // 4)
    tx1_chip  = int(np.argmax(CORR_CHIPS[:n_init].mean(axis=0)))
    tx2_chip  = tx1_chip   # Spoofer starts phase-aligned (START_OFFSET_CHIPS = 0)

    print(f"  Clock chain active — peaks are stationary (no drift correction needed)")
    print(f"  TX1 (Legit) initial chip: {tx1_chip}")
    print(f"  TX2 (Spoof) starts aligned at chip: {tx2_chip}")
    print(f"  Tracking both peaks with ±6 chip local window...")

    # ── 2. Track Both Signals with Stationary Local Search ───────────────────
    peak_a_idx  = np.zeros(n_windows, dtype=int)
    peak_a_mag  = np.zeros(n_windows)
    peak_b_idx  = np.zeros(n_windows, dtype=int)
    peak_b_mag  = np.zeros(n_windows)

    search_bw = 6   # ±6 chips — enough for USB jitter, not for 200 chips/sec drift

    pos_a = float(tx1_chip)
    pos_b = float(tx2_chip)

    for i, t in enumerate(timestamps):
        row = CORR_CHIPS[i]

        # Track Peak A (TX1 Legit) locally
        best_a_val = -1.0
        best_a_idx = round(pos_a)
        for offset in range(-search_bw, search_bw + 1):
            idx = (round(pos_a) + offset) % CODE_PERIOD
            val = float(row[idx])
            if val > best_a_val:
                best_a_val = val
                best_a_idx = idx
        pos_a = float(best_a_idx)
        peak_a_idx[i] = best_a_idx
        peak_a_mag[i] = best_a_val

        # Track Peak B (TX2 Spoof) locally
        # After capture (spoofer drag), peak B drifts slowly away from peak A
        best_b_val = -1.0
        best_b_idx = round(pos_b)
        for offset in range(-search_bw, search_bw + 1):
            idx = (round(pos_b) + offset) % CODE_PERIOD
            val = float(row[idx])
            if val > best_b_val:
                best_b_val = val
                best_b_idx = idx
        pos_b = float(best_b_idx)
        peak_b_idx[i] = best_b_idx
        peak_b_mag[i] = best_b_val

    # Capture crossover detection
    # Crossover occurs when the spoofer's peak magnitude exceeds the legit peak magnitude
    start_search = min(n_windows - 1, int(4.0 / (samples_per_win / SAMPLE_RATE)))
    crossover_t  = None
    for i in range(start_search, n_windows):
        # We check a small window forward to verify it's a true crossover, not noise
        if peak_b_mag[i] > peak_a_mag[i] and i+5 < n_windows and np.mean(peak_b_mag[i:i+5]) > np.mean(peak_a_mag[i:i+5]):
            crossover_t = timestamps[i]
            print(f"  Capture crossover detected at t = {crossover_t:.2f}s")
            break
            
    if crossover_t is None:
        print("  No crossover detected (TX2 may not have exceeded TX1 yet)")

    # Save CSV
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s","peak_a_mag","peak_a_chip",
                              "peak_b_mag","peak_b_chip","stronger"])
        for i in range(n_windows):
            stronger = "TX1" if peak_a_mag[i] >= peak_b_mag[i] else "TX2-spoofer"
            w.writerow([f"{timestamps[i]:.4f}",
                        f"{peak_a_mag[i]:.1f}", int(peak_a_idx[i]),
                        f"{peak_b_mag[i]:.1f}", int(peak_b_idx[i]),
                        stronger])
    print(f"  CSV: {out_csv}")

    # ── Plots ─────────────────────────────────────────────────────────────────
    BG = "#0d1117"
    fig = plt.figure(figsize=(15, 14))
    fig.patch.set_facecolor(BG)
    gs  = gridspec.GridSpec(4, 1, figure=fig, hspace=0.45)
    axs = [fig.add_subplot(gs[i]) for i in range(4)]
    for ax in axs:
        ax.set_facecolor(BG)
        ax.tick_params(colors="#aaaaaa")
        for sp in ax.spines.values(): sp.set_color("#333333")
        ax.xaxis.label.set_color("#aaaaaa")
        ax.yaxis.label.set_color("#aaaaaa")

    def draw_vline(ax):
        if crossover_t:
            ax.axvline(crossover_t, color="#ffff00", ls="--", lw=1.5,
                       label=f"Capture at t={crossover_t:.1f}s")

    # Plot 1: Correlation Magnitudes
    axs[0].plot(timestamps, peak_a_mag, color="#00d4ff", lw=1.5, label="Peak A (TX1 Legit)")
    axs[0].plot(timestamps, peak_b_mag, color="#ff6b35", lw=1.5, label="Peak B (TX2 Spoof)")
    draw_vline(axs[0])
    axs[0].set_title("Correlation Peak Magnitudes — Orange crossing above Blue = CAPTURED", color="white")
    axs[0].set_ylabel("Peak Magnitude", color="#aaaaaa")
    axs[0].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=9)

    # Plot 2: Chip Offsets
    axs[1].plot(timestamps, peak_a_idx, color="#00d4ff", lw=1.5, label="TX1 Legit chip")
    axs[1].plot(timestamps, peak_b_idx, color="#ff6b35", lw=1.5, label="TX2 Spoof chip")
    draw_vline(axs[1])
    axs[1].set_title("Chip Offset vs Time — Orange splitting and drifting in Phase 3 = DRAGGED", color="white")
    axs[1].set_ylabel("Chip Offset (0-1022)", color="#aaaaaa")
    axs[1].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=9)

    # Plot 3: Waterfall
    extent = [0, CODE_PERIOD-1, float(timestamps[-1]), float(timestamps[0])]
    im = axs[2].imshow(CORR_CHIPS, aspect="auto", cmap="inferno", extent=extent)
    plt.colorbar(im, ax=axs[2], label="Corr Mag", fraction=0.03)
    axs[2].plot(peak_a_idx, timestamps, color="#00d4ff", lw=1.0, ls=":", alpha=0.8)
    axs[2].plot(peak_b_idx, timestamps, color="#ff6b35", lw=1.0, ls=":", alpha=0.8)
    if crossover_t:
        axs[2].axhline(crossover_t, color="#ffff00", ls="--", lw=1.0)
    axs[2].set_title("Waterfall — Ridges overlapping first, then splitting and drifting right", color="white")
    axs[2].set_xlabel("Chip Offset", color="#aaaaaa")
    axs[2].set_ylabel("Time (s)", color="#aaaaaa")

    # Plot 4: Magnitude Difference (TX2 - TX1)
    diff = peak_b_mag - peak_a_mag
    axs[3].fill_between(timestamps, diff, where=(diff >= 0), color="#ff6b35", alpha=0.7, label="TX2 stronger (spoofed)")
    axs[3].fill_between(timestamps, diff, where=(diff < 0), color="#00d4ff", alpha=0.7, label="TX1 stronger (legit)")
    axs[3].plot(timestamps, diff, color="white", lw=0.8)
    axs[3].axhline(0, color="white", ls="--", lw=0.8)
    draw_vline(axs[3])
    axs[3].set_title("Attack Phase: Power Margin (TX2 - TX1)", color="white")
    axs[3].set_ylabel("Mag Difference", color="#aaaaaa")
    axs[3].set_xlabel("Time (s)", color="#aaaaaa")
    axs[3].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=9)

    for ax in axs[:-1]:
        ax.set_xlabel("Time (s)", color="#aaaaaa")

    title = f"GPS Spoofing Attack — Aligned Analysis | PRN SV{sv_id} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    fig.suptitle(title, color="white", fontsize=13, y=0.99, fontweight="bold")
    plt.savefig(out_plot, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"  Plot saved: {out_plot}")
    plt.show()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--file",       type=str,   default="rx_capture.bin")
    p.add_argument("--prn",        type=int,   default=1)
    p.add_argument("--window_ms",  type=float, default=5.0)
    p.add_argument("--rx_lead",    type=float, default=5.0,  help="Seconds of RX lead to skip (must match RX_LEAD_S in run_experiment.py)")
    p.add_argument("--min_sep",    type=int,   default=10)
    p.add_argument("--out_csv",    type=str,   default="spoofing_results.csv")
    p.add_argument("--out_plot",   type=str,   default="spoofing_analysis.png")
    args = p.parse_args()

    analyze(args.file, args.prn, args.window_ms, args.rx_lead, args.min_sep, args.out_csv, args.out_plot)


if __name__ == "__main__":
    main()
