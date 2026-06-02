"""
validate_output.py
─────────────────
Validates and analyzes the session CSV output.
Shows detection accuracy, LoRa transmission statistics, and confidence analysis.

Usage:
    python validate_output.py output/session_20260326_133456.csv
    
Or to analyze latest session:
    python validate_output.py
"""

import csv
import os
import sys
from datetime import datetime
from collections import defaultdict

class OutputValidator:
    
    def __init__(self, csv_path=None):
        if csv_path is None:
            # Find latest CSV file
            output_dir = 'output'
            csv_files = [f for f in os.listdir(output_dir) if f.startswith('session_') and f.endswith('.csv')]
            if not csv_files:
                print("❌ No session CSV files found in output/")
                sys.exit(1)
            csv_path = os.path.join(output_dir, sorted(csv_files)[-1])
        
        self.csv_path = csv_path
        self.data = []
        self.load_data()
    
    @staticmethod
    def normalize_label(value):
        if value is None:
            return ''
        label = str(value).strip().lower().replace(' ', '_')
        if label == 'speedhump':
            label = 'speed_hump'
        if label == 'h':
            label = 'hazard'
        if label == 'c':
            label = 'caution'
        if label == 'n':
            label = 'normal'
        return label

    def _compute_metrics(self, confusion, label):
        tp = confusion[label].get(label, 0)
        fp = sum(confusion[pred].get(label, 0) for pred in confusion if pred != label)
        fn = sum(confusion[label].get(pred, 0) for pred in confusion[label] if pred != label)
        precision = tp / (tp + fp) if tp + fp > 0 else 0.0
        recall = tp / (tp + fn) if tp + fn > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if precision + recall > 0 else 0.0
        support = sum(confusion[label].values())
        return precision, recall, f1, support

    def _print_metrics_table(self, confusion, labels, title):
        print(f"\n{title}")
        print("-" * 70)
        print(f"{'Class':<15} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
        print("-" * 70)
        for label in labels:
            precision, recall, f1, support = self._compute_metrics(confusion, label)
            print(f"{label:<15} {precision*100:>9.1f}% {recall*100:>9.1f}% {f1*100:>9.1f}% {support:>10}")
        print("-" * 70)

    def load_data(self):
        """Load CSV data"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.data = list(reader)
        print(f"Loaded {len(self.data)} records from {os.path.basename(self.csv_path)}\n")
    
    def validate_ground_truth(self):
        """Check accuracy against ground truth labels"""
        print("=" * 70)
        print("GROUND TRUTH ACCURACY ANALYSIS")
        print("=" * 70)
        
        records_with_gt = [r for r in self.data if r.get('ground_truth', '').strip()]
        if not records_with_gt:
            print("No ground truth labels found in this session")
            return
        
        normalized_gt = [self.normalize_label(r.get('ground_truth', '')) for r in records_with_gt]
        event_labels = {'pothole', 'speed_hump', 'braking', 'normal'}
        decision_labels = {'normal', 'caution', 'hazard'}
        gt_set = set(normalized_gt)
        
        if gt_set & event_labels:
            prediction_field = 'lora_event'
            label_type = 'event'
            target_labels = ['pothole', 'speed_hump', 'braking']
        elif gt_set & decision_labels:
            prediction_field = 'decision'
            label_type = 'decision'
            target_labels = ['normal', 'caution', 'hazard']
        else:
            prediction_field = 'lora_event'
            label_type = 'event'
            target_labels = ['pothole', 'speed_hump', 'braking']

        correct = 0
        confusion = defaultdict(lambda: defaultdict(int))
        
        for record in records_with_gt:
            gt = self.normalize_label(record.get('ground_truth', ''))
            pred = self.normalize_label(record.get(prediction_field, ''))
            if gt == pred:
                correct += 1
            confusion[gt][pred] += 1
        
        accuracy = (correct / len(records_with_gt)) * 100
        print(f"\n✓ Total labeled samples: {len(records_with_gt)}")
        print(f"✓ Correct predictions: {correct} ({accuracy:.1f}%)")
        print(f"✗ Incorrect predictions: {len(records_with_gt) - correct} ({100-accuracy:.1f}%)\n")
        
        print(f"CONFUSION MATRIX ({label_type.capitalize()} Actual → Predicted):")
        print("-" * 70)
        actual_labels = sorted(confusion.keys())
        pred_labels = sorted(set(label for d in confusion.values() for label in d.keys()))
        print(f"{'Actual':<15}", end='')
        for label in pred_labels:
            print(f"{label:>12}", end='')
        print()
        print("-" * (15 + 12 * len(pred_labels)))
        for actual in actual_labels:
            print(f"{actual:<15}", end='')
            for predicted in pred_labels:
                count = confusion[actual].get(predicted, 0)
                print(f"{count:>12}", end='')
            print()
        
        if label_type == 'event':
            self._print_metrics_table(confusion, target_labels, "\nPER-CLASS EVENT METRICS")
        else:
            self._print_metrics_table(confusion, target_labels, "\nPER-CLASS DECISION METRICS")
    
    def analyze_lora_transmission(self):
        """Analyze LoRa transmission statistics"""
        print("\n" + "=" * 70)
        print("📡 LoRa TRANSMISSION ANALYSIS")
        print("=" * 70)
        
        total_records = len(self.data)
        lora_sent = sum(1 for r in self.data if r.get('lora_sent', '').strip() == 'YES')
        lora_passed = sum(1 for r in self.data if r.get('lora_confidence_check', '').strip() == 'PASS')
        lora_blocked = sum(1 for r in self.data if r.get('lora_confidence_check', '').strip() == 'BLOCKED')
        
        hazards = sum(1 for r in self.data if r.get('decision', '').strip().upper() == 'HAZARD')
        hazards_sent = sum(1 for r in self.data 
                          if r.get('decision', '').strip().upper() == 'HAZARD' 
                          and r.get('lora_confidence_check', '').strip() == 'PASS')
        
        cautions = sum(1 for r in self.data if r.get('decision', '').strip().upper() == 'CAUTION')
        cautions_blocked = sum(1 for r in self.data 
                              if r.get('decision', '').strip().upper() == 'CAUTION' 
                              and r.get('lora_confidence_check', '').strip() == 'BLOCKED')
        
        print(f"\nMessage Statistics:")
        print(f"   Total records: {total_records}")
        print(f"   LoRa PASS (would send): {lora_passed} ({100*lora_passed/total_records:.1f}%)")
        print(f"   LoRa BLOCKED (confidence too low): {lora_blocked} ({100*lora_blocked/total_records:.1f}%)")
        print(f"   Actually sent: {lora_sent}")
        
        print(f"\nHAZARD Handling:")
        print(f"   Total HAZARD detections: {hazards}")
        print(f"   HAZARD messages sent: {hazards_sent} ({100*hazards_sent/max(1,hazards):.1f}%)")
        print(f"   HAZARD messages blocked (low conf): {hazards - hazards_sent}")
        
        print(f"\nCAUTION Handling (should be SKIPPED):")
        print(f"   Total CAUTION detections: {cautions}")
        print(f"   CAUTION messages blocked (as intended): {cautions_blocked}")
        
        # Latency analysis
        latencies = []
        for r in self.data:
            try:
                lat = float(r.get('lora_latency_ms', 0))
                if lat > 0:
                    latencies.append(lat)
            except:
                pass
        
        if latencies:
            print(f"\nLoRa Latency Analysis:")
            print(f"   Samples with latency: {len(latencies)}")
            print(f"   Min latency: {min(latencies):.2f}ms")
            print(f"   Max latency: {max(latencies):.2f}ms")
            print(f"   Avg latency: {sum(latencies)/len(latencies):.2f}ms")
    
    def analyze_confidence_levels(self):
        """Analyze confidence score distribution"""
        print("\n" + "=" * 70)
        print("CONFIDENCE LEVEL ANALYSIS")
        print("=" * 70)
        
        confidence_scores = []
        for r in self.data:
            try:
                conf = float(r.get('confidence', 0))
                confidence_scores.append(conf)
            except:
                pass
        
        if not confidence_scores:
            print("No confidence data available")
            return
        
        confidence_scores.sort()
        
        print(f"\nConfidence Distribution:")
        print(f"   Min: {min(confidence_scores):.1f}%")
        print(f"   Max: {max(confidence_scores):.1f}%")
        print(f"   Avg: {sum(confidence_scores)/len(confidence_scores):.1f}%")
        print(f"   Median: {confidence_scores[len(confidence_scores)//2]:.1f}%")
        
        # Breakdown by confidence buckets
        buckets = {
            "0-25%": 0,
            "25-50%": 0,
            "50-75%": 0,
            "75-100%": 0
        }
        
        for conf in confidence_scores:
            if conf < 25:
                buckets["0-25%"] += 1
            elif conf < 50:
                buckets["25-50%"] += 1
            elif conf < 75:
                buckets["50-75%"] += 1
            else:
                buckets["75-100%"] += 1
        
        print(f"\nConfidence Buckets:")
        for bucket, count in buckets.items():
            pct = 100 * count / len(confidence_scores)
            bar = "█" * int(pct / 2)
            print(f"   {bucket}: {count:>4} ({pct:>5.1f}%) {bar}")
    
    def analyze_decision_breakdown(self):
        """Analyze decision type breakdown"""
        print("\n" + "=" * 70)
        print("DECISION BREAKDOWN")
        print("=" * 70)
        
        decisions = defaultdict(int)
        for r in self.data:
            decision = r.get('decision', '').strip().upper()
            decisions[decision] += 1
        
        total = sum(decisions.values())
        
        print(f"\nTotal decisions: {total}\n")
        for decision in ['NORMAL', 'CAUTION', 'HAZARD']:
            count = decisions[decision]
            pct = 100 * count / total
            bar = "█" * int(pct / 3)
            print(f"  {decision:8}: {count:>4} ({pct:>5.1f}%) {bar}")
    
    def generate_report(self):
        """Generate full validation report"""
        self.validate_ground_truth()
        self.analyze_lora_transmission()
        self.analyze_confidence_levels()
        self.analyze_decision_breakdown()
        
        print("\n" + "=" * 70)
        print("✓ VALIDATION COMPLETE")
        print("=" * 70)
        print(f"\nSession file: {os.path.basename(self.csv_path)}")
        print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else None
    validator = OutputValidator(csv_file)
    validator.generate_report()
