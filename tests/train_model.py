import sys
import os
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Paths
data_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'imu_simulation', 'training_data.csv'
)
model_path = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'imu_simulation', 'hazard_model.pkl'
)

print("Loading training data...")
df = pd.read_csv(data_path)

print(f"Total samples: {len(df)}")
print(f"Label distribution:")
print(df['label'].value_counts())
print("-" * 40)

# Split features and labels
X = df[[
    'imu_now',
    'imu_1ago',
    'imu_2ago',
    'imu_rate_of_change',
    'motion_score',
    'camera_high'
]]
y = df['label']

# Split into training and testing sets
# 80% train, 20% test
X_train, X_test, y_train, y_test = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42
)

print(f"Training samples: {len(X_train)}")
print(f"Testing samples:  {len(X_test)}")
print("-" * 40)

# Train the model
print("Training Random Forest model...")
model = RandomForestClassifier(
    n_estimators=100,    # 100 decision trees
    max_depth=10,        # max depth of each tree
    random_state=42
)
model.fit(X_train, y_train)
print("Training complete.")
print("-" * 40)

# Evaluate
print("Evaluating model...")
y_pred = model.predict(X_test)

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

print("Confusion Matrix:")
print(confusion_matrix(y_test, y_pred))
print("-" * 40)

# Save model
joblib.dump(model, model_path)
print(f"Model saved to: {model_path}")
print("Training pipeline complete.")