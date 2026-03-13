from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import joblib
import numpy as np
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_key_change_in_production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Load the trained Machine Learning model
try:
    model = joblib.load('student_model.pkl')
except FileNotFoundError:
    print("Error: Model file 'student_model.pkl' not found. Run model_trainer.py first.")
    model = None

# --- DATABASE MODELS ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False) # 'admin', 'teacher', 'student'

class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    attendance = db.Column(db.Float)
    internal = db.Column(db.Float)
    assignment = db.Column(db.Float)
    quiz = db.Column(db.Float)
    result = db.Column(db.String(50))
    risk_level = db.Column(db.String(50))
    grade = db.Column(db.String(5)) # <-- NEW COLUMN ADDED HERE

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES ---

@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'teacher' or current_user.role == 'admin':
            return redirect(url_for('dashboard'))
        return redirect(url_for('predict_form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role in ['teacher', 'admin']:
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('predict_form'))
        else:
            flash('Login Failed. Please check your username and password.', 'danger')
            
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
        flash("Access Denied. Teachers only.", "danger")
        return redirect(url_for('predict_form'))
        
    records = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()
    
    low_risk = sum(1 for r in records if r.risk_level == "LOW RISK")
    high_risk = sum(1 for r in records if r.risk_level == "HIGH RISK")
    
    attendance_data = [r.attendance for r in records]
    performance_data = [(r.internal + r.assignment + r.quiz) for r in records]

    return render_template('dashboard.html', 
                           low_risk=low_risk, 
                           high_risk=high_risk,
                           attendance_data=attendance_data,
                           performance_data=performance_data,
                           total_predictions=len(records),
                           records=records)

@app.route('/predict_form')
@login_required
def predict_form():
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    if request.method == 'POST':
        try:
            attendance = float(request.form['attendance'])
            internal = float(request.form['internal'])
            assignment = float(request.form['assignment'])
            quiz = float(request.form['quiz'])

            # 1. ML Prediction for Risk (Pass/Fail)
            input_data = np.array([[attendance, internal, assignment, quiz]])
            prediction = model.predict(input_data)[0]

            if prediction == 1:
                result_text = "PASS"
                risk_level = "LOW RISK"
                css_class = "success"
            else:
                result_text = "FAIL"
                risk_level = "HIGH RISK"
                css_class = "danger"

            # 2. Calculate Total Marks & Assign Grade based on your scale
            total_score = internal + assignment + quiz
            
            if total_score >= 90: grade = 'S'
            elif total_score >= 80: grade = 'A'
            elif total_score >= 70: grade = 'B'
            elif total_score >= 60: grade = 'C'
            elif total_score >= 50: grade = 'D'
            elif total_score >= 40: grade = 'E'
            else: grade = 'F'

            # 3. Save to Database
            new_record = PredictionHistory(
                teacher_id=current_user.id,
                attendance=attendance,
                internal=internal,
                assignment=assignment,
                quiz=quiz,
                result=result_text,
                risk_level=risk_level,
                grade=grade # <-- SAVING THE GRADE
            )
            db.session.add(new_record)
            db.session.commit()

            return render_template('result.html', 
                                   prediction_text=result_text, 
                                   risk_level=risk_level,
                                   css_class=css_class,
                                   grade=grade,          # <-- PASSING GRADE TO TEMPLATE
                                   total_score=total_score) 
                                   
        except Exception as e:
            return f"An error occurred: {str(e)}"

# --- AUTO-SETUP DATABASE ---
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='teacher1').first():
        admin = User(username='admin', password=generate_password_hash('admin123'), role='admin')
        teacher1 = User(username='teacher1', password=generate_password_hash('pass123'), role='teacher')
        student1 = User(username='student1', password=generate_password_hash('student123'), role='student')

        db.session.add(admin)
        db.session.add(teacher1)
        db.session.add(student1)
        db.session.commit()
        print("✅ Database created and default users added successfully!")

if __name__ == "__main__":
    app.run(debug=True)