"""
generate_waveform.py  — TX1 (Legitimate Signal)
------------------------------------------------
Generates tx1.bin: fixed-power PRN1 waveform for the legitimate transmitter.
Just run it: python generate_waveform.py
No arguments needed.
"""

import numpy as np
import os

# ── Settings ──────────────────────────────────────────────────────────────────
SV_ID       = 1       # GPS PRN satellite ID (1-32)
DURATION_S  = 30      # seconds of waveform
AMPLITUDE   = 30      # Lowered from 80 to 40 so the spoofer can physically overpower it
OUTPUT_FILE = "tx1.bin"

# ── Constants ───────────────────────────────────────────────────────────────
SAMPLE_RATE      = 2_046_000   # MUST match hackrf_transfer -s argument exactly
CHIP_RATE        = 1_023_000
SAMPLES_PER_CHIP = SAMPLE_RATE // CHIP_RATE   # = 2 (correct for GPS L1 C/A at 2.046 Msps)
CODE_PERIOD      = 1023
SAMPLES_PER_CODE = CODE_PERIOD * SAMPLES_PER_CHIP  # = 2046


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


print(f"[TX1] Generating: SV{SV_ID}  {DURATION_S}s  amplitude={AMPLITUDE}")

n_samples = DURATION_S * SAMPLE_RATE
n_periods = -(-n_samples // SAMPLES_PER_CODE)   # ceiling division

chips     = generate_prn(SV_ID)
upsampled = np.repeat(np.tile(chips, n_periods), SAMPLES_PER_CHIP)[:n_samples]

i_int8 = np.clip(upsampled * AMPLITUDE, -127, 127).astype(np.int8)
q_int8 = np.zeros(n_samples, dtype=np.int8)

interleaved        = np.empty(2 * n_samples, dtype=np.int8)
interleaved[0::2]  = i_int8
interleaved[1::2]  = q_int8
interleaved.tofile(OUTPUT_FILE)

print(f"Done. {OUTPUT_FILE}  ({os.path.getsize(OUTPUT_FILE)/1e6:.0f} MB)")
