import matplotlib.pyplot as plt
import matplotlib.animation as animation
from collections import deque

class IMUPlotter:
    
    def __init__(self, window_size=100):
        # Store last 100 readings
        self.window_size = window_size
        self.z_values = deque([1.0] * window_size, maxlen=window_size)
        self.time_values = deque(range(window_size), maxlen=window_size)
        self.time_counter = window_size
        
        # Set up the plot
        self.fig, self.ax = plt.subplots(figsize=(10, 4))
        self.fig.patch.set_facecolor('#1e1e1e')
        self.ax.set_facecolor('#1e1e1e')
        
        # Plot line
        self.line, = self.ax.plot(
            list(self.time_values),
            list(self.z_values),
            color='#00ff88',
            linewidth=2
        )
        
        # Threshold lines
        self.ax.axhline(
            y=1.8, color='orange', 
            linestyle='--', linewidth=1,
            label='Caution threshold'
        )
        self.ax.axhline(
            y=2.3, color='red',
            linestyle='--', linewidth=1,
            label='Hazard threshold'
        )
        
        # Labels
        self.ax.set_title(
            'IMU Z-Axis Simulation (Vertical Acceleration)',
            color='white', fontsize=12
        )
        self.ax.set_ylabel('Acceleration (g)', color='white')
        self.ax.set_xlabel('Time (readings)', color='white')
        self.ax.tick_params(colors='white')
        self.ax.set_ylim(0, 3.5)
        self.ax.legend(loc='upper right')
        
        plt.tight_layout()
        print("IMU Plotter initialized.")
    
    def update(self, new_value):
        """Add new reading and refresh plot"""
        self.z_values.append(new_value)
        self.time_counter += 1
        self.time_values.append(self.time_counter)
        
        self.line.set_xdata(list(self.time_values))
        self.line.set_ydata(list(self.z_values))
        self.ax.set_xlim(
            min(self.time_values),
            max(self.time_values)
        )
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()
    
    def show(self):
        plt.ion()
        plt.show()