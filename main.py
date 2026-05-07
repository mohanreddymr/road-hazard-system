import cv2
import os
import sys
import threading
import server
from modules.motion_detector_yolo import MotionDetectorYOLO as MotionDetector
from modules.road_detector         import RoadDetector
from modules.imu_reader            import IMUReader
from modules.fusion_engine         import FusionEngine
from modules.dashboard             import Dashboard
from modules.data_logger           import DataLogger
from modules.graph_generator       import GraphGenerator
 
# ── Initialize ──
detector  = MotionDetector()
road_det  = RoadDetector()
imu       = IMUReader(port='COM3')   # ← change to your COM port
fusion    = FusionEngine()
dash      = Dashboard()
logger    = DataLogger()
grapher   = GraphGenerator()
 
# ── Flask server ──
server_thread = threading.Thread(target=server.start_server, daemon=True)
server_thread.start()
print("="*45)
print("  Dashboard → http://127.0.0.1:5000")
print("="*45)
 
# ── Camera ──
camera_index = int(sys.argv[1]) if len(sys.argv)>1 else 0
print(f"Camera index: {camera_index}")
cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)    # reduces lag
 
if not cap.isOpened():
    print(f"ERROR: Cannot open camera {camera_index}")
    sys.exit(1)
 
print("Camera open. Press Q to quit.")
print("-"*45)
 
EV_LABELS = {
    'normal':    'NORMAL ROAD',
    'pothole':   'POTHOLE',
    'speed_hump':'SPEED HUMP',
    'braking':   'BRAKING',
    'crack':     'CRACK',
}
EV_COLORS = {
    'normal':    (60,240,60),
    'pothole':   (30,30,230),
    'speed_hump':(0,155,255),
    'braking':   (0,200,255),
    'crack':     (0,120,220),
}
EV_DESCS = {
    'normal':    'Road normal',
    'pothole':   'Pothole detected',
    'speed_hump':'Speed hump detected',
    'braking':   'Front vehicle braking',
    'crack':     'Road crack detected',
}
 
while True:
    ret, frame = cap.read()
    if not ret:
        print("Camera read failed.")
        break
 
    # ── 1: YOLO vehicle detection ──
    motion_score, vert_pos, annotated = detector.detect(frame)
    distance_m    = detector.get_distance()
    vehicle_speed = detector.get_vehicle_speed()
    vehicle_count = detector.get_vehicle_count()   # live, resets dynamically
 
    # ── 2: Camera event from front car tracking ──
    cam_event, cam_conf, cam_desc = detector.get_camera_event()
 
    # ── 3: Road surface detection (independent) ──
    road_event, road_conf, road_desc, annotated = \
        road_det.detect(annotated)   # runs on annotated frame
 
    # ── 4: IMU (secondary) ──
    imu_z = imu.read()
 
    # ── 5: Three-source fusion ──
    result = fusion.decide(
        motion_score, imu_z,
        cam_event  = cam_event,  cam_conf  = cam_conf,
        road_event = road_event, road_conf = road_conf,
    )
 
    # ── 6: Log ──
    logger.log(imu_z, motion_score, result)
 
    # ── 7: Web dashboard ──
    server.update_frame(annotated)
    server.update_data({
        "status":         result["decision"],
        "motor_speed":    result["motor_speed"],
        "confidence":     result["confidence"],
        "imu_z":          result["raw_imu"],
        "motion_score":   result["raw_motion"],
        "vert_disp":      round(float(vert_pos),1),
        "imu_spike":      result["imu_spike"],
        "camera_high":    result["camera_high"],
        "readings":       logger.total_readings,
        "hazards":        logger.hazard_count,
        "cautions":       logger.caution_count,
        "normals":        logger.normal_count,
        "distance_m":     distance_m    or 0,
        "vehicle_speed":  vehicle_speed or 0,
        "vehicle_count":  vehicle_count,
        "severity":       result.get("severity_score",0),
        "camera_event":   EV_LABELS.get(cam_event,  "NORMAL ROAD"),
        "road_event":     EV_LABELS.get(road_event, "NORMAL ROAD"),
        "camera_event_desc": EV_DESCS.get(cam_event,''),
        "road_event_desc":   EV_DESCS.get(road_event,''),
    })
 
    # ── 8: OpenCV popup ──
    display = dash.draw(
        annotated, result,
        distance_m       = distance_m,
        vehicle_speed    = vehicle_speed,
        vehicle_count    = vehicle_count,
        cam_event        = EV_LABELS.get(cam_event,  "NORMAL ROAD"),
        cam_event_desc   = EV_DESCS.get(cam_event,   ''),
        road_event       = EV_LABELS.get(road_event, "NORMAL ROAD"),
        road_event_desc  = EV_DESCS.get(road_event,  ''),
        imu_event_conf   = round(max(cam_conf,road_conf)*100),
    )
 
    # ── 9: Terminal ──
    if result["decision"]!="NORMAL" or cam_event!="normal" or road_event!="normal":
        print(
            f"  {result['decision']:7} | "
            f"CAM={EV_LABELS.get(cam_event,'?'):12} | "
            f"ROAD={EV_LABELS.get(road_event,'?'):12} | "
            f"Motor={result['motor_speed']:3}% | "
            f"Dist={str(distance_m)+'m' if distance_m else 'N/A':6} | "
            f"Veh={vehicle_count}"
        )
 
    cv2.imshow("ADAS - Road Hazard System", display)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
 
cap.release()
cv2.destroyAllWindows()
imu.close()
 
print("\nGenerating report...")
logger.save_summary()
grapher.generate(logger.csv_path)
print("Done.")
 