%% =========================================================
%  STAGE 2: Realistic Channel Model
%  Applies code delay + Doppler shift + AWGN to s_tx
%  Output: r — the received signal seen by your GPS receiver
% ==========================================================

clear; clc; close all;

%% ---- Load Stage 1 output ----
load('stage1_output.mat');
% Imports: f_chip, f_s, f_IF, T_code, N_chips, samp_per_chip,
%          N_samp, t, prn_id, prn_code_chips, prn_upsampled,
%          nav_bit, s_baseband, s_tx, A_signal, phi_0

%% ---- Channel Parameters ----
% These are the TRUE values the receiver must estimate in Stage 3
% In a real scenario these are completely unknown to the receiver

% --- Code delay ---
% Represents signal travel time from satellite to receiver
% Real GPS: 67–86 ms travel time = 68,000–88,000 chip delays
% We simulate within ONE epoch (0–1022 chips) because PRN repeats every 1ms
% The receiver cannot distinguish delays beyond one epoch without extra logic

true_chip_delay  = 150.7;          % [chips] — fractional delay allowed
true_samp_delay  = round(true_chip_delay * samp_per_chip);  % Convert to samples
                                   % = round(150.7 × 10) = 1507 samples

% Physical meaning:
%   1 chip delay = 293 m of extra path length
%   150.7 chips  = 150.7 × 293 m ≈ 44.2 km of propagation distance variation

% --- Doppler frequency shift ---
% Caused by relative motion between satellite and receiver
% Satellite orbital speed ≈ 3.9 km/s → projects onto receiver LOS
% Maximum L1 Doppler ≈ ±4.2 kHz for stationary receiver
% Additional ±1 kHz possible from receiver clock drift

true_doppler_hz  = 1823.0;         % [Hz] — positive = satellite approaching
                                   % Stage 3 must search ±5000 Hz to find this

% Physical meaning:
%   f_received = f_transmitted × (1 + v_radial/c)
%   1823 Hz shift at 1575.42 MHz → radial velocity ≈ 347 m/s (satellite component)

% --- Signal power / SNR ---
% Real GPS signal at antenna: ≈ −130 dBm (extremely weak)
% Thermal noise floor at receiver: ≈ −110 dBm in 2 MHz bandwidth
% So raw pre-correlation SNR ≈ −20 dB (signal buried in noise)
% After 1ms coherent integration: processing gain = 10·log10(1023) ≈ 30 dB
% Post-correlation SNR ≈ +10 dB (detectable peak)

SNR_dB = -20;                      % Pre-correlation SNR [dB]
                                   % Signal is below noise floor — realistic

SNR_linear = 10^(SNR_dB/10);      % Convert to linear scale = 0.01

%% ---- Step 1: Apply Code Delay ----
% Circular shift of s_tx by true_samp_delay samples
% This simulates the signal arriving 'late' due to propagation

% Why circular shift?
%   We simulate exactly one PRN epoch (1ms)
%   PRN code is periodic — after 1023 chips it repeats
%   Circular shift correctly models a delayed but continuous PRN stream
%   In real receivers, the delay is tracked across epochs using DLL

s_delayed = circshift(s_tx, true_samp_delay);

% What this does at sample level:
%   Original s_tx:    [s(0),    s(1),    ..., s(10229)]
%   s_delayed:        [s(10230-1507), ..., s(0), s(1), ..., s(10229-1507)]
%   The code pattern is now shifted by 1507 samples = 150.7 chips

%% ---- Step 2: Apply Doppler Frequency Shift ----
% Doppler shifts both the carrier AND the chip rate
% Carrier Doppler: Δf_carrier = f_doppler (dominant effect)
% Code Doppler:    Δf_code = f_doppler × (f_chip/f_IF) ≈ tiny, often ignored in acquisition
% We apply carrier Doppler only (standard acquisition approximation)

% The Doppler-shifted signal:
%   r_doppler(t) = s_delayed(t) × exp(j·2π·f_d·t)   [complex form]
% For real signal:
%   r_doppler(t) = s_delayed(t) × cos(2π·f_d·t)  ← NOT correct
%   This approach would create sum and difference frequencies
%
% Correct approach: re-modulate at shifted carrier frequency
%   Original carrier: cos(2π·f_IF·t + φ₀)
%   Doppler carrier:  cos(2π·(f_IF + f_d)·t + φ₀)
%
% We rebuild the signal with the Doppler-shifted carrier

s_baseband_delayed = nav_bit * circshift(prn_upsampled, true_samp_delay);
carrier_doppler    = cos(2*pi*(f_IF + true_doppler_hz)*t + phi_0);
s_doppler          = A_signal * s_baseband_delayed .* carrier_doppler;

% Why rebuild instead of multiply by a Doppler sinusoid?
%   Multiplying s_delayed × cos(2π·f_d·t) creates:
%     cos(2π·f_IF·t) × cos(2π·f_d·t) = 0.5·cos(2π·(f_IF+f_d)·t) + 0.5·cos(2π·(f_IF-f_d)·t)
%   This creates two frequency components — incorrect
%   Rebuilding with (f_IF + f_d) is exact and clean

%% ---- Step 3: Add AWGN Noise ----
% Thermal noise is modeled as Additive White Gaussian Noise
% White: flat power spectral density across all frequencies
% Gaussian: amplitude follows normal distribution (Central Limit Theorem)
% This models Johnson-Nyquist thermal noise in receiver front-end

% Signal power (should be A_signal²/2 for sinusoidal carrier)
signal_power = mean(s_doppler .^ 2);   % Measured from the actual signal

% Noise power required to achieve target SNR
% SNR = signal_power / noise_power  →  noise_power = signal_power / SNR_linear
noise_power  = signal_power / SNR_linear;
noise_std    = sqrt(noise_power);       % Standard deviation of noise samples

% Generate AWGN
rng(42);    % Fixed random seed — makes results reproducible across runs
noise = noise_std * randn(1, N_samp);   % Gaussian noise, zero mean

% Received signal = delayed + Doppler-shifted signal + noise
r = s_doppler + noise;

% At this point r is what the GPS receiver ADC actually sees:
%   - PRN code pattern hidden inside
%   - Carrier at wrong frequency (f_IF + f_doppler)
%   - Code starting at wrong position (delayed by 150.7 chips)
%   - Everything buried under noise (SNR = -20 dB)
% The receiver has NO idea about any of these parameters

%% ---- Verification: Power Check ----
fprintf('\n--- Stage 2 Channel Model: Power Audit ---\n');
fprintf('Signal power (linear)  : %.6f\n', signal_power);
fprintf('Noise power  (linear)  : %.6f\n', noise_power);
fprintf('Measured SNR (dB)      : %.2f dB\n', 10*log10(signal_power/noise_power));
fprintf('Target  SNR            : %d dB\n',   SNR_dB);
fprintf('True code delay        : %.1f chips = %d samples\n', true_chip_delay, true_samp_delay);
fprintf('True Doppler           : %.1f Hz\n', true_doppler_hz);

%% ---- Visualization ----
figure('Name','Stage 2: Channel Effects','NumberTitle','off');

% Plot 1: Clean transmitted signal vs received (noise visible)
subplot(3,2,1);
plot_idx = 1:500;
plot(t(plot_idx)*1e6, s_tx(plot_idx), 'b', 'LineWidth', 1.0);
xlabel('Time [\mus]'); ylabel('Amplitude');
title('Clean Transmitted s_{tx}(t)'); grid on;

subplot(3,2,2);
plot(t(plot_idx)*1e6, r(plot_idx), 'r', 'LineWidth', 0.8);
xlabel('Time [\mus]'); ylabel('Amplitude');
title(sprintf('Received r(t) — SNR = %d dB', SNR_dB)); grid on;

% Plot 2: Frequency spectrum — Doppler shift visible
subplot(3,2,3);
NFFT = N_samp;
f_axis = (-NFFT/2 : NFFT/2-1) * (f_s/NFFT);
S_tx_fft = fftshift(abs(fft(s_tx,  NFFT)));
plot(f_axis/1e6, 20*log10(S_tx_fft + 1e-10), 'b', 'LineWidth', 1.0);
xlabel('Frequency [MHz]'); ylabel('Power [dB]');
title('Spectrum: Clean s_{tx} — Centered at f_{IF} = 4 MHz');
xlim([0 8]); grid on;

subplot(3,2,4);
S_r_fft = fftshift(abs(fft(r, NFFT)));
plot(f_axis/1e6, 20*log10(S_r_fft + 1e-10), 'r', 'LineWidth', 1.0);
xlabel('Frequency [MHz]'); ylabel('Power [dB]');
title(sprintf('Spectrum: Received r(t) — Doppler shifted by +%.0f Hz', true_doppler_hz));
xlim([0 8]); grid on;

% Plot 3: Code delay visualization via baseband cross-correlation
subplot(3,2,[5,6]);
% Strip carrier from received signal (multiply by local carrier at f_IF, no Doppler)
r_baseband_approx = r .* cos(2*pi*f_IF*t);   % Will have residual Doppler — intentional
chips_axis = (0:N_samp-1) / samp_per_chip;
[xcorr_vals, lags] = xcorr(r_baseband_approx, prn_upsampled, 'normalized');
lag_chips = lags / samp_per_chip;
plot(lag_chips, abs(xcorr_vals), 'k', 'LineWidth', 0.8);
xline(true_chip_delay, 'r--', sprintf('True delay: %.1f chips', true_chip_delay), ...
      'LineWidth', 1.5, 'LabelVerticalAlignment','bottom');
xlabel('Lag [chips]'); ylabel('|Correlation|');
title('Baseband Cross-Correlation (carrier stripped without Doppler — peak attenuated but visible)');
xlim([-100 N_chips+100]); grid on;

sgtitle('Stage 2: Channel Effects on GPS Signal', 'FontSize', 13, 'FontWeight', 'bold');

%% ---- Save Stage 2 Output ----
save('stage2_output.mat', ...
    'f_chip','f_s','f_IF','T_code','N_chips','samp_per_chip','N_samp','t', ...
    'prn_id','prn_code_chips','prn_upsampled','nav_bit','s_baseband','s_tx', ...
    'A_signal','phi_0', ...
    'true_chip_delay','true_samp_delay','true_doppler_hz', ...
    'SNR_dB','SNR_linear','noise_std','noise', ...
    's_delayed','s_doppler','r');

disp('Stage 2 complete. Received signal r(t) saved.');