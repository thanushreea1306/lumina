# notebooks/train_call_model.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import joblib
import os

print("="*60)
print("🚀 LUMINA - Training Call Feature Model")
print("="*60)

# 1. Create synthetic training data based on REAL scam patterns
np.random.seed(42)

# Create 10,000 synthetic call records
n_samples = 10000

# Generate features based on known scam patterns
data = []
for i in range(n_samples):
    # 15% scam rate (realistic)
    is_scam = 1 if np.random.random() < 0.15 else 0
    
    if is_scam:
        # Digital arrest scam pattern
        call_duration = np.random.randint(60, 500)
        is_unknown = 1 if np.random.random() < 0.85 else 0
        is_video = 1 if np.random.random() < 0.75 else 0
        hour = np.random.randint(9, 17)
        call_history = np.random.choice([0, 1, 2], p=[0.8, 0.15, 0.05])
        outgoing_ratio = np.random.uniform(0.01, 0.3)
    else:
        # Normal call pattern
        call_duration = np.random.randint(1, 45)
        is_unknown = 1 if np.random.random() < 0.2 else 0
        is_video = 1 if np.random.random() < 0.15 else 0
        hour = np.random.randint(8, 22)
        call_history = np.random.randint(3, 20)
        outgoing_ratio = np.random.uniform(0.4, 0.9)
    
    data.append({
        'call_duration_min': call_duration,
        'is_unknown_number': is_unknown,
        'is_video_call': is_video,
        'hour_of_day': hour,
        'caller_call_history': call_history,
        'outgoing_activity_ratio': outgoing_ratio,
        'is_scam': is_scam
    })

df = pd.DataFrame(data)
print(f"✅ Generated {len(df)} synthetic call records")
print(f"   Scam calls: {df['is_scam'].sum()} ({df['is_scam'].mean()*100:.1f}%)")

# 2. Prepare features
features = [
    'call_duration_min',
    'is_unknown_number',
    'is_video_call',
    'hour_of_day',
    'caller_call_history',
    'outgoing_activity_ratio'
]
X = df[features]
y = df['is_scam']

# 3. Train model
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    scale_pos_weight=(len(y) - y.sum()) / y.sum(),
    random_state=42
)
model.fit(X_train_scaled, y_train)

# 4. Evaluate
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

print("\n" + "="*60)
print("📊 MODEL EVALUATION")
print("="*60)
print(f"Accuracy: {model.score(X_test_scaled, y_test):.3f}")
print(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.3f}")
print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# 5. Save model
os.makedirs('models/saved', exist_ok=True)
joblib.dump(model, 'models/saved/risk_classifier.pkl')
joblib.dump(scaler, 'models/saved/scaler.pkl')
joblib.dump(features, 'models/saved/features.pkl')

print("\n✅ Model saved to models/saved/risk_classifier.pkl")
print(f"   Features: {features}")