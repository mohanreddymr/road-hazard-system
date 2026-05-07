import serial
import time
import random
 
class IMUReader:
 
    def __init__(self, port='COM3', baud=9600):
        self.port       = port
        self.baud       = baud
        self.serial     = None
        self.last_value = 1.0
        self.event_type = 'normal'
 
        # High pass filter state
        self.filtered = 0.0
        self.prev_raw = 1.0
 
        print(f"Connecting to Arduino on {port}...")
        try:
            self.serial = serial.Serial(port, baud, timeout=1)
            time.sleep(2)
            self.serial.flushInput()
            print(f"Arduino connected on {port}")
            print("IMU Reader active — real sensor data flowing.")
        except Exception as e:
            print(f"WARNING: Could not connect to Arduino: {e}")
            print("Falling back to simulation mode")
            self.serial = None
 
        print("-" * 40)
 
    def _read_raw(self):
        """Read raw value from Arduino serial"""
        if self.serial is None:
            return self._simulate()
        try:
            line = self.serial.readline().decode('utf-8').strip()
            if line and line != 'MPU6050 ready':
                return float(line)
            return self.last_value
        except Exception:
            return self.last_value
 
    def _simulate(self):
        """Fallback simulation if Arduino not connected"""
        r = random.random()
        if r < 0.004:
            return 2.9 + random.uniform(-0.1, 0.1)
        if r < 0.008:
            return 1.5 + random.uniform(-0.1, 0.1)
        return 1.0 + random.uniform(-0.02, 0.02)
 
    def _apply_high_pass_filter(self, raw):
        """
        High pass filter — removes constant gravity baseline.
        Keeps only sudden impacts (potholes, bumps).
        Returns filtered value around 1.0 baseline.
        """
        alpha = 0.85
        self.filtered = alpha * (self.filtered + raw - self.prev_raw)
        self.prev_raw = raw
        # Add back baseline so 1.0 = normal, >1.8 = event
        return 1.0 + abs(self.filtered)
 
    def read(self):
        """
        Read one Z-axis value.
        Applies high pass filter to remove noise.
        """
        raw     = self._read_raw()
        filtered = self._apply_high_pass_filter(raw)
        self.last_value = filtered
        self._classify(filtered)
        return filtered
 
    def _classify(self, z):
        """Classify road event from Z value"""
        if z > 2.3:
            self.event_type = 'pothole'
        elif z > 1.8:
            self.event_type = 'speed_bump'
        else:
            self.event_type = 'normal'
 
    def get_event_type(self):
        return self.event_type
 
    def close(self):
        if self.serial:
            self.serial.close()
            print("Arduino connection closed.")