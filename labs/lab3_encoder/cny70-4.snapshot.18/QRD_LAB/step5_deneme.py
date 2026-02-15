from machine import ADC, Pin
import time

# =========================================================
# QRD1114 DISTANCE (mm) using ADC + CALIBRATION LUT
#
# Workflow:
# 1) Run once in CALIBRATION_MODE = True
#    - Put target at known distances (mm)
#    - Script prints: distance_mm, mean_u16, std_u16
#    - Copy those lines into CAL_POINTS below (or paste in REPL)
#
# 2) Set CALIBRATION_MODE = False
#    - Script prints live: adc_u16, distance_mm_est, repeatability
#
# Notes:
# - This is the correct way because QRD1114 response is nonlinear.
# - Works best with same target material and lighting used in calibration.
# =========================================================

# -------------------------
# USER SETTINGS
# -------------------------
ADC_PIN = 27          # GP27=ADC1 (or 28 / 26)
VREF = 3.3
ADC_MAX = 65535

SAMPLES = 200         # samples per measurement window
SAMPLE_PERIOD_MS = 3  # 200*3ms = 0.6s window

CALIBRATION_MODE = False   # <-- set True to collect calibration points

# -------------------------
# PUT YOUR CALIBRATION HERE
# Format: (distance_mm, mean_u16)
# Must cover your expected range and be monotonic (mostly).
# Example dummy values below - REPLACE with your measured data.
# -------------------------
CAL_POINTS = [
    # (mm, u16)
    (2.0, 12000),
    (3.0, 16000),
    (4.0, 20000),
    (5.0, 24000),
    (6.0, 28000),
    (8.0, 34000),
    (10.0, 39000),
    (12.0, 43000),
    (15.0, 48000),
    (20.0, 54000),
]

# If your sensor behaves opposite (u16 decreases with distance),
# keep CAL_POINTS but it must be ordered by u16 in the converter (handled below).

# -------------------------
# ADC SETUP
# -------------------------
adc = ADC(ADC_PIN)

# -------------------------
# STATS
# -------------------------
def mean(vals):
    return sum(vals) / len(vals) if vals else 0.0

def std(vals, mu):
    if not vals:
        return 0.0
    s2 = 0.0
    for x in vals:
        d = x - mu
        s2 += d * d
    return (s2 / len(vals)) ** 0.5

def read_samples(n=SAMPLES, period_ms=SAMPLE_PERIOD_MS):
    data = []
    for _ in range(n):
        data.append(adc.read_u16())
        time.sleep_ms(period_ms)
    return data

# -------------------------
# ADC -> DISTANCE via LUT + linear interpolation
# -------------------------
def build_lut(points):
    """
    Convert list of (mm,u16) into LUT ordered by u16:
    returns list of (u16, mm)
    """
    lut = [(u, mm) for (mm, u) in points]
    lut.sort(key=lambda x: x[0])  # sort by u16
    return lut

LUT = build_lut(CAL_POINTS)

def adc_to_mm(u):
    """
    Piecewise linear interpolation on LUT (u16->mm).
    Clamps outside the calibrated range.
    """
    if u <= LUT[0][0]:
        return LUT[0][1]
    if u >= LUT[-1][0]:
        return LUT[-1][1]

    # find segment
    for i in range(len(LUT) - 1):
        u0, d0 = LUT[i]
        u1, d1 = LUT[i + 1]
        if u0 <= u <= u1:
            # interpolate
            if u1 == u0:
                return d0
            t = (u - u0) / (u1 - u0)
            return d0 + t * (d1 - d0)

    return LUT[-1][1]

# -------------------------
# OPTIONAL: distance resolution estimate (mm)
# Uses local slope around current reading and measured std of ADC
# -------------------------
def estimate_resolution_mm(u_mean, u_std):
    """
    Resolution approx: sigma_u / |du/dmm|
    We estimate du/dmm from nearest LUT segment.
    """
    if len(LUT) < 2:
        return None

    # clamp to range
    u = u_mean
    if u <= LUT[0][0]:
        u = LUT[0][0]
    if u >= LUT[-1][0]:
        u = LUT[-1][0]

    # find nearest segment
    for i in range(len(LUT) - 1):
        u0, d0 = LUT[i]
        u1, d1 = LUT[i + 1]
        if u0 <= u <= u1:
            du = (u1 - u0)
            dd = (d1 - d0)
            if dd == 0:
                return None
            slope_du_per_mm = du / dd  # du/dmm
            return u_std / abs(slope_du_per_mm)

    return None

# -------------------------
# CALIBRATION MODE
# -------------------------
def do_calibration():
    print("\n=== CALIBRATION MODE ===")
    print("Place the SAME target at a known distance (mm).")
    print("Type distance in mm, press Enter. Type 'q' to quit.")
    print("Output is CSV: distance_mm,mean_u16,std_u16\n")

    print("distance_mm,mean_u16,std_u16")
    while True:
        s = input("distance_mm> ").strip()
        if s.lower() in ("q", "quit", "exit"):
            break
        try:
            dist = float(s)
        except:
            print("Enter a number (e.g. 5) or 'q'")
            continue

        samples = read_samples()
        mu = mean(samples)
        sd = std(samples, mu)
        print("{:.2f},{:.2f},{:.2f}".format(dist, mu, sd))

    print("Done calibration. Copy results into CAL_POINTS as (mm,u16).")

# -------------------------
# MEASURE MODE (prints distance mm live)
# -------------------------
def do_measure():
    print("\n=== MEASURE MODE ===")
    print("Using LUT from CAL_POINTS (u16 -> mm).")
    print("Printing: adc_mean_u16, adc_std_u16, dist_mm, dist_resolution_mm\n")

    while True:
        samples = read_samples()
        mu_u = mean(samples)
        sd_u = std(samples, mu_u)

        dist_mm = adc_to_mm(mu_u)
        res_mm = estimate_resolution_mm(mu_u, sd_u)

        if res_mm is None:
            res_str = "NA"
        else:
            res_str = "{:.3f}".format(res_mm)

        print("u16_mean={:.0f}, u16_std={:.0f}, dist_mm={:.2f}, res_mm={}".format(
            mu_u, sd_u, dist_mm, res_str
        ))

        # slow down prints a bit
        time.sleep_ms(150)

# -------------------------
# RUN
# -------------------------
print("QRD1114 Distance (mm) via ADC + Calibration LUT")
print("ADC pin=GP{}".format(ADC_PIN))

if CALIBRATION_MODE:
    do_calibration()
else:
    do_measure()
