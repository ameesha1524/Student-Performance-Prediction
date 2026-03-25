import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import VotingClassifier
from sklearn.neural_network import MLPClassifier
import joblib

print("Generating synthetic student data...")
np.random.seed(42)
n_samples = 1000

# Generate realistic student data bounds
attendance = np.random.randint(30, 100, n_samples)
internal = np.random.randint(5, 50, n_samples)
assignment = np.random.randint(5, 30, n_samples)
quiz = np.random.randint(2, 20, n_samples)

# Calculate outcome (1 = Pass, 0 = Fail) based on a realistic threshold
total_score = internal + assignment + quiz
y = np.where((total_score >= 40) & (attendance >= 50), 1, 0)

# Add some random noise to make the ML models work harder
flip_indices = np.random.choice(n_samples, size=int(n_samples * 0.05), replace=False)
y[flip_indices] = 1 - y[flip_indices]

X = pd.DataFrame({
    'attendance': attendance,
    'internal': internal,
    'assignment': assignment,
    'quiz': quiz
})

print("Training XGBoost, LightGBM, and Deep Neural Network...")
# 1. XGBoost
xgb_model = xgb.XGBClassifier(use_label_encoder=False, eval_metric='logloss', random_state=42)

# 2. LightGBM
lgb_model = lgb.LGBMClassifier(random_state=42, verbose=-1)

# 3. Deep Neural Network
dnn_model = MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=1000, random_state=42)

# 4. The Voting Ensemble
ensemble_model = VotingClassifier(
    estimators=[('xgb', xgb_model), ('lgb', lgb_model), ('dnn', dnn_model)],
    voting='soft' # Uses probability averaging for higher accuracy
)

ensemble_model.fit(X, y)

# Save the new brain
joblib.dump(ensemble_model, 'ensemble_model.pkl')
print("Success! Saved as 'ensemble_model.pkl'. You can now use this in your Flask app.")