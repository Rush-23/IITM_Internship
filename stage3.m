%% =========================================================
%  STAGE 3: 2D Acquisition Engine (Parallel Code Phase Search)
%  Doppler × Code Delay search using FFT-based correlation
% ==========================================================

clear; clc; close all;

%% ---- Load Stage 2 output ----
load('stage2_output.mat');
% Key variables used here:
%   r              → received signal (10230 samples)
%   prn_upsampled  → local clean PRN replica (10230 samples)
%   t              → time vector
%   f_s, f_IF, N_samp, samp_per_chip, N_chips
%   true_chip_delay, true_doppler_hz  (for verification only)

%% ---- Doppler Search Grid ----
% Real GPS receivers search ±5 kHz in steps of 500 Hz
% Why 500 Hz step?
%   Coherent integration time = T_code = 1ms
%   Frequency resolution = 1/T_code = 1000 Hz (full 3dB bandwidth)
%   Safe bin spacing = 500 Hz → worst-case loss ≈ 3.9 dB (acceptable)
%   Using smaller steps increases accuracy but costs computation

doppler_step_hz  = 5;
doppler_bins_hz  = -5000 : doppler_step_hz : 5000;   % 21 bins
num_doppler_bins = length(doppler_bins_hz);

fprintf('Doppler search: %d bins from %d to %d Hz\n', ...
        num_doppler_bins, doppler_bins_hz(1), doppler_bins_hz(end));

%% ---- Pre-compute Local PRN FFT ----
% Cross-correlation via FFT:
%   xcorr(a,b) in freq domain = FFT(a) × conj(FFT(b))
% Pre-computing conj(FFT(prn)) outside the loop saves N_doppler_bins × N_samp
% multiplications — critical for real-time receivers

local_prn_fft_conj = conj(fft(prn_upsampled));   % [1 × N_samp], complex

%% ---- 2D Correlation Search ----
% For each Doppler bin:
%   1. Wipe off carrier at guessed (f_IF + f_d_guess) using complex exponential
%   2. FFT the baseband result
%   3. Multiply by conj(FFT(PRN)) → frequency-domain cross-correlation
%   4. IFFT → correlation values for ALL code delays simultaneously
%   5. Store magnitude squared (correlation power)

correlation_surface = zeros(num_doppler_bins, N_samp);   % [bins × samples]

for k = 1 : num_doppler_bins
    f_d_guess = doppler_bins_hz(k);

    % Step 1: Carrier wipe-off using complex exponential
    % exp(-j·2π·(f_IF + f_d)·t) simultaneously handles I and Q channels
    % Real receiver: separate I and Q mixers, then combined as I + jQ
    % This single line replaces both mixers mathematically
    local_carrier = exp(-1j * 2*pi * (f_IF + f_d_guess) * t);
    baseband      = r .* local_carrier;    % Carrier stripped → baseband

    % Step 2 & 3: FFT-based circular cross-correlation
    % All N_samp code delays evaluated in one FFT pair — O(N·logN) not O(N²)
    baseband_fft  = fft(baseband);
    corr_fft      = baseband_fft .* local_prn_fft_conj;

    % Step 4: Back to time domain — each sample = correlation at that delay
    corr_time     = ifft(corr_fft);

    % Step 5: Magnitude squared = correlation power (removes phase dependency)
    % Why magnitude squared and not magnitude?
    %   Removes carrier phase ambiguity (phi_0 unknown)
    %   I² + Q² = |complex correlation|² is phase-independent
    correlation_surface(k, :) = abs(corr_time) .^ 2;
end

%% ---- Normalize Correlation Surface ----
% Normalize so noise floor ≈ 1.0 everywhere
% This makes peak detection threshold physically meaningful
% and independent of signal amplitude or noise power

% Estimate noise floor: median of entire surface
% (median is robust — not skewed by the peak itself)
noise_floor_estimate = median(correlation_surface(:));
correlation_surface_norm = correlation_surface / noise_floor_estimate;

% After normalization:
%   Noise floor ≈ 1.0
%   True signal peak >> 1.0 (typically 20–100x above floor for SNR=-20dB after integration)

%% ---- Peak Detection ----
% Find global maximum in the normalized 2D surface

[peak_per_bin, code_idx_per_bin] = max(correlation_surface_norm, [], 2);
[peak_value_norm, best_bin_idx]  = max(peak_per_bin);

% Extract acquisition estimates
acq_doppler_hz  = doppler_bins_hz(best_bin_idx);
acq_samp_delay  = code_idx_per_bin(best_bin_idx) - 1;   % Convert to 0-indexed
acq_chip_delay  = acq_samp_delay / samp_per_chip;

%% ---- Peak-to-Noise Ratio (Acquisition Quality Metric) ----
% Real receivers use C/N0 (carrier-to-noise density) for acquisition decision
% We compute a simpler but equivalent metric: Peak-to-Average Ratio
% A real receiver declares lock if this exceeds a threshold (typically ~15–20x)

% Exclude peak region for clean noise floor estimate
flat_surface = correlation_surface_norm;
flat_surface(best_bin_idx, max(1,acq_samp_delay-20):min(N_samp,acq_samp_delay+20)) = NaN;
noise_floor_clean = mean(flat_surface(:), 'omitnan');
peak_to_noise_ratio = peak_value_norm / noise_floor_clean;

% Acquisition decision threshold
acq_threshold = 3.0;   % Peak must be 3× noise floor to declare lock
                        % Real receivers use higher thresholds (8–12×) at better SNR
acq_success = peak_to_noise_ratio > acq_threshold;

%% ---- Results ----
fprintf('\n--- Stage 3: Acquisition Results ---\n');
fprintf('True  Doppler   : %8.1f Hz  |  Acquired: %8.1f Hz  |  Error: %.1f Hz\n', ...
        true_doppler_hz, acq_doppler_hz, abs(true_doppler_hz - acq_doppler_hz));
fprintf('True  Chip Delay: %8.2f chips|  Acquired: %8.2f chips|  Error: %.2f chips\n', ...
        true_chip_delay, acq_chip_delay, abs(true_chip_delay - acq_chip_delay));
fprintf('Peak-to-Noise   : %.2f x\n', peak_to_noise_ratio);
fprintf('Acquisition     : %s\n', string(acq_success).upper + " (threshold = " + acq_threshold + "x)");

%% ---- Save Stage 3 Output ----
save('stage3_output.mat', ...
    'correlation_surface', 'correlation_surface_norm', ...
    'doppler_bins_hz', 'num_doppler_bins', 'doppler_step_hz', ...
    'acq_doppler_hz', 'acq_chip_delay', 'acq_samp_delay', ...
    'peak_value_norm', 'peak_to_noise_ratio', 'noise_floor_estimate', ...
    'acq_threshold', 'acq_success', ...
    'f_chip','f_s','f_IF','T_code','N_chips','samp_per_chip','N_samp','t', ...
    'prn_id','prn_code_chips','prn_upsampled','nav_bit','s_baseband','s_tx', ...
    'A_signal','phi_0','true_chip_delay','true_samp_delay','true_doppler_hz', ...
    'SNR_dB','SNR_linear','r',"peak_per_bin");

disp('Stage 3 complete.');