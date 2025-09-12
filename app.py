from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta
import psycopg2
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)

# --- Database connection ---
def get_db_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        DATABASE_URL = "postgresql://postgres:Maxelo%402023@localhost:5432/maxelo_attendance_db"
    return psycopg2.connect(DATABASE_URL)

# --- Index page ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Login (dummy admin login) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT id, names, surname, email, role FROM MaxeloClientTable WHERE email=%s AND password=%s",
                    (email, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['user_surname'] = user[2]
            session['email'] = user[3]
            session['role'] = user[4]
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# --- Admin Dashboard ---
@app.route('/dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Get total employees
    cur.execute("SELECT COUNT(*) FROM MaxeloClientTable")
    employee_count = cur.fetchone()[0]

    # Dummy present/absent (for now until attendance table is linked)
    present_today = 0
    absent_today = employee_count

    cur.close()
    conn.close()

    current_user = {
        "id": session['user_id'],
        "full_name": f"{session['user_name']} {session['user_surname']}",
        "email": session['email'],
        "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    return render_template(
        "admin_dashboard.html",
        employee_count=employee_count,
        present_today=present_today,
        absent_today=absent_today,
        current_user=current_user
    )

# --- View Employees ---
@app.route('/employees')
def view_employees():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, names, surname, email, role, position FROM MaxeloClientTable ORDER BY id ASC")
    employees = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("view_employees.html", employees=employees)

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

# --- Dummy Register Page ---
@app.route('/register')
def view_register():
    return "<h2>Employee Register page coming soon...</h2>"

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
