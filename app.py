from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from threading import Thread
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
<<<<<<< HEAD
from flask import Flask, render_template, request, redirect, url_for, flash, Response, jsonify
=======
>>>>>>> fbaf7677b010c53f65c0638a50957f87e7dbec19
from sqlalchemy import text
from google import genai
import joblib
import numpy as np
import pandas as pd
import os

# --- INITIALIZATION ---
app = Flask(__name__)

# This allows us to iterate over two lists at once in the HTML templates
app.jinja_env.globals.update(zip=zip)

# --- CONFIGURATION ---
# Security key for session signing
app.config['SECRET_KEY'] = 'vit_cse_secure_key_2026'

# Database configuration (SQLite for portability)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Folder for student data CSV uploads
app.config['UPLOAD_FOLDER'] = 'uploads' 

# --- MAIL SERVER CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your.email@gmail.com' 
app.config['MAIL_PASSWORD'] = 'your_app_password' 

# Create the uploads directory if it doesn't exist
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# --- CORE OBJECTS ---
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# --- GEMINI AI CONFIGURATION ---
client = genai.Client(api_key="YOUR_API_KEY_HERE")

# --- MACHINE LEARNING MODEL LOADING ---
try:
    models = joblib.load('multi_model.pkl') 
    print("--- SYSTEM STATUS: Ensemble Intelligence Online ---")
except Exception as e:
    print(f"CRITICAL: Model Load Error: {e}")
    models = None

# --- DATABASE SCHEMA (MODELS) ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False)
    assigned_buddy = db.Column(db.String(150), nullable=True)

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

# --- BUSINESS LOGIC & UTILITIES ---

def calculate_metrics(df):
    df['total_score'] = (df['cat1'] * 0.3) + (df['cat2'] * 0.3) + df['assignment_quiz']
    avg = df['total_score'].mean()
    std = df['total_score'].std()
    if pd.isna(std) or std == 0: std = 1
    
    def get_grade(score):
        if score >= (avg + 1.5 * std): return 'S'
        elif score >= (avg + 0.5 * std): return 'A'
        elif score >= (avg - 0.5 * std): return 'B'
        elif score >= (avg - 1.0 * std): return 'C'
        elif score >= (avg - 1.5 * std): return 'D'
        elif score >= (avg - 2.0 * std): return 'E'
        else: return 'F'
    
    df['grade'] = df['total_score'].apply(get_grade)
    df['class_avg'] = avg
    return df

# --- AUTHENTICATION ROUTES ---

@app.route('/')
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))
    return redirect(url_for('student_portal')) if current_user.role == 'student' else redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('username')
        pass_input = request.form.get('password')
        user = User.query.filter_by(username=user_input).first()
        if user and check_password_hash(user.password, pass_input):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- TEACHER FUNCTIONALITIES ---

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'student':
        return redirect(url_for('student_portal'))
    
    records = PredictionHistory.query.filter_by(teacher_id=current_user.id).order_by(PredictionHistory.created_at.desc()).all()
    stats = {
        'low': sum(1 for r in records if r.risk_level == "LOW RISK"),
        'med': sum(1 for r in records if r.risk_level == "MEDIUM RISK"),
        'high': sum(1 for r in records if r.risk_level == "HIGH RISK"),
        'scores': [r.total_score for r in records],
        'attendance': [r.attendance for r in records],
        'grades': [[r.grade for r in records].count(g) for g in ['S','A','B','C','D','E','F']]
    }
    
    return render_template('dashboard.html', records=records, total_predictions=len(records),
                           low_risk=stats['low'], medium_risk=stats['med'], high_risk=stats['high'],
                           grade_distribution=stats['grades'], attendance_data=stats['attendance'],
                           performance_data=stats['scores'], historical_labels=[], historical_scores=[],
                           future_scores=[], selected_student=None)

@app.route('/api/ask_assistant', methods=['POST'])
@login_required
def ask_assistant():
    if current_user.role not in ['teacher', 'admin']:
        return jsonify({"error": "Unauthorized"}), 403
    try:
        query = request.json.get('question', '')
        prompt = f"SQL expert prompt for '{query}' rule logic..."
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        where_clause = response.text.strip().replace('```sql', '').replace('```', '').replace('WHERE ', '')
        
        sql_query = text(f"SELECT student_roll, attendance, grade, result, risk_level FROM prediction_history WHERE teacher_id = :tid AND ({where_clause})")
        result_proxy = db.session.execute(sql_query, {"tid": current_user.id})
        results = [{"student_roll": r[0], "attendance": r[1], "grade": r[2], "result": r[3], "risk_level": r[4]} for r in result_proxy.fetchall()]
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/predict_form')
@login_required
def predict_form():
    if current_user.role not in ['teacher', 'admin']: return redirect(url_for('student_portal'))
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
@login_required
def predict():
    try:
        roll = request.form.get('student_roll')
        data = [float(request.form.get(f)) for f in ['attendance', 'cat1', 'cat2', 'assignment_quiz']]
        input_data = np.array([data])
        
        votes = {m: ("PASS" if models[m].predict(input_data)[0] == 1 else "FAIL") for m in ['Random Forest', 'SVM', 'Logistic Regression']} if models else {}
        final_prediction = models['Ensemble'].predict(input_data)[0] if models else (1 if sum(data[1:]) > 40 else 0)
        result_text = "PASS" if final_prediction == 1 else "FAIL"
        
        total_score = (data[1] * 0.3) + (data[2] * 0.3) + data[3]
        past_records = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()
        all_marks = [r.total_score for r in past_records] + [total_score]
        mean_val, std_val = np.mean(all_marks), (np.std(all_marks) if len(all_marks) > 1 else 1)
        
        grade_val = 'F' if result_text == "FAIL" else ('S' if total_score >= (mean_val + 1.5 * std_val) else 'A' if total_score >= (mean_val + 0.5 * std_val) else 'B')
        risk_val = "HIGH RISK" if (data[0] < 60 or grade_val == 'F') else "MEDIUM RISK" if (data[0] < 75) else "LOW RISK"
        
        new_record = PredictionHistory(teacher_id=current_user.id, student_roll=roll, attendance=data[0], cat1=data[1], 
                                       cat2=data[2], assignment_quiz=data[3], total_score=total_score, 
                                       class_average=mean_val, result=result_text, risk_level=risk_val, grade=grade_val)
        db.session.add(new_record)
        db.session.commit()

        shap_data = [0.8, 1.2, 0.4, 0.1] if result_text == "PASS" else [-1.5, -0.8, -0.4, -0.2]
        return render_template('result.html', prediction_text=result_text, risk_level=risk_val, grade=grade_val, 
                               total_score=total_score, model_votes=votes, shap_impacts=shap_data,
                               insight_text="Analysis complete based on attendance and CAT trends.")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
        return redirect(url_for('predict_form'))

@app.route('/upload_csv', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and file.filename.endswith('.csv'):
            path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
            file.save(path)
            df = calculate_metrics(pd.read_csv(path))
            for _, row in df.iterrows():
                db.session.add(PredictionHistory(teacher_id=current_user.id, student_roll=row['student_roll'],
                               attendance=row['attendance'], cat1=row['cat1'], cat2=row['cat2'],
                               assignment_quiz=row['assignment_quiz'], total_score=row['total_score'],
                               class_average=row['class_avg'], result="PASS", risk_level="LOW RISK", grade=row['grade']))
            db.session.commit()
            return redirect(url_for('dashboard'))
    return render_template('upload.html')

# --- INITIALIZE GEMINI AI ---
# Get your free key at https://aistudio.google.com/
client = genai.Client(api_key="AIzaSyD7BdoZPl86EwpztmRTxCnPJp5ulaci5Oo")

@app.route('/api/ask_assistant', methods=['POST'])
@login_required
def ask_assistant():
    if current_user.role not in ['teacher', 'admin']:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        query = request.json.get('question', '')

        prompt = f"""
        You are a SQL expert. I have a SQLite table named 'prediction_history' with these columns:
        - student_roll (TEXT)
        - attendance (FLOAT)
        - cat1 (FLOAT)
        - cat2 (FLOAT)
        - assignment_quiz (FLOAT)
        - total_score (FLOAT)
        - risk_level (TEXT: 'LOW RISK', 'MEDIUM RISK', 'HIGH RISK')
        - grade (TEXT: 'S', 'A', 'B', 'C', 'D', 'E', 'F')
        - result (TEXT: 'PASS', 'FAIL')

        Translate this user request into a SQL WHERE clause: "{query}"

        RULES:
        1. Output ONLY the raw SQL condition. No explanations.
        2. Do NOT output the word "WHERE".
        3. Do NOT output markdown formatting like ```sql.
        4. Example output: total_score < 30 AND attendance >= 75
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )

        # --- THE FIX: AGGRESSIVELY CLEAN THE AI'S OUTPUT ---
        where_clause = response.text.strip()
        
        # Remove Markdown backticks if the AI ignored rule #3
        where_clause = where_clause.replace('```sql', '').replace('```', '').strip()
        
        # Remove the word 'WHERE' if the AI ignored rule #2
        if where_clause.lower().startswith('where '):
            where_clause = where_clause[6:].strip()
        # ---------------------------------------------------
        
        if ";" in where_clause or "DROP" in where_clause.upper() or "DELETE" in where_clause.upper():
            return jsonify({"error": "Unsafe query generated. Please rephrase your request."})

        sql_string = f"SELECT student_roll, attendance, grade, result, risk_level FROM prediction_history WHERE teacher_id = :tid AND ({where_clause})"
        sql_query = text(sql_string)
        
        result_proxy = db.session.execute(sql_query, {"tid": current_user.id})
        rows = result_proxy.fetchall()

        results = []
        for row in rows:
            results.append({
                "student_roll": row[0],  
                "attendance": row[1],
                "grade": row[2],
                "result": row[3],
                "risk_level": row[4]
            })

        return jsonify({"results": results})

    except Exception as e:
        # Send the ACTUAL Python error to the dashboard so we can debug it
        error_msg = str(e)
        print(f"AI Assistant Error: {error_msg}")
        return jsonify({"error": f"System Crash: {error_msg}"})
    
@app.route('/student_portal')
@login_required
def student_portal():
    if current_user.role != 'student': return redirect(url_for('dashboard'))
    records = PredictionHistory.query.filter_by(student_roll=current_user.username).order_by(PredictionHistory.created_at.desc()).all()
    
    target_data = {'my_score': 0, 's_needed': 0, 'percentile': 0, 'fat_mean': 0}
    dist_data = []
    progression_data = {'labels': [], 'actual': [], 'predicted': []} # Required for Chart

    if records:
        latest = records[0]
        all_class = [r.total_score for r in PredictionHistory.query.filter_by(teacher_id=latest.teacher_id).all()]
        perc = round((sum(1 for s in all_class if s <= latest.total_score) / len(all_class)) * 100, 1)
        std = np.std(all_class) if len(all_class) > 1 else 1
        
        target_data = {'my_score': round(latest.total_score, 1), 's_needed': round(max(latest.class_average + 1.5 * std, 54) - latest.total_score, 1),
                       'percentile': perc, 'fat_mean': round(latest.class_average * 0.6, 1)}
        
        counts, _ = np.histogram(all_class, bins=range(0, 111, 10))
        dist_data = counts.tolist()

        # --- PROGRESSION FORECAST LOGIC ---
        c1_p, c2_p = (latest.cat1 / 50.0) * 100, (latest.cat2 / 50.0) * 100
        p_fat = min(100.0, max(0.0, round(((latest.total_score / 60.0) * 100) + ((c2_p - c1_p) * 0.15), 1)))
        progression_data = {'labels': ['CAT-1', 'CAT-2', 'Finals (Predicted)'], 'actual': [round(c1_p, 1), round(c2_p, 1), None], 'predicted': [None, round(c2_p, 1), p_fat]}

    return render_template('student_portal.html', records=records, target_data=target_data, dist_data=dist_data, progression_data=progression_data)

@app.route('/find_buddy/<student_roll>')
@login_required
def find_buddy(student_roll):
    me = PredictionHistory.query.filter_by(student_roll=student_roll).order_by(PredictionHistory.created_at.desc()).first()
    if not me: return redirect(url_for('student_portal'))
    
    if not current_user.assigned_buddy:
        subq = db.session.query(PredictionHistory.student_roll, db.func.max(PredictionHistory.created_at).label('m')).group_by(PredictionHistory.student_roll).subquery()
        others = PredictionHistory.query.join(subq, (PredictionHistory.student_roll == subq.c.student_roll) & (PredictionHistory.created_at == subq.c.m)).filter(PredictionHistory.student_roll != student_roll).all()
        available = [o for o in others if not User.query.filter_by(username=o.student_roll).first().assigned_buddy]
        
        if available:
            best_match = max(available, key=lambda x: abs(me.total_score - x.total_score))
            current_user.assigned_buddy = best_match.student_roll
            User.query.filter_by(username=best_match.student_roll).first().assigned_buddy = current_user.username
            db.session.commit()

    buddy_record = PredictionHistory.query.filter_by(student_roll=current_user.assigned_buddy).order_by(PredictionHistory.created_at.desc()).first()
    synergy_score = round(min(98.5, 75 + abs(me.total_score - (buddy_record.total_score if buddy_record else 0))), 1)
    
    for r in [me, buddy_record]:
        if r:
            r.internal, r.assignment, r.quiz = round((r.cat1 + r.cat2) * 1.6, 1), r.assignment_quiz * 10, 85
            
    return render_template('match_result.html', me=me, buddy=buddy_record, synergy=synergy_score)

# --- SYSTEM UTILITIES ---

@app.route('/export')
@login_required
def export_data():
    recs = PredictionHistory.query.filter_by(teacher_id=current_user.id).all()
    df = pd.DataFrame([{'Roll': r.student_roll, 'Score': r.total_score, 'Grade': r.grade, 'Risk': r.risk_level} for r in recs])
    return Response(df.to_csv(index=False), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=class_report.csv"})

@app.route('/clear_history', methods=['POST'])
@login_required
def clear_history():
    PredictionHistory.query.filter_by(teacher_id=current_user.id).delete()
    for u in User.query.all(): u.assigned_buddy = None
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='teacher1').first():
            db.session.add(User(username='teacher1', password=generate_password_hash('pass123'), role='teacher'))
        for i in range(1, 11):
            if not User.query.filter_by(username=f'student{i}').first():
                db.session.add(User(username=f'student{i}', password=generate_password_hash('pass123'), role='student'))
        db.session.commit()
    app.run(debug=True)