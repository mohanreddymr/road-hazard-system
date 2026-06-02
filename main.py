"""
FRONT VEHICLE — main.py
━━━━━━━━━━━━━━━━━━━━━━━
Runs on Front Vehicle laptop.
Does:
  1. YOLO vehicle detection
  2. Road surface detection
  3. IMU sensor fusion
  4. ML decision making
  5. Sends hazard via Serial to ESP32 (front)
     which transmits via LoRa to rear vehicle
  6. Web dashboard on http://127.0.0.1:5000
  7. OpenCV popup window
"""

import argparse
import csv
import cv2
import os
import sys
import threading
import time
from collections import defaultdict
import server

# ── Your existing modules (unchanged) ──
from modules.motion_detector_yolo import MotionDetectorYOLO as MotionDetector
from modules.road_detector         import RoadDetector
from modules.imu_reader_enhanced  import IMUReaderEnhanced
from modules.fusion_engine_v3     import FusionEngineV3
from modules.dashboard             import Dashboard
from modules.data_logger           import DataLogger
from modules.graph_generator       import GraphGenerator
from validate_output               import OutputValidator

# ══════════════════════════════════════════
# ESP32 SERIAL CONNECTION (Front Vehicle)
# ══════════════════════════════════════════
import serial as pyserial

ESP32_PORT = 'COM6'    # ← CHANGE THIS to your front ESP32 COM port
ESP32_BAUD = 9600

esp32 = None

def connect_esp32():
    global esp32
    try:
        esp32 = pyserial.Serial(ESP32_PORT, ESP32_BAUD, timeout=1)
        time.sleep(2)
        esp32.flushInput()
        print(f"✅ ESP32 (front) connected on {ESP32_PORT}")
    except Exception as e:
        print(f"⚠️  ESP32 not found on {ESP32_PORT}: {e}")
        print("   Running without V2V LoRa transmission.")
        esp32 = None


def load_ground_truth(path):
    labels = []
    if not path:
        return labels
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames and 'ground_truth' in [name.strip().lower() for name in reader.fieldnames]:
                for row in reader:
                    value = row.get('ground_truth', '').strip()
                    if value:
                        labels.append(value)
            else:
                f.seek(0)
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        labels.append(str(row[0]).strip())
    except Exception as e:
        print(f"⚠️  Could not load ground truth file {path}: {e}")
    return labels


def write_live_label(file_handle, frame_index, label):
    try:
        writer = csv.writer(file_handle)
        writer.writerow([frame_index, label, time.strftime('%Y-%m-%d %H:%M:%S')])
        file_handle.flush()
    except Exception as e:
        print(f"⚠️ Could not write live label: {e}")



def send_to_esp32(event_type, severity, rssi=0.0):
    """
    Sends hazard message to front ESP32 via Serial.
    ESP32 transmits via LoRa to rear vehicle.

    Agreed message format (5 fields, colon-separated):
        DECISION:EVENT:SEVERITY:RSSI:TIMESTAMP
    Example:
        HAZARD:POTHOLE:0.85:-72:1716811234.123
        NORMAL:NORMAL:0.00:0:1716811234.456
    """
    global esp32
    if esp32 is None:
        return

    msg_map = {
        'pothole':    'POTHOLE',
        'speed_hump': 'SPEED_HUMP',
        'braking':    'BRAKING',
        'normal':     'NORMAL',
    }

    # ── Map event → decision ──
    event_upper = event_type.upper()
    msg_event   = msg_map.get(event_type.lower(), 'NORMAL')

    if event_type.lower() in ('pothole', 'speed_hump'):
        decision = 'HAZARD'
    elif event_type.lower() == 'braking':
        decision = 'CAUTION'
    else:
        decision = 'NORMAL'

    send_time = time.time()          # epoch seconds (float, 3 decimal places)
    rssi_int  = int(round(rssi))     # RSSI as integer dBm (e.g. -72)

    # Format: DECISION:EVENT:SEVERITY:RSSI:TIMESTAMP\n
    message = f"{decision}:{msg_event}:{severity:.2f}:{rssi_int}:{send_time:.3f}\n"

    try:
        esp32.write(message.encode())
        print(f"  📡 LoRa TX → {message.strip()}")
    except Exception as e:
        print(f"  ESP32 write error: {e}")
        esp32 = None
# ══════════════════════════════════════════
# INITIALIZE ALL MODULES
# ══════════════════════════════════════════
print("Initializing modules...")
detector = MotionDetector()
road_det = RoadDetector()
imu      = IMUReaderEnhanced(port='COM3')  # ← your IMU COM port
fusion   = FusionEngineV3()
dash     = Dashboard()
logger   = DataLogger()
grapher  = GraphGenerator()

# Connect ESP32
connect_esp32()

# ── Flask server (front vehicle dashboard) ──
server_thread = threading.Thread(
    target=server.start_server, daemon=True
)
server_thread.start()
print("=" * 45)
print("  Front Dashboard → http://127.0.0.1:5000")
print("=" * 45)

parser = argparse.ArgumentParser(description='Front vehicle hazard detection')
parser.add_argument('camera_index', nargs='?', type=int, default=0)
parser.add_argument('--feedback-path', help='Path to save Y/N feedback log')
parser.add_argument('--primary-mode', choices=['area','distance','center','confidence'], default='area',
                    help='Primary vehicle selection mode')
args = parser.parse_args()

frame_index = 0
live_label_path = args.feedback_path or os.path.join(logger.output_dir, f'session_{logger.session_number}_feedback.csv')
live_label_file = None

# Accuracy tracking
total_labeled = 0
correct_labeled = 0
accuracy_by_type = {}  # Track accuracy per decision type
labeled_decisions = {}  # Store labeled data for post-session report

# Event-level metrics for ground truth event labels
event_confusion = defaultdict(lambda: defaultdict(int))
labeling_mode = False
feedback_prompt = ''
try:
    live_label_file = open(live_label_path, 'w', newline='', encoding='utf-8')
    writer = csv.writer(live_label_file)
    writer.writerow(['frame_index', 'decision', 'predicted_event', 'actual_event', 'user_feedback', 'is_correct', 'timestamp'])
    print(f"✓ Real-time feedback enabled. Saving to: {live_label_path}")
except Exception as e:
    print(f"⚠️ Could not open feedback file: {e}")
    live_label_file = None

# Apply primary selection mode to detector (area/distance/center/confidence)
try:
    detector.primary_mode = args.primary_mode
    print(f"Primary selection mode: {args.primary_mode}")
except Exception:
    pass
# ── Camera ──
camera_index = args.camera_index
print(f"Opening camera {camera_index}...")
cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

if not cap.isOpened():
    print(f"ERROR: Cannot open camera {camera_index}")
    sys.exit(1)

print("Camera opened. Press Q to quit.")
print("-" * 45)

# ── Event label maps ──
EV_LABELS = {
    'normal':    'NORMAL ROAD',
    'pothole':   'POTHOLE',
    'speed_hump':'SPEED HUMP',
    'braking':   'BRAKING',
}
EV_DESCS = {
    'normal':    'Road surface normal',
    'pothole':   'Pothole detected',
    'speed_hump':'Speed hump detected',
    'braking':   'Front vehicle braking',
}

# ── LoRa send rate limiter ──
# Send to ESP32 max once per second to avoid flooding
last_lora_send = 0
LORA_INTERVAL  = 1.0  # seconds

# ── LoRa Confidence Thresholds ──
# STRATEGY: Only send HIGH-CONFIDENCE HAZARD + confirmations
# Rear vehicle has own sensors, so don't disturb driver with CAUTION
LORA_CONFIDENCE_HAZARD = 0.75   # 75% - high bar, real danger only
LORA_CONFIDENCE_CAUTION = 1.00  # 100% - NEVER SEND CAUTION (rear has own sensors)
LORA_CONFIDENCE_NORMAL = 0.0    # Always - confirmation/clearing alerts

# ══════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════
try:
    while True:
        ret, frame = cap.read()
        if not ret:
            print("Camera read failed.")
            break

        # ── Step 1: YOLO vehicle detection ──
        motion_score, vert_pos, annotated = detector.detect(frame)
        distance_m    = detector.get_distance()
        vehicle_speed = detector.get_vehicle_speed()
        vehicle_count = detector.get_vehicle_count()

        # ── Step 2: Camera event from front car ──
        cam_event, cam_conf, cam_desc = detector.get_camera_event()

        # ── Step 3: Road surface detection ──
        road_event, road_conf, road_desc, annotated = \
            road_det.detect(annotated)

        # Only use the three target hazard classes in fusion
        if cam_event == 'crack':
            cam_event = 'normal'
            cam_conf = 0.0
        if road_event == 'crack':
            road_event = 'normal'
            road_conf = 0.0

        # ── Step 4: IMU reading ──
        imu_z, imu_x, imu_y = imu.read()

        # ── Step 5: Fusion decision ──
        result = fusion.decide(
            motion_score, imu_z, imu_x=imu_x, imu_y=imu_y,
            cam_event  = cam_event,  cam_conf  = cam_conf,
            road_event = road_event, road_conf = road_conf,
            rear_event = 'normal', rear_conf = 0.0,
        )

        # ── Step 6: ground truth label and log
        ground_truth = None

        # ── Step 7: Determine best hazard event to send ──
        # Priority: road detector > camera > IMU
        # NOW WITH CONFIDENCE FILTERING
    
        # Get overall confidence from fusion engine
        fusion_confidence = result.get("confidence", 0.0) / 100.0  # Convert to 0-1
    
        if road_event not in ('normal', '') and road_conf > 0.3:
            lora_event    = road_event
            lora_severity = result.get("severity_score", 0.0)
        elif cam_event not in ('normal', '') and cam_conf > 0.3:
            lora_event    = cam_event
            lora_severity = result.get("severity_score", 0.0)
        elif result["decision"] == "HAZARD":
            lora_event    = "pothole"
            lora_severity = result.get("severity_score", 0.0)
        elif result["decision"] == "CAUTION":
            lora_event    = cam_event if cam_event != 'normal' else "braking"
            lora_severity = result.get("severity_score", 0.0)
        else:
            lora_event    = "normal"
            lora_severity = 0.0

        # ── Step 7B: Apply confidence filter before sending ──
        # STRATEGY: Send high-confidence HAZARD + BRAKING warnings
        # Skip low-confidence CAUTION (except BRAKING which is important warning)
        should_send = False
        if result["decision"] == "HAZARD" and fusion_confidence >= LORA_CONFIDENCE_HAZARD:
            should_send = True  # Real danger - send alert
        elif result["decision"] == "CAUTION" and cam_event == "braking" and cam_conf > 0.60:
            should_send = True  # BRAKING is important warning - send it
        elif result["decision"] == "CAUTION":
            should_send = False  # Other caution - rear vehicle has own detection
        elif result["decision"] == "NORMAL":  
            should_send = True  # Always send confirmation
    
        # Downgrade low-confidence HAZARD to NORMAL (don't send unconfirmed alerts)
        if not should_send and result["decision"] == "HAZARD":
            lora_event = "normal"
            lora_severity = 0.0

        # ── Step 8: Send to ESP32 (rate limited + confidence filtered) ──
        now = time.time()
        if now - last_lora_send >= LORA_INTERVAL:
            if should_send:  # Only send if confidence threshold met
                send_to_esp32(lora_event, lora_severity)
            last_lora_send = now

        # ── Step 9: Push to web dashboard ──
        accuracy_pct = (correct_labeled / total_labeled * 100) if total_labeled > 0 else 0.0
        server.update_frame(annotated)
        server.update_data({
            "status":            result["decision"],
            "motor_speed":       result["motor_speed"],
            "confidence":        result["confidence"],
            "imu_z":             result["raw_imu"],
            "motion_score":      result["raw_motion"],
            "vert_disp":         round(float(vert_pos), 1),
            "imu_spike":         result["imu_spike"],
            "camera_high":       result["camera_high"],
            "readings":          logger.total_readings,
            "hazards":           logger.hazard_count,
            "cautions":          logger.caution_count,
            "normals":           logger.normal_count,
            "distance_m":        distance_m    or 0,
            "vehicle_speed":     vehicle_speed or 0,
            "vehicle_count":     vehicle_count,
            "severity":          result.get("severity_score", 0),
            "camera_event":      EV_LABELS.get(cam_event,  "NORMAL ROAD"),
            "road_event":        EV_LABELS.get(road_event, "NORMAL ROAD"),
            "camera_event_desc": EV_DESCS.get(cam_event,  ''),
            "road_event_desc":   EV_DESCS.get(road_event, ''),
            "lora_sending":      lora_event != 'normal',
            "lora_event":        EV_LABELS.get(lora_event, 'NORMAL ROAD'),
            "lora_confidence":   round(fusion_confidence * 100, 1),  # Display confidence
            "lora_blocked":      not should_send and result["decision"] != "NORMAL",  # Was blocked?
            "accuracy_pct":      round(accuracy_pct, 1),
            "total_labeled":     total_labeled,
            "correct_labeled":   correct_labeled,
        })

        # ── Step 10: OpenCV popup window ──
    
        display = dash.draw(
            annotated, result,
            distance_m      = distance_m,
            vehicle_speed   = vehicle_speed,
            vehicle_count   = vehicle_count,
            cam_event       = EV_LABELS.get(cam_event,  "NORMAL ROAD"),
            cam_event_desc  = EV_DESCS.get(cam_event,   ''),
            road_event      = EV_LABELS.get(road_event, "NORMAL ROAD"),
            road_event_desc = EV_DESCS.get(road_event,  ''),
            imu_event_conf  = round(max(cam_conf, road_conf) * 100),
            accuracy_pct    = accuracy_pct,
            total_labeled   = total_labeled
        )

        cv2.putText(display,
                    "Press Y/N to mark decision correct/incorrect.",
                    (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(display,
                    "If incorrect, press P/S/B/0 for actual event after N.",
                    (12, 46), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 255, 255), 1, cv2.LINE_AA)

        # ── Step 11: Terminal output ─
        if result["decision"] != "NORMAL" or (should_send and lora_event != "normal"):
            if not should_send and result["decision"] == "HAZARD":
                alert_status = f"⚠️  DETECTED (Conf={fusion_confidence*100:.0f}% <75%, not sent)"
            elif not should_send and result["decision"] == "CAUTION":
                alert_status = f"ℹ️  CAUTION (Rear has own sensors, skipped)"
            elif should_send:
                alert_status = f"📡 SENDING"
            else:
                alert_status = f"📡 NO ESP32"
        
            v2v_status = alert_status if esp32 else "📡 NO ESP32"
            print(
                f"  {result['decision']:7} | "
                f"CAM={EV_LABELS.get(cam_event,'?'):12} | "
                f"ROAD={EV_LABELS.get(road_event,'?'):12} | "
                f"LoRa={EV_LABELS.get(lora_event,'?'):12} | "
                f"Conf={fusion_confidence*100:.0f}% | "
                f"Motor={result['motor_speed']:3}% | {v2v_status}"
            )

        if labeling_mode:
            cv2.putText(display,
                        feedback_prompt,
                        (12, 66), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                        (0, 255, 255), 1, cv2.LINE_AA)

        cv2.imshow("ADAS Front Vehicle", display)
        key = cv2.waitKey(10) & 0xFF

        actual_event = None
        is_correct = None

        if labeling_mode:
            if key == ord('q'):
                break
            elif key == ord('p'):
                actual_event = 'pothole'
            elif key == ord('s'):
                actual_event = 'speed_hump'
            elif key == ord('b'):
                actual_event = 'braking'
            elif key == ord('0'):
                actual_event = 'normal'
            elif key == ord('c'):
                labeling_mode = False
                feedback_prompt = ''

            if actual_event is not None:
                labeling_mode = False
                feedback_prompt = ''
                is_correct = False

        else:
            if key == ord('q'):
                break
            elif key == ord('y'):
                actual_event = lora_event
                is_correct = True
                correct_labeled += 1
            elif key == ord('n'):
                labeling_mode = True
                feedback_prompt = "INCORRECT: press P/S/B/0 for actual event, C to cancel"

        if is_correct is not None:
            total_labeled += 1
            decision_type = result["decision"]
            predicted_event = lora_event

            # Track accuracy per decision type
            if decision_type not in accuracy_by_type:
                accuracy_by_type[decision_type] = {"correct": 0, "total": 0}
            accuracy_by_type[decision_type]["total"] += 1
            if is_correct:
                accuracy_by_type[decision_type]["correct"] += 1

            # Track event-level confusion for report
            if actual_event is not None:
                event_confusion[actual_event][predicted_event] += 1

            # Store for post-session report
            if frame_index not in labeled_decisions:
                labeled_decisions[frame_index] = {
                    "decision": decision_type,
                    "predicted_event": predicted_event,
                    "actual_event": actual_event or '',
                    "user_feedback": "CORRECT" if is_correct else "INCORRECT",
                    "is_correct": is_correct,
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
                }

            # Write to feedback file
            if live_label_file:
                writer = csv.writer(live_label_file)
                writer.writerow([
                    frame_index, decision_type, predicted_event,
                    actual_event or '', "CORRECT" if is_correct else "INCORRECT",
                    1 if is_correct else 0, time.strftime('%Y-%m-%d %H:%M:%S')
                ])
                live_label_file.flush()

        logger.log(imu_z, motion_score, result, ground_truth=actual_event,
                   imu_x=imu_x, imu_y=imu_y, cam_event=cam_event, cam_conf=cam_conf,
                   road_event=road_event, road_conf=road_conf, rear_event='normal', rear_conf=0.0,
                   lora_event=lora_event, lora_sent=should_send, lora_latency_ms=0.0)
        frame_index += 1

except KeyboardInterrupt:
    print("\nSession interrupted by user.")
except Exception as e:
    print(f"\nUnexpected error during session: {e}")
finally:
    # ── Cleanup ──
    try:
        cap.release()
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    try:
        imu.close()
    except Exception:
        pass
    if live_label_file:
        try:
            live_label_file.close()
        except Exception:
            pass
    if esp32:
        try:
            esp32.close()
        except Exception:
            pass

    # ═══════════════════════════════════════════
    # GENERATE ACCURACY REPORT
    # ═══════════════════════════════════════════
    print("\n" + "="*70)
    print("📊 REAL-TIME VALIDATION ACCURACY REPORT")
    print("="*70)

    if total_labeled > 0:
        overall_accuracy = (correct_labeled / total_labeled) * 100
        print(f"\n✓ Total Labeled Frames: {total_labeled}")
        print(f"✓ Correct Predictions : {correct_labeled}")
        print(f"✓ Incorrect Predictions: {total_labeled - correct_labeled}")
        print(f"✓ Overall Accuracy    : {overall_accuracy:.1f}%")
    
        print("\n📈 ACCURACY BY DECISION TYPE:")
        print("-" * 70)
        print(f"{'Decision Type':<20} {'Correct':<12} {'Total':<12} {'Accuracy':<12}")
        print("-" * 70)
    
        for decision_type in sorted(accuracy_by_type.keys()):
            stats = accuracy_by_type[decision_type]
            correct = stats["correct"]
            total = stats["total"]
            acc = (correct / total * 100) if total > 0 else 0.0
            print(f"{decision_type:<20} {correct:<12} {total:<12} {acc:>10.1f}%")
    
        # Save accuracy report to file
        accuracy_report_path = logger.csv_path.replace('.csv', '_accuracy_report.txt')
        def compute_metrics(confusion, label):
            tp = confusion[label].get(label, 0)
            fp = sum(confusion[pred].get(label, 0) for pred in confusion if pred != label)
            fn = sum(confusion[label].get(pred, 0) for pred in confusion[label] if pred != label)
            precision = tp / (tp + fp) if tp + fp > 0 else 0.0
            recall = tp / (tp + fn) if tp + fn > 0 else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if precision + recall > 0 else 0.0
            support = sum(confusion[label].values())
            return precision, recall, f1, support

        with open(accuracy_report_path, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write("📊 REAL-TIME VALIDATION ACCURACY REPORT\n")
            f.write("="*70 + "\n\n")
            f.write(f"Session File: {logger.csv_path}\n")
            f.write(f"Feedback File: {live_label_path}\n\n")
            f.write(f"Total Labeled Frames: {total_labeled}\n")
            f.write(f"Correct Predictions : {correct_labeled}\n")
            f.write(f"Incorrect Predictions: {total_labeled - correct_labeled}\n")
            f.write(f"Overall Accuracy    : {overall_accuracy:.1f}%\n\n")
            f.write("ACCURACY BY DECISION TYPE:\n")
            f.write("-" * 70 + "\n")
        
            for decision_type in sorted(accuracy_by_type.keys()):
                stats = accuracy_by_type[decision_type]
                correct = stats["correct"]
                total = stats["total"]
                acc = (correct / total * 100) if total > 0 else 0.0
                f.write(f"{decision_type:<20} {correct:>6}/{total:<6} → {acc:>6.1f}%\n")

            if event_confusion:
                f.write("\nEVENT METRICS (actual event → predicted event):\n")
                f.write("-" * 70 + "\n")
                f.write(f"{'Event':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}\n")
                f.write("-" * 70 + "\n")
                for label in ['pothole', 'speed_hump', 'braking', 'normal']:
                    precision, recall, f1, support = compute_metrics(event_confusion, label)
                    f.write(f"{label:<15} {precision*100:>9.1f}% {recall*100:>9.1f}% {f1*100:>9.1f}% {support:>10}\n")

        print(f"\n✓ Accuracy report saved to: {accuracy_report_path}\n")
    else:
        print("\nℹ️  No labeled frames during this session.")
        print("Tip: Press 'Y' to mark correct decisions, 'N' for incorrect ones.\n")

    print("\nGenerating session report...")
    logger.save_summary()

    if total_labeled > 0:
        print("\nRunning validate_output report on this session...")
        validator = OutputValidator(logger.csv_path)
        validator.generate_report()
    else:
        print("\nNo labeled frames to validate. Press Y or N during sessions next time.")

    grapher.generate(logger.csv_path)
    print("Session complete.")
