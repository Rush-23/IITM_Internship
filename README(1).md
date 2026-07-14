# 🛰️ GNSS Study, Real-Time Experimentation and Receiver Tracking Analysis

<div align="center">

## MATLAB Implementation Repository

**Internship Project – Department of Electrical Engineering**  
**Indian Institute of Technology Madras**

Author: **Rushil V**  
B.E. Electronics and Communication Engineering  
SSN College of Engineering

![MATLAB](https://img.shields.io/badge/MATLAB-R2026a-orange?logo=mathworks)
![Platform](https://img.shields.io/badge/Platform-Windows-blue)
![Domain](https://img.shields.io/badge/Domain-GNSS%20%7C%20GPS-green)
![Focus](https://img.shields.io/badge/Focus-GPS%20Spoofing-red)

</div>

---

# 📖 Project Overview

This repository contains the complete MATLAB implementation developed during my internship at the **Department of Electrical Engineering, Indian Institute of Technology Madras (IIT Madras)**.

The project demonstrates the complete processing chain of a simplified **GPS L1 C/A receiver**, beginning with GPS signal generation and progressing through acquisition, tracking, and GPS spoofing analysis.

The implementation was developed as a **six-stage pipeline**, allowing each subsystem to be verified independently before integration into the complete receiver.

---

# 🎯 Objectives

- ✅ Generate GPS L1 C/A signals
- ✅ Simulate realistic GPS propagation channels
- ✅ Perform FFT-based satellite acquisition
- ✅ Implement DLL/FLL receiver tracking
- ✅ Generate and inject spoofed GPS signals
- ✅ Analyse spoofing effects on receiver acquisition and tracking

---

# 🗂 Repository Structure

```text
MATLAB/
│
├── stage1.m                  # GPS Signal Generation
├── stage2.m                  # Channel Model
├── stage3.m                  # Signal Acquisition
├── stage4.m                  # Acquisition Analysis
├── stage5.m                  # Receiver Tracking (DLL/FLL)
├── stage6.m                  # GPS Spoof Signal Injection
│
├── generate_gps_prn.m        # PRN Generator
│
├── stage1_output.mat
├── stage2_output.mat
├── stage3_output.mat
├── stage4_output.mat
├── stage5_output.mat
└── stage6_output.mat
```

---

# ⚙️ Software Requirements

| Requirement | Version |
|-------------|---------|
| MATLAB | R2024b or later *(Recommended: R2026a)* |
| Signal Processing Toolbox | Optional |
| Communications Toolbox | Optional |
| Parallel Computing Toolbox | Not Required |

---

# 🚀 Execution Pipeline

Run the scripts **in order**:

```text
Stage 1
   │
   ▼
Stage 2
   │
   ▼
Stage 3
   │
   ▼
Stage 4
   │
   ▼
Stage 5
   │
   ▼
Stage 6
```

Each stage generates a `.mat` file required by the next stage.

---

# 🧩 Stage Description

## 🟢 Stage 1 – GPS Signal Generation
Creates a simplified GPS L1 C/A signal by generating the PRN sequence, adding navigation data, and modulating it onto the carrier.

**Output:** `stage1_output.mat`

---

## 🔵 Stage 2 – Channel Model
Introduces:
- Code delay
- Doppler shift
- Additive White Gaussian Noise (AWGN)

to emulate a realistic satellite communication channel.

**Output:** `stage2_output.mat`

---

## 🟡 Stage 3 – Signal Acquisition
Performs FFT-based circular correlation across code phase and Doppler bins to estimate satellite parameters.

**Output:** `stage3_output.mat`

---

## 🟠 Stage 4 – Acquisition Analysis
Visualizes:
- Acquisition heatmaps
- Correlation peaks
- Code-phase estimates
- Doppler response

**Output:** `stage4_output.mat`

---

## 🔴 Stage 5 – Receiver Tracking
Implements:
- Delay Lock Loop (DLL)
- Frequency Lock Loop (FLL)

to maintain synchronization with the authentic GPS signal.

**Output:** `stage5_output.mat`

---

## 🟣 Stage 6 – GPS Spoof Signal Injection
Generates a counterfeit GPS signal with configurable:
- Code delay
- Doppler frequency
- Spoof power (0 dB, +6 dB, +15 dB)

The spoofed signal is combined with the authentic signal to study receiver behaviour during spoofing attacks.

**Output:** `stage6_output.mat`

---

# 📊 Expected Outputs

Running the project produces:

- 📈 GPS signal waveforms
- 📈 Acquisition correlation surfaces
- 📈 Doppler search plots
- 📈 DLL/FLL tracking responses
- 📈 Spoofing acquisition heatmaps
- 📈 Tracking performance analysis

These outputs correspond to the figures presented in the internship report.

---

# 📄 Related Report

**Title:**  
**GNSS Study, Real-Time Experimentation and Receiver Tracking Analysis**

Department of Electrical Engineering  
Indian Institute of Technology Madras

---

# 👨‍💻 Author

**Rushil V**

- B.E. Electronics and Communication Engineering
- SSN College of Engineering
- Internship at Indian Institute of Technology Madras

---

# 📝 Notes

- Run the stages sequentially.
- Do not delete intermediate `.mat` files.
- The implementation is intended for academic and research purposes.

---

# 📜 License

This repository is provided **for academic, educational, and research purposes only.**
