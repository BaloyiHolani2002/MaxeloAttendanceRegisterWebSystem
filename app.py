from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta, date
import pytz
import psycopg2
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=7)

# --- Database connection ---
def get_db_connection():
    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:
        # Running on Render or remote
        if "sslmode" not in DATABASE_URL:
            DATABASE_URL += "?sslmode=require"
    else:
        # Local development
        DATABASE_URL = "postgresql://postgres:Maxelov%402023@localhost:5432/maxelo_attendance_db"

    return psycopg2.connect(DATABASE_URL)

# --- Database initialization ---
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Create MaxeloClientTable
        cur.execute("""
            CREATE TABLE IF NOT EXISTS maxeloclienttable (
                id BIGSERIAL PRIMARY KEY,
                names VARCHAR(100) NOT NULL,
                surname VARCHAR(100) NOT NULL,
                phonenumber VARCHAR(20) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                role VARCHAR(50) NOT NULL,
                position VARCHAR(50)
            )
        """)

        # Create AttendanceRegister
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendanceregister (
                id BIGSERIAL PRIMARY KEY,
                employee_id BIGINT NOT NULL REFERENCES maxeloclienttable(id) ON DELETE CASCADE,
                clockin TIMESTAMP,
                clockout TIMESTAMP,
                notes TEXT
            )
        """)

        # Insert default admin if not exists
        cur.execute("SELECT id FROM maxeloclienttable WHERE email = 'admin@maxelo.com'")
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO maxeloclienttable (names, surname, phonenumber, password, email, role, position)
                VALUES ('System', 'Admin', '0820000000', 'admin123', 'admin@maxelo.com', 'admin', 'Manager')
            """)

        conn.commit()
        cur.close()
        conn.close()
        print("Database initialized successfully.")

    except Exception as e:
        print(f"Error initializing database: {e}")

# Initialize DB on app start
init_db()

# --- Index ---
@app.route('/')
def index():
    return render_template('index.html')

# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT id, names, surname, email, role
                FROM maxeloclienttable
                WHERE email=%s AND password=%s
            """, (email, password))
            user = cur.fetchone()
            cur.close()
            conn.close()

            if user:
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['user_surname'] = user[2]
                session['email'] = user[3]
                session['role'] = user[4].lower()

                flash("Login successful!", "success")

                if user_type == "admin" and session['role'] == "admin":
                    return redirect(url_for('admin_dashboard'))
                elif user_type == "employee" and session['role'] in ["employee", "intern", "admin"]:
                    return redirect(url_for('employee_dashboard'))
                else:
                    flash("Role mismatch: wrong login option.", "error")
                    return redirect(url_for('login'))
            else:
                flash("Invalid email or password", "error")
                return redirect(url_for('login'))

        except Exception as e:
            flash(f"Database error: {str(e)}", "error")
            return redirect(url_for('login'))

    return render_template('login.html')

# --- Admin Dashboard ---
@app.route('/dashboard/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('login'))

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Total employees
        cur.execute("""
            SELECT COUNT(*) FROM maxeloclienttable WHERE role IN ('employee', 'intern', 'admin')
        """)
        employee_count = cur.fetchone()[0]

        # Present today
        today = datetime.now().date()
        cur.execute("""
            SELECT COUNT(*) FROM attendanceregister a
            JOIN maxeloclienttable e ON a.employee_id = e.id
            WHERE DATE(a.clockin) = %s AND e.role IN ('employee', 'intern', 'admin')
        """, (today,))
        present_count = cur.fetchone()[0]

        cur.close()
        conn.close()

        return render_template(
            "admin_dashboard.html",
            employee_count=employee_count,
            present_today=present_count,
            absent_today=employee_count - present_count,
            current_user={
                "id": session['user_id'],
                "full_name": f"{session['user_name']} {session['user_surname']}",
                "email": session['email'],
                "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        )
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('login'))

# --- Employee Dashboard ---
@app.route("/dashboard/employee")
def employee_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()

        # User info
        cur.execute("""
            SELECT names, surname, email, phonenumber, role, position
            FROM maxeloclienttable
            WHERE id=%s
        """, (user_id,))
        user = cur.fetchone()

        # Today's attendance
        cur.execute("""
            SELECT clockin, clockout, notes
            FROM attendanceregister
            WHERE employee_id=%s AND DATE(clockin) = CURRENT_DATE
            ORDER BY clockin DESC LIMIT 1
        """, (user_id,))
        today_attendance = cur.fetchone()

        # Current month attendance
        cur.execute("""
            SELECT DATE(clockin), clockin, clockout, notes
            FROM attendanceregister
            WHERE employee_id=%s AND DATE_TRUNC('month', clockin) = DATE_TRUNC('month', CURRENT_DATE)
            ORDER BY clockin DESC
        """, (user_id,))
        attendance_records = cur.fetchall()

        cur.close()
        conn.close()

        return render_template(
            "employee_dashboard.html",
            user={
                "name": user[0],
                "surname": user[1],
                "email": user[2],
                "phoneNumber": user[3],
                "role": user[4],
                "position": user[5],
            },
            today=date.today(),
            clock_in_time=today_attendance[0] if today_attendance else None,
            clock_out_time=today_attendance[1] if today_attendance else None,
            attendance_type=today_attendance[2] if today_attendance else None,
            attendance_records=[
                {"date": rec[0], "clock_in": rec[1], "clock_out": rec[2], "notes": rec[3]}
                for rec in attendance_records
            ],
            month_name=date.today().strftime("%B")
        )

    except Exception as e:
        flash(f"Database error: {str(e)}", "error")
        return redirect(url_for('login'))

# --- Clock In ---
@app.route('/clock_in', methods=['POST'])
def clock_in():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    attendance_type = request.form.get("attendanceType", "")
    note_text = request.form.get("notes", "")
    combined_notes = f"({attendance_type}) {note_text}".strip()
    sa_time = datetime.now(pytz.timezone("Africa/Johannesburg"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO attendanceregister (employee_id, clockin, notes)
            VALUES (%s, %s, %s)
        """, (session['user_id'], sa_time, combined_notes))
        conn.commit()
        cur.close()
        conn.close()
        flash("Clocked in successfully!", "success")
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")

    return redirect(url_for('employee_dashboard'))

# --- Clock Out ---
@app.route('/clock_out', methods=['POST'])
def clock_out():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    sa_time = datetime.now(pytz.timezone("Africa/Johannesburg"))

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id FROM attendanceregister
            WHERE employee_id=%s AND clockout IS NULL
            ORDER BY clockin DESC LIMIT 1
        """, (session['user_id'],))
        row = cur.fetchone()
        if row:
            attendance_id = row[0]
            cur.execute("UPDATE attendanceregister SET clockout=%s WHERE id=%s", (sa_time, attendance_id))
            conn.commit()
            flash("Clocked out successfully!", "success")
        else:
            flash("No active clock-in found for today.", "warning")
        cur.close()
        conn.close()
    except Exception as e:
        flash(f"Database error: {str(e)}", "error")

    return redirect(url_for('employee_dashboard'))

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
