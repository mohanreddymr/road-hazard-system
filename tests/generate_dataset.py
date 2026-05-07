import sys
import os
import csv
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.imu_simulator import IMUSimulator

# Output path
output_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'imu_simulation', 'training_data.csv'
)

imu = IMUSimulator()

# Store last 3 readings for pattern features
history = [1.0, 1.0, 1.0]

print("Generating training dataset...")
print("This will generate 2000 labeled samples.")

with open(output_path, 'w', newline='') as f:
    writer = csv.writer(f)
    
    # Header row
    writer.writerow([
        'imu_now',
        'imu_1ago',
        'imu_2ago',
        'imu_rate_of_change',
        'motion_score',
        'camera_high',
        'label'
    ])
    
    for i in range(2000):
        # Get IMU reading
        imu_now = imu.read()
        event   = imu.get_event_type()
        
        # Simulate camera motion score
        # (correlated with IMU event for realism)
        if event == "pothole":
            motion_score = random.uniform(1.8, 4.0)
        elif event == "speed_bump":
            motion_score = random.uniform(1.0, 2.5)
        else:
            motion_score = random.uniform(0.0, 1.4)
        
        # Calculate rate of change
        imu_rate = imu_now - history[0]
        
        # Camera high flag
        camera_high = 1 if motion_score > 1.5 else 0
        
        # Assign label based on event
        if event == "pothole":
            label = "hazard"
        elif event == "speed_bump":
            label = "caution"
        else:
            label = "normal"
        
        # Write row
        writer.writerow([
            round(imu_now, 4),
            round(history[0], 4),
            round(history[1], 4),
            round(imu_rate, 4),
            round(motion_score, 4),
            camera_high,
            label
        ])
        
        # Update history
        history.insert(0, imu_now)
        history = history[:3]

print(f"Dataset saved to: {output_path}")
print("2000 samples generated successfully.")