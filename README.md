# 🛰️ GNSS Study, Real-Time Experimentation and Receiver Tracking Analysis

<div align="center">

### Internship Project

**Department of Electrical Engineering**  
**Indian Institute of Technology Madras**

**Author:** Rushil V  
B.E. Electronics and Communication Engineering  
SSN College of Engineering

![MATLAB](https://img.shields.io/badge/MATLAB-R2026a-orange?logo=mathworks)
![Python](https://img.shields.io/badge/Python-3.10-blue?logo=python)
![GNU Radio](https://img.shields.io/badge/GNU%20Radio-3.10-green)
![HackRF](https://img.shields.io/badge/SDR-HackRF-red)
![GPS](https://img.shields.io/badge/GNSS-GPS-success)
![Status](https://img.shields.io/badge/Status-Completed-brightgreen)

</div>

---

# 📖 Overview

This repository contains the complete implementation developed during my internship at the **Department of Electrical Engineering, Indian Institute of Technology Madras (IIT Madras)**.

The project investigates **Global Navigation Satellite Systems (GNSS)** with a focus on **GPS L1 C/A signal generation, receiver acquisition, tracking, spoofing, and real-time experimentation using Software Defined Radio (SDR)**.

Unlike a purely simulation-based project, this work combines **MATLAB**, **GNU Radio**, **HackRF One**, and **Python** to bridge theory and practical implementation.

---

# 🎯 Project Objectives

- Generate GPS L1 C/A signals.
- Simulate realistic GPS propagation channels.
- Perform FFT-based GPS signal acquisition.
- Implement Delay Lock Loop (DLL) and Frequency Lock Loop (FLL) tracking.
- Generate and inject spoofed GPS signals.
- Validate concepts using GNU Radio and HackRF One.
- Analyse real IQ recordings using Python.
- Study receiver behaviour during GPS spoofing attacks.

---

# 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| MATLAB | GPS signal generation, acquisition, tracking and spoofing simulation |
| Python | IQ data analysis, spoof detection and DLL analysis |
| GNU Radio | SDR transmit and receive flowgraphs |
| HackRF One | Real-time RF transmission and reception |
| BU-353N GPS Receiver | Receiver validation and experimentation |

---

# 📂 Repository Structure

```text
IITM_Internship/
│
├── MATLAB/
│   ├── stage1.m
│   ├── stage2.m
│   ├── stage3.m
│   ├── stage4.m
│   ├── stage5.m
│   ├── stage6.m
│   └── generate_gps_prn.m
│
├── Python/
│   ├── analyze_spoofing.py
│   ├── receiver_dll.py
│   └── requirements.txt
│
├── GNU_Radio/
│   ├── *.grc
│
├── Figures/
├── Sample_Data/
├── Report/
└── README.md
```

---

# 🚀 MATLAB Workflow

```text
Stage 1  → GPS Signal Generation
      ↓
Stage 2  → Channel Model
      ↓
Stage 3  → FFT-Based Acquisition
      ↓
Stage 4  → Acquisition Analysis
      ↓
Stage 5  → DLL/FLL Receiver Tracking
      ↓
Stage 6  → GPS Spoof Signal Injection
```

Each MATLAB stage generates a `.mat` file used as the input to the next stage.

---

# 🐍 Python Workflow

## analyze_spoofing.py

- Loads captured IQ data.
- Performs PRN correlation.
- Tracks authentic and spoofed correlation peaks.
- Detects spoofing capture events.
- Generates correlation, waterfall and power-margin plots.

## receiver_dll.py

- Simulates the behaviour of a GPS receiver Delay Lock Loop.
- Tracks code phase.
- Computes receiver position error.
- Detects lock transfer from the authentic signal to the spoofed signal.

---

# 📡 SDR Experimentation

The real-time experiments were carried out using:

- HackRF One SDR
- GNU Radio Companion
- GPS L1 C/A signal
- BPSK modulation
- Python-based IQ analysis

Experimental workflow:

```text
MATLAB Simulation
        │
        ▼
GNU Radio Flowgraphs
        │
        ▼
HackRF One Transmission
        │
        ▼
Real IQ Capture
        │
        ▼
Python Analysis
        │
        ▼
DLL Receiver Simulation
```

---

# 📊 Expected Outputs

Running this project produces:

- GPS signal generation plots
- Acquisition correlation surfaces
- Doppler search results
- DLL/FLL tracking performance
- GPS spoofing heatmaps
- SDR transmission and reception results
- Spoof capture analysis
- Receiver lock-transfer analysis
- Position error estimation

---

# ▶️ How to Run

## MATLAB

Execute the scripts in order:

1. stage1.m
2. stage2.m
3. stage3.m
4. stage4.m
5. stage5.m
6. stage6.m

## Python

Install dependencies:

```bash
pip install numpy scipy matplotlib
```

Run:

```bash
python analyze_spoofing.py
python receiver_dll.py
```

---

# 📄 Internship Report

**Title**

**GNSS Study, Real-Time Experimentation and Receiver Tracking Analysis**

Department of Electrical Engineering  
Indian Institute of Technology Madras

---

# 👨‍💻 Author

**Rushil V**

- B.E. Electronics and Communication Engineering
- SSN College of Engineering
- Internship at the Department of Electrical Engineering, IIT Madras

---

# 🙏 Acknowledgements

I sincerely thank my internship supervisor and the Department of Electrical Engineering, IIT Madras, for providing the opportunity, guidance, and resources required to carry out this work.

---

# 📜 License

This repository is intended for **academic, educational, and research purposes only**.
