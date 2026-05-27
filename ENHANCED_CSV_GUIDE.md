# Enhanced CSV Logging & Validation System

## Overview

Your road hazard detection system now **automatically generates detailed CSV logs** with all sensor data, decisions, and validation information. This guide explains how to use it.

---

## Quick Start (3 Steps)

### Step 1: Run the System with Optional Ground Truth Labeling

**Without ground truth (basic logging):**
```bash
python main.py 0
```

**With live ground truth labeling (recommended for testing):**
```bash
python main.py 0 --live-label --live-label-path output/live_ground_truth.csv
```

### Step 2: During Execution

Press keys to label frames (optional):
- `N` = Mark as NORMAL road
- `C` = Mark as CAUTION (warning signs) 
- `H` = Mark as HAZARD (dangerous)
- `X` = Clear current label
- `Q` = Quit (auto-saves CSV)

### Step 3: Analyze the Output

```bash
python validate_output.py
```

This generates a comprehensive report showing:
- ✅ Accuracy vs ground truth
- 📡 LoRa transmission statistics
- 🎯 Confidence distributions
- 📋 Decision breakdown

---

## What Gets Logged

Every frame generates one CSV row with 22 columns:

```
timestamp,imu_z,imu_x,imu_y,motion_score,camera_event,camera_conf,road_event,
road_conf,rear_event,rear_conf,decision,confidence,severity_score,motor_speed,
lora_event,lora_sent,lora_confidence_check,lora_latency_ms,motion_conf,imu_conf,
road_conf_fusion,ground_truth
```

### Column Breakdown

**Raw Sensor Data:**
| Column | Example | Meaning |
|--------|---------|---------|
| `timestamp` | 14:32:15.123 | When frame processed |
| `imu_z` | 2.8 | Z-axis acceleration (1.0 = normal) |
| `imu_x`, `imu_y` | 1.0, 1.0 | X/Y accelerations |
| `motion_score` | 2.5 | How much motion detected (0-5) |

**Detection Module Results:**
| Column | Example | Meaning |
|--------|---------|---------|
| `camera_event` | pothole | What camera detected |
| `camera_conf` | 0.65 | How confident (0-1) |
| `road_event` | pothole | Road surface analysis result |
| `road_conf` | 0.72 | Road analyzer confidence |
| `rear_event` | normal | What rear vehicle detected |
| `rear_conf` | 0.0 | Rear confidence (if connected) |

**System Decision:**
| Column | Example | Meaning |
|--------|---------|---------|
| `decision` | HAZARD | Final decision (NORMAL/CAUTION/HAZARD) |
| `confidence` | 81.5 | Overall confidence % |
| `severity_score` | 0.85 | How severe (0-1) |
| `motor_speed` | 40 | Recommended vehicle speed % |

**LoRa V2V Communication:**
| Column | Example | Meaning |
|--------|---------|---------|
| `lora_event` | pothole | What was transmitted to rear |
| `lora_sent` | YES | Was message actually sent? |
| `lora_confidence_check` | PASS | Did it pass 75% confidence gate? |
| `lora_latency_ms` | 0.0 | Message transmission delay |

**Sensor Contributions (for debugging):**
| Column | Example | Meaning |
|--------|---------|---------|
| `motion_conf` | 0.40 | Motion detector's confidence |
| `imu_conf` | 0.20 | IMU detector's confidence |
| `road_conf_fusion` | 0.72 | Road detector's contribution |

**Ground Truth Label (your manual annotation):**
| Column | Example | Meaning |
|--------|---------|---------|
| `ground_truth` | HAZARD | Your label (N=NORMAL, C=CAUTION, H=HAZARD) |

---

## CSV File Locations

After each session:

```
output/
├── session_20260326_133456.csv           ← Main CSV with all data
├── session_20260326_133456_summary.txt   ← Auto-generated report  
├── live_ground_truth.csv                 ← Your manual labels (if created)
└── [previous sessions...]
```

---

## Validation Script Usage

### Validate Latest Session (Auto-Detects)
```bash
python validate_output.py
```

### Validate Specific Session
```bash
python validate_output.py output/session_20260326_133456.csv
```

### Output Explanation

**Ground Truth Accuracy Section:**
```
📊 GROUND TRUTH ACCURACY ANALYSIS

✓ Total labeled samples: 247
✓ Correct predictions: 234 (94.7%)
✗ Incorrect predictions: 13 (5.3%)

CONFUSION MATRIX (Actual → Predicted):
Actual      NORMAL    CAUTION     HAZARD
NORMAL        200         2          1
CAUTION         1        32          2
HAZARD          0         1         20
```

Interpretation:
- **Diagonal (200, 32, 20)** = Correct predictions ✅
- **Off-diagonal** = Errors (e.g., 1 False Positive: marked CAUTION but predicted NORMAL)

---

**LoRa Transmission Section:**
```
📡 LoRa TRANSMISSION ANALYSIS

📊 Message Statistics:
   Total records: 1470
   LoRa PASS (would send): 118 (8.0%)      ← These were high-confidence
   LoRa BLOCKED (low confidence): 1352 (91.9%)  ← Correctly filtered
   Actually sent: 118

🚨 HAZARD Handling:
   Total HAZARD detections: 118
   HAZARD messages sent: 118 (100.0%)        ← All high-conf hazards sent ✅
   HAZARD messages blocked: 0

⚠️  CAUTION Handling (should be SKIPPED):
   Total CAUTION detections: 202
   CAUTION messages blocked (as intended): 202  ← GOOD! No false alarms ✅
```

What this means:
- **All HAZARD** above 75% were sent ✅
- **All CAUTION** were blocked (Fire Alarm Model) ✅
- Rear vehicle won't be disturbed by low-confidence warnings ✅

---

**Confidence Distribution:**
```
🎯 CONFIDENCE LEVEL ANALYSIS

📈 Confidence Distribution:
   Min: 22.1%
   Max: 96.3%
   Avg: 67.4%
   Median: 71.0%

📊 Confidence Buckets:
   0-25%:   15 (1.0%) 
   25-50%: 120 (8.2%) 
   50-75%: 487 (33.1%) ████████████
   75-100%: 848 (57.7%) ██████████████████████
```

What this means:
- 57.7% have high confidence (>75%) ✅
- 33.1% are in medium range (50-75%) - can be tuned
- Only 9.2% are low confidence (<50%) ✅

---

**Decision Breakdown:**
```
📋 DECISION BREAKDOWN

Total decisions: 1470

  NORMAL  : 1150 (78.2%) ██████████████████████
  CAUTION :  202 (13.7%) ████
  HAZARD  :  118 (8.0%)  ██
```

---

## Manual Validation (Without Script)

### View CSV in Excel/Spreadsheet

1. Open `output/session_*.csv` in Excel
2. Sort by any column to find patterns:
   - High `confidence` with low `camera_conf` = Probably road detector triggered
   - `lora_confidence_check=BLOCKED` with `decision=HAZARD` = Confidence just below 75%
   - `ground_truth≠decision` = System made a mistake

### Count Specific Events

**Count HAZARD decisions that were sent:**
```bash
# Windows PowerShell
(Import-Csv output/session_*.csv | Where-Object {$_.decision -eq "HAZARD" -and $_.lora_sent -eq "YES"}).Count

# Or bash
grep "HAZARD" output/session_*.csv | grep "YES" | wc -l
```

**Count false positives (marked NORMAL but predicted HAZARD):**
```bash
grep "NORMAL.*HAZARD" output/session_*.csv | wc -l
```

---

## What Good Results Look Like

### ✅ System Working Well

- `confidence > 85%` for NORMAL decisions
- `confidence > 75%` for HAZARD decisions  
- `lora_sent = YES` when `confidence >= 75%`
- `lora_sent = NO` for CAUTION (all blocked)
- Ground truth accuracy > 90%
- Few or no rows with `lora_confidence_check=BLOCKED`

### ⚠️ Potential Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| All `confidence = 85%` (identical) | Not enough data fusion | Check if all sensors connected |
| `lora_sent = YES` but `confidence = 45%` | Threshold too low | Increase HAZARD_THRESHOLD in fusion_engine_v3.py |
| Many `lora_confidence_check=BLOCKED` for real hazards | Threshold too high | Decrease to 0.70 or 0.68 |
| Ground truth accuracy < 80% | Significant mistuning | Review individual error rows in CSV |

---

## Integration with System

### How It Works End-to-End

```
1. main.py runs your detection pipeline
   ↓
2. For each frame, collects: imu_z, imu_x, imu_y, cam_event, cam_conf, 
   road_event, road_conf, rear_event, rear_conf
   ↓
3. Calls: fusion.decide(motion_score, imu_z, imu_x, imu_y, ...)
   ↓
4. Fusion engine returns: {decision, confidence, severity_score, motion_conf, 
   imu_conf, road_conf, ...}
   ↓
5. Determines LoRa transmission:
   - IF decision=HAZARD AND confidence≥75% → PASS (send)
   - IF decision=CAUTION → BLOCKED (don't send) ← Fire Alarm Model
   - IF decision=NORMAL → PASS (send for confirmation)
   ↓
6. Logs everything to CSV:
   logger.log(imu_z, motion_score, result, ground_truth=ground_truth,
              imu_x=imu_x, imu_y=imu_y, cam_event=cam_event, cam_conf=cam_conf,
              road_event=road_event, road_conf=road_conf, rear_event='normal',
              rear_conf=0.0, lora_event=lora_event, lora_sent=should_send,
              lora_latency_ms=0.0)
   ↓
7. CSV row written with all 22 columns ✅
```

---

## Ground Truth Labeling Tips

When running with `--live-label`:

**Best Practices:**
- Label **every** hazard you see (don't skip any)
- Label **normal** sections too (helps with false positive detection)
- Be consistent: use same criteria throughout session
- If unsure, leave blank (only labeled rows counted)

**Example Session:**
```
Frame 1-50    → Mark as NORMAL (normal road) → N key
Frame 51-75   → Pothole visible → Mark as HAZARD → H key
Frame 76-90   → Road is OK again → Mark as NORMAL → N key
Frame 91-105  → Minor roughness → Mark as CAUTION → C key
...
```

**Before pressing Q to quit:**
- Review the session file if needed
- CSV will be saved automatically
- Run validation immediately after for hot feedback

---

## Troubleshooting

### CSV File Not Generated
- Check `output/` folder exists (auto-created)
- Check write permissions on output/
- Look for errors in console output

### CSV Has Empty Columns
- Make sure all detection modules return the expected fields
- Check fusion_engine_v3.py returns motion_conf, imu_conf, road_conf

### validate_output.py Fails
- Install required packages: `pip install numpy pandas` (if needed)
- Check CSV file exists: `dir output/session_*.csv`
- Run with explicit path: `python validate_output.py output/session_20260326_133456.csv`

### Ground Truth Shows 0% Accuracy
- Were labels actually pressed during run? (check output for messages)
- Check that ground_truth column isn't empty: `grep -v "^[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,[^,]*,$" output/session_*.csv | head`

---

## Next Steps

### Testing Workflow
1. ✅ Run system with ground truth labels
2. ✅ Generate CSV automatically  
3. ✅ Validate output with `validate_output.py`
4. 🔄 If needed, adjust thresholds and re-test
5. 📊 Collect statistics for report

### Threshold Tuning
If you need to adjust sensitivity:

**Reduce false positives** (too many HAZARD):
- Increase `LORA_CONFIDENCE_HAZARD` from 0.75 to 0.80 in main.py
- Increase `HAZARD_THRESHOLD` in fusion_engine_v3.py

**Reduce missed detections** (real hazards not detected):
- Decrease `LORA_CONFIDENCE_HAZARD` to 0.70 in main.py
- Lower `HAZARD_THRESHOLD` in fusion_engine_v3.py

**Then re-run tests and validate again!**

---

## Key Files

```
main.py                     ← Front vehicle detection & LoRa transmission
modules/data_logger.py      ← CSV logging (22 columns)
modules/fusion_engine_v3.py ← Confidence-based decision making
validate_output.py          ← Analysis & statistics tool
CSV_VALIDATION_GUIDE.md     ← Technical reference
output/                     ← Your session CSV files
```

---

Your road hazard system is now **fully instrumented with comprehensive logging** for validation, tuning, and analysis! 🚗📡
