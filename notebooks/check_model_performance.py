# notebooks/check_model_performance.py
import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, precision_score, recall_score, f1_score

print("="*60)
print("🔍 CHECKING MODEL PERFORMANCE")
print("="*60)

# Load your dataset
df = pd.read_csv("data/datasets/India_Cyber_Scam_Hinglish_Dataset.csv")
print(f"✅ Loaded {len(df)} records")

# Feature engineering for CALL FEATURES (matching training)
# Create synthetic call features from text data
def extract_scam_score(text):
    if not isinstance(text, str):
        return 0
    text = text.lower()
    keywords = ['arrest', 'police', 'cbi', 'court', 'judge', 'customs', 
                'investigation', 'money laundering', 'digital arrest']
    return sum(1 for word in keywords if word in text)

# Create features that match the model's expectations
df['scam_keywords'] = df['text'].apply(extract_scam_score)
df['word_count'] = df['text'].apply(lambda x: len(str(x).split()))
df['has_phone'] = df['text'].str.contains(r'\d{10}').astype(int)
df['has_upi'] = df['text'].str.contains(r'@|upi').astype(int)
df['is_digital_arrest'] = (df['scam_category'] == 'police_digital_arrest').astype(int)

# NOW MAP TO CALL FEATURES (6 features)
# We'll simulate call features from text data
# Digital arrest calls have: long duration, unknown, video, mid-morning, no history, low activity

def create_call_features(row):
    if row['is_digital_arrest'] == 1:
        # Scam pattern
        return {
            'call_duration_min': np.random.randint(120, 480),  # 2-8 hours
            'is_unknown_number': 1,
            'is_video_call': 1,
            'hour_of_day': np.random.randint(9, 17),  # Mid-morning to afternoon
            'caller_call_history': 0,
            'outgoing_activity_ratio': np.random.uniform(0.01, 0.2)
        }
    else:
        # Normal pattern
        return {
            'call_duration_min': np.random.randint(1, 30),  # Short
            'is_unknown_number': np.random.choice([0, 1], p=[0.7, 0.3]),
            'is_video_call': np.random.choice([0, 1], p=[0.85, 0.15]),
            'hour_of_day': np.random.randint(8, 22),
            'caller_call_history': np.random.randint(3, 20),
            'outgoing_activity_ratio': np.random.uniform(0.4, 0.9)
        }

# Apply to create features
features_list = df.apply(create_call_features, axis=1)
features_df = pd.DataFrame(features_list.tolist())

# Now we have 6 features matching the model
print(f"\n✅ Created {len(features_df)} call feature records")
print(f"   Features: {features_df.columns.tolist()}")

X = features_df
y = df['is_digital_arrest']

# Split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Scale
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Load model
model = joblib.load('models/saved/risk_classifier.pkl')

# Predict
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

print("\n" + "="*60)
print("📊 CONFUSION MATRIX")
print("="*60)
print(confusion_matrix(y_test, y_pred))

print("\n" + "="*60)
print("📊 CLASSIFICATION REPORT (FOCUS ON SCAM CLASS)")
print("="*60)
print(classification_report(y_test, y_pred))

print("\n" + "="*60)
print("🎯 SCAM CLASS METRICS (MOST IMPORTANT)")
print("="*60)
print(f"Precision (Scam Class): {precision_score(y_test, y_pred):.3f}")
print(f"Recall (Scam Class): {recall_score(y_test, y_pred):.3f}")
print(f"F1-Score (Scam Class): {f1_score(y_test, y_pred):.3f}")

# Interpretation
print("\n" + "="*60)
print("💡 INTERPRETATION")
print("="*60)
recall = recall_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)

if recall >= 0.7 and precision >= 0.7:
    print("✅ Strong scam detection! Both precision and recall are good.")
elif recall < 0.5:
    print("⚠️ RECALL IS LOW - Your model is MISSING many scams.")
    print("   Try adjusting the model or collecting more scam samples.")
elif precision < 0.5:
    print("⚠️ PRECISION IS LOW - Your model is falsely flagging normal calls.")
    print("   Try adjusting the threshold or refining features.")
else:
    print("✅ Decent performance. Consider tuning the model for better results.")

# Feature importance
print("\n" + "="*60)
print("📊 FEATURE IMPORTANCE")
print("="*60)
importances = model.feature_importances_
for name, imp in zip(X.columns, importances):
    print(f"   {name}: {imp:.3f}")