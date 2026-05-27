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
    
    def load_data(self):
        """Load CSV data"""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            self.data = list(reader)
        print(f"✓ Loaded {len(self.data)} records from {os.path.basename(self.csv_path)}\n")
    
    def validate_ground_truth(self):
        """Check accuracy against ground truth labels"""
        print("=" * 70)
        print("📊 GROUND TRUTH ACCURACY ANALYSIS")
        print("=" * 70)
        
        records_with_gt = [r for r in self.data if r.get('ground_truth', '').strip()]
        if not records_with_gt:
            print("ℹ️  No ground truth labels found in this session")
            return
        
        correct = 0
        confusion = defaultdict(lambda: defaultdict(int))
        
        for record in records_with_gt:
            gt = record.get('ground_truth', '').strip().upper()
            decision = record.get('decision', '').strip().upper()
            
            if gt == decision:
                correct += 1
            
            confusion[gt][decision] += 1
        
        accuracy = (correct / len(records_with_gt)) * 100
        
        print(f"\n✓ Total labeled samples: {len(records_with_gt)}")
        print(f"✓ Correct predictions: {correct} ({accuracy:.1f}%)")
        print(f"✗ Incorrect predictions: {len(records_with_gt) - correct} ({100-accuracy:.1f}%)\n")
        
        # Confusion matrix
        print("CONFUSION MATRIX (Actual → Predicted):")
        print("-" * 70)
        
        actual_labels = sorted(confusion.keys())
        pred_labels = sorted(set(label for d in confusion.values() for label in d.keys()))
        
        print(f"{'Actual':<12}", end='')
        for label in pred_labels:
            print(f"{label:>12}", end='')
        print()
        print("-" * (12 + 12 * len(pred_labels)))
        
        for actual in actual_labels:
            print(f"{actual:<12}", end='')
            for predicted in pred_labels:
                count = confusion[actual][predicted]
                print(f"{count:>12}", end='')
            print()
    
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
        
        print(f"\n📊 Message Statistics:")
        print(f"   Total records: {total_records}")
        print(f"   LoRa PASS (would send): {lora_passed} ({100*lora_passed/total_records:.1f}%)")
        print(f"   LoRa BLOCKED (confidence too low): {lora_blocked} ({100*lora_blocked/total_records:.1f}%)")
        print(f"   Actually sent: {lora_sent}")
        
        print(f"\n🚨 HAZARD Handling:")
        print(f"   Total HAZARD detections: {hazards}")
        print(f"   HAZARD messages sent: {hazards_sent} ({100*hazards_sent/max(1,hazards):.1f}%)")
        print(f"   HAZARD messages blocked (low conf): {hazards - hazards_sent}")
        
        print(f"\n⚠️  CAUTION Handling (should be SKIPPED):")
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
            print(f"\n⏱️  LoRa Latency Analysis:")
            print(f"   Samples with latency: {len(latencies)}")
            print(f"   Min latency: {min(latencies):.2f}ms")
            print(f"   Max latency: {max(latencies):.2f}ms")
            print(f"   Avg latency: {sum(latencies)/len(latencies):.2f}ms")
    
    def analyze_confidence_levels(self):
        """Analyze confidence score distribution"""
        print("\n" + "=" * 70)
        print("🎯 CONFIDENCE LEVEL ANALYSIS")
        print("=" * 70)
        
        confidence_scores = []
        for r in self.data:
            try:
                conf = float(r.get('confidence', 0))
                confidence_scores.append(conf)
            except:
                pass
        
        if not confidence_scores:
            print("ℹ️  No confidence data available")
            return
        
        confidence_scores.sort()
        
        print(f"\n📈 Confidence Distribution:")
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
        
        print(f"\n📊 Confidence Buckets:")
        for bucket, count in buckets.items():
            pct = 100 * count / len(confidence_scores)
            bar = "█" * int(pct / 2)
            print(f"   {bucket}: {count:>4} ({pct:>5.1f}%) {bar}")
    
    def analyze_decision_breakdown(self):
        """Analyze decision type breakdown"""
        print("\n" + "=" * 70)
        print("📋 DECISION BREAKDOWN")
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
