"""
imu_reader_enhanced.py
━━━━━━━━━━━━━━━━━━━
SIMULATED IMU Data (Arduino removed)
Generates realistic normal readings that don't trigger false detection.
"""

import time
import random
import numpy as np

class IMUReaderEnhanced:
    
    def __init__(self, port='COM3', baud=9600):
        self.port = port
        self.baud = baud
        self.serial = None  # Not used - simulation mode
        self.last_value = (1.0, 1.0, 1.0)  # (x, y, z)
        self.event_type = 'normal'
        
        # High pass filters (one per axis)
        self.filtered_x, self.filtered_y, self.filtered_z = 0.0, 0.0, 0.0
        self.prev_raw_x, self.prev_raw_y, self.prev_raw_z = 1.0, 1.0, 1.0
        
        # Pattern detection
        self.impact_history = []
        self.rotation_history = []
        
        print("🔧 IMU SIMULATION MODE (Arduino removed)")
        print("   Generating safe IMU readings (z stays 0.95-1.08)")
        print("   IMU will NOT trigger false detection alerts")
        print("-" * 50)
    
    def _read_raw(self):
        """Return simulated 3-axis values: X,Y,Z (no serial)"""
        return self._simulate()
    
    def _simulate(self):
        """
        Generate SAFE simulated IMU readings
        Z always 0.95-1.08 (never triggers 2.2 or 2.8 thresholds)
        X,Y always ~1.0 with minimal noise
        Purpose: Realistic sensor data without false pothole/bump alerts
        """
        # Safe range: far below detection thresholds
        # Pothole threshold: z > 2.8
        # Bump threshold: z > 2.2
        # So we stay in 0.95-1.08 range
        
        r = random.random()
        
        # 99.5% normal driving conditions
        if r < 0.995:
            x = 1.0 + random.uniform(-0.015, 0.015)   # ±1.5%
            y = 1.0 + random.uniform(-0.015, 0.015)   # ±1.5%
            z = 1.0 + random.uniform(-0.06, 0.08)     # 0.94-1.08 (safe)
            return (x, y, z)
        
        # 0.5% slight variations (but still safe)
        x = 1.0 + random.uniform(-0.03, 0.03)
        y = 1.0 + random.uniform(-0.03, 0.03)
        z = 1.0 + random.uniform(-0.05, 0.05)        # Still well below 2.2
        return (x, y, z)
    
    def _apply_high_pass_filter(self, raw_x, raw_y, raw_z):
        """High pass filter for each axis"""
        alpha = 0.85
        
        self.filtered_x = alpha * (self.filtered_x + raw_x - self.prev_raw_x)
        self.filtered_y = alpha * (self.filtered_y + raw_y - self.prev_raw_y)
        self.filtered_z = alpha * (self.filtered_z + raw_z - self.prev_raw_z)
        
        self.prev_raw_x = raw_x
        self.prev_raw_y = raw_y
        self.prev_raw_z = raw_z
        
        return (
            1.0 + abs(self.filtered_x),
            1.0 + abs(self.filtered_y),
            1.0 + abs(self.filtered_z)
        )
    
    def read(self):
        """Returns (z, x, y) tuple"""
        raw_x, raw_y, raw_z = self._read_raw()
        filtered_x, filtered_y, filtered_z = self._apply_high_pass_filter(raw_x, raw_y, raw_z)
        
        self.last_value = (filtered_x, filtered_y, filtered_z)
        self._classify(filtered_z, filtered_x, filtered_y)
        
        return filtered_z, filtered_x, filtered_y
    
    def _classify(self, z, x, y):
        """Classify based on all axes"""
        magnitude = np.sqrt(x**2 + y**2 + z**2)
        
        # INCREASED thresholds to reduce false positives
        if z > 2.8 or magnitude > 3.2:  # Was: 2.3, 2.8
            self.event_type = 'pothole'
        elif z > 2.2 or (x > 1.8 and y > 1.8):  # Was: 1.8, 1.5
            self.event_type = 'speed_bump'
        else:
            self.event_type = 'normal'
    
    def get_event_type(self):
        return self.event_type
    
    def get_all_axes(self):
        """Returns last readings as (z, x, y)"""
        return self.last_value
    
    def close(self):
        """Cleanup (no serial connection to close)"""
        pass
