from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import joblib
import numpy as np
import os
import pandas as pd

app = Flask(__name__)
app = Flask(__name__)
app.jinja_env.globals.update(zip=zip)
app.config['SECRET_KEY'] = 'super_secret_key_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

try:
    model = joblib.load('student_model.pkl')
except FileNotFoundError:
    print("Error: Model file 'student_model.pkl' not found.")
    model = None

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) 

class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    student_roll = db.Column(db.String(50)) # Track unique students
    attendance = db.Column(db.Float)
    internal = db.Column(db.Float)
    assignment = db.Column(db.Float)
    quiz = db.Column(db.Float)
    result = db.Column(db.String(50))
    risk_level = db.Column(db.String(50))
    grade = db.Column(db.String(5))
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # For Time-Series tracking

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard')) if current_user.role in ['teacher', 'admin'] else redirect(url_for('predict_form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard')) if user.role in ['teacher', 'admin'] else redirect(url_for('predict_form'))
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
        return redirect(url_for('predict_form'))
        
    selected_student = request.args.get('student_roll')
    records = PredictionHistory.query.filter_by(teacher_id=current_user.id).order_by(PredictionHistory.created_at.desc()).all()
    
    # Global Stats
    low_risk = sum(1 for r in records if r.risk_level == "LOW RISK")
    medium_risk = sum(1 for r in records if r.risk_level == "MEDIUM RISK")
    high_risk = sum(1 for r in records if r.risk_level == "HIGH RISK")
    
    # Historical Trend Logic
    historical_labels = []
    historical_scores = []
    if selected_student:
        history = PredictionHistory.query.filter_by(teacher_id=current_user.id, student_roll=selected_student).order_by(PredictionHistory.created_at.asc()).all()
        historical_labels = [h.created_at.strftime('%b %d') for h in history]
        historical_scores = [(h.internal + h.assignment + h.quiz) for h in history]

    all_grades = [r.grade for r in records]
    grade_dist = [all_grades.count(g) for g in ['S', 'A', 'B', 'C', 'D', 'E', 'F']]

    return render_template('dashboard.html', 
                           low_risk=low_risk, medium_risk=medium_risk, high_risk=high_risk,
                           historical_labels=historical_labels, historical_scores=historical_scores,
                           selected_student=selected_student, grade_distribution=grade_dist,
                           attendance_data=[r.attendance for r in records],
                           performance_data=[(r.internal + r.assignment + r.quiz) for r in records],
                           total_predictions=len(records), records=records)

@app.route('/predict_form')
@login_required
def predict_form():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        roll = request.form.get('student_roll', 'N/A')
        att = float(request.form['attendance'])
        inter = float(request.form['internal'])
        assgn = float(request.form['assignment'])
        qz = float(request.form['quiz'])
        
        pred = model.predict(np.array([[att, inter, assgn, qz]]))[0]
        total = inter + assgn + qz
        
        # Explainable AI Logic
        importances = model.feature_importances_.tolist()
        student_pcts = [(att), (inter/50*100), (assgn/30*100), (qz/20*100)]
        
        # Grading & Risk Logic
        if pred == 0:
            res, risk, css, grd = "FAIL", "HIGH RISK", "danger", "F"
        else:
            res = "PASS"
            if total >= 90: grd = 'S'
            elif total >= 80: grd = 'A'
            elif total >= 70: grd = 'B'
            elif total >= 60: grd = 'C'
            elif total >= 50: grd = 'D'
            elif total >= 40: grd = 'E'
            else: grd = 'F'
            
            if att < 60 or grd == 'F': risk, css = "HIGH RISK", "danger"
            elif (60 <= att <= 75) or (grd in ['D', 'E']): risk, css = "MEDIUM RISK", "warning"
            else: risk, css = "LOW RISK", "success"

        new_rec = PredictionHistory(teacher_id=current_user.id, student_roll=roll, attendance=att, 
                                    internal=inter, assignment=assgn, quiz=qz, result=res, risk_level=risk, grade=grd)
        db.session.add(new_rec)
        db.session.commit()

        # Simplified Insight for result page
        insight = f"Primary impact: <b>{['Attendance', 'Internal', 'Assignment', 'Quiz'][np.argmax(importances)]}</b>"
        
        return render_template('result.html', prediction_text=res, risk_level=risk, css_class=css, 
                               grade=grd, total_score=total, student_pcts=student_pcts, insight_text=insight)
    except Exception as e:
        return str(e)

@app.route('/predict_bulk', methods=['POST'])
@login_required
def predict_bulk():
    file = request.files.get('file')
    if file and file.filename.endswith('.csv'):
        try:
            df = pd.read_csv(file)
            # Clean up column names (lowercase and remove spaces)
            df.columns = df.columns.str.strip().str.lower()
            
            records_to_add = []
            
            for _, row in df.iterrows():
                # Extract data from CSV row
                roll = str(row.get('student_roll', 'Bulk-User'))
                att = float(row['attendance'])
                inter = float(row['internal'])
                assgn = float(row['assignment'])
                qz = float(row['quiz'])
                
                # 1. AI Model Prediction
                input_data = np.array([[att, inter, assgn, qz]])
                pred = model.predict(input_data)[0]
                total = inter + assgn + qz
                
                # 2. Advanced Grading & Risk Logic (The Fix)
                if pred == 0:
                    res, risk, grd = "FAIL", "HIGH RISK", "F"
                else:
                    res = "PASS"
                    # Calculate Grade based on Total Score
                    if total >= 90: grd = 'S'
                    elif total >= 80: grd = 'A'
                    elif total >= 70: grd = 'B'
                    elif total >= 60: grd = 'C'
                    elif total >= 50: grd = 'D'
                    elif total >= 40: grd = 'E'
                    else: grd = 'F'
                    
                    # Calculate Risk Level based on Attendance and Grade
                    if att < 60 or grd == 'F':
                        risk = "HIGH RISK"
                    elif (60 <= att <= 75) or (grd in ['D', 'E']):
                        risk = "MEDIUM RISK"
                    else:
                        risk = "LOW RISK"

                # Create the database record
                new_rec = PredictionHistory(
                    teacher_id=current_user.id, 
                    student_roll=roll, 
                    attendance=att, 
                    internal=inter, 
                    assignment=assgn, 
                    quiz=qz, 
                    result=res, 
                    risk_level=risk, 
                    grade=grd
                )
                records_to_add.append(new_rec)
            
            # Batch save for better performance
            db.session.add_all(records_to_add)
            db.session.commit()
            flash(f"Success! Processed {len(records_to_add)} students with full grading logic.", "success")
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "danger")
            return redirect(url_for('predict_form'))
            
    flash("Invalid file format. Please upload a .csv file.", "danger")
    return redirect(url_for('predict_form'))

@app.route('/export')
@login_required
def export_data():
    recs = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()
    df = pd.DataFrame([{ 'Roll': r.student_roll, 'Grade': r.grade, 'Result': r.result } for r in recs])
    return Response(df.to_csv(index=False), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=report.csv"})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='teacher1').first():
            db.session.add(User(username='teacher1', password=generate_password_hash('pass123'), role='teacher'))
            db.session.commit()
    app.run(debug=True)