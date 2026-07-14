"""
receiver_dll.py
---------------
Simulates a GPS receiver DLL (Delay Lock Loop) tracking the received signal.
Supports re-acquisition scanning to track fast-drifting hardware peaks.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os, sys, csv
import argparse
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 2_046_000
CHIP_RATE        = 1_023_000
SAMPLES_PER_CHIP = SAMPLE_RATE // CHIP_RATE  # 2
CODE_PERIOD      = 1023
SAMPLES_PER_CODE = CODE_PERIOD * SAMPLES_PER_CHIP  # 2046
CHIP_TO_METERS   = 293.0


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
    g1=lfsr([3,10]); g2f=lfsr([2,3,6,8,9,10])
    ta,tb=G2_TAPS[sv_id]
    g2d=np.array([(g2f[(i+1023-(ta-1))%1023]^g2f[(i+1023-(tb-1))%1023])
                  for i in range(1023)],dtype=np.int8)
    return 1.0-2.0*((g1^g2d)&1).astype(np.float32)


def load_iq(path):
    raw = np.fromfile(path, dtype=np.int8)
    if len(raw) % 2: raw = raw[:-1]
    return (raw[0::2].astype(np.float32)
            + 1j*raw[1::2].astype(np.float32)).astype(np.complex64)


def correlation_waterfall(iq_data, sv_id, n_codes_per_win):
    prn  = generate_prn(sv_id)
    prn_up = np.repeat(prn, SAMPLES_PER_CHIP).astype(np.complex64)
    PCONJ  = np.conj(np.fft.fft(prn_up))
    n_codes = len(iq_data) // SAMPLES_PER_CODE
    mat  = iq_data[:n_codes*SAMPLES_PER_CODE].reshape(n_codes, SAMPLES_PER_CODE)
    print(f"  Batch FFT: {n_codes} code periods ...")
    CORR = np.abs(np.fft.ifft(np.fft.fft(mat, axis=1) * PCONJ, axis=1))
    n_win = n_codes // n_codes_per_win
    CW   = (CORR[:n_win*n_codes_per_win]
            .reshape(n_win, n_codes_per_win, SAMPLES_PER_CODE)
            .mean(axis=1))
    return CW.reshape(n_win, CODE_PERIOD, SAMPLES_PER_CHIP).max(axis=2)


def run_dll(CORR_CHIPS, tx1_chip, timestamps, gain, spacing, bw_chips):
    """
    Runs the DLL tracking loop with re-acquisition fallback search.
    If the peak drops below a threshold (noise), it searches a local window.
    """
    tau = float(tx1_chip)
    tracked = []
    prompt = []
    disc_hist = []
    
    # With shared clock chain, the peak is now stationary — no large drift expected.
    # Use a small ±bw_chips local search window only to handle minor jitter.
    # Noise floor = median of the lower half of all correlation values.
    # Using global mean is wrong when TX2 is very strong (it pulls the mean up).
    flat = CORR_CHIPS.flatten()
    noise_floor = np.median(flat[flat < np.percentile(flat, 50)])
    lock_threshold = noise_floor * 3.0
    print(f"  Noise floor: {noise_floor:.1f}  Lock threshold: {lock_threshold:.1f}")

    for i, row in enumerate(CORR_CHIPS):
        # Small local search window to handle minor USB jitter (not 200 chips/sec drift)
        best_val = -1.0
        best_idx = round(tau)
        for offset in range(-round(bw_chips), round(bw_chips) + 1):
            idx = (round(tau) + offset) % CODE_PERIOD
            val = float(row[idx])
            if val > best_val:
                best_val = val
                best_idx = idx
        if best_val > lock_threshold:
            tau = float(best_idx)
        P = best_val

        # Early/Late measurements
        E = float(row[round(tau - spacing/2) % CODE_PERIOD])
        L = float(row[round(tau + spacing/2) % CODE_PERIOD])
        
        # Discriminator
        d = (E - L) / (E + L) if (E + L) > 1e-6 else 0.0
        
        # Update tau
        tau = (tau - gain * d) % CODE_PERIOD
        
        # Save history
        tracked.append(tau)
        prompt.append(P)
        disc_hist.append(d)

    tracked = np.array(tracked)
    prompt  = np.array(prompt)
    disc    = np.array(disc_hist)

    # Position error (circular wrap)
    raw = tracked - tx1_chip
    err_chips = np.where(raw > CODE_PERIOD/2, raw-CODE_PERIOD,
                np.where(raw < -CODE_PERIOD/2, raw+CODE_PERIOD, raw))
    err_m = err_chips * CHIP_TO_METERS

    # Lock transfer detection
    lock_t = None
    for i in range(10, len(tracked)):
        if abs(err_chips[i]) > 1.5 and i+3 < len(tracked) and abs(err_chips[i+3]) > 1.5:
            lock_t = timestamps[i]
            break

    return tracked, prompt, disc, err_chips, err_m, lock_t


def _style(ax):
    ax.set_facecolor("#0d1117")
    ax.tick_params(colors="#aaaaaa")
    for sp in ax.spines.values(): sp.set_color("#333333")
    ax.xaxis.label.set_color("#aaaaaa")
    ax.yaxis.label.set_color("#aaaaaa")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="GPS DLL simulator with re-lock search")
    p.add_argument("--file",       type=str,   default="rx_capture.bin")
    p.add_argument("--prn",        type=int,   default=1)
    p.add_argument("--window_ms",  type=float, default=5.0)
    p.add_argument("--rx_lead",    type=float, default=5.0,  help="Seconds of RX lead to skip (must match RX_LEAD_S in run_experiment.py)")
    p.add_argument("--dll_bw",     type=float, default=2.0,  help="Local search window width in chips (small — no clock drift)")
    p.add_argument("--gain",       type=float, default=0.3,  help="DLL loop gain")
    p.add_argument("--el_spacing", type=float, default=0.5,  help="Early-Late spacing in chips (tight — stable signal)")
    p.add_argument("--out_plot",   type=str,   default="dll_tracking.png")
    p.add_argument("--out_csv",    type=str,   default="dll_results.csv")
    args = p.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: {args.file} not found. Run run_rx.py first."); sys.exit(1)

    print(f"\n{'='*55}")
    print(f"  GPS Receiver DLL Simulation")
    print(f"  File : {args.file}")
    print(f"  DLL  : BW=+-{args.dll_bw} chips  Gain={args.gain}  Spacing={args.el_spacing}")
    print(f"{'='*55}\n")

    iq      = load_iq(args.file)
    skip    = int(args.rx_lead * SAMPLE_RATE)
    iq_data = iq[skip:]
    print(f"  Loaded {len(iq):,} samples ({len(iq)/SAMPLE_RATE:.1f}s). Skipping {args.rx_lead}s lead.")

    n_codes_per_win = max(1, round(args.window_ms))
    CORR_CHIPS      = correlation_waterfall(iq_data, args.prn, n_codes_per_win)
    n_windows       = CORR_CHIPS.shape[0]
    timestamps      = np.arange(n_windows) * n_codes_per_win * SAMPLES_PER_CODE / SAMPLE_RATE

    # TX1 true chip position = peak in first few windows
    n_init    = min(20, n_windows//4)
    tx1_chip  = int(np.argmax(CORR_CHIPS[:n_init].mean(axis=0)))
    print(f"  TX1 initial chip offset: {tx1_chip}")

    print(f"  Running DLL on {n_windows} windows ...")
    tracked, prompt, disc, err_chips, err_m, lock_t = run_dll(
        CORR_CHIPS, tx1_chip, timestamps, args.gain, args.el_spacing, args.dll_bw
    )

    if lock_t:
        print(f"  Lock transfer at t={lock_t:.2f}s")
        print(f"  Final position error: {abs(err_m[-1]):.0f} m ({abs(err_chips[-1]):.2f} chips)")
        print(f"  STATUS: SPOOFING SUCCESSFUL")
    else:
        print(f"  No lock transfer detected.")

    # ── Save CSV ──────────────────────────────────────────────────────────────
    with open(args.out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_s","tracked_chip","prompt_mag","discriminator",
                    "err_chips","err_m","status"])
        for i,t in enumerate(timestamps):
            st = "SPOOFED" if lock_t and t>=lock_t else "LEGIT"
            w.writerow([f"{t:.3f}", f"{tracked[i]:.2f}", f"{prompt[i]:.1f}",
                        f"{disc[i]:.4f}", f"{err_chips[i]:.3f}", f"{err_m[i]:.1f}", st])
    print(f"  CSV: {args.out_csv}")

    # ── Plot ──────────────────────────────────────────────────────────────────
    BG  = "#0d1117"
    fig = plt.figure(figsize=(15, 16))
    fig.patch.set_facecolor(BG)
    gs  = gridspec.GridSpec(5, 1, figure=fig, hspace=0.5)
    axs = [fig.add_subplot(gs[i]) for i in range(5)]
    for ax in axs: _style(ax)

    def vline(ax):
        if lock_t: ax.axvline(lock_t, color="#ffff00", ls="--", lw=1.5,
                              label=f"Lock transfer t={lock_t:.1f}s")

    # 1. DLL tracked chip offset
    axs[0].axhline(tx1_chip, color="#00d4ff", ls="--", lw=1, alpha=0.7,
                   label=f"TX1 true position (chip {tx1_chip})")
    axs[0].plot(timestamps, tracked, color="#ff6b35", lw=1.5, label="DLL tracked")
    axs[0].fill_between(timestamps, tx1_chip-0.5, tx1_chip+0.5,
                        alpha=0.15, color="#00d4ff", label="TX1 lock zone")
    vline(axs[0])
    axs[0].set_title("DLL Tracked Chip — Orange leaving blue = SPOOFED", color="white")
    axs[0].set_ylabel("Chip Offset", color="#aaaaaa")
    axs[0].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=9)

    # 2. Prompt correlator magnitude
    axs[1].plot(timestamps, prompt, color="#7fff7f", lw=1.2)
    axs[1].fill_between(timestamps, prompt, alpha=0.15, color="#7fff7f")
    vline(axs[1])
    axs[1].set_title("Prompt Correlator Magnitude (what receiver sees at tracked position)",
                     color="white")
    axs[1].set_ylabel("Magnitude", color="#aaaaaa")

    # 3. Discriminator error
    axs[2].plot(timestamps, disc, color="#ff9900", lw=1.0)
    axs[2].axhline(0, color="white", lw=0.7, ls="--")
    vline(axs[2])
    axs[2].set_title("DLL Discriminator Error — nonzero = being pulled by a signal",
                     color="white")
    axs[2].set_ylabel("Early-Late Error", color="#aaaaaa")

    # 4. Position error
    spoofed = np.abs(err_chips) > 1.0
    axs[3].fill_between(timestamps, err_m,
                        where=~spoofed, alpha=0.7, color="#00d4ff", label="Tracking TX1")
    axs[3].fill_between(timestamps, err_m,
                        where=spoofed,  alpha=0.7, color="#ff4444", label="SPOOFED")
    axs[3].plot(timestamps, err_m, color="white", lw=0.8)
    axs[3].axhline(0, color="#00d4ff", ls="--", lw=0.8, alpha=0.5)
    vline(axs[3])
    axs[3].set_title("Receiver Position ERROR vs TX1 True Position",
                     color="white")
    axs[3].set_ylabel("Error (m)", color="#aaaaaa")
    axs[3].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=9)

    # 5. Waterfall + DLL path overlay
    extent = [0, CODE_PERIOD-1, float(timestamps[-1]), float(timestamps[0])]
    im = axs[4].imshow(CORR_CHIPS, aspect="auto", cmap="inferno",
                       extent=extent, interpolation="nearest")
    plt.colorbar(im, ax=axs[4], label="Corr Mag", fraction=0.03)
    axs[4].plot(tracked, timestamps, color="#00ff88", lw=1.5, label="DLL path")
    axs[4].axvline(tx1_chip, color="#00d4ff", ls="--", lw=0.8, alpha=0.7)
    if lock_t: axs[4].axhline(lock_t, color="#ffff00", ls="--", lw=1.0)
    axs[4].set_title("Waterfall + DLL Path — green line leaving TX1 ridge = captured",
                     color="white")
    axs[4].set_xlabel("Chip Offset", color="#aaaaaa")
    axs[4].set_ylabel("Time (s)", color="#aaaaaa")
    axs[4].legend(facecolor="#1a1f2e", labelcolor="white", fontsize=8)

    for ax in axs[:-1]: ax.set_xlabel("Time (s)", color="#aaaaaa")

    final = f"Final position error: {abs(err_m[-1]):.0f} m  ({abs(err_chips[-1]):.2f} chips)"
    fig.text(0.5, 0.005, final, ha="center", color="#ffaa00",
             fontsize=11, fontweight="bold")

    fig.suptitle(
        f"GPS Spoofing — DLL Receiver Simulation | PRN SV{args.prn} | "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        color="white", fontsize=13, y=0.995, fontweight="bold"
    )

    plt.savefig(args.out_plot, dpi=150, bbox_inches="tight", facecolor=BG)
    print(f"  Plot: {args.out_plot}")
    plt.show()


if __name__ == "__main__":
    main()
