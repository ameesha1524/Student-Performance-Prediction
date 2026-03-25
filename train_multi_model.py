import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
import joblib

print("Generating synthetic student data...")
np.random.seed(42)
n_samples = 1000

attendance = np.random.randint(30, 100, n_samples)
internal = np.random.randint(5, 50, n_samples)
assignment = np.random.randint(5, 30, n_samples)
quiz = np.random.randint(2, 20, n_samples)

total_score = internal + assignment + quiz
y = np.where((total_score >= 40) & (attendance >= 50), 1, 0)

# Add noise for realism
flip_indices = np.random.choice(n_samples, size=int(n_samples * 0.05), replace=False)
y[flip_indices] = 1 - y[flip_indices]

X = pd.DataFrame({'attendance': attendance, 'internal': internal, 'assignment': assignment, 'quiz': quiz})

print("Training RF, SVM, LR, and Ensemble models...")

# 1. Initialize the Models
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
svm_model = SVC(probability=True, random_state=42) # probability=True is required for soft voting
lr_model = LogisticRegression(max_iter=1000, random_state=42)

# 2. Build the Ensemble
ensemble_model = VotingClassifier(
    estimators=[('rf', rf_model), ('svm', svm_model), ('lr', lr_model)],
    voting='soft'
)

# 3. Train everything
rf_model.fit(X, y)
svm_model.fit(X, y)
lr_model.fit(X, y)
ensemble_model.fit(X, y)

# 4. Package them into a dictionary and save
multi_model_dict = {
    'Random Forest': rf_model,
    'SVM': svm_model,
    'Logistic Regression': lr_model,
    'Ensemble': ensemble_model
}

joblib.dump(multi_model_dict, 'multi_model.pkl')
print("Success! Saved all 4 models as 'multi_model.pkl'.")
