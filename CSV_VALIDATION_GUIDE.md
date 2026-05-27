# CSV Output Validation Guide

## How CSV Files Are Generated

When you run the system, it **automatically generates detailed CSV files** in the `output/` folder:

```
output/
├── session_20260326_133456.csv     ← Main detailed log
├── session_20260326_133456_summary.txt
└── live_ground_truth.csv           ← Your manual labels (if using --live-label)
```

---

## CSV Columns Explained

### Session CSV Structure

Each row contains these columns:

**Sensor Raw Data:**
- `timestamp` - When this frame was processed (HH:MM:SS.mmm)
- `imu_z`, `imu_x`, `imu_y` - Raw IMU acceleration (in g's, 1g = 9.8 m/s²)
- `motion_score` - Camera motion detection score (0-5)

**Detection Results:**
- `camera_event` - What camera detected (normal/pothole/crack/speed_hump/braking)
- `camera_conf` - Camera confidence (0-1)
- `road_event` - Road analyzer result (normal/pothole/crack/speed_hump)
- `road_conf` - Road analyzer confidence (0-1)
- `rear_event` - Rear vehicle detection (if connected)
- `rear_conf` - Rear vehicle confidence (0-1)

**Fusion Decision:**
- `decision` - Final system decision (NORMAL/CAUTION/HAZARD)
- `confidence` - Overall confidence (0-100%)
- `severity_score` - How severe (0-1)
- `motor_speed` - Recommended motor speed (%)

**LoRa Transmission:**
- `lora_event` - What was sent via LoRa (or "normal" if blocked)
- `lora_sent` - Was message sent? (YES/NO)
- `lora_confidence_check` - Did it pass confidence gate? (PASS/BLOCKED)
- `lora_latency_ms` - How long message took to reach rear vehicle

**Sensor Contribution:**
- `motion_conf` - Camera motion confidence
- `imu_conf` - IMU confidence in final decision
- `road_conf_fusion` - Road detector confidence in fusion

**Validation:**
- `ground_truth` - Your manual label (if entered during session)

---

## Example CSV Data

```
timestamp,imu_z,imu_x,imu_y,motion_score,camera_event,camera_conf,road_event,road_conf,rear_event,rear_conf,decision,confidence,severity_score,motor_speed,lora_event,lora_sent,lora_confidence_check,lora_latency_ms,motion_conf,imu_conf,road_conf_fusion,ground_truth
14:32:15.123,1.0012,0.9998,1.0045,0.15,normal,0.0,normal,0.0,normal,0.0,NORMAL,92.0,0.0,100,normal,YES,PASS,0.0,0.15,0.0,0.0,NORMAL
14:32:15.423,1.2340,1.1020,1.0890,2.50,normal,0.0,pothole,0.72,normal,0.0,HAZARD,81.5,0.85,40,pothole,YES,PASS,0.0,0.4,0.2,0.72,HAZARD
14:32:15.723,0.9887,1.0023,1.0156,0.25,crack,0.45,normal,0.15,normal,0.0,CAUTION,58.0,0.35,70,normal,NO,BLOCKED,0.0,0.25,0.05,0.15,CAUTION
```

---

## How to Validate Output

### Option 1: Use the Validation Script

```bash
python validate_output.py
```

This automatically analyzes the **latest session** and shows:
- ✅ Ground truth accuracy
- 📡 LoRa transmission statistics  
- 🎯 Confidence level distribution
- 📋 Decision breakdown

Or analyze a specific file:

```bash
python validate_output.py output/session_20260326_133456.csv
```

---

### Option 2: Check CSV in Excel/Spreadsheet

1. Open `output/session_YYYYMMDD_HHMMSS.csv` in Excel
2. Scroll through and check:
   - **NORMAL rows**: `decision=NORMAL`, `confidence>90%`
   - **HAZARD rows**: Multiple sensors agree (high camera_conf + high road_conf)
   - **BLOCKED rows**: `lora_confidence_check=BLOCKED` but `decision=HAZARD` means confidence too low

---

### Option 3: Compare with Ground Truth

If you used `--live-label` during recording:

1. **During session**, press keys to label frames:
   - `N` = Mark as NORMAL
   - `C` = Mark as CAUTION
   - `H` = Mark as HAZARD
   - `X` = Clear label

2. **After session**, `validate_output.py` shows:
   ```
   ✓ Total labeled samples: 247
   ✓ Correct predictions: 234 (94.7%)
   ✗ Incorrect predictions: 13 (5.3%)
   ```

3. **Confusion matrix** shows which types of errors:
   ```
   Actual        NORMAL        CAUTION        HAZARD
   NORMAL            200             2             1
   CAUTION             1            32             2
   HAZARD              0             1            20
   ```

---

## What to Look For

### ✅ Good System Performance

- `confidence > 85%` for most NORMAL decisions
- `confidence > 75%` for HAZARD decisions (matches LoRa gate)
- `lora_sent = YES` only when `confidence >= 75%`
- No CAUTION messages sent (should all be BLOCKED)
- High accuracy when ground truth labels used

---

### ⚠️ Potential Issues

| Issue | Sign | Fix |
|-------|------|-----|
| Too many false HAZARD | `lora_sent=YES` but `confidence=45%` | Increase HAZARD threshold in main.py |
| Missing real hazards | Real pothole but `confidence=62%` | Lower HAZARD threshold to 0.70 |
| Too much noise | Many rows with `lora_confidence_check=BLOCKED` | This is GOOD - means confidence gate working |
| All NORMAL | `decision=NORMAL` for 99% | Check if camera is working |

---

## CSV Analysis Examples

### Check Confidence Distribution

Count how many decisions at each confidence level:

```bash
# Linux/Mac
cut -d',' -f13 session_*.csv | sort | uniq -c | sort -rn

# Or use the validate script
python validate_output.py
```

### Check LoRa Transmission Success

```bash
# Count how many HAZARD decisions were actually sent
grep "HAZARD" session_*.csv | grep "YES" | wc -l
```

### Find False Positives

```bash
# Rows where system detected HAZARD but ground truth was NORMAL
grep "HAZARD.*NORMAL" session_*.csv
```

---

## Automated Report Generation

The **summary file** (generated automatically after each session):

```
output/session_20260326_133456_summary.txt

╔══════════════════════════════════════════╗
║     ROAD HAZARD SYSTEM — SESSION REPORT  ║
╚══════════════════════════════════════════╝

Session Duration : 245 seconds
Total Readings   : 1470

DECISION BREAKDOWN:
  NORMAL  : 1150 (78.2%)
  CAUTION : 202  (13.7%)
  HAZARD  : 118  (8.0%)

Ground Truth Samples : 247
  Correct           : 234 (94.7%)
  Incorrect         : 13  (5.3%)

CONFUSION MATRIX (actual → predicted):
            NORMAL      CAUTION       HAZARD
      NORMAL    200            2            1
     CAUTION      1           32            2
       HAZARD      0            1           20
```

---

## Next Steps

1. **Run the system** with ground truth labels:
   ```bash
   python main.py 0 --live-label --live-label-path output/live_ground_truth.csv
   ```

2. **During run**, press keys to label frames (N=NORMAL, C=CAUTION, H=HAZARD)

3. **After stopping** (Q key), CSV is saved automatically

4. **Validate results**:
   ```bash
   python validate_output.py
   ```

5. **Check the report** to see accuracy and identify problem areas

---

## CSV Column Quick Reference

| Column | Range | What It Means |
|--------|-------|---------------|
| `imu_z` | 0.8-3.5 | Z-axis acceleration (1.0 = normal, >2.8 = pothole) |
| `motion_score` | 0-5 | Camera motion (0 = no motion, >2.5 = large change) |
| `*_conf` | 0-1 | Confidence (0 = not sure, 1 = 100% sure) |
| `confidence` | 0-100 | Overall system confidence |
| `motor_speed` | 0-100 | Recommended speed (low = hazard detected) |
| `lora_sent` | YES/NO | Did message transmit to rear vehicle? |
| `lora_latency_ms` | 20-500 | How long message took (ms) |

---

This system now gives you **complete visibility** into every decision your ADAS makes! 🎯
