function prn = generate_gps_prn(sv_id)
% GENERATE_GPS_PRN  Generates real GPS L1 C/A Gold code for satellite sv_id
%
%   Real GPS uses two 10-stage LFSRs:
%     G1: feedback taps at positions [3,10]
%     G2: feedback taps are satellite-specific (defined in IS-GPS-200)
%   Output of G2 is XOR'd with a specific delayed version (via tap selection)
%   Gold code = G1 XOR G2_tapped
%
%   Output: prn [1×1023] with values ±1

% G2 tap selection table (IS-GPS-200, Table 3-Ia)
% Each row: [tap_i, tap_j] used to form the G2 output for that SV
g2_taps = [
    2,6;  1,6;  2,7;  2,8;  1,9;  3,10; ...   % SV 1–6
    2,10; 2,3;  3,7;  4,11; 5,11; 6,11; ...   % SV 7–12 (padded)
    1,2;  4,5;  5,6;  6,7;  7,8;  8,9; ...    % SV 13–18
    9,10; 1,3;  2,4;  3,5;  4,6;  5,7; ...    % SV 19–24
    6,8;  7,9;  8,10; 1,4;  2,5;  3,6; ...    % SV 25–30
    4,7;  5,8];                                 % SV 31–32

if sv_id < 1 || sv_id > 32
    error('SV ID must be between 1 and 32');
end

taps = g2_taps(sv_id, :);

% Initialize shift registers (all ones per GPS spec)
g1 = ones(1, 10);
g2 = ones(1, 10);

prn_bits = zeros(1, 1023);

for i = 1:1023
    % G1 output bit
    g1_out = g1(10);

    % G2 output via phase selector (XOR of two tap positions)
    g2_out = xor(g2(taps(1)), g2(taps(2)));

    % Gold code bit = G1 XOR G2_tapped
    prn_bits(i) = xor(g1_out, g2_out);

    % G1 feedback: taps [3,10]
    g1_feedback = xor(g1(3), g1(10));
    g1 = [g1_feedback, g1(1:9)];

    % G2 feedback: taps [2,3,6,8,9,10]
    g2_feedback = xor(g2(2), xor(g2(3), xor(g2(6), xor(g2(8), xor(g2(9), g2(10))))));
    g2 = [g2_feedback, g2(1:9)];
end

% Convert {0,1} → {+1,−1} (BPSK convention: 0→+1, 1→−1)
prn = 1 - 2*prn_bits;
end