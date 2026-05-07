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
            results = self.model(road_crop, verbose=False, conf=0.35)
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
 
        # ── Texture analysis using Laplacian ──
        # High Laplacian variance = rough surface (pothole/crack)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture   = float(laplacian.var())
        self.texture_buf.append(texture)
 
        # ── Brightness analysis ──
        brightness = float(gray.mean())
        self.brightness_buf.append(brightness)
 
        if len(self.texture_buf) < 5:
            return 'normal', 0.0, 'Analysing road...', annotated
 
        avg_texture    = sum(self.texture_buf) / len(self.texture_buf)
        avg_brightness = sum(self.brightness_buf) / len(self.brightness_buf)
 
        # Baseline from first few readings
        # High texture spike = surface irregularity
        tex_list = list(self.texture_buf)
        tex_mean = sum(tex_list) / len(tex_list)
        tex_max  = max(tex_list)
 
        # ── Classification ──
        # Pothole: very high texture (rough edges/shadows)
        # Speed hump: moderate texture + brightness change
        # Normal: low, consistent texture
 
        if tex_max > tex_mean * 2.5 and tex_max > 800:
            conf = min(1.0, (tex_max - 800) / 2000.0)
            self._hold('pothole', conf,
                       'Road texture spike — surface irregularity')
 
        elif tex_max > tex_mean * 1.8 and tex_max > 400:
            conf = min(1.0, (tex_max - 400) / 1500.0)
            self._hold('speed_hump', conf,
                       'Road texture change — possible hump')
 
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
        elif time.time() >= self.held_until:
            self.last_event = 'normal'
            self.last_conf  = 0.0
 
    def _get_desc(self):
        descs = {
            'normal':    'Road surface clear',
            'pothole':   'Pothole detected on road surface',
            'speed_hump':'Speed hump detected on road',
            'crack':     'Road crack detected',
        }
        return descs.get(self.last_event, '')