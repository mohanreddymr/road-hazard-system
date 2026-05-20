"""
generate_dataset_v2.py
━━━━━━━━━━━━━━━━━━━━━
Generates improved training dataset.
Run this FIRST, then run train_model_v2.py
"""
 
import numpy as np
import csv
import os
 
OUTPUT = os.path.join('data', 'imu_simulation', 'real_imu_data.csv')
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
 
np.random.seed(42)
 
def make_features(window):
    w     = np.array(window)
    diffs = np.abs(np.diff(w))
    return {
        'imu_now':       round(float(w[-1]), 4),
        'imu_mean':      round(float(w.mean()), 4),
        'imu_std':       round(float(w.std()), 4),
        'imu_max':       round(float(w.max()), 4),
        'imu_min':       round(float(w.min()), 4),
        'imu_range':     round(float(w.max()-w.min()), 4),
        'imu_max_diff':  round(float(diffs.max()) if len(diffs)>0 else 0, 4),
        'imu_mean_diff': round(float(diffs.mean()) if len(diffs)>0 else 0, 4),
        'imu_rate':      round(float(w[-1]-w[-2]) if len(w)>=2 else 0, 4),
    }
 
samples = []
 
print("Generating improved training dataset...")
 
# ── NORMAL: 1000 samples ──
# Steady ~1g with realistic sensor noise
for _ in range(1000):
    noise = np.random.normal(0, 0.012, 10)
    window = list(1.0 + noise)
    f = make_features(window)
    f['label'] = 'normal'
    samples.append(f)
 
# ── POTHOLE: 500 samples ──
# Sharp single spike then return
for _ in range(500):
    window = list(1.0 + np.random.normal(0, 0.012, 7))
    spike  = np.random.uniform(2.0, 3.8)
    drop   = np.random.uniform(0.2, 0.6)
    window += [spike, drop, 1.0 + np.random.normal(0, 0.015)]
    f = make_features(window)
    f['label'] = 'pothole'
    samples.append(f)
 
# ── SPEED HUMP: 500 samples ──
# Gradual smooth rise and fall
for _ in range(500):
    peak = np.random.uniform(1.4, 2.2)
    window = []
    for i in range(10):
        t = i / 9.0
        v = 1.0 + (peak - 1.0) * np.sin(np.pi * t)
        window.append(v + np.random.normal(0, 0.018))
    f = make_features(window)
    f['label'] = 'speed_hump'
    samples.append(f)
 
# ── BRAKING: 500 samples ──
# Flat Z (no vertical), slight drift
for _ in range(500):
    base   = 1.0 + np.random.normal(0, 0.008)
    drift  = np.random.uniform(-0.04, 0.04)
    window = [base + drift * (i/9) + np.random.normal(0,0.008)
              for i in range(10)]
    f = make_features(window)
    f['label'] = 'braking'
    samples.append(f)
 
# Shuffle
np.random.shuffle(samples)
 
# Save
fields = list(samples[0].keys())
with open(OUTPUT, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(samples)
 
print(f"✅ Generated {len(samples)} samples → {OUTPUT}")
dist = {}
for s in samples:
    dist[s['label']] = dist.get(s['label'], 0) + 1
print(f"   Distribution: {dist}")
print("\nNow run: python tests/train_model_v2.py")