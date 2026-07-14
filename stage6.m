%% =========================================================
%  STAGE 6: Spoof Signal Injection
%  Injects a counterfeit GPS signal into the received signal
%  Demonstrates receiver confusion and false lock
% ==========================================================

clear; clc; close all;

%% ---- Load Stage 5 output ----
load('stage5_output.mat');
% Key variables:
%   r_long, f_s, f_IF, N_samp, N_epochs, samp_per_chip, N_chips
%   prn_code_chips, prn_upsampled, nav_bit, A_signal, phi_0
%   true_chip_delay, true_doppler_hz, SNR_dB, SNR_linear
%   tau_history, f_history (authentic tracking result for comparison)

%% ---- Spoof Signal Parameters ----
% Attacker transmits a fake GPS signal with these parameters
% Receiver has no prior knowledge of these values

spoof_chip_delay  = 400.0;     % [chips] — false position injected by attacker
                               % 400 - 150.7 = 249.3 chips away from truth
                               % = 249.3 × 293m ≈ 73 km false position offset

spoof_doppler_hz  = 500.0;     % [Hz] — attacker sets this to match or differ
                               % Here we place it 1323 Hz away from authentic
                               % So spoof peak appears at different Doppler bin

spoof_phi         = pi/3;      % [radians] — arbitrary spoof carrier phase

% Power advantage scenarios — we will test all three
% and compare acquisition surfaces side by side
spoof_powers = [0, 6, 15];
% 0 dB  → equal power  → two equal peaks, receiver uncertain
% 6 dB  → 2× power     → spoof peak clearly larger
% 15 dB → 5.6× power   → spoof completely dominates

%% ---- Generate Spoof Signal (Multi-Epoch) ----
% Identical structure to authentic signal generation in Stage 5
% Only delay, Doppler, phase, and amplitude differ

spoof_samp_delay = round(spoof_chip_delay * samp_per_chip);

r_spoof_base = zeros(1, N_epochs * N_samp);   % Unit-power spoof signal

for ep = 1:N_epochs
    t_ep = ((ep-1)*N_samp : ep*N_samp - 1) / f_s;

    % Spoof PRN — same PRN code as authentic satellite (key to spoofing)
    % Attacker must know the target satellite's PRN — publicly known for GPS
    prn_epoch_s  = repelem(prn_code_chips, samp_per_chip);
    prn_delayed_s = circshift(prn_epoch_s, spoof_samp_delay);

    % Spoof carrier at different Doppler
    carrier_s = cos(2*pi*(f_IF + spoof_doppler_hz)*t_ep + spoof_phi);

    % Unit amplitude spoof (will scale by power ratio below)
    r_spoof_base((ep-1)*N_samp+1 : ep*N_samp) = ...
        A_signal * nav_bit * prn_delayed_s .* carrier_s;
end

%% ---- Inject Spoof at Three Power Levels ----
% For each power ratio, create a combined received signal
% Then run acquisition to show how the correlation surface changes
%% ---- Inject Spoof at Three Power Levels ----
% For each power ratio, create a combined received signal
% Then run acquisition to show how the correlation surface changes

figure('Name','Stage 6: Spoof Injection — Acquisition Surfaces','NumberTitle','off',...
       'Position',[50 50 1400 900]);

acq_results = struct();   % Store results for Stage 7

for pi_idx = 1:3
    power_dB     = spoof_power_ratios_dB(pi_idx);
    power_linear = 10^(power_dB/10);
    A_spoof      = A_signal * sqrt(power_linear);   % Spoof amplitude

    % Combined received signal: authentic + spoof + noise
    % Noise already embedded in r_long from Stage 5
    r_combined = r_long + A_spoof * r_spoof_base;

    % Run acquisition on first epoch of combined signal
    r_epoch = r_combined(1:N_samp);
    t_epoch = (0:N_samp-1) / f_s;

    % 2D acquisition search (same engine as Stage 3)
    doppler_step_hz  = 500;
    doppler_bins_hz  = -5000:doppler_step_hz:5000;
    num_doppler_bins = length(doppler_bins_hz);
    local_prn_fft_conj = conj(fft(prn_upsampled));

    corr_surface = zeros(num_doppler_bins, N_samp);

    for k = 1:num_doppler_bins
        local_carrier = exp(-1j * 2*pi*(f_IF + doppler_bins_hz(k))*t_epoch);
        baseband      = r_epoch .* local_carrier;
        corr_fft      = fft(baseband) .* local_prn_fft_conj;
        corr_surface(k,:) = abs(ifft(corr_fft)).^2;
    end

    % Normalize
    noise_floor = median(corr_surface(:));
    corr_surface_norm = corr_surface / noise_floor;

    % Find top 2 peaks (authentic + spoof)
    % Peak 1: global maximum
    [peak_per_bin, code_idx_per_bin] = max(corr_surface_norm, [], 2);
    [peak1_val, bin1_idx] = max(peak_per_bin);
    peak1_doppler = doppler_bins_hz(bin1_idx);
    peak1_delay   = (code_idx_per_bin(bin1_idx)-1) / samp_per_chip;

    % Suppress peak 1 region and find peak 2
    corr_suppressed = corr_surface_norm;
    suppress_bins   = max(1, bin1_idx-1) : min(num_doppler_bins, bin1_idx+1);
    suppress_chips  = max(1, code_idx_per_bin(bin1_idx)-15) : ...
                      min(N_samp, code_idx_per_bin(bin1_idx)+15);
    corr_suppressed(suppress_bins, suppress_chips) = 0;

    [peak2_per_bin, code_idx2] = max(corr_suppressed, [], 2);
    [peak2_val, bin2_idx] = max(peak2_per_bin);
    peak2_doppler = doppler_bins_hz(bin2_idx);
    peak2_delay   = (code_idx2(bin2_idx)-1) / samp_per_chip;

    % Store for Stage 7
    acq_results(pi_idx).power_dB      = power_dB;
    acq_results(pi_idx).r_combined    = r_combined;
    acq_results(pi_idx).corr_surface  = corr_surface_norm;
    acq_results(pi_idx).peak1_val     = peak1_val;
    acq_results(pi_idx).peak1_doppler = peak1_doppler;
    acq_results(pi_idx).peak1_delay   = peak1_delay;
    acq_results(pi_idx).peak2_val     = peak2_val;
    acq_results(pi_idx).peak2_doppler = peak2_doppler;
    acq_results(pi_idx).peak2_delay   = peak2_delay;

    % Print results
    fprintf('\n--- Power Ratio: %d dB (A_spoof = %.2fx authentic) ---\n', ...
            power_dB, sqrt(power_linear));
    fprintf('Peak 1: Doppler=%4d Hz, Delay=%.1f chips, Power=%.1fx\n', ...
            peak1_doppler, peak1_delay, peak1_val);
    fprintf('Peak 2: Doppler=%4d Hz, Delay=%.1f chips, Power=%.1fx\n', ...
            peak2_doppler, peak2_delay, peak2_val);
    fprintf('Receiver locks onto: %s signal\n', ...
            ternary_str(peak1_val >= peak2_val, 'DOMINANT (check delay)', 'AUTHENTIC'));

    % 2D Heatmap visualization
    code_axis = (0:N_samp-1) / samp_per_chip;

    subplot(2,3,pi_idx);
    imagesc(code_axis, doppler_bins_hz, corr_surface_norm);
    colormap('jet'); colorbar;
    set(gca,'YDir','normal');
    xlabel('Code Phase [chips]'); ylabel('Doppler [Hz]');
    title(sprintf('Spoof Power = %d dB\n(A_{spoof} = %.1fx authentic)', ...
                  power_dB, sqrt(power_linear)), 'FontSize', 11);
    hold on;
    % Mark authentic peak location
    xline(true_chip_delay,  'w--', 'LineWidth', 1.2);
    yline(true_doppler_hz,  'w--', 'LineWidth', 1.2);
    % Mark spoof peak location
    xline(spoof_chip_delay, 'm--', 'LineWidth', 1.2);
    yline(spoof_doppler_hz, 'm--', 'LineWidth', 1.2);
    % Mark detected peaks
    plot(peak1_delay, peak1_doppler, 'w^', 'MarkerSize',12,'MarkerFaceColor','w');
    plot(peak2_delay, peak2_doppler, 'm^', 'MarkerSize',12,'MarkerFaceColor','m');
    hold off;

    % Cross-section at best Doppler bin
    subplot(2,3,pi_idx+3);
    [~, best_bin] = min(abs(doppler_bins_hz - peak1_doppler));
    plot(code_axis, corr_surface_norm(best_bin,:), 'b', 'LineWidth', 1.2);
    hold on;
    xline(true_chip_delay,  'r--', 'Auth',  'LineWidth',1.5,'LabelVerticalAlignment','bottom');
    xline(spoof_chip_delay, 'm--', 'Spoof', 'LineWidth',1.5,'LabelVerticalAlignment','bottom');
    xlabel('Code Phase [chips]'); ylabel('Normalized Power');
    title(sprintf('Code Slice at Doppler = %d Hz', peak1_doppler));
    grid on; hold off;
end

sgtitle('Stage 6: Spoof Signal Injection — Three Power Levels', ...
        'FontSize', 13, 'FontWeight', 'bold');


%% ---- Save Stage 6 Output ----
save('stage6_output.mat', ...
    'f_chip','f_s','f_IF','T_code','N_chips','samp_per_chip','N_samp', ...
    'prn_id','prn_code_chips','prn_upsampled','nav_bit','A_signal','phi_0', ...
    'true_chip_delay','true_doppler_hz','SNR_dB','SNR_linear', ...
    'spoof_chip_delay','spoof_doppler_hz','spoof_phi', ...
    'spoof_powers','r_spoof_base', ...
    'r_long', ...
    'tau_history','f_history', ...
    'N_epochs','samp_per_chip','early_late_spacing', ...
    'K_dll','K_pll','K_fll');

disp('Stage 6 complete. Spoof injected at 3 power levels. Ready for Stage 7.');

