# notebooks/train_model.py
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import xgboost as xgb
import joblib
import os
import matplotlib.pyplot as plt
import seaborn as sns

print("="*60)
print("🚀 LUMINA - Training ML Model with Real Dataset")
print("="*60)

# 1. Load your dataset
df = pd.read_csv("data/datasets/India_Cyber_Scam_Hinglish_Dataset.csv")
print(f"✅ Loaded dataset: {len(df)} rows")
print(f"   Columns: {df.columns.tolist()}")

# 2. Create features from text
def extract_features(text):
    """Extract scam indicators from text"""
    if not isinstance(text, str):
        return 0
    text = text.lower()
    
    # Digital arrest keywords
    keywords = ['arrest', 'police', 'cbi', 'court', 'judge', 'customs', 
                'investigation', 'money laundering', 'digital arrest',
                'supreme court', 'high court', 'warrant', 'summons']
    
    score = sum(1 for word in keywords if word in text)
    return score

# Feature engineering
df['scam_keyword_score'] = df['text'].apply(extract_features)
df['word_count'] = df['text'].apply(lambda x: len(str(x).split()))
df['has_phone'] = df['text'].str.contains(r'\d{10}').astype(int)
df['has_upi'] = df['text'].str.contains(r'@|upi').astype(int)

# Convert urgency_level to numeric
urgency_map = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
df['urgency_score'] = df['urgency_level'].map(urgency_map).fillna(0)

# Convert language_style to numeric
lang_map = {'hinglish': 0, 'english': 1, 'hindi': 2}
df['language_code'] = df['language_style'].map(lang_map).fillna(0)

# 3. Prepare features for ML
feature_cols = [
    'scam_keyword_score', 
    'word_count', 
    'has_phone', 
    'has_upi',
    'urgency_score',
    'language_code',
    'audio_duration'
]

# Convert audio_duration to numeric (handle any non-numeric)
df['audio_duration'] = pd.to_numeric(df['audio_duration'], errors='coerce').fillna(0)

X = df[feature_cols].fillna(0)
y = (df['scam_category'] == 'police_digital_arrest').astype(int)

print(f"\n📊 Dataset Info:")
print(f"   Total samples: {len(df)}")
print(f"   Digital arrest samples: {y.sum()} ({y.mean()*100:.1f}%)")
print(f"   Features: {feature_cols}")

# 4. Split and scale
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# 5. Train XGBoost
print("\n🚀 Training XGBoost model...")
model = xgb.XGBClassifier(
    n_estimators=100,
    max_depth=4,
    learning_rate=0.1,
    scale_pos_weight=(len(y) - y.sum()) / y.sum(),  # Handle class imbalance
    random_state=42
)
model.fit(X_train_scaled, y_train)

# 6. Evaluate
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

print("\n" + "="*60)
print("📊 MODEL EVALUATION")
print("="*60)
print(f"Accuracy: {model.score(X_test_scaled, y_test):.3f}")
print(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.3f}")

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# 7. Feature importance
importances = model.feature_importances_
feature_importance = pd.DataFrame({
    'feature': feature_cols,
    'importance': importances
}).sort_values('importance', ascending=False)

print("\n📊 Feature Importance:")
print(feature_importance)

# 8. Save model
os.makedirs('models/saved', exist_ok=True)
joblib.dump(model, 'models/saved/risk_classifier.pkl')
joblib.dump(scaler, 'models/saved/scaler.pkl')
joblib.dump(feature_cols, 'models/saved/feature_cols.pkl')
print("\n✅ Model saved to models/saved/risk_classifier.pkl")
print("✅ Scaler saved to models/saved/scaler.pkl")