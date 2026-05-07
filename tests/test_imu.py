import sys
import os
import time
import csv

# Add parent folder to path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.imu_simulator import IMUSimulator
from modules.imu_plotter import IMUPlotter

# Initialize
imu = IMUSimulator()
plotter = IMUPlotter()
plotter.show()

# Prepare CSV file to save readings
csv_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'imu_simulation', 'imu_readings.csv'
)

print("Saving IMU data to:", csv_path)
print("Watch the graph — spikes = road events")
print("Press Ctrl+C to stop")
print("-" * 40)

with open(csv_path, 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['reading_number', 'z_value', 'event_type'])
    
    reading_number = 0
    
    try:
        while True:
            # Get one IMU reading
            z_value = imu.read()
            event = imu.get_event_type()
            reading_number += 1
            
            # Save to CSV
            writer.writerow([reading_number, round(z_value, 4), event])
            
            # Update graph
            plotter.update(z_value)
            
            # Print to terminal when event happens
            if event == "pothole":
                print(f"⚠️  POTHOLE detected! Z={round(z_value,2)}g")
            elif event == "speed_bump":
                print(f"🔶 SPEED BUMP detected! Z={round(z_value,2)}g")
            
            # Simulate ~50 readings per second
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("\nStopped. Data saved to imu_readings.csv")