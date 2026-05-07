import joblib
import os
import numpy as np
 
class FusionEngine:
    """
    Three-source fusion:
      1. Camera (front car tracking)  — PRIMARY
      2. Road detector (road surface) — PRIMARY
      3. IMU                          — SECONDARY confirmation
 
    Decision priority:
      Road detector event > Camera event > Motion score > IMU
    """
 
    def __init__(self):
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'data', 'imu_simulation', 'hazard_model.pkl'
        )
        print("Loading ML model...")
        self.model = joblib.load(model_path)
        print("ML model loaded.")
 
        self.imu_hist     = [1.0, 1.0, 1.0]
        self.dec_hist     = []
        self.HIST_SIZE    = 7
        self.current      = "NORMAL"
        self.severity     = 0.0
 
        print("Fusion: Camera + Road + IMU → decision")
        print("-"*40)
 
    def decide(self, motion_score, imu_z,
               cam_event='normal',  cam_conf=0.0,
               road_event='normal', road_conf=0.0):
        """
        Fuses all three sources into one decision.
        """
        imu  = float(imu_z)
        rate = imu - self.imu_hist[0]
        imu_spike = imu > 1.8
 
        # ── Priority 1: Road detector (direct road observation) ──
        if road_event in ('pothole','crack') and road_conf > 0.3:
            decision = 'hazard'
            sev      = 0.5 + road_conf * 0.5
 
        elif road_event == 'speed_hump' and road_conf > 0.3:
            decision = 'caution'
            sev      = 0.3 + road_conf * 0.4
 
        # ── Priority 2: Camera (front car tracking) ──
        elif cam_event == 'pothole' and cam_conf > 0.3:
            decision = 'hazard'
            sev      = 0.5 + cam_conf * 0.4
 
        elif cam_event in ('speed_hump','braking') and cam_conf > 0.3:
            decision = 'caution'
            sev      = 0.25 + cam_conf * 0.4
 
        # ── Priority 3: Motion score ──
        elif motion_score > 3.0:
            decision = 'hazard'
            sev      = min(1.0, motion_score/5.0)
 
        elif motion_score > 0.8:
            decision = 'caution'
            sev      = motion_score/5.0
 
        # ── Priority 4: IMU alone ──
        elif imu_spike:
            decision = 'caution'
            sev      = min(1.0,(imu-1.0)/2.0)
 
        else:
            decision = 'normal'
            sev      = 0.0
 
        sev = round(min(1.0, float(sev)), 2)
 
        # IMU can upgrade caution → hazard
        if imu_spike and decision == 'caution':
            decision = 'hazard'
            sev      = min(1.0, sev+0.2)
 
        self.severity = sev
 
        # ── ML confidence score ──
        nm   = min(motion_score*3.0, 5.0)
        ch   = 1 if nm>1.5 else 0
        feat = np.array([[imu, self.imu_hist[0],
                          self.imu_hist[1], rate, nm, ch]])
        try:
            prob = self.model.predict_proba(feat)
            conf = float(prob.max())*100
            # Boost when camera or road detector is confident
            best_cam_conf = max(cam_conf, road_conf)
            if best_cam_conf > 0.6:
                conf = min(99.0, conf + best_cam_conf*18)
        except:
            conf = max(cam_conf, road_conf)*100
 
        # ── Stability buffer ──
        self.dec_hist.append(decision)
        if len(self.dec_hist) > self.HIST_SIZE:
            self.dec_hist.pop(0)
        stable = max(set(self.dec_hist),
                     key=self.dec_hist.count).upper()
        self.current = stable
 
        # ── Graduated speed ──
        speed = self._speed(decision, sev)
 
        self.imu_hist.insert(0, imu)
        self.imu_hist = self.imu_hist[:3]
 
        return {
            "decision":       stable,
            "motor_speed":    speed,
            "confidence":     round(conf,1),
            "severity_score": sev,
            "camera_high":    bool(ch),
            "imu_spike":      imu_spike,
            "raw_motion":     round(motion_score,2),
            "raw_imu":        round(imu,3),
            "cam_event":      cam_event,
            "road_event":     road_event,
        }
 
    def _speed(self, dec, sev):
        if dec=='normal':  return 100
        if dec=='caution': return round(max(50, 100-sev*50))
        if dec=='hazard':  return round(max(15, 100-sev*70))
        return 100