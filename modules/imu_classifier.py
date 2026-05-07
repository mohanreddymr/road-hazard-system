import time
from collections import deque
 
class IMUClassifier:
    """
    Classifies road events from IMU waveform SHAPE.
    Differentiates between:
      - Normal driving
      - Speed hump (gradual rise + fall)
      - Pothole    (sharp spike + drop)
      - Braking    (sustained deceleration, Z stays flat)
    """
 
    def __init__(self):
        # Rolling window of recent Z readings
        self.z_window    = deque(maxlen=30)
        self.t_window    = deque(maxlen=30)
 
        # Current classification
        self.event_type  = "normal"
        self.event_conf  = 1.0
 
        # Event hold timer — keeps classification visible
        self.event_start = time.time()
        self.hold_time   = 1.5   # seconds to hold event display
 
        print("IMU Classifier initialized.")
        print("Classifying: normal / pothole / speed_hump / braking")
 
    def add_reading(self, z_value):
        """Add new Z reading to window"""
        self.z_window.append(z_value)
        self.t_window.append(time.time())
 
    def classify(self):
        """
        Analyses waveform shape and returns event type.
 
        POTHOLE signature:
          - Very sharp spike (large change in 1-2 readings)
          - Peak > 2.0g
          - Followed by rapid drop back to baseline
          - Short duration
 
        SPEED HUMP signature:
          - Gradual rise over several readings
          - Peak 1.4g - 2.0g
          - Gradual fall back to baseline
          - Longer duration
 
        BRAKING signature:
          - Z-axis stays near 1.0g (no vertical change)
          - But pattern of sustained readings
          - We detect this via motion detector (camera)
 
        NORMAL:
          - Z stays close to 1.0g
          - No significant peaks
        """
        if len(self.z_window) < 5:
            return "normal", 1.0
 
        z = list(self.z_window)
 
        peak    = max(z)
        trough  = min(z)
        mean    = sum(z) / len(z)
        baseline = 1.0
 
        # Rate of change between consecutive readings
        diffs       = [abs(z[i]-z[i-1]) for i in range(1, len(z))]
        max_diff    = max(diffs) if diffs else 0
        mean_diff   = sum(diffs) / len(diffs) if diffs else 0
 
        # How sharp is the peak? (sharpness = max single-step change)
        sharpness = max_diff
 
        # How sustained is the event?
        above_threshold = sum(1 for v in z if v > 1.3)
 
        # ── CLASSIFICATION RULES ──
 
        # POTHOLE: sharp spike, high peak, short duration
        if peak > 2.0 and sharpness > 0.6:
            conf = min(1.0, (peak - 2.0) / 1.0 + 0.5)
            self._set_event("pothole", round(conf, 2))
            return self.event_type, self.event_conf
 
        # SPEED HUMP: moderate peak, gradual change, sustained
        if 1.4 < peak <= 2.2 and sharpness < 0.5 and above_threshold >= 4:
            conf = min(1.0, (peak - 1.4) / 0.8 + 0.4)
            self._set_event("speed_hump", round(conf, 2))
            return self.event_type, self.event_conf
 
        # NORMAL: small variations
        if peak < 1.4:
            self._set_event("normal", 1.0)
            return self.event_type, self.event_conf
 
        # BORDERLINE — use hold timer
        return self.event_type, self.event_conf
 
    def _set_event(self, event, conf):
        """Set event with hold timer — prevents flickering"""
        if event != "normal":
            self.event_type  = event
            self.event_conf  = conf
            self.event_start = time.time()
        else:
            # Only reset to normal if hold time has passed
            if (time.time() - self.event_start) > self.hold_time:
                self.event_type = "normal"
                self.event_conf = 1.0
 
    def get_event(self):
        """Returns current event type and confidence"""
        return self.event_type, self.event_conf
 
    def get_display_info(self):
        """
        Returns human-readable event info for dashboard display.
        """
        event, conf = self.get_event()
 
        info = {
            "normal":     ("NORMAL ROAD",   (0, 255, 136), "Smooth surface"),
            "pothole":    ("POTHOLE",        (0, 0, 255),   "Sharp impact detected"),
            "speed_hump": ("SPEED HUMP",     (0, 165, 255), "Gradual bump detected"),
            "braking":    ("BRAKING",        (0, 229, 255), "Deceleration event"),
        }
 
        label, color, desc = info.get(event, ("UNKNOWN", (255,255,255), ""))
        return label, color, desc, round(conf * 100)