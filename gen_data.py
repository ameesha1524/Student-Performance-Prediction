import pandas as pd
import numpy as np

# Set seed for reproducibility
np.random.seed(42)

num_students = 70

data = {
    # Format: student1, student2, ... student70
    'student_roll': [f'student{i+1}' for i in range(num_students)],
    
    # Attendance: High risk (below 60), Medium (60-75), Low (75-100)
    'attendance': np.random.choice(
        [np.random.randint(40, 59), np.random.randint(60, 74), np.random.randint(75, 99)],
        size=num_students, p=[0.2, 0.3, 0.5]
    ),
    
    # CAT1 & CAT2 (Out of 50)
    'cat1': np.random.randint(10, 50, size=num_students),
    'cat2': np.random.randint(10, 50, size=num_students),
    
    # Assignment/Quiz (Out of 10)
    'assignment_quiz': np.random.uniform(3, 10, size=num_students).round(1)
}

df = pd.DataFrame(data)

# Force the first two to be your existing users for easy testing
df.loc[0, ['attendance', 'cat1', 'cat2', 'assignment_quiz']] = [85, 45, 42, 9.5] # student1 (Pass)
df.loc[1, ['attendance', 'cat1', 'cat2', 'assignment_quiz']] = [50, 15, 12, 4.0] # student2 (Fail/Risk)

# Save to CSV
df.to_csv('students_70.csv', index=False)
print("Updated 'students_70.csv' created with 'studentX' format!")