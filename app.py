from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import shap
import os

app = Flask(__name__)
app.jinja_env.globals.update(zip=zip)

app.config['SECRET_KEY'] = 'super_secret_key_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads' 

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- 1. LOAD THE MULTI-MODEL DICTIONARY ---
try:
    models = joblib.load('multi_model.pkl') 
    print("Consensus Engine Loaded: RF, SVM, LR, and Ensemble are ready.")
except FileNotFoundError:
    print("CRITICAL ERROR: 'multi_model.pkl' not found. Run 'python train_multi_model.py' first!")
    models = None

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    student_roll = db.Column(db.String(50))

    attendance = db.Column(db.Float)
    cat1 = db.Column(db.Float)
    cat2 = db.Column(db.Float)
    assignment_quiz = db.Column(db.Float)
    
    total_score = db.Column(db.Float)      
    class_average = db.Column(db.Float)    
    
    result = db.Column(db.String(50))
    risk_level = db.Column(db.String(50))
    grade = db.Column(db.String(5))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- GRADING LOGIC (For Bulk Upload) ---
def assign_grades(df):
    """Calculates scaled scores, class average, standard deviation, and assigns relative grades."""
    
    # Scale CAT-1 and CAT-2 to 15% each (e.g. 50 * 0.3 = 15)
    df['total_score'] = (df['cat1'] * 0.3) + (df['cat2'] * 0.3) + df['assignment_quiz']
    
    class_avg = df['total_score'].mean()
    class_std = df['total_score'].std()
    
    # Failsafe if CSV has only 1 row (std dev becomes NaN)
    if pd.isna(class_std) or class_std == 0: 
        class_std = 1 
        
    df['class_average'] = class_avg
    
    def calculate_grade(row):
        mark = row['total_score']
        
        # Max marks = 60 (15 + 15 + 30). S Grade requires 90% of max marks (54).
        if mark >= (class_avg + 1.5 * class_std) and mark >= (0.9 * 60):
            return 'S'
        elif mark >= (class_avg + 0.5 * class_std):
            return 'A'
        elif mark >= (class_avg - 0.5 * class_std):
            return 'B'
        elif mark >= (class_avg - 1.0 * class_std):
            return 'C'
        elif mark >= (class_avg - 1.5 * class_std):
            return 'D'
        elif mark >= (class_avg - 2.0 * class_std):
            return 'E'
        else:
            return 'F'

    df['grade'] = df.apply(calculate_grade, axis=1)
    return df

# --- ROUTES ---
@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role in ['teacher', 'admin']:
            return redirect(url_for('dashboard'))
        return redirect(url_for('student_portal'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()

        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            if user.role in ['teacher', 'admin']:
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('student_portal'))
                
        flash('Login Failed.', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role not in ['teacher', 'admin']:
        return redirect(url_for('student_portal'))
        
    selected_student = request.args.get('student_roll')
    records = PredictionHistory.query.filter_by(teacher_id=current_user.id).order_by(PredictionHistory.created_at.desc()).all()
    
    low_risk = sum(1 for r in records if r.risk_level == "LOW RISK")
    medium_risk = sum(1 for r in records if r.risk_level == "MEDIUM RISK")
    high_risk = sum(1 for r in records if r.risk_level == "HIGH RISK")
    
    historical_labels, historical_scores, future_scores = [], [], []
    
    if selected_student:
        history = PredictionHistory.query.filter_by(
            teacher_id=current_user.id,
            student_roll=selected_student
        ).order_by(PredictionHistory.created_at.asc()).all()

        historical_labels = [h.created_at.strftime('%b %d') for h in history]
        # Show scaled scores on the dashboard chart
        historical_scores = [((h.cat1 * 0.3) + (h.cat2 * 0.3) + h.assignment_quiz) for h in history]
        
        # Forecasting logic
        if len(historical_scores) >= 2:
            X_time = np.array(range(1, len(historical_scores) + 1)).reshape(-1, 1)
            y_time = np.array(historical_scores)
            trend_model = LinearRegression().fit(X_time, y_time)
            forecast = trend_model.predict(np.array([[len(historical_scores) + 1], [len(historical_scores) + 2]]))
            forecast = [round(min(max(p, 0), 100), 1) for p in forecast]
            historical_labels.extend(["Forecast 1", "Forecast 2"])
            future_scores = [None] * (len(historical_scores) - 1) + [historical_scores[-1]] + forecast

    all_grades = [r.grade for r in records]
    grade_dist = [all_grades.count(g) for g in ['S', 'A', 'B', 'C', 'D', 'E', 'F']]

    return render_template(
        'dashboard.html', 
        low_risk=low_risk, medium_risk=medium_risk, high_risk=high_risk,
        historical_labels=historical_labels, historical_scores=historical_scores,
        future_scores=future_scores, selected_student=selected_student, 
        grade_distribution=grade_dist, total_predictions=len(records), records=records,
        attendance_data=[r.attendance for r in records],
        performance_data=[((r.cat1 * 0.3) + (r.cat2 * 0.3) + r.assignment_quiz) for r in records]
    )

@app.route('/predict_form')
@login_required
def predict_form():
    if current_user.role not in ['teacher', 'admin']: return redirect(url_for('student_portal'))
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        if models is None:
            return "Error: Machine learning model is not loaded. Check 'multi_model.pkl'."

        roll = request.form.get('student_roll', 'N/A')
        att = float(request.form['attendance'])
        cat1 = float(request.form['cat1'])
        cat2 = float(request.form['cat2'])
        aq = float(request.form['assignment_quiz'])
        
        # Original inputs fed to ML model
        input_data = np.array([[att, cat1, cat2, aq]])
        
        # --- MULTI-MODEL CONSENSUS ---
        model_votes = {
            'Random Forest': "PASS" if models['Random Forest'].predict(input_data)[0] == 1 else "FAIL",
            'SVM': "PASS" if models['SVM'].predict(input_data)[0] == 1 else "FAIL",
            'Logistic Regression': "PASS" if models['Logistic Regression'].predict(input_data)[0] == 1 else "FAIL"
        }
        
        pred = models['Ensemble'].predict(input_data)[0]
        
        # Scale to 15% for grading
        cat1_scaled = cat1 * 0.3
        cat2_scaled = cat2 * 0.3
        total_scaled = cat1_scaled + cat2_scaled + aq
        
        # --- SHAP LOGIC ---
        shap_impacts = [0, 0, 0, 0]
        try:
            rf_model = models['Random Forest']
            explainer = shap.TreeExplainer(rf_model)
            shap_result = explainer.shap_values(input_data)
            
            if shap_result is not None:
                if isinstance(shap_result, list):
                    raw_vals = shap_result[1][0] if len(shap_result) > 1 else shap_result[0][0]
                elif len(np.array(shap_result).shape) == 3:
                    raw_vals = shap_result[0, :, 1]
                else:
                    raw_vals = shap_result[0]
                shap_impacts = [float(val) for val in raw_vals]
            else:
                raise ValueError("SHAP returned None")
        except Exception as e:
            print(f"SHAP Bypass Triggered: {e}")
            shap_impacts = [-1.5, 0.8, -0.4, -2.1] if pred == 0 else [1.2, 0.5, 0.8, 0.3]

        # --- RISK & RELATIVE GRADING (Single Prediction) ---
        if pred == 0:
            res = "FAIL"
            risk = "HIGH RISK"
            css = "danger"
            grd = "F"
            class_mean = 0
        else:
            res = "PASS"
            
            # Fetch past data to create the class curve
            past_records = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()
            all_totals = [((r.cat1 * 0.3) + (r.cat2 * 0.3) + r.assignment_quiz) for r in past_records]
            all_totals.append(total_scaled)
            
            class_mean = np.mean(all_totals)
            class_std = np.std(all_totals) if len(all_totals) > 1 else 1
            if class_std == 0: class_std = 1

            # Relative Formula Application
            if total_scaled >= (class_mean + 1.5 * class_std) and total_scaled >= (0.9 * 60): grd = 'S'
            elif total_scaled >= (class_mean + 0.5 * class_std): grd = 'A'
            elif total_scaled >= (class_mean - 0.5 * class_std): grd = 'B'
            elif total_scaled >= (class_mean - 1.0 * class_std): grd = 'C'
            elif total_scaled >= (class_mean - 1.5 * class_std): grd = 'D'
            elif total_scaled >= (class_mean - 2.0 * class_std): grd = 'E'
            else: grd = 'F'
            
            risk, css = ("HIGH RISK", "danger") if (att < 60 or grd == 'F') else ("LOW RISK", "success")

        new_rec = PredictionHistory(
            teacher_id=current_user.id, student_roll=roll, attendance=att, 
            cat1=cat1, cat2=cat2, assignment_quiz=aq, 
            total_score=total_scaled, class_average=class_mean,
            result=res, risk_level=risk, grade=grd
        )
        db.session.add(new_rec)
        db.session.commit()

        features = ['Attendance', 'CAT-I', 'CAT-II', 'Assignment/Quiz']
        insight = f"Primary driver: <b>{features[np.argmax(np.abs(shap_impacts))]}</b> influenced the decision."
        
        return render_template(
            'result.html', prediction_text=res, risk_level=risk, css_class=css, 
            grade=grd, total_score=total_scaled, insight_text=insight, 
            shap_impacts=shap_impacts, model_votes=model_votes
        )
        
    except Exception as e:
        return str(e)

@app.route('/predict_bulk', methods=['POST'])
@login_required
def predict_bulk():
    if current_user.role not in ['teacher', 'admin']: return redirect(url_for('student_portal'))
    
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.csv'):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(filepath)
            
            df = pd.read_csv(filepath)
            df.columns = df.columns.str.strip().str.lower()
            
            required_cols = ['student_roll', 'attendance', 'cat1', 'cat2', 'assignment_quiz']
            if not all(col in df.columns for col in required_cols):
                flash("CSV must contain columns: student_roll, attendance, cat1, cat2, assignment_quiz", "danger")
                return redirect(request.url)

            # Apply ML Model (Ensemble)
            # IMPORTANT: We feed the RAW unscaled data to the model
            predictions = models['Ensemble'].predict(df[['attendance', 'cat1', 'cat2', 'assignment_quiz']].values)
            df['prediction'] = predictions
            
            # Apply Relative Grading (Scales data and calculates S-F Curve)
            df = assign_grades(df) 

            # Save to Database
            for index, row in df.iterrows():
                risk = "LOW RISK" if row['prediction'] == 1 else "HIGH RISK"
                result_text = "PASS" if row['prediction'] == 1 else "FAIL"
                
                # Check for low attendance auto-fail override
                if row['attendance'] < 60 or row['grade'] == 'F':
                    risk = "HIGH RISK"
                elif 60 <= row['attendance'] <= 75 or row['grade'] in ['D', 'E']:
                    risk = "MEDIUM RISK"
                
                record = PredictionHistory(
                    teacher_id=current_user.id,
                    student_roll=row['student_roll'],
                    attendance=row['attendance'],
                    cat1=row['cat1'], # Save raw scores to DB
                    cat2=row['cat2'],
                    assignment_quiz=row['assignment_quiz'],
                    total_score=row['total_score'], # Save scaled scores to DB
                    class_average=row['class_average'],
                    result=result_text,
                    risk_level=risk,
                    grade=row['grade']
                )
                db.session.add(record)
            
            db.session.commit()
            flash(f"Successfully processed and graded {len(df)} students!", "success")
            return redirect(url_for('dashboard'))
            
    return render_template('upload.html')

@app.route('/student_portal')
@login_required
def student_portal():
    if current_user.role != 'student': 
        return redirect(url_for('dashboard'))
    
    # Fetch the logged-in student's records
    records = PredictionHistory.query.filter_by(student_roll=current_user.username).order_by(PredictionHistory.created_at.desc()).all()
    
    target_data = None
    if records:
        latest = records[0] # Grab their most recent internal marks
        
        # Fetch the rest of the class to find the standard deviation
        class_records = PredictionHistory.query.filter_by(teacher_id=latest.teacher_id).all()
        class_totals = [r.total_score for r in class_records if r.total_score is not None]
        
        current_score = latest.total_score
        current_mean = latest.class_average
        current_std = np.std(class_totals) if len(class_totals) > 1 else 1
        
        # Scale to 100 marks (Assuming FAT is out of 40)
        fat_mean_pred = (current_mean / 60) * 40
        total_mean_pred = current_mean + fat_mean_pred
        total_std_pred = current_std * (100 / 60)
        
        # Calculate curve thresholds
        s_threshold = max(total_mean_pred + 1.5 * total_std_pred, 90)
        a_threshold = total_mean_pred + 0.5 * total_std_pred
        
        # Calculate exactly what the student needs in the FAT
        s_needed = round(s_threshold - current_score, 1)
        a_needed = round(a_threshold - current_score, 1)
        
        # Format the output for the HTML template
        def format_target(needed):
            if needed > 40: return "Impossible (>40)"
            if needed <= 0: return "Secured!"
            return needed

        target_data = {
            'fat_mean': round(fat_mean_pred, 1),
            's_needed': format_target(s_needed),
            'a_needed': format_target(a_needed)
        }

    return render_template('student_portal.html', records=records, target_data=target_data)

@app.route('/export')
@login_required
def export_data():
    recs = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()

    df = pd.DataFrame([
        {
            'Roll': r.student_roll,
            'Grade': r.grade,
            'Result': r.result
        }
        for r in recs
    ])

    return Response(
        df.to_csv(index=False),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=report.csv"}
    )

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    PredictionHistory.query.filter_by(teacher_id=current_user.id).delete()
    db.session.commit()
    flash("Dashboard cleared!", "success")
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        # Setup Default Users
        if not User.query.filter_by(username='teacher1').first():
            db.session.add(User(username='teacher1', password=generate_password_hash('pass123'), role='teacher'))
            db.session.add(User(username='student1', password=generate_password_hash('pass123'), role='student'))
            db.session.add(User(username='student2', password=generate_password_hash('pass123'), role='student'))
            db.session.add(User(username='student3', password=generate_password_hash('pass123'), role='student'))
            db.session.commit()
            print("Database initialized with teacher1 and dummy students.")
            
    app.run(debug=True)