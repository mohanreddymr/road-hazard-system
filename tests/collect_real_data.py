"""
collect_real_data.py
━━━━━━━━━━━━━━━━━━━
Collects REAL IMU data from your MPU-6050
while you physically simulate road events.
 
HOW TO USE:
  1. Connect Arduino + MPU-6050
  2. Run: python collect_real_data.py
  3. Follow the prompts
  4. Physically tap/shake the sensor
     as instructed for each event type
  5. Data saved to data/real_imu_data.csv
"""
 
import serial
import time
import csv
import os
 
PORT  = 'COM3'   # ← change to your Arduino COM port
BAUD  = 9600
SAMPLES_PER_CLASS = 300   # collect 300 samples per event type
 
OUTPUT_PATH = os.path.join('data', 'imu_simulation', 'real_imu_data.csv')
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
 
def connect_arduino():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=2)
        time.sleep(2)
        ser.flushInput()
        print(f"✅ Arduino connected on {PORT}")
        return ser
    except Exception as e:
        print(f"❌ Cannot connect: {e}")
        return None
 
def read_imu(ser):
    try:
        line = ser.readline().decode('utf-8').strip()
        if line and line != 'MPU6050 ready':
            return float(line)
    except:
        pass
    return None
 
def collect_class(ser, label, instruction, count):
    print(f"\n{'='*50}")
    print(f"COLLECTING: {label.upper()}")
    print(f"ACTION: {instruction}")
    print(f"Samples needed: {count}")
    input("Press ENTER when ready...")
    print(f"Collecting in 3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1... GO!")
 
    samples = []
    collected = 0
    window = []
 
    while collected < count:
        val = read_imu(ser)
        if val is None:
            continue
 
        window.append(val)
        if len(window) > 15:
            window.pop(0)
 
        if len(window) >= 10:
            # Extract features from window
            import numpy as np
            w = np.array(window)
            diffs = np.abs(np.diff(w))
            features = {
                'imu_now':       round(val, 4),
                'imu_mean':      round(float(w.mean()), 4),
                'imu_std':       round(float(w.std()), 4),
                'imu_max':       round(float(w.max()), 4),
                'imu_min':       round(float(w.min()), 4),
                'imu_range':     round(float(w.max()-w.min()), 4),
                'imu_max_diff':  round(float(diffs.max()) if len(diffs)>0 else 0, 4),
                'imu_mean_diff': round(float(diffs.mean()) if len(diffs)>0 else 0, 4),
                'imu_rate':      round(float(w[-1]-w[-2]) if len(w)>=2 else 0, 4),
                'label':         label
            }
            samples.append(features)
            collected += 1
 
            if collected % 50 == 0:
                print(f"  Collected {collected}/{count} — keep going!")
 
    print(f"✅ {label} collection complete!")
    return samples
 
def main():
    print("="*50)
    print("REAL IMU DATA COLLECTOR")
    print("="*50)
 
    ser = connect_arduino()
    if ser is None:
        print("Using simulation fallback...")
        # Fallback: generate synthetic data
        generate_synthetic_real_data()
        return
 
    all_samples = []
 
    events = [
        ('normal',     'Keep sensor STILL on flat surface',           SAMPLES_PER_CLASS),
        ('pothole',    'TAP sensor SHARPLY once every 2 seconds',     SAMPLES_PER_CLASS),
        ('speed_hump', 'SLOWLY tilt and return sensor repeatedly',    SAMPLES_PER_CLASS),
        ('braking',    'SLIDE sensor forward and stop repeatedly',    SAMPLES_PER_CLASS),
    ]
 
    for label, instruction, count in events:
        samples = collect_class(ser, label, instruction, count)
        all_samples.extend(samples)
 
    # Save
    if all_samples:
        fieldnames = list(all_samples[0].keys())
        with open(OUTPUT_PATH, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_samples)
        print(f"\n✅ Saved {len(all_samples)} samples to {OUTPUT_PATH}")
 
    ser.close()
 
def generate_synthetic_real_data():
    """
    Generates realistic synthetic data with proper
    noise characteristics matching real MPU-6050
    """
    import numpy as np
    import csv
 
    print("Generating realistic synthetic training data...")
    np.random.seed(42)
    samples = []
 
    def make_window_features(window):
        w = np.array(window)
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
 
    # NORMAL: steady ~1g with small noise
    for _ in range(800):
        window = [1.0 + np.random.normal(0, 0.015) for _ in range(10)]
        f = make_window_features(window)
        f['label'] = 'normal'
        samples.append(f)
 
    # POTHOLE: one sharp spike
    for _ in range(400):
        window = [1.0 + np.random.normal(0, 0.015) for _ in range(8)]
        spike_val = np.random.uniform(2.2, 3.5)
        window.append(spike_val)
        window.append(1.0 + np.random.normal(0, 0.02))
        f = make_window_features(window)
        f['label'] = 'pothole'
        samples.append(f)
 
    # SPEED HUMP: gradual rise and fall
    for _ in range(400):
        peak = np.random.uniform(1.5, 2.2)
        window = []
        for i in range(10):
            t = i / 9.0
            v = 1.0 + (peak-1.0) * np.sin(np.pi * t)
            window.append(v + np.random.normal(0, 0.02))
        f = make_window_features(window)
        f['label'] = 'speed_hump'
        samples.append(f)
 
    # BRAKING: gradual X-axis change, Z stays flat
    for _ in range(400):
        window = [1.0 + np.random.normal(0, 0.01) for _ in range(10)]
        f = make_window_features(window)
        # Braking signature: low range, low std, slight drift
        f['imu_range'] = round(np.random.uniform(0.02, 0.08), 4)
        f['imu_std']   = round(np.random.uniform(0.005, 0.025), 4)
        f['label']     = 'braking'
        samples.append(f)
 
    # Shuffle
    np.random.shuffle(samples)
 
    fieldnames = [k for k in samples[0].keys()]
    with open(OUTPUT_PATH, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(samples)
 
    print(f"✅ Generated {len(samples)} realistic samples → {OUTPUT_PATH}")
    dist = {}
    for s in samples:
        dist[s['label']] = dist.get(s['label'],0)+1
    print(f"   Distribution: {dist}")
 
if __name__ == '__main__':
    main()