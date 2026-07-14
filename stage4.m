%% =========================================================
%  STAGE 4: Acquisition Surface Visualization
%  3D surface + 2D heatmap — both needed for Stage 8 spoof detection
% ==========================================================

clear; clc; close all;

%% ---- Load ----
load('stage3_output.mat');

% Code phase axis: 0 to 1022 chips
code_axis_chips = (0 : N_samp-1) / samp_per_chip;

%% ---- Plot 1: 3D Acquisition Surface ----
figure('Name','Stage 4: Acquisition Surface','NumberTitle','off', ...
       'Position',[100 100 1100 480]);

subplot(1,2,1);
surf(code_axis_chips, doppler_bins_hz, correlation_surface_norm, ...
     'EdgeColor','none');
colormap('jet'); colorbar;
xlabel('Code Phase [chips]','FontSize',11);
ylabel('Doppler [Hz]','FontSize',11);
zlabel('Normalized Correlation Power','FontSize',11);
title('3D Acquisition Surface','FontSize',13,'FontWeight','bold');
view(-45, 35); grid on; axis tight;

% Mark the peak
hold on;
plot3(acq_chip_delay, acq_doppler_hz, peak_value_norm, ...
      'w^', 'MarkerSize', 12, 'MarkerFaceColor', 'w', 'LineWidth', 2);
hold off;

%% ---- Plot 2: 2D Heatmap (Top-Down View) ----
% This is the critical view for Stage 8
% When spoofing is added, a second peak will appear here — immediately visible

subplot(1,2,2);
imagesc(code_axis_chips, doppler_bins_hz, correlation_surface_norm);
colormap('jet'); colorbar;
set(gca, 'YDir', 'normal');   % Ensure Doppler axis increases upward
xlabel('Code Phase [chips]','FontSize',11);
ylabel('Doppler [Hz]','FontSize',11);
title('2D Acquisition Heatmap (Top-Down View)','FontSize',13,'FontWeight','bold');
grid on;

% Mark acquired peak
hold on;
plot(acq_chip_delay, acq_doppler_hz, 'w^', ...
     'MarkerSize', 12, 'MarkerFaceColor', 'w', 'LineWidth', 2);
text(acq_chip_delay + 15, acq_doppler_hz, ...
     sprintf(' Doppler: %d Hz\n Delay: %.1f chips\n P/N: %.1fx', ...
             acq_doppler_hz, acq_chip_delay, peak_to_noise_ratio), ...
     'Color','white','FontSize',9,'FontWeight','bold');
hold off;

sgtitle('Stage 4: GPS Acquisition Surface — Authentic Signal', ...
        'FontSize',14,'FontWeight','bold');

%% ---- Plot 3: Cross-Sections Through the Peak ----
% Slice the surface at the best Doppler bin and best code phase
% Shows the correlation peak shape — important for DLL in Stage 5

figure('Name','Stage 4: Peak Cross-Sections','NumberTitle','off', ...
       'Position',[100 100 900 400]);

% Find best bin index
[~, best_doppler_idx] = min(abs(doppler_bins_hz - acq_doppler_hz));
[~, best_code_idx]    = min(abs(code_axis_chips  - acq_chip_delay));

subplot(1,2,1);
plot(code_axis_chips, correlation_surface_norm(best_doppler_idx, :), ...
     'b', 'LineWidth', 1.4);
xline(acq_chip_delay, 'r--', sprintf('%.1f chips', acq_chip_delay), ...
      'LineWidth', 1.5, 'LabelVerticalAlignment','bottom');
xlabel('Code Phase [chips]'); ylabel('Normalized Power');
title(sprintf('Code Slice at Best Doppler = %d Hz', acq_doppler_hz));
grid on;

subplot(1,2,2);
plot(doppler_bins_hz, peak_per_bin, 'r', 'LineWidth', 1.4);
xline(acq_doppler_hz, 'b--', sprintf('%d Hz', acq_doppler_hz), ...
      'LineWidth', 1.5, 'LabelVerticalAlignment','bottom');
xlabel('Doppler [Hz]'); ylabel('Peak Correlation Power');
title('Doppler Slice at Best Code Phase');
grid on;

sgtitle('Stage 4: Acquisition Peak Cross-Sections','FontSize',13,'FontWeight','bold');

disp('Stage 4 complete. Ready for Stage 5 (Tracking Loops).');