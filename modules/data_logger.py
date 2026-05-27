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
        self.total_gt       = 0
        self.correct_count  = 0
        self.incorrect_count= 0
        self.confusion      = {}
        self.session_start  = datetime.now()
        
        with open(self.csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 
                'imu_z', 'imu_x', 'imu_y', 'motion_score',
                'camera_event', 'camera_conf', 
                'road_event', 'road_conf',
                'rear_event', 'rear_conf',
                'decision', 'confidence', 'severity_score',
                'motor_speed',
                'lora_event', 'lora_sent', 'lora_confidence_check', 'lora_latency_ms',
                'motion_conf', 'imu_conf', 'road_conf_fusion',
                'ground_truth'
            ])
        
        print(f"Data Logger initialized.")
        print(f"Logging to: {self.csv_path}")
        print("-" * 40)
    
    def log(self, imu_z, motion_score, fusion_result, ground_truth=None, imu_x=None, imu_y=None, 
            cam_event='normal', cam_conf=0.0, road_event='normal', road_conf=0.0, 
            rear_event='normal', rear_conf=0.0, lora_event='normal', lora_sent=False, lora_latency_ms=0.0):
        self.total_readings += 1
        decision = fusion_result["decision"]
        
        if decision == "NORMAL":   self.normal_count  += 1
        elif decision == "CAUTION": self.caution_count += 1
        elif decision == "HAZARD":  self.hazard_count  += 1
        
        if ground_truth is not None:
            actual = str(ground_truth).strip().upper()
            self.total_gt += 1
            if decision == actual:
                self.correct_count += 1
            else:
                self.incorrect_count += 1
            self.confusion[(actual, decision)] = self.confusion.get((actual, decision), 0) + 1
        
        lora_confidence = fusion_result.get("confidence", 0) / 100.0
        lora_would_send = (decision == "HAZARD" and lora_confidence >= 0.75) or (decision == "NORMAL")
        
        with open(self.csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().strftime("%H:%M:%S.%f")[:-3],
                round(imu_z, 4), round(imu_x or 1.0, 4), round(imu_y or 1.0, 4), round(motion_score, 4),
                cam_event, round(cam_conf, 4), road_event, round(road_conf, 4), rear_event, round(rear_conf, 4),
                decision, fusion_result.get("confidence", 0), round(fusion_result.get("severity_score", 0), 4), 
                fusion_result.get("motor_speed", 100),
                lora_event, "YES" if lora_sent else "NO", "PASS" if lora_would_send else "BLOCKED", round(lora_latency_ms, 2),
                round(fusion_result.get("motion_conf", 0), 4), round(fusion_result.get("imu_conf", 0), 4), 
                round(fusion_result.get("road_conf", 0), 4),
                ground_truth or ''
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

"""
        if self.total_gt > 0:
            accuracy = round((self.correct_count / self.total_gt) * 100, 1)
            summary += f"Ground Truth Samples : {self.total_gt}\n"
            summary += f"  Correct           : {self.correct_count} ({accuracy}%)\n"
            summary += f"  Incorrect         : {self.incorrect_count} ({round(100 - accuracy, 1)}%)\n\n"
            summary += self._build_confusion_matrix() + "\n"
            summary += "\n"
        summary += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(summary)
        
        print(summary)
        print(f"Summary saved to: {summary_path}")

    def _build_confusion_matrix(self):
        if not self.confusion:
            return "No ground truth confusion data available."

        labels = sorted({label for pair in self.confusion.keys() for label in pair})
        header = "            " + "".join(f"{label:>10}" for label in labels)
        lines = ["CONFUSION MATRIX (actual → predicted):", header]

        for actual in labels:
            row = [f"{actual:>12}"]
            for predicted in labels:
                row.append(f"{self.confusion.get((actual, predicted), 0):>10}")
            lines.append("".join(row))
        return "\n".join(lines)
    
    def _pct(self, count):
        if self.total_readings == 0:
            return 0
        return round((count / self.total_readings) * 100, 1)