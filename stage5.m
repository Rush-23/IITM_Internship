%% =========================================================
%  STAGE 5: Simplified Tracking Loops (DLL + PLL)
%  Runs over multiple epochs, converges to true delay/Doppler
% ==========================================================

clear; clc; close all;

%% ---- Load Stage 3 output ----
load('stage3_output.mat');
% Key variables:
%   r, t, f_s, f_IF, N_samp, samp_per_chip, N_chips
%   prn_upsampled, prn_code_chips
%   acq_chip_delay, acq_doppler_hz
%   true_chip_delay, true_doppler_hz

%% ---- Tracking Parameters ----
N_epochs     = 1000;        % Number of 1ms epochs to track
                           % 100ms total — enough to see convergence clearly

early_late_spacing = 0.5;  % Δ in chips — standard GPS receiver value
                           % Smaller → more precise but noisier discriminator
                           % Larger → more robust but less precise

K_dll = 0.01;             % DLL loop gain
                           % Small → slow but stable convergence
                           % Large → fast but may oscillate

K_pll = 0.30;              % PLL phase correction gain
K_fll = 0.10;              % FLL frequency correction gain
                           % Two gains make this a 2nd order loop

%% ---- Initialize Tracking State ----
% Start from acquisition estimates — these are rough, loops will refine them

tau_est    = acq_chip_delay;     % Current code delay estimate [chips]
f_est      = acq_doppler_hz;     % Current Doppler estimate [Hz]
phi_est    = 0;                  % Current carrier phase estimate [radians]

% Storage for tracking history — used for visualization and Stage 6 comparison
tau_history   = zeros(1, N_epochs);
f_history     = zeros(1, N_epochs);
dll_disc_hist = zeros(1, N_epochs);
pll_disc_hist = zeros(1, N_epochs);
I_P_history   = zeros(1, N_epochs);
Q_P_history   = zeros(1, N_epochs);

%% ---- Generate Multi-Epoch Received Signal ----
% Stage 2 gave us only 1 epoch of r
% For tracking we need N_epochs of continuous signal
% We regenerate it here using the same channel parameters

% Rebuild full received signal across N_epochs
rng(42);   % Same seed as Stage 2 for consistency
r_long = zeros(1, N_epochs * N_samp);

for ep = 1:N_epochs
    % Time vector for this epoch
    t_ep = ((ep-1)*N_samp : ep*N_samp - 1) / f_s;

    % PRN for this epoch — continuous code (delay wraps modulo N_chips)
    % Compute sample offset accounting for delay
    delay_samp_ep = round(true_chip_delay * samp_per_chip);
    prn_epoch = repelem(prn_code_chips, samp_per_chip);

    % Apply delay via circular shift
    prn_delayed = circshift(prn_epoch, delay_samp_ep);

    % Carrier with Doppler
    carrier_ep = cos(2*pi*(f_IF + true_doppler_hz)*t_ep + phi_0);

    % Signal + noise
    s_ep   = A_signal * nav_bit * prn_delayed .* carrier_ep;
    n_ep   = (sqrt(mean(s_ep.^2)/SNR_linear)) * randn(1, N_samp);
    r_long((ep-1)*N_samp+1 : ep*N_samp) = s_ep + n_ep;
end

%% ---- Main Tracking Loop ----
for ep = 1:N_epochs

    % Extract current epoch samples
    epoch_samples = r_long((ep-1)*N_samp+1 : ep*N_samp);
    t_ep = ((ep-1)*N_samp : ep*N_samp-1) / f_s;

    %% -- Step 1: Carrier Wipe-Off --
    % Remove carrier using current PLL estimate
    % Complex exponential gives both I and Q simultaneously
    local_carrier_pll = exp(-1j * 2*pi*(f_IF + f_est)*t_ep - 1j*phi_est);
    baseband_epoch    = epoch_samples .* local_carrier_pll;

    %% -- Step 2: Generate Early, Prompt, Late PRN Replicas --
    % Convert delays to sample indices, wrap modulo N_samp
    tau_samp    = round(tau_est * samp_per_chip);
    delta_samp  = round(early_late_spacing * samp_per_chip);

    % Circular shift of upsampled PRN by delay estimate
    % Prompt: at current estimate
    % Early:  half-chip ahead (smaller delay = earlier in time)
    % Late:   half-chip behind (larger delay = later in time)
    P_code = circshift(prn_upsampled, tau_samp);
    E_code = circshift(prn_upsampled, tau_samp - delta_samp);
    L_code = circshift(prn_upsampled, tau_samp + delta_samp);

    %% -- Step 3: Correlate Each Replica --
    % Dot product = coherent integration over 1 epoch
    % Result is a complex number (I + jQ) for each correlator

    P_corr = sum(baseband_epoch .* P_code) / N_samp;   % Prompt
    E_corr = sum(baseband_epoch .* E_code) / N_samp;   % Early
    L_corr = sum(baseband_epoch .* L_code) / N_samp;   % Late

    % Extract I and Q from prompt correlator
    I_P = real(P_corr);
    Q_P = imag(P_corr);

    %% -- Step 4: DLL Discriminator --
    % Normalized early-minus-late power
    E_pwr = abs(E_corr)^2;
    L_pwr = abs(L_corr)^2;

    if (E_pwr + L_pwr) > 0
        dll_disc = (E_pwr - L_pwr) / (E_pwr + L_pwr);
    else
        dll_disc = 0;
    end

    % Physical meaning of dll_disc:
    %   +0.5 → tau_est is 0.5 chips too late → need to advance
    %   -0.5 → tau_est is 0.5 chips too early → need to retard
    %    0.0 → perfectly locked

    %% -- Step 5: PLL Discriminator --
    % atan2 discriminator — gives phase error in radians
    pll_disc = atan2(Q_P, I_P);

    % Physical meaning:
    %   +π/4  → local carrier is 45° behind received carrier
    %   -π/4  → local carrier is 45° ahead
    %    0    → phase locked

    %% -- Step 6: Update Estimates (Loop Filter) --
    % DLL: advance or retard code phase
    tau_est = tau_est - K_dll * dll_disc;

    % Wrap tau_est to valid range [0, N_chips)
    tau_est = mod(tau_est, N_chips);

    % PLL: correct phase and frequency
    phi_est = phi_est + K_pll * pll_disc;
    f_est   = f_est   + K_fll * pll_disc;

    %% -- Store History --
    tau_history(ep)   = tau_est;
    f_history(ep)     = f_est;
    dll_disc_hist(ep) = dll_disc;
    pll_disc_hist(ep) = pll_disc;
    I_P_history(ep)   = I_P;
    Q_P_history(ep)   = Q_P;

end

%% ---- Results ----
fprintf('\n--- Stage 5: Tracking Results (after %d epochs) ---\n', N_epochs);
fprintf('True  Chip Delay : %.4f chips  |  Final Estimate: %.4f chips  |  Error: %.4f chips\n', ...
        true_chip_delay, tau_history(end), abs(true_chip_delay - tau_history(end)));
fprintf('True  Doppler    : %.2f Hz     |  Final Estimate: %.2f Hz     |  Error: %.2f Hz\n', ...
        true_doppler_hz, f_history(end), abs(true_doppler_hz - f_history(end)));

%% ---- Visualization ----
figure('Name','Stage 5: Tracking Loop Convergence','NumberTitle','off', ...
       'Position',[100 100 1000 700]);

% Plot 1: Code delay convergence
subplot(2,3,1);
plot(1:N_epochs, tau_history, 'b', 'LineWidth', 1.4); hold on;
yline(true_chip_delay, 'r--', 'True delay', 'LineWidth', 1.5);
xlabel('Epoch [ms]'); ylabel('Code Delay [chips]');
title('DLL: Code Delay Convergence'); grid on;

% Plot 2: Doppler convergence
subplot(2,3,2);
plot(1:N_epochs, f_history, 'r', 'LineWidth', 1.4); hold on;
yline(true_doppler_hz, 'b--', 'True Doppler', 'LineWidth', 1.5);
xlabel('Epoch [ms]'); ylabel('Doppler Estimate [Hz]');
title('PLL: Doppler Convergence'); grid on;

% Plot 3: DLL discriminator over time
subplot(2,3,3);
plot(1:N_epochs, dll_disc_hist, 'k', 'LineWidth', 1.2);
yline(0, 'r--', 'LineWidth', 1.2);
xlabel('Epoch [ms]'); ylabel('DLL Discriminator');
title('DLL Discriminator (→ 0 at lock)'); grid on;

% Plot 4: I/Q prompt correlator — should align to I axis when locked
subplot(2,3,4);
scatter(I_P_history, Q_P_history, 20, 1:N_epochs, 'filled');
colorbar; colormap('cool');
xlabel('I_P'); ylabel('Q_P');
title('I/Q Constellation (color = epoch)');
xline(0,'k--'); yline(0,'k--'); grid on; axis equal;
% When PLL locks: all points collapse onto positive I axis (Q→0)

% Plot 5: Tracking error over time
subplot(2,3,5);
delay_error = tau_history - true_chip_delay;
plot(1:N_epochs, delay_error, 'b', 'LineWidth', 1.4);
yline(0, 'r--', 'LineWidth', 1.5);
xlabel('Epoch [ms]'); ylabel('Error [chips]');
title('Code Delay Tracking Error'); grid on;

% Plot 6: PLL discriminator
subplot(2,3,6);
plot(1:N_epochs, pll_disc_hist, 'm', 'LineWidth', 1.2);
yline(0, 'r--', 'LineWidth', 1.2);
xlabel('Epoch [ms]'); ylabel('PLL Discriminator [rad]');
title('PLL Discriminator (→ 0 at lock)'); grid on;

sgtitle('Stage 5: DLL + PLL Tracking Loop Convergence', ...
        'FontSize', 13, 'FontWeight', 'bold');

%% ---- Save Stage 5 Output ----
save('stage5_output.mat', ...
    'f_chip','f_s','f_IF','T_code','N_chips','samp_per_chip','N_samp', ...
    'prn_id','prn_code_chips','prn_upsampled','nav_bit','A_signal','phi_0', ...
    'true_chip_delay','true_samp_delay','true_doppler_hz','SNR_dB','SNR_linear', ...
    'tau_history','f_history','dll_disc_hist','pll_disc_hist', ...
    'I_P_history','Q_P_history', ...
    'tau_est','f_est','phi_est', ...
    'N_epochs','early_late_spacing','K_dll','K_pll','K_fll', ...
    'r_long');

disp('Stage 5 complete. Tracking loops converged. Ready for Stage 6 (Spoofing).');