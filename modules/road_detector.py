"""
road_detector.py
────────────────
Detects road hazards DIRECTLY from the road surface visible
in the camera frame — independent of front car tracking.
 
Uses a YOLOv8 model trained on road damage dataset (RDD2022).
Detects: potholes, cracks, speed humps directly on road.
 
If the pre-trained road model is not available,
falls back to a simple visual analysis approach.
"""
 
import cv2
import numpy as np
from collections import deque
import time
import os
 
class RoadDetector:
 
    # Road region = bottom portion of frame
    # (where road surface is visible)
    ROAD_REGION_FRACTION = 0.55   # bottom 55% of frame
 
    def __init__(self):
        self.model       = None
        self.model_ready = False
        self.last_event  = 'normal'
        self.last_conf   = 0.0
        self.held_until  = 0.0
        self.HOLD_SEC    = 1.5
 
        # Try loading road damage model
        self._load_model()
 
        # Fallback: visual texture analyser
        self.brightness_buf = deque(maxlen=10)
        self.texture_buf    = deque(maxlen=10)
 
        print("Road Detector initialized.")
        print("-" * 40)
 
    def _load_model(self):
        """
        Tries to load a pre-trained road damage YOLO model.
        Falls back to texture analysis if not found.
        """
        # Check if user has downloaded a road damage model
        candidates = [
            'road_damage.pt',
            'models/road_damage.pt',
            'pothole_detector.pt',
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    from ultralytics import YOLO
                    self.model = YOLO(path)
                    self.model_ready = True
                    print(f"Road damage model loaded: {path}")
                    return
                except Exception as e:
                    print(f"Could not load {path}: {e}")
 
        # No model found — use texture analysis
        print("No road damage model found.")
        print("Using visual texture analysis for road detection.")
        print("(For better results: download a pothole YOLO model")
        print(" and save as 'road_damage.pt' in project folder)")
        self.model_ready = False
 
    def detect(self, frame):
        """
        Detects road hazards directly from frame.
        Returns: (event_type, confidence, description, annotated_frame)
 
        event_type: 'normal' | 'pothole' | 'speed_hump' | 'crack'
        """
        if self.model_ready:
            return self._detect_with_model(frame)
        else:
            return self._detect_with_texture(frame)
 
    def _detect_with_model(self, frame):
        """Use YOLO road damage model"""
        annotated = frame.copy()
        h, w      = frame.shape[:2]
 
        # Only analyse road region (bottom of frame)
        road_y = int(h * (1 - self.ROAD_REGION_FRACTION))
        road_crop = frame[road_y:, :]
 
        try:
            results = self.model(road_crop, verbose=False, conf=0.50)  # Increased from 0.35
            class_map = {
                0: ('pothole',    'Direct pothole detected on road'),
                1: ('crack',      'Road crack detected'),
                2: ('speed_hump', 'Speed hump detected on road'),
                3: ('pothole',    'Road damage detected'),
            }
 
            best_ev   = 'normal'
            best_conf = 0.0
            best_desc = 'Road surface clear'
 
            for r in results:
                for bd in r.boxes:
                    x1,y1,x2,y2 = map(int, bd.xyxy[0])
                    conf = float(bd.conf[0])
                    cls  = int(bd.cls[0])
 
                    ev, desc = class_map.get(cls, ('pothole','Road hazard'))
 
                    if conf > best_conf:
                        best_ev   = ev
                        best_conf = conf
                        best_desc = desc
 
                    # Draw on road region
                    color = {'pothole':(40,40,240),
                             'crack':(0,165,255),
                             'speed_hump':(0,210,255)}.get(ev,(40,40,240))
                    cv2.rectangle(annotated,
                                  (x1, y1+road_y),
                                  (x2, y2+road_y),
                                  color, 2)
                    cv2.putText(annotated,
                                f"ROAD:{ev.upper()} {conf:.0%}",
                                (x1, y1+road_y-8),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.50, color, 1, cv2.LINE_AA)
 
            self._hold(best_ev, best_conf, best_desc)
 
        except Exception as e:
            pass
 
        return self.last_event, self.last_conf, \
               self._get_desc(), annotated
 
    def _detect_with_texture(self, frame):
        """
        Texture-based road analysis when no model available.
        Detects unusual brightness/texture patterns in road region.
        These patterns indicate surface irregularities.
        """
        annotated = frame.copy()
        h, w      = frame.shape[:2]
 
        # Extract road region
        road_y    = int(h * (1 - self.ROAD_REGION_FRACTION))
        road_crop = frame[road_y:, :]
 
        # Convert to grayscale
        gray = cv2.cvtColor(road_crop, cv2.COLOR_BGR2GRAY)

        # ── Laplacian texture (previous method) ──
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture   = float(laplacian.var())
        self.texture_buf.append(texture)

        # ── Edge density using Canny (sharp discontinuities) ──
        edges = cv2.Canny(gray, 50, 150)
        edge_count = float(cv2.countNonZero(edges))
        area = max(1, gray.shape[0] * gray.shape[1])
        edge_density = edge_count / area

        # ── Sobel gradient magnitude variance ──
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        sobel_mag = np.sqrt(sobelx**2 + sobely**2)
        sobel_var = float(sobel_mag.var())

        # ── Entropy of intensity histogram (measures texture randomness) ──
        hist = cv2.calcHist([gray], [0], None, [64], [0,256])
        hist_sum = hist.sum() if hist.sum() > 0 else 1
        p = (hist / hist_sum).flatten()
        # avoid log(0)
        p_nonzero = p[p>0]
        entropy = float(-np.sum(p_nonzero * np.log2(p_nonzero))) if p_nonzero.size>0 else 0.0

        # Brightness baseline
        brightness = float(gray.mean())
        self.brightness_buf.append(brightness)

        # Need a small history to stabilise
        if len(self.texture_buf) < 5:
            return 'normal', 0.0, 'Analysing road...', annotated

        # Normalise feature signals to 0..1 using heuristics
        # (INCREASED thresholds to reduce false positives)
        tex_norm   = min(1.0, max(0.0, (texture - 600.0) / 3000.0))  # Was: 300/2000
        edge_norm  = min(1.0, edge_density / 0.05)  # Was: 0.02 (stricter)
        sobel_norm = min(1.0, max(0.0, (sobel_var - 200.0) / 1200.0))  # Was: 50/800
        ent_norm   = min(1.0, entropy / 7.0)  # Was: 6.0 (stricter)

        # Weighted fusion of texture cues (HIGHER MIN THRESHOLD)
        combined_score = (
            0.35 * tex_norm +
            0.30 * edge_norm +
            0.15 * sobel_norm +
            0.05 * ent_norm
        )

        # Adjust confidence by brightness change (very dark/bright regions reduce confidence)
        avg_brightness = sum(self.brightness_buf) / len(self.brightness_buf)
        brightness_penalty = min(0.4, abs(brightness - avg_brightness) / 80.0)
        confidence = max(0.0, combined_score * (1.0 - brightness_penalty))

        # Decision thresholds - MUCH STRICTER (tuned to reduce false positives)
        if confidence > 0.75:  # Was: 0.60
            # Strong irregularity → pothole
            self._hold('pothole', confidence, 'Texture+edge strong — likely pothole')
        elif confidence > 0.50:  # Was: 0.35
            # Moderate → speed hump or rough patch
            self._hold('speed_hump', confidence, 'Moderate texture change — possible hump')
        else:
            self._hold('normal', 0.0, 'Road surface clear')
 
        # Draw road analysis region on frame
        cv2.rectangle(annotated,
                      (0, road_y), (w, h),
                      (40, 40, 40), 1)
        cv2.putText(annotated, "ROAD ANALYSIS ZONE",
                    (6, road_y+14),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.38, (60,60,60), 1, cv2.LINE_AA)
 
        if self.last_event != 'normal':
            color = {'pothole':(40,40,240),
                     'speed_hump':(0,165,255)}.get(self.last_event,(40,40,240))
            cv2.putText(annotated,
                        f"ROAD:{self.last_event.upper()} {self.last_conf*100:.0f}%",
                        (6, road_y+30),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, color, 2, cv2.LINE_AA)
 
        return self.last_event, self.last_conf, \
               self._get_desc(), annotated
 
    def _hold(self, ev, conf, desc):
        if ev != 'normal':
            self.last_event = ev
            self.last_conf  = conf
            self.held_until = time.time() + self.HOLD_SEC
        else:
            self.last_event = 'normal'
            self.last_conf  = 0.0
            self.held_until = 0.0
 
    def _get_desc(self):
        descs = {
            'normal':    'Road surface clear',
            'pothole':   'Pothole detected on road surface',
            'speed_hump':'Speed hump detected on road',
            'crack':     'Road crack detected',
        }
        return descs.get(self.last_event, '')