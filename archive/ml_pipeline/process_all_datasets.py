# notebooks/process_all_datasets.py
import pandas as pd
import numpy as np
import os
import glob

print("="*60)
print("🚀 LUMINA - Processing ALL Datasets")
print("="*60)

# 1. LOAD INDIA CYBER SCAM DATASET
print("\n📂 Loading India Cyber Scam Dataset...")
df_cyber = pd.read_csv("data/datasets/India_Cyber_Scam_Hinglish_Dataset.csv")
print(f"   ✅ Loaded: {len(df_cyber)} rows")
print(f"   Columns: {df_cyber.columns.tolist()}")

# 2. LOAD FRAUDZEN CALL RECORDS (first few files)
print("\n📂 Loading Fraudzen Call Records...")
fraudzen_files = glob.glob("data/datasets/Fraudzen-dataset/**/*.csv", recursive=True)
print(f"   Found {len(fraudzen_files)} files")

# Process first 10 files
df_calls = []
for i, file in enumerate(fraudzen_files[:10]):
    try:
        df = pd.read_csv(file, on_bad_lines='skip')
        print(f"   ✅ Loaded: {os.path.basename(file)} - {len(df)} rows")
        df_calls.append(df)
    except Exception as e:
        print(f"   ⚠️ Error: {os.path.basename(file)}")

if df_calls:
    df_fraudzen = pd.concat(df_calls, ignore_index=True)
    print(f"\n   ✅ Total call records: {len(df_fraudzen)}")
else:
    df_fraudzen = pd.DataFrame()
    print("   ⚠️ No call records loaded")

# 3. SHOW SAMPLE DATA
print("\n📊 Sample Cyber Scam Data:")
print(df_cyber[['text', 'scam_category']].head(3))

if not df_fraudzen.empty:
    print("\n📊 Sample Fraudzen Data:")
    print(df_fraudzen.head(2))

# 4. CREATE FEATURES FOR ML
print("\n🔧 Creating features...")

# From Cyber Scam
df_cyber['scam_keywords'] = df_cyber['text'].apply(
    lambda x: sum(1 for w in ['arrest', 'police', 'cbi', 'court', 'judge', 'customs'] 
                  if w in str(x).lower())
)
df_cyber['word_count'] = df_cyber['text'].apply(lambda x: len(str(x).split()))
df_cyber['is_digital_arrest'] = (df_cyber['scam_category'] == 'police_digital_arrest').astype(int)

print(f"\n📊 Digital Arrest samples: {df_cyber['is_digital_arrest'].sum()}")
print(f"   Scam keyword average: {df_cyber['scam_keywords'].mean():.2f}")

# 5. TRAIN MODEL
print("\n🚀 Training XGBoost Model...")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
import joblib

features = ['scam_keywords', 'word_count']
X = df_cyber[features].fillna(0)
y = df_cyber['is_digital_arrest']

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
    random_state=42
)
model.fit(X_train_scaled, y_train)

# Evaluate
y_pred = model.predict(X_test_scaled)
y_proba = model.predict_proba(X_test_scaled)[:, 1]

print("\n" + "="*60)
print("📊 MODEL EVALUATION")
print("="*60)
print(f"Accuracy: {model.score(X_test_scaled, y_test):.3f}")
print(f"AUC-ROC: {roc_auc_score(y_test, y_proba):.3f}")

# Save model
os.makedirs('models/saved', exist_ok=True)
joblib.dump(model, 'models/saved/risk_classifier.pkl')
joblib.dump(scaler, 'models/saved/scaler.pkl')
print("\n✅ Model saved to models/saved/risk_classifier.pkl")