"""
train_model_v2.py
━━━━━━━━━━━━━━━━━
Improved ML training pipeline.
Uses:
  - Richer features (9 instead of 6)
  - Class balancing with SMOTE
  - Ensemble of 3 models
  - 5-fold stratified cross validation
  - Proper evaluation per class
  - Saves best model as hazard_model.pkl
"""
 
import os
import sys
import numpy as np
import pandas as pd
import joblib
import warnings
warnings.filterwarnings('ignore')
 
from sklearn.ensemble          import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.svm               import SVC
from sklearn.preprocessing     import StandardScaler, LabelEncoder
from sklearn.model_selection   import train_test_split, StratifiedKFold, cross_val_score
from sklearn.metrics           import classification_report, confusion_matrix, accuracy_score
from sklearn.pipeline          import Pipeline
 
# Try importing imbalanced-learn for SMOTE
try:
    from imblearn.over_sampling import SMOTE
    SMOTE_AVAILABLE = True
except ImportError:
    SMOTE_AVAILABLE = False
    print("⚠️  imbalanced-learn not installed.")
    print("   Run: pip install imbalanced-learn")
    print("   Continuing without SMOTE...")
 
# ── Paths ──
DATA_DIR   = os.path.join('data', 'imu_simulation')
REAL_DATA  = os.path.join(DATA_DIR, 'real_imu_data.csv')
OLD_DATA   = os.path.join(DATA_DIR, 'training_data.csv')
MODEL_PATH = os.path.join(DATA_DIR, 'hazard_model.pkl')
SCALER_PATH= os.path.join(DATA_DIR, 'scaler.pkl')
 
os.makedirs(DATA_DIR, exist_ok=True)
 
# ══════════════════════════════════════════
# STEP 1 — LOAD DATA
# ══════════════════════════════════════════
def load_data():
    dfs = []
 
    # Load real IMU data (preferred)
    if os.path.exists(REAL_DATA):
        df = pd.read_csv(REAL_DATA)
        print(f"✅ Real IMU data loaded: {len(df)} samples")
        dfs.append(df)
    else:
        print("⚠️  No real IMU data found.")
        print("   Run collect_real_data.py first for best accuracy.")
 
    # Also use old training data if available
    if os.path.exists(OLD_DATA):
        df_old = pd.read_csv(OLD_DATA)
        # Check if old data has compatible columns
        if 'label' in df_old.columns:
            # Convert old format to new format
            df_new = convert_old_data(df_old)
            dfs.append(df_new)
            print(f"✅ Old training data loaded: {len(df_old)} samples")
 
    if not dfs:
        print("❌ No training data found.")
        print("   Run collect_real_data.py first.")
        sys.exit(1)
 
    combined = pd.concat(dfs, ignore_index=True)
    print(f"📊 Total samples: {len(combined)}")
    return combined
 
def convert_old_data(df_old):
    """
    Converts old 6-feature format to new 9-feature format.
    Estimates missing features from available ones.
    """
    df_new = pd.DataFrame()
 
    if 'imu_now' in df_old.columns:
        df_new['imu_now']       = df_old['imu_now']
        df_new['imu_mean']      = df_old.get('imu_now', df_old['imu_now'])
        df_new['imu_std']       = abs(df_old.get('imu_rate_of_change', 0.02))
        df_new['imu_max']       = df_old['imu_now'] * 1.05
        df_new['imu_min']       = df_old['imu_now'] * 0.95
        df_new['imu_range']     = abs(df_old.get('imu_rate_of_change', 0.02)) * 2
        df_new['imu_max_diff']  = abs(df_old.get('imu_rate_of_change', 0.02))
        df_new['imu_mean_diff'] = abs(df_old.get('imu_rate_of_change', 0.02)) * 0.5
        df_new['imu_rate']      = df_old.get('imu_rate_of_change', 0.0)
        df_new['label']         = df_old['label']
 
    return df_new
 
# ══════════════════════════════════════════
# STEP 2 — FEATURE ENGINEERING
# ══════════════════════════════════════════
FEATURES = [
    'imu_now',       # Current Z reading
    'imu_mean',      # Mean of window
    'imu_std',       # Standard deviation (spread)
    'imu_max',       # Peak value
    'imu_min',       # Trough value
    'imu_range',     # Max - Min (total excursion)
    'imu_max_diff',  # Largest single-step jump (sharpness)
    'imu_mean_diff', # Average step size (smoothness)
    'imu_rate',      # Rate of change (last two readings)
]
 
def prepare_features(df):
    """Extract and validate feature matrix"""
    # Check all features exist
    missing = [f for f in FEATURES if f not in df.columns]
    if missing:
        print(f"⚠️  Missing features: {missing}")
        # Fill missing with defaults
        for f in missing:
            df[f] = 0.0
 
    X = df[FEATURES].values.astype(np.float32)
    y = df['label'].values
 
    # Replace NaN/Inf
    X = np.nan_to_num(X, nan=0.0, posinf=3.5, neginf=0.0)
 
    return X, y
 
# ══════════════════════════════════════════
# STEP 3 — CLASS BALANCING
# ══════════════════════════════════════════
def balance_classes(X, y):
    """
    Balances imbalanced classes.
    Uses SMOTE if available, otherwise manual oversampling.
    """
    unique, counts = np.unique(y, return_counts=True)
    print(f"\n📊 Class distribution before balancing:")
    for cls, cnt in zip(unique, counts):
        print(f"   {cls}: {cnt} samples")
 
    if SMOTE_AVAILABLE:
        # Determine minimum samples for SMOTE
        min_samples = min(counts)
        k_neighbors = min(5, min_samples-1)
 
        if k_neighbors < 1:
            print("⚠️  Not enough samples for SMOTE. Using manual oversampling.")
            return manual_oversample(X, y)
 
        sm = SMOTE(
            sampling_strategy='auto',
            k_neighbors=k_neighbors,
            random_state=42
        )
        X_bal, y_bal = sm.fit_resample(X, y)
        print(f"\n📊 Class distribution after SMOTE:")
        unique2, counts2 = np.unique(y_bal, return_counts=True)
        for cls, cnt in zip(unique2, counts2):
            print(f"   {cls}: {cnt} samples")
        return X_bal, y_bal
    else:
        return manual_oversample(X, y)
 
def manual_oversample(X, y):
    """Simple oversampling of minority classes"""
    unique, counts = np.unique(y, return_counts=True)
    max_count = max(counts)
 
    X_list = [X]
    y_list = [y]
 
    for cls, cnt in zip(unique, counts):
        if cnt < max_count:
            idx = np.where(y == cls)[0]
            needed = max_count - cnt
            extra_idx = np.random.choice(idx, needed, replace=True)
            X_list.append(X[extra_idx])
            y_list.append(y[extra_idx])
 
    X_bal = np.vstack(X_list)
    y_bal = np.concatenate(y_list)
 
    # Shuffle
    perm = np.random.permutation(len(y_bal))
    print(f"✅ Manual oversampling complete. Total: {len(y_bal)}")
    return X_bal[perm], y_bal[perm]
 
# ══════════════════════════════════════════
# STEP 4 — BUILD ENSEMBLE MODEL
# ══════════════════════════════════════════
def build_model():
    """
    Voting ensemble of 3 strong classifiers.
    Each handles different aspects of the data.
    """
 
    # Model 1: Random Forest (handles noise well)
    rf = RandomForestClassifier(
        n_estimators    = 200,
        max_depth       = 15,
        min_samples_leaf= 2,
        class_weight    = 'balanced',
        random_state    = 42,
        n_jobs          = -1
    )
 
    # Model 2: Gradient Boosting (best for tabular sensor data)
    gb = GradientBoostingClassifier(
        n_estimators    = 150,
        learning_rate   = 0.08,
        max_depth       = 5,
        min_samples_leaf= 3,
        subsample       = 0.8,
        random_state    = 42
    )
 
    # Model 3: SVM with RBF kernel (good for boundary cases)
    svm = SVC(
        kernel      = 'rbf',
        C           = 10,
        gamma       = 'scale',
        probability = True,   # needed for VotingClassifier
        class_weight= 'balanced',
        random_state= 42
    )
 
    # Voting ensemble — soft voting uses probabilities
    ensemble = VotingClassifier(
        estimators = [
            ('rf',  rf),
            ('gb',  gb),
            ('svm', svm),
        ],
        voting = 'soft',   # uses predicted probabilities
        n_jobs = -1
    )
 
    return ensemble
 
# ══════════════════════════════════════════
# STEP 5 — TRAIN AND EVALUATE
# ══════════════════════════════════════════
def train_and_evaluate(X, y):
    """
    Full training pipeline:
      - Scale features
      - 5-fold cross validation
      - Final train/test split evaluation
      - Save model + scaler
    """
    print("\n" + "="*50)
    print("TRAINING ML MODEL")
    print("="*50)
 
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
 
    # Encode labels
    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    print(f"Classes: {list(le.classes_)}")
 
    # ── Cross Validation ──
    print("\n🔄 Running 5-fold Stratified Cross Validation...")
    model = build_model()
    skf   = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
 
    cv_scores = cross_val_score(
        model, X_scaled, y_enc,
        cv=skf, scoring='accuracy', n_jobs=-1
    )
    print(f"   CV Scores: {[f'{s:.3f}' for s in cv_scores]}")
    print(f"   Mean CV Accuracy: {cv_scores.mean():.4f} ({cv_scores.mean()*100:.1f}%)")
    print(f"   Std CV Accuracy:  {cv_scores.std():.4f}")
 
    # ── Final Train/Test Split ──
    print("\n🔄 Final Train/Test evaluation...")
    X_tr, X_te, y_tr, y_te = train_test_split(
        X_scaled, y_enc,
        test_size    = 0.2,
        stratify     = y_enc,
        random_state = 42
    )
 
    print(f"   Training samples: {len(X_tr)}")
    print(f"   Testing samples:  {len(X_te)}")
 
    print("\n⚙️  Training ensemble model (may take 30-60 seconds)...")
    model.fit(X_tr, y_tr)
 
    y_pred = model.predict(X_te)
    test_acc = accuracy_score(y_te, y_pred)
 
    print(f"\n✅ Test Accuracy: {test_acc:.4f} ({test_acc*100:.1f}%)")
 
    print("\n📊 Per-Class Report:")
    print(classification_report(
        y_te, y_pred,
        target_names=le.classes_
    ))
 
    print("📊 Confusion Matrix:")
    cm = confusion_matrix(y_te, y_pred)
    print(f"   Classes: {list(le.classes_)}")
    print(cm)
 
    # ── Train final model on ALL data ──
    print("\n⚙️  Training final model on complete dataset...")
    final_model = build_model()
    final_model.fit(X_scaled, y_enc)
 
    # ── Save ──
    joblib.dump({
        'model':   final_model,
        'scaler':  scaler,
        'encoder': le,
        'features':FEATURES,
        'cv_mean': cv_scores.mean(),
        'test_acc':test_acc,
    }, MODEL_PATH)
 
    joblib.dump(scaler, SCALER_PATH)
 
    print(f"\n✅ Model saved to: {MODEL_PATH}")
    print(f"✅ Scaler saved to: {SCALER_PATH}")
    print(f"\n🎯 Final CV Accuracy:   {cv_scores.mean()*100:.1f}%")
    print(f"🎯 Final Test Accuracy: {test_acc*100:.1f}%")
 
    return final_model, scaler, le, cv_scores.mean()
 
# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════
if __name__ == '__main__':
    print("="*50)
    print("IMPROVED ML MODEL TRAINER v2")
    print("="*50)
 
    # Install missing packages
    try:
        import sklearn
    except ImportError:
        os.system('pip install scikit-learn')
 
    # Load data
    df = load_data()
 
    # Show class distribution
    print(f"\n📊 Label distribution:")
    print(df['label'].value_counts())
 
    # Prepare features
    X, y = prepare_features(df)
    print(f"\n✅ Feature matrix: {X.shape}")
 
    # Balance classes
    X_bal, y_bal = balance_classes(X, y)
 
    # Train
    model, scaler, encoder, cv_acc = train_and_evaluate(X_bal, y_bal)
 
    if cv_acc >= 0.90:
        print("\n🏆 EXCELLENT — Model accuracy above 90%")
    elif cv_acc >= 0.85:
        print("\n✅ GOOD — Model accuracy above 85%")
    elif cv_acc >= 0.80:
        print("\n⚠️  ACCEPTABLE — Consider collecting more real data")
    else:
        print("\n❌ LOW — Run collect_real_data.py for real sensor data")
        print("   Real data will significantly improve accuracy")