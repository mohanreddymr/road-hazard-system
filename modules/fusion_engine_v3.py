"""
fusion_engine_v3.py
Improved adaptive fusion engine for road hazard detection
"""

import joblib
import os
import numpy as np
from collections import deque


class KalmanFilter1D:
    """Simple 1D Kalman filter"""

    def __init__(self, process_variance=0.01, measurement_variance=0.1):
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.value = 0.5
        self.estimate_error = 1.0
        self.kalman_gain = 0.0

    def update(self, measurement):
        self.estimate_error += self.process_variance

        self.kalman_gain = self.estimate_error / (
            self.estimate_error + self.measurement_variance
        )

        self.value = self.value + self.kalman_gain * (
            measurement - self.value
        )

        self.estimate_error = (
            1 - self.kalman_gain
        ) * self.estimate_error

        return self.value


class FusionEngineV3:

    def __init__(self):

        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "imu_simulation",
            "hazard_model.pkl"
        )

        print("Loading improved ML model v3...")

        saved = joblib.load(model_path)

        if isinstance(saved, dict):
            self.model = saved["model"]
            self.scaler = saved.get("scaler", None)
            self.encoder = saved.get("encoder", None)

            cv_acc = saved.get("cv_mean", 0)
            test_acc = saved.get("test_acc", 0)

            print(
                f"✅ Model loaded — CV: {cv_acc*100:.1f}% | Test: {test_acc*100:.1f}%"
            )

        else:
            self.model = saved
            self.scaler = None
            self.encoder = None
            print("✅ Model loaded (legacy format)")

        if self.scaler is None:
            scaler_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "data",
                "imu_simulation",
                "scaler.pkl"
            )

            if os.path.exists(scaler_path):
                self.scaler = joblib.load(scaler_path)

        # IMU windows
        self.imu_window_z = deque(maxlen=10)
        self.imu_window_x = deque(maxlen=10)
        self.imu_window_y = deque(maxlen=10)

        # Kalman filters
        self.kalman_imu = KalmanFilter1D(
            process_variance=0.005,
            measurement_variance=0.08
        )

        self.kalman_motion = KalmanFilter1D(
            process_variance=0.01,
            measurement_variance=0.1
        )

        self.kalman_road = KalmanFilter1D(
            process_variance=0.015,
            measurement_variance=0.12
        )

        # Decision stability
        self.decision_history = deque(maxlen=5)
        self.confidence_history = deque(maxlen=5)

        self.false_positive_penalty = 0.0

        self.current = "NORMAL"
        self.severity = 0.0

        # UPDATED SENSOR WEIGHTS - Motion dominant, IMU reduced
        self.weights = {
            "motion": 0.45,
            "road": 0.35,
            "imu": 0.05,
            "rear": 0.15,
        }

        print("Fusion Engine v3 ready.")
        print(f"Sensor weights: {self.weights}")
        print("-" * 50)

    def _extract_multiaxis_features(self, imu_z, imu_x=None, imu_y=None):

        self.imu_window_z.append(float(imu_z))

        if imu_x is not None:
            self.imu_window_x.append(float(imu_x))

        if imu_y is not None:
            self.imu_window_y.append(float(imu_y))

        wz = np.array(list(self.imu_window_z))
        wx = np.array(list(self.imu_window_x)) if len(self.imu_window_x) > 0 else wz
        wy = np.array(list(self.imu_window_y)) if len(self.imu_window_y) > 0 else wz

        w_all = np.concatenate([wz, wx, wy])

        features = np.array([[
            float(wz[-1]),
            float(wz.mean()),
            float(wz.std()),
            float(np.sqrt(wz.var() + wx.var() + wy.var())),
            float(wz.max() - wz.min()),
            float(w_all.max()),
            float(w_all.std()),
            float(np.percentile(w_all, 90)),
            float(np.abs(np.diff(wz[-2:])).mean() if len(wz) > 1 else 0),
        ]], dtype=np.float32)

        features = np.nan_to_num(
            features,
            nan=0.0,
            posinf=3.5,
            neginf=0.0
        )

        return features

    def decide(
        self,
        motion_score,
        imu_z,
        imu_x=None,
        imu_y=None,
        cam_event="normal",
        cam_conf=0.0,
        road_event="normal",
        road_conf=0.0,
        rear_event="normal",
        rear_conf=0.0
    ):

        # STEP 1: Sensor smoothing
        motion_smooth = self.kalman_motion.update(motion_score / 5.0)

        features = self._extract_multiaxis_features(
            imu_z,
            imu_x,
            imu_y
        )

        imu_smooth = self.kalman_imu.update(
            min(float(imu_z), 3.5) / 3.5
        )

        road_smooth = self.kalman_road.update(road_conf)

        # STEP 2: Individual confidence
        motion_conf = min(1.0, motion_smooth * 1.5)

        ml_conf = self._get_ml_confidence(features)

        imu_conf = min(
            1.0,
            max(0.0, (imu_z - 1.0) / 2.5)
        )

        # STEP 3: Weighted fusion
        weighted_conf = (
            motion_conf * self.weights["motion"] +
            road_conf * self.weights["road"] +
            imu_conf * self.weights["imu"] +
            rear_conf * self.weights["rear"]
        )

        weighted_conf *= (1.0 - self.false_positive_penalty)

        # UPDATED THRESHOLDS for explicit caution/hazard tiers
        HAZARD_THRESHOLD = 0.55
        CAUTION_THRESHOLD = 0.25

        hazard_classes = ("pothole", "speed_hump", "braking")

        # STEP 4: Decision logic
        if weighted_conf >= HAZARD_THRESHOLD:
            decision = "hazard"
            severity = min(1.0, weighted_conf)

        elif weighted_conf >= CAUTION_THRESHOLD:
            decision = "caution"
            severity = weighted_conf * 0.7

        else:
            decision = "normal"
            severity = 0.0

        # Ensure braking remains a caution-level warning until confidence is strong
        if cam_event == "braking" and cam_conf > 0.45 and weighted_conf < HAZARD_THRESHOLD:
            decision = "caution"
            severity = max(severity, cam_conf * 0.65)

        # STEP 5: Temporal smoothing
        self.decision_history.append(decision)
        self.confidence_history.append(weighted_conf)

        if len(self.decision_history) >= 2:
            stable_decision = max(
                set(self.decision_history),
                key=self.decision_history.count
            )
        else:
            stable_decision = decision

        self.current = stable_decision.upper()
        self.severity = severity

        # STEP 6: Motor control
        motor_speed = self._calc_speed(
            stable_decision,
            severity
        )

        imu_spike = imu_z > 1.7
        camera_high = cam_conf > 0.25 or road_conf > 0.25

        return {
            "decision": self.current,
            "motor_speed": motor_speed,
            "confidence": round(weighted_conf * 100, 1),
            "severity_score": round(severity, 2),
            "motion_conf": round(motion_conf, 3),
            "imu_conf": round(imu_conf, 3),
            "road_conf": round(road_conf, 3),
            "rear_conf": round(rear_conf, 3),
            "raw_motion": round(motion_score, 2),
            "raw_imu": round(imu_z, 3),
            "imu_spike": imu_spike,
            "camera_high": camera_high,
            "consensus_votes": {
                "motion": motion_conf,
                "road": road_conf,
                "imu": imu_conf,
                "rear": rear_conf,
            },
            "sources_breakdown": {
                "camera_event": cam_event,
                "road_event": road_event,
                "rear_event": rear_event,
                "imu_z": round(imu_z, 3),
            }
        }

    def _get_ml_confidence(self, features):

        try:
            if self.scaler is not None:
                features_scaled = self.scaler.transform(features)
            else:
                features_scaled = features

            proba = self.model.predict_proba(features_scaled)
            confidence = float(proba.max())

            return min(1.0, confidence)

        except:
            return 0.5

    def _calc_speed(self, decision, severity):

        if decision == "normal":
            return 100

        if decision == "caution":
            return round(max(50, 100 - severity * 50))

        if decision == "hazard":
            return round(max(15, 100 - severity * 70))

        return 100

    def update_false_positive_penalty(self, penalty):

        self.false_positive_penalty = max(
            0,
            min(1.0, penalty)
        )