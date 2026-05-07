import csv
import os
from datetime import datetime

class DataLogger:
    
    def __init__(self):
        self.output_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'output'
        )
        os.makedirs(self.output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.csv_path = os.path.join(
            self.output_dir,
            f"session_{timestamp}.csv"
        )
        
        self.total_readings = 0
        self.normal_count   = 0
        self.caution_count  = 0
        self.hazard_count   = 0
        self.session_start  = datetime.now()
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'imu_z', 'motion_score',
                'decision', 'motor_speed', 'confidence'
            ])
        
        print(f"Data Logger initialized.")
        print(f"Logging to: {self.csv_path}")
        print("-" * 40)
    
    def log(self, imu_z, motion_score, fusion_result):
        self.total_readings += 1
        decision = fusion_result["decision"]
        
        if decision == "NORMAL":   self.normal_count  += 1
        elif decision == "CAUTION": self.caution_count += 1
        elif decision == "HAZARD":  self.hazard_count  += 1
        
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%H:%M:%S.%f")[:-3],
                round(imu_z, 4),
                round(motion_score, 4),
                decision,
                fusion_result["motor_speed"],
                fusion_result["confidence"]
            ])
    
    def save_summary(self):
        session_duration = (datetime.now() - self.session_start).seconds
        summary_path = self.csv_path.replace('.csv', '_summary.txt')
        
        summary = f"""
╔══════════════════════════════════════════╗
║     ROAD HAZARD SYSTEM — SESSION REPORT  ║
╚══════════════════════════════════════════╝

Session Duration : {session_duration} seconds
Total Readings   : {self.total_readings}

DECISION BREAKDOWN:
  NORMAL  : {self.normal_count}  ({self._pct(self.normal_count)}%)
  CAUTION : {self.caution_count} ({self._pct(self.caution_count)}%)
  HAZARD  : {self.hazard_count}  ({self._pct(self.hazard_count)}%)

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(summary)
        print(f"Summary saved to: {summary_path}")
    
    def _pct(self, count):
        if self.total_readings == 0:
            return 0
        return round((count / self.total_readings) * 100, 1)