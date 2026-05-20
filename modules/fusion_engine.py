"""
fusion_engine_v2.py
━━━━━━━━━━━━━━━━━━
Improved fusion engine.
Uses new 9-feature model with scaler.
Camera remains PRIMARY decision source.
IMU secondary confirmation.
"""
 
import joblib
import os
import numpy as np
from collections import deque
 
class FusionEngine:
 
    def __init__(self):
        model_path  = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'imu_simulation', 'hazard_model.pkl'
        )
        scaler_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'imu_simulation', 'scaler.pkl'
        )
 
        print("Loading improved ML model...")
        saved      = joblib.load(model_path)
 
        # Handle both old format (just model) and new format (dict)
        if isinstance(saved, dict):
            self.model   = saved['model']
            self.scaler  = saved.get('scaler',  None)
            self.encoder = saved.get('encoder', None)
            cv_acc       = saved.get('cv_mean', 0)
            test_acc     = saved.get('test_acc', 0)
            print(f"✅ Model loaded — CV: {cv_acc*100:.1f}% | Test: {test_acc*100:.1f}%")
        else:
            # Old format
            self.model   = saved
            self.scaler  = None
            self.encoder = None
            print("✅ Model loaded (legacy format)")
 
        # Load scaler separately if exists and not in dict
        if self.scaler is None and os.path.exists(scaler_path):
            self.scaler = joblib.load(scaler_path)
 
        # IMU window for feature extraction
        self.imu_window   = deque(maxlen=10)
        self.imu_history  = [1.0, 1.0, 1.0]
 
        # Stability buffer
        self.dec_history  = deque(maxlen=7)
        self.current      = "NORMAL"
        self.severity     = 0.0
 
        # Class label map
        self.label_map = {
            0: 'normal',
            1: 'caution',
            2: 'hazard',
            # If encoder available use it
        }
 
        print("Fusion Engine v2 ready.")
        print("Camera=PRIMARY | IMU=secondary | Model=ensemble")
        print("-" * 40)
 
    def _extract_features(self, imu_z):
        """
        Extracts 9 features from IMU window.
        Matches features used during training.
        """
        self.imu_window.append(float(imu_z))
        w = np.array(list(self.imu_window))
 
        if len(w) < 2:
            w = np.array([1.0] * 10)
 
        diffs = np.abs(np.diff(w))
 
        features = np.array([[
            float(w[-1]),                               # imu_now
            float(w.mean()),                            # imu_mean
            float(w.std()),                             # imu_std
            float(w.max()),                             # imu_max
            float(w.min()),                             # imu_min
            float(w.max() - w.min()),                   # imu_range
            float(diffs.max()) if len(diffs)>0 else 0, # imu_max_diff
            float(diffs.mean()) if len(diffs)>0 else 0,# imu_mean_diff
            float(w[-1]-w[-2]) if len(w)>=2 else 0,    # imu_rate
        ]], dtype=np.float32)
 
        # Replace NaN/Inf
        features = np.nan_to_num(features, nan=0.0, posinf=3.5, neginf=0.0)
 
        return features
 
    def _get_ml_confidence(self, features):
        """
        Gets prediction confidence from ML model.
        Returns confidence as 0-100 float.
        """
        try:
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features
 
            proba      = self.model.predict_proba(features_scaled)
            confidence = float(proba.max()) * 100
            return round(confidence, 1)
        except Exception as e:
            return 50.0
 
    def decide(self, motion_score, imu_z,
               cam_event='normal',  cam_conf=0.0,
               road_event='normal', road_conf=0.0):
        """
        Three-source fusion decision.
        Priority: Road detector > Camera > Motion > IMU
        """
        imu_z = float(imu_z)
 
        # Extract IMU features for ML model
        features  = self._extract_features(imu_z)
        ml_conf   = self._get_ml_confidence(features)
 
        imu_spike = imu_z > 1.8
        ev_cam    = cam_event.lower()
        ev_road   = road_event.lower()
 
        # ── Priority 1: Road detector ──
        if ev_road in ('pothole', 'crack') and road_conf > 0.3:
            decision = 'hazard'
            severity = min(1.0, 0.55 + road_conf * 0.45)
 
        elif ev_road == 'speed_hump' and road_conf > 0.3:
            decision = 'caution'
            severity = min(1.0, 0.3 + road_conf * 0.4)
 
        # ── Priority 2: Camera (front car) ──
        elif ev_cam == 'pothole' and cam_conf > 0.3:
            decision = 'hazard'
            severity = min(1.0, 0.5 + cam_conf * 0.4)
 
        elif ev_cam in ('speed_hump', 'braking') and cam_conf > 0.3:
            decision = 'caution'
            severity = min(1.0, 0.25 + cam_conf * 0.4)
 
        # ── Priority 3: Motion score ──
        elif motion_score > 3.0:
            decision = 'hazard'
            severity = min(1.0, motion_score / 5.0)
 
        elif motion_score > 0.8:
            decision = 'caution'
            severity = motion_score / 5.0
 
        # ── Priority 4: IMU alone ──
        elif imu_spike:
            decision = 'caution'
            severity = min(1.0, (imu_z - 1.0) / 2.0)
 
        else:
            decision = 'normal'
            severity = 0.0
 
        severity = round(min(1.0, float(severity)), 2)
 
        # IMU upgrades caution → hazard when it confirms
        if imu_spike and decision == 'caution':
            decision = 'hazard'
            severity = min(1.0, severity + 0.2)
 
        self.severity = severity
 
        # Boost ML confidence when camera/road is certain
        best_src_conf = max(cam_conf, road_conf)
        if best_src_conf > 0.65:
            ml_conf = min(99.0, ml_conf + best_src_conf * 15)
 
        # ── Stability buffer ──
        self.dec_history.append(decision)
        stable = max(
            set(self.dec_history),
            key=self.dec_history.count
        ).upper()
        self.current = stable
 
        # ── Graduated motor speed ──
        motor_speed = self._calc_speed(decision, severity)
 
        # Update IMU history
        self.imu_history.insert(0, imu_z)
        self.imu_history = self.imu_history[:3]
 
        return {
            "decision":       stable,
            "motor_speed":    motor_speed,
            "confidence":     round(ml_conf, 1),
            "severity_score": severity,
            "camera_high":    bool(motion_score > 0.8),
            "imu_spike":      imu_spike,
            "raw_motion":     round(motion_score, 2),
            "raw_imu":        round(imu_z, 3),
            "cam_event":      cam_event,
            "road_event":     road_event,
        }
 
    def _calc_speed(self, decision, severity):
        if decision == 'normal':  return 100
        if decision == 'caution': return round(max(50, 100 - severity * 50))
        if decision == 'hazard':  return round(max(15, 100 - severity * 70))
        return 100