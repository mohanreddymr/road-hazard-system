import pandas as pd
import matplotlib.pyplot as plt
import os

class GraphGenerator:
    
    def generate(self, csv_path):
        print("Generating session graph...")
        
        df = pd.read_csv(csv_path)
        
        if len(df) < 10:
            print("Not enough data to generate graph.")
            return
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
        fig.patch.set_facecolor('#1e1e1e')
        
        # ── Plot 1: IMU Z-axis ──
        ax1.set_facecolor('#1e1e1e')
        ax1.plot(
            df.index, df['imu_z'],
            color='#00ff88', linewidth=1.5, label='IMU Z-axis'
        )
        ax1.axhline(y=1.8, color='orange', linestyle='--', linewidth=1, label='Caution threshold')
        ax1.axhline(y=2.3, color='red',    linestyle='--', linewidth=1, label='Hazard threshold')
        ax1.set_title('IMU Z-Axis Readings', color='white', fontsize=12)
        ax1.set_ylabel('Acceleration (g)', color='white')
        ax1.tick_params(colors='white')
        ax1.legend(loc='upper right')
        ax1.set_ylim(0, 3.5)

        # ── Plot 2: Motor speed ──
        ax2.set_facecolor('#1e1e1e')
        colors = {'NORMAL': '#00ff88', 'CAUTION': '#ffa500', 'HAZARD': '#ff0000'}
        
        for i in range(len(df) - 1):
            color = colors.get(df['decision'].iloc[i], '#00ff88')
            ax2.plot(
                [i, i+1],
                [df['motor_speed'].iloc[i], df['motor_speed'].iloc[i+1]],
                color=color, linewidth=2
            )
        
        ax2.set_title(
            'Motor Speed (Green=Normal, Orange=Caution, Red=Hazard)',
            color='white', fontsize=12
        )
        ax2.set_ylabel('Motor Speed (%)', color='white')
        ax2.set_xlabel('Reading Number',  color='white')
        ax2.tick_params(colors='white')
        ax2.set_ylim(0, 110)
        
        plt.tight_layout()
        
        graph_path = csv_path.replace('.csv', '_graph.png')
        plt.savefig(graph_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"Graph saved to: {graph_path}")
        return graph_path