import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
import joblib

# Step 1: Generate Sample Data (Simulating students.csv)
# Assuming ranges: Attendance (0-100), Internal (0-30), Assignment (0-20), Quiz (0-10)
np.random.seed(42)
num_samples = 500

data = {
    'attendance': np.random.randint(30, 101, num_samples),
    'internal': np.random.randint(5, 31, num_samples),
    'assignment': np.random.randint(2, 21, num_samples),
    'quiz': np.random.randint(1, 11, num_samples)
}
df = pd.DataFrame(data)

# Define pass/fail logic for the dummy data (Pass = 1, Fail = 0)
# A student passes if attendance > 60 AND total score > 30
df['total_score'] = df['internal'] + df['assignment'] + df['quiz']
df['final_result'] = np.where((df['attendance'] > 60) & (df['total_score'] > 30), 1, 0)

# Drop the temporary total_score column
df = df.drop(columns=['total_score'])

# Step 2: Data Preprocessing
X = df[['attendance', 'internal', 'assignment', 'quiz']] # Features
y = df['final_result']                                   # Target Label

# Splitting Dataset (80% Train, 20% Test)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Step 3: Model Training
# Initialize and train Random Forest Classifier
rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
rf_model.fit(X_train, y_train)

# Step 4: Model Evaluation (Optional printouts to verify)
accuracy = rf_model.score(X_test, y_test)
print(f"Model trained successfully with an accuracy of: {accuracy * 100:.2f}%")

# Step 5: Model Saving
joblib.dump(rf_model, 'student_model.pkl')
print("Model saved as 'student_model.pkl'")