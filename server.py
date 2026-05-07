from flask import Flask, jsonify, Response, render_template
from flask_cors import CORS
import threading
import cv2
import numpy as np
import time

app = Flask(__name__)
CORS(app)

latest_data = {
    "status":       "NORMAL",
    "motor_speed":  100,
    "confidence":   "97.0",
    "imu_z":        1.0,
    "motion_score": 0.05,
    "vert_disp":    0.0,
    "imu_spike":    False,
    "camera_high":  False,
    "readings":     0,
    "hazards":      0,
    "cautions":     0,
    "normals":      0,
}

latest_frame = None
frame_lock   = threading.Lock()
data_lock    = threading.Lock()

def update_data(new_data):
    with data_lock:
        latest_data.update(new_data)

def update_frame(frame):
    global latest_frame
    with frame_lock:
        latest_frame = frame.copy()

@app.route('/')
def index():
    return render_template('adas_dashboard.html')

@app.route('/data')
def get_data():
    with data_lock:
        return jsonify(latest_data)

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame',
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma':        'no-cache',
            'Expires':       '0',
        }
    )

def generate_frames():
    while True:
        with frame_lock:
            frame = latest_frame

        if frame is None:
            frame = np.zeros((480, 640, 3), dtype='uint8')
            cv2.putText(frame, "WAITING FOR CAMERA...",
                        (140, 240),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8, (0, 100, 100), 2)

        # Resize to reduce bandwidth
        frame = cv2.resize(frame, (640, 480))

        ret, buffer = cv2.imencode(
            '.jpg', frame,
            [cv2.IMWRITE_JPEG_QUALITY, 60]
        )
        if not ret:
            continue

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' +
               buffer.tobytes() +
               b'\r\n')

        time.sleep(0.04)

def start_server():
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )