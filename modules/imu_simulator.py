import numpy as np
import random
import time

class IMUSimulator:
    
    def __init__(self):
        # Normal gravity reading (1g = 9.8 m/s²)
        self.baseline = 1.0
        
        # Small random noise always present in real sensors
        self.noise_level = 0.02
        
        # Track current event being simulated
        self.current_event = "normal"
        self.event_counter = 0
        
        # How often should events happen?
        # (every ~100 readings = roughly every 2 seconds)
        self.event_probability = 0.01
        
        print("IMU Simulator initialized.")
        print("Simulating MPU-6050 Z-axis readings.")
        print("-" * 40)
    
    def _add_noise(self, value):
        """Add small random noise to simulate real sensor"""
        return value + random.uniform(
            -self.noise_level, 
            self.noise_level
        )
    
    def read(self):
        """
        Returns one Z-axis reading.
        Simulates: normal / pothole / speed_bump
        """
        
        # If currently in middle of an event, continue it
        if self.event_counter > 0:
            return self._continue_event()
        
        # Randomly trigger a new event
        rand = random.random()
        
        if rand < 0.005:
            # Pothole event (0.5% chance per reading)
            self.current_event = "pothole"
            self.event_counter = 6
            return self._start_pothole()
            
        elif rand < 0.010:
            # Speed bump event (0.5% chance per reading)
            self.current_event = "speed_bump"
            self.event_counter = 10
            return self._start_speedbump()
        
        else:
            # Normal road — just baseline + noise
            self.current_event = "normal"
            return self._add_noise(self.baseline)
    
    def _start_pothole(self):
        """First reading of pothole — big spike up"""
        return self._add_noise(2.8)
    
    def _continue_event(self):
        """Continue current event over multiple readings"""
        self.event_counter -= 1
        
        if self.current_event == "pothole":
            if self.event_counter == 5:
                return self._add_noise(2.8)   # impact spike
            elif self.event_counter == 4:
                return self._add_noise(0.3)   # sudden drop
            elif self.event_counter == 3:
                return self._add_noise(1.4)   # bounce back
            elif self.event_counter == 2:
                return self._add_noise(1.1)   # settling
            else:
                return self._add_noise(1.0)   # back to normal
                
        elif self.current_event == "speed_bump":
            if self.event_counter in [9, 8]:
                return self._add_noise(1.3)   # gradual rise
            elif self.event_counter in [7, 6]:
                return self._add_noise(1.8)   # peak
            elif self.event_counter in [5, 4]:
                return self._add_noise(1.5)   # gradual fall
            elif self.event_counter in [3, 2]:
                return self._add_noise(1.2)   # almost normal
            else:
                return self._add_noise(1.0)   # back to normal
        
        return self._add_noise(self.baseline)
    
    def _start_speedbump(self):
        """First reading of speed bump"""
        return self._add_noise(1.3)
    
    def get_event_type(self):
        """Returns what event is currently happening"""
        return self.current_event