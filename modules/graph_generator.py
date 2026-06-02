import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

class GraphGenerator:

    EVENT_COLORS = {
        'normal':    '#999999',
        'pothole':   '#ff4d4d',
        'speed_hump':'#ffb300',
        'braking':   '#6f8cff',
    }

    def generate(self, csv_path):
        print("Generating session graph...")

        df = pd.read_csv(csv_path)
        if len(df) < 10:
            print("Not enough data to generate graph.")
            return

        x = df.index
        df = df.copy()
        df['severity_pct'] = df['severity_score'] * 100
        df['decision_code'] = df['decision'].map({'NORMAL': 0, 'CAUTION': 1, 'HAZARD': 2}).fillna(0)

        fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True,
                                 gridspec_kw={'height_ratios': [2, 1]})
        fig.patch.set_facecolor('#1e1e1e')
        for ax in axes:
            ax.set_facecolor('#1e1e1e')
            ax.tick_params(colors='white')
            for spine in ax.spines.values():
                spine.set_color('#666666')

        axes[0].plot(x, df['confidence'], color='#4fd1c5', linewidth=2.2, label='Confidence')
        axes[0].plot(x, df['severity_pct'], color='#ff6b6b', linewidth=2.2, linestyle='--', label='Severity (%)')
        axes[0].scatter(x, df['severity_pct'], color='#ff6b6b', s=16, alpha=0.7)

        if df['motor_speed'].nunique() > 1:
            speed_ax = axes[0].twinx()
            speed_ax.plot(x, df['motor_speed'], color='#a29bfe', linewidth=1.6, linestyle=':', label='Motor Speed')
            speed_ax.set_ylabel('Motor Speed (%)', color='#a29bfe')
            speed_ax.tick_params(colors='#a29bfe')
            speed_ax.set_ylim(0, max(110, df['motor_speed'].max() + 5))
            speed_lines, speed_labels = speed_ax.get_legend_handles_labels()
        else:
            speed_lines, speed_labels = [], []

        axes[0].set_title('Confidence and Severity Over Time', color='white', fontsize=16)
        axes[0].set_ylabel('Percent / Score', color='white')
        axes[0].set_xlabel('Sample index', color='white')
        axes[0].grid(color='#333333', linestyle='--', linewidth=0.5, alpha=0.6)

        main_lines, main_labels = axes[0].get_legend_handles_labels()
        legend_entries = main_lines + speed_lines
        legend_labels = main_labels + speed_labels
        axes[0].legend(legend_entries, legend_labels, frameon=False, loc='upper right', labelcolor='white')

        color_series = df['lora_event'].map(self.EVENT_COLORS).fillna('#777777')
        axes[1].scatter(x, df['decision_code'], c=color_series, s=22, alpha=0.9)
        axes[1].set_yticks([0, 1, 2])
        axes[1].set_yticklabels(['NORMAL', 'CAUTION', 'HAZARD'], color='white')
        axes[1].set_title('Decision Timeline (colored by reported event)', color='white', fontsize=16)
        axes[1].set_ylabel('Decision', color='white')
        axes[1].set_xlabel('Sample index', color='white')
        axes[1].set_ylim(-0.5, 2.5)
        axes[1].grid(color='#333333', linestyle='--', linewidth=0.5, alpha=0.6)

        legend_entries = [Line2D([0], [0], marker='o', color='w', markerfacecolor=color, markersize=9, linestyle='')
                          for color in self.EVENT_COLORS.values()]
        axes[1].legend(legend_entries, list(self.EVENT_COLORS.keys()), frameon=False, loc='upper right', labelcolor='white')

        plt.tight_layout()
        graph_path = csv_path.replace('.csv', '_graph.png')
        plt.savefig(graph_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close()

        print(f"Graph saved to: {graph_path}")
        return graph_path