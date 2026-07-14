%% =========================================================
%  STAGE 1: Realistic GPS-Like Signal Generation
%  GPS L1 C/A structure at simulated IF
% ==========================================================

clear; clc; close all;

%% ---- System Parameters ----
% These are locked across all stages - do not change them later

f_chip   = 1.023e6;      % GPS C/A chip rate [chips/sec]
f_s      = 10.23e6;      % Sampling frequency [samples/sec] — 10x oversampling
f_IF     = 4e6;          % Simulated Intermediate Frequency [Hz]
T_code   = 1e-3;         % One PRN epoch duration [sec] = 1 ms
N_chips  = 1023;         % Chips per PRN epoch (real GPS C/A)
samp_per_chip = f_s / f_chip;   % = 10 samples per chip
N_samp   = round(T_code * f_s); % = 10230 samples per epoch

% Time vector for one epoch
t = (0 : N_samp-1) / f_s;      % [sec], length = 10230

%% ---- PRN Gold Code Generation ----
% GPS uses Gold codes derived from two 10-stage LFSRs (G1, G2)
% Each satellite has a unique PRN assigned by tap selection on G2
% Here we implement the real GPS G1/G2 generator structure

prn_id = 1;   % Satellite PRN number (1–32), change to test others
prn_code_chips = generate_gps_prn(prn_id);  % Returns ±1 vector, length 1023

% Physical meaning:
%   Each chip is 1/1.023MHz ≈ 977 ns wide ≈ 293 m of propagation delay
%   This is the fundamental ranging resolution unit

%% ---- Upsample PRN to Sampling Rate ----
% Each chip is repeated samp_per_chip times (10x here)
% This converts the 1023-chip sequence to 10230 samples

prn_upsampled = repelem(prn_code_chips, samp_per_chip);
% Size check: must equal N_samp
assert(length(prn_upsampled) == N_samp, 'PRN upsampling size mismatch');

% Physical meaning:
%   We need sub-chip resolution in acquisition (Stage 3)
%   10x oversampling gives us ~0.1 chip = ~29m delay resolution

%% ---- Navigation Data Bit ----
% Real GPS data rate = 50 bps → 1 bit per 20 ms → same bit for 20 epochs
% For 1 epoch simulation: fix data bit = +1 (no bit transition in this window)
% This assumption is valid for coherent integration across 1 ms

nav_bit = +1;   % Navigation data bit: +1 or -1

%% ---- BPSK Modulated Spread Signal (Baseband) ----
% Baseband GPS signal before carrier:
%   s_bb(t) = nav_bit × prn(t)
% This is the direct-sequence spread spectrum signal

s_baseband = nav_bit * prn_upsampled;   % ±1 BPSK chips at baseband

%% ---- Carrier Generation at IF ----
% Real GPS receiver front-end downconverts RF (1575.42 MHz) to IF
% We directly simulate at IF = 4 MHz, skipping RF entirely
% This is standard practice in GPS software receiver design

phi_0 = pi/6;   % Arbitrary initial carrier phase [radians]
                 % In a real receiver, this is unknown and must be estimated
carrier = cos(2*pi*f_IF*t + phi_0);    % Length = N_samp

%% ---- Transmitted GPS-Like Signal ----
% s(t) = A · d(t) · c(t) · cos(2π·f_IF·t + φ₀)
% This is the structure of a real GPS L1 C/A signal at IF

A_signal = 1.0;   % Signal amplitude (unity for now; SNR set via AWGN in Stage 2)
s_tx = A_signal * s_baseband .* carrier;   % Element-wise: spread + modulate

%% ---- Visualization ----
figure('Name','Stage 1: GPS Signal Generation','NumberTitle','off');

% Plot 1: PRN chips (first 50 chips)
subplot(3,1,1);
chip_indices = 1 : 50*samp_per_chip;
stairs(t(chip_indices)*1e6, prn_upsampled(chip_indices), 'b', 'LineWidth', 1.2);
xlabel('Time [\mus]'); ylabel('Chip value');
title(sprintf('PRN Code — Satellite %d (first 50 chips)', prn_id));
ylim([-1.5 1.5]); grid on;

% Plot 2: IF carrier
subplot(3,1,2);
plot_samp = 1:200;
plot(t(plot_samp)*1e6, carrier(plot_samp), 'r', 'LineWidth', 1.0);
xlabel('Time [\mus]'); ylabel('Amplitude');
title(sprintf('IF Carrier at %.1f MHz', f_IF/1e6));
grid on;

% Plot 3: Transmitted BPSK signal (zoomed)
subplot(3,1,3);
plot(t(plot_samp)*1e6, s_tx(plot_samp), 'k', 'LineWidth', 1.0);
xlabel('Time [\mus]'); ylabel('Amplitude');
title('Transmitted GPS-Like Signal s(t) = d(t)·c(t)·cos(2\pi f_{IF} t)');
grid on;

sgtitle('Stage 1: GPS L1 C/A Signal Structure', 'FontSize', 13, 'FontWeight', 'bold');

%% ---- Save workspace for Stage 2 ----
save('stage1_output.mat', ...
    'f_chip','f_s','f_IF','T_code','N_chips','samp_per_chip','N_samp', ...
    't','prn_id','prn_code_chips','prn_upsampled','nav_bit', ...
    's_baseband','s_tx','A_signal','phi_0');

disp('Stage 1 complete. Signal generated and saved.');
disp(['  Samples per epoch : ', num2str(N_samp)]);
disp(['  Samples per chip  : ', num2str(samp_per_chip)]);
disp(['  Chip width        : ', num2str(1/f_chip*1e9,'%.1f'), ' ns  (~', ...
      num2str(3e8/f_chip,'%.0f'), ' m propagation)']);