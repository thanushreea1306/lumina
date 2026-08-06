# notebooks/generate_ml_visuals.py
import pandas as pd
import numpy as np
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import confusion_matrix, roc_curve, auc, classification_report
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

print("="*60)
print("📊 GENERATING ML EVALUATION VISUALS")
print("="*60)

# Load model and scaler
model = joblib.load('models/saved/risk_classifier.pkl')
scaler = joblib.load('models/saved/scaler.pkl')
features = joblib.load('models/saved/features.pkl')

print(f"Model expects {len(features)} features: {features}")

# Generate synthetic test data with ALL 11 features
np.random.seed(42)
n_samples = 2000

# Create realistic synthetic data
data = []
for i in range(n_samples):
    is_scam = 1 if np.random.random() < 0.15 else 0
    
    if is_scam:
        call_duration = np.random.normal(180, 80)
        is_unknown = 1 if np.random.random() < 0.85 else 0
        is_video = 1 if np.random.random() < 0.75 else 0
        hour = np.random.randint(9, 18)
        call_history = np.random.choice([0, 1, 2], p=[0.7, 0.2, 0.1])
        outgoing_ratio = np.random.uniform(0.01, 0.3)
        is_weekend = 0
        call_duration_log = np.log1p(call_duration)
        is_early_morning = 0
        is_late_night = 0
        activity_category = 0
    else:
        call_duration = np.random.exponential(15)
        is_unknown = 1 if np.random.random() < 0.3 else 0
        is_video = 1 if np.random.random() < 0.15 else 0
        hour = np.random.randint(8, 22)
        call_history = np.random.randint(3, 15)
        outgoing_ratio = np.random.uniform(0.4, 0.9)
        is_weekend = np.random.choice([0, 1], p=[0.7, 0.3])
        call_duration_log = np.log1p(call_duration)
        is_early_morning = 1 if 5 <= hour <= 8 else 0
        is_late_night = 1 if hour >= 22 or hour <= 4 else 0
        activity_category = 2 if outgoing_ratio > 0.66 else 1 if outgoing_ratio > 0.33 else 0
    
    data.append({
        'call_duration_min': max(0.5, call_duration),
        'is_unknown_number': is_unknown,
        'is_video_call': is_video,
        'hour_of_day': hour,
        'caller_call_history': call_history,
        'outgoing_activity_ratio': max(0, min(1, outgoing_ratio)),
        'is_weekend': is_weekend,
        'call_duration_log': call_duration_log,
        'is_early_morning': is_early_morning,
        'is_late_night': is_late_night,
        'activity_category': activity_category,
        'is_scam': is_scam
    })

df = pd.DataFrame(data)

# Prepare features
X = df[features]
y = df['is_scam']

print(f"Generated {len(df)} samples with {len(features)} features")

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)

# Scale
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Predict
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

# 1. Confusion Matrix
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_test, y_pred)
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=['Normal', 'Scam'],
            yticklabels=['Normal', 'Scam'])
plt.title('Confusion Matrix - LUMINA Risk Classifier')
plt.xlabel('Predicted')
plt.ylabel('Actual')
plt.tight_layout()
plt.savefig('data/processed/confusion_matrix.png', dpi=150)
print("✅ Confusion matrix saved to data/processed/confusion_matrix.png")

# 2. ROC Curve
plt.figure(figsize=(8, 6))
fpr, tpr, _ = roc_curve(y_test, y_proba)
roc_auc = auc(fpr, tpr)
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.3f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('ROC Curve - LUMINA Risk Classifier')
plt.legend(loc="lower right")
plt.tight_layout()
plt.savefig('data/processed/roc_curve.png', dpi=150)
print(f"✅ ROC curve saved to data/processed/roc_curve.png (AUC = {roc_auc:.3f})")

# 3. Classification Report
print("\n" + "="*60)
print("📊 CLASSIFICATION REPORT")
print("="*60)
print(classification_report(y_test, y_pred, target_names=['Normal', 'Scam']))

# 4. Feature Importance (already saved)
print("\n✅ ML visuals generated successfully!")