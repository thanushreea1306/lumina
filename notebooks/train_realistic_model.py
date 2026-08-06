# notebooks/train_realistic_model.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score, roc_auc_score
import xgboost as xgb
import joblib
import os
import matplotlib.pyplot as plt

print("="*60)
print("🚀 LUMINA - Training REALISTIC Model")
print("="*60)

# Set random seed for reproducibility
np.random.seed(42)

# 1. CREATE REALISTIC SYNTHETIC DATA
print("\n📊 Generating realistic synthetic data...")

def generate_realistic_calls(n_samples=10000):
    """Generate realistic call data with overlap between scam and normal"""
    data = []
    
    for i in range(n_samples):
        # Decide if it's a scam (15% rate - realistic)
        is_scam = 1 if np.random.random() < 0.15 else 0
        
        # For scam calls - realistic pattern with SOME overlap
        if is_scam:
            duration = np.random.normal(120, 80)  # 120 min avg, 80 min std
            duration = max(30, min(480, duration))  # Clamp 30-480 min
            
            unknown = np.random.choice([0, 1], p=[0.15, 0.85])  # 85% unknown
            video = np.random.choice([0, 1], p=[0.20, 0.80])    # 80% video
            hour = np.random.choice(range(8, 19))  # 8am to 6pm
            history = np.random.choice([0, 1, 2, 3, 4], p=[0.50, 0.25, 0.15, 0.07, 0.03])
            activity = np.random.beta(2, 8)  # Low activity (0-0.4 range)
            weekend = 0  # Weekday
        else:
            # Normal calls - realistic pattern
            duration = np.random.exponential(15)  # 15 min avg
            duration = max(0.5, min(60, duration))  # Clamp 0.5-60 min
            
            unknown = np.random.choice([0, 1], p=[0.70, 0.30])  # 30% unknown
            video = np.random.choice([0, 1], p=[0.85, 0.15])    # 15% video
            hour = np.random.choice(range(6, 23))  # 6am to 10pm
            history = np.random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], p=[0.15, 0.15, 0.13, 0.11, 0.09, 0.08, 0.07, 0.06, 0.05, 0.11])
            activity = np.random.beta(8, 3)  # High activity (0.5-0.9 range)
            weekend = np.random.choice([0, 1], p=[0.70, 0.30])
        
        data.append({
            'call_duration_min': duration,
            'is_unknown_number': unknown,
            'is_video_call': video,
            'hour_of_day': hour,
            'caller_call_history': history,
            'outgoing_activity_ratio': activity,
            'is_weekend': weekend,
            'is_scam': is_scam
        })
    
    return pd.DataFrame(data)

# Generate data
df = generate_realistic_calls(15000)
print(f"✅ Generated {len(df)} call records")
print(f"   Scam calls: {df['is_scam'].sum()} ({df['is_scam'].mean()*100:.1f}%)")

# 2. FEATURE ENGINEERING - Add more features
print("\n🔧 Creating features...")

df['call_duration_log'] = np.log1p(df['call_duration_min'])  # Log transform
df['is_early_morning'] = ((df['hour_of_day'] >= 5) & (df['hour_of_day'] <= 8)).astype(int)
df['is_late_night'] = ((df['hour_of_day'] >= 22) | (df['hour_of_day'] <= 4)).astype(int)
df['activity_category'] = pd.cut(df['outgoing_activity_ratio'], bins=3, labels=[0, 1, 2]).astype(int)

# 3. PREPARE FEATURES
features = [
    'call_duration_min',
    'is_unknown_number',
    'is_video_call',
    'hour_of_day',
    'caller_call_history',
    'outgoing_activity_ratio',
    'is_weekend',
    'call_duration_log',
    'is_early_morning',
    'is_late_night',
    'activity_category'
]

X = df[features]
y = df['is_scam']

print(f"   Features: {len(features)} features")

# 4. TRAIN/VALIDATION/TEST SPLIT
print("\n📊 Splitting data...")
X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)

print(f"   Training: {len(X_train)} samples")
print(f"   Validation: {len(X_val)} samples")
print(f"   Test: {len(X_test)} samples")

# 5. SCALE FEATURES
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_val_scaled = scaler.transform(X_val)
X_test_scaled = scaler.transform(X_test)

# 6. TRAIN XGBOOST WITH EARLY STOPPING
print("\n🚀 Training XGBoost model...")

model = xgb.XGBClassifier(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.08,
    subsample=0.8,
    colsample_bytree=0.8,
    scale_pos_weight=(len(y) - y.sum()) / y.sum(),  # Handle class imbalance
    random_state=42,
    eval_metric='logloss'
)

model.fit(
    X_train_scaled, y_train,
    eval_set=[(X_val_scaled, y_val)],
    early_stopping_rounds=20,
    verbose=False
)

# 7. EVALUATE ON TEST SET
print("\n" + "="*60)
print("📊 FINAL MODEL EVALUATION")
print("="*60)

y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

# Confusion Matrix
cm = confusion_matrix(y_test, y_pred)
print("\nConfusion Matrix:")
print(cm)

# Metrics
accuracy = model.score(X_test_scaled, y_test)
auc_roc = roc_auc_score(y_test, y_proba)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print(f"\nAccuracy: {accuracy:.3f}")
print(f"AUC-ROC: {auc_roc:.3f}")
print(f"Precision (Scam Class): {precision:.3f}")
print(f"Recall (Scam Class): {recall:.3f}")
print(f"F1-Score (Scam Class): {f1:.3f}")

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# 8. FEATURE IMPORTANCE
print("\n" + "="*60)
print("📊 FEATURE IMPORTANCE")
print("="*60)
importances = model.feature_importances_
feature_importance = pd.DataFrame({
    'feature': features,
    'importance': importances
}).sort_values('importance', ascending=False)

print(feature_importance.to_string(index=False))

# 9. SAVE MODEL
os.makedirs('models/saved', exist_ok=True)
joblib.dump(model, 'models/saved/risk_classifier.pkl')
joblib.dump(scaler, 'models/saved/scaler.pkl')
joblib.dump(features, 'models/saved/features.pkl')

print("\n✅ Model saved to models/saved/risk_classifier.pkl")
print("✅ Scaler saved to models/saved/scaler.pkl")
print("✅ Features saved to models/saved/features.pkl")

# 10. SAVE FEATURE IMPORTANCE PLOT
plt.figure(figsize=(10, 8))
plt.barh(feature_importance['feature'], feature_importance['importance'])
plt.xlabel('Feature Importance')
plt.title('LUMINA - Feature Importance')
plt.tight_layout()
plt.savefig('data/processed/feature_importance.png')
print("✅ Feature importance plot saved to data/processed/feature_importance.png")