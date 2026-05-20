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

import cv2
import os
import sys
import threading
import time
import server

# ── Your existing modules (unchanged) ──
from modules.motion_detector_yolo import MotionDetectorYOLO as MotionDetector
from modules.road_detector         import RoadDetector
from modules.imu_reader            import IMUReader
from modules.fusion_engine         import FusionEngine
from modules.dashboard             import Dashboard
from modules.data_logger           import DataLogger
from modules.graph_generator       import GraphGenerator

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

def send_to_esp32(event_type, severity):
    """
    Sends hazard message to front ESP32 via Serial.
    ESP32 will transmit this via LoRa to rear vehicle.

    Message format: "POTHOLE:0.85"
    """
    global esp32
    if esp32 is None:
        return

    # Map event to clean message
    msg_map = {
        'pothole':    'POTHOLE',
        'speed_hump': 'SPEED_HUMP',
        'braking':    'BRAKING',
        'crack':      'CRACK',
        'normal':     'NORMAL',
    }
    msg_event = msg_map.get(event_type.lower(), 'NORMAL')
    message   = f"{msg_event}:{severity:.2f}\n"

    try:
        esp32.write(message.encode())
    except Exception as e:
        print(f"ESP32 write error: {e}")
        esp32 = None  # will attempt reconnect next time

# ══════════════════════════════════════════
# INITIALIZE ALL MODULES
# ══════════════════════════════════════════
print("Initializing modules...")
detector = MotionDetector()
road_det = RoadDetector()
imu      = IMUReader(port='COM3')  # ← your IMU COM port
fusion   = FusionEngine()
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

# ── Camera ──
camera_index = int(sys.argv[1]) if len(sys.argv) > 1 else 0
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
    'crack':     'CRACK',
}
EV_DESCS = {
    'normal':    'Road surface normal',
    'pothole':   'Pothole detected',
    'speed_hump':'Speed hump detected',
    'braking':   'Front vehicle braking',
    'crack':     'Road crack detected',
}

# ── LoRa send rate limiter ──
# Send to ESP32 max once per second to avoid flooding
last_lora_send = 0
LORA_INTERVAL  = 1.0  # seconds

# ══════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════
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

    # ── Step 4: IMU reading ──
    imu_z = imu.read()

    # ── Step 5: Fusion decision ──
    result = fusion.decide(
        motion_score, imu_z,
        cam_event  = cam_event,  cam_conf  = cam_conf,
        road_event = road_event, road_conf = road_conf,
    )

    # ── Step 6: Log data ──
    logger.log(imu_z, motion_score, result)

    # ── Step 7: Determine best hazard event to send ──
    # Priority: road detector > camera > IMU
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

    # ── Step 8: Send to ESP32 (rate limited) ──
    now = time.time()
    if now - last_lora_send >= LORA_INTERVAL:
        send_to_esp32(lora_event, lora_severity)
        last_lora_send = now

    # ── Step 9: Push to web dashboard ──
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
    )

    # ── Step 11: Terminal output ──
    if result["decision"] != "NORMAL" or lora_event != "normal":
        v2v = "📡 SENDING" if esp32 else "📡 NO ESP32"
        print(
            f"  {result['decision']:7} | "
            f"CAM={EV_LABELS.get(cam_event,'?'):12} | "
            f"ROAD={EV_LABELS.get(road_event,'?'):12} | "
            f"LoRa={EV_LABELS.get(lora_event,'?'):12} | "
            f"Motor={result['motor_speed']:3}% | {v2v}"
        )

    cv2.imshow("ADAS Front Vehicle", display)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# ── Cleanup ──
cap.release()
cv2.destroyAllWindows()
imu.close()
if esp32:
    esp32.close()

print("\nGenerating session report...")
logger.save_summary()
grapher.generate(logger.csv_path)
print("Session complete.")