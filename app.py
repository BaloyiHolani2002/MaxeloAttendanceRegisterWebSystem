from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime, timedelta, date
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


# --- Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']  # radio button choice

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, names, surname, email, role 
            FROM MaxeloClientTable 
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

            # --- Redirect rules ---
            if user_type == "admin" and session['role'] == "admin":
                return redirect(url_for('admin_dashboard'))
            elif user_type == "employee" and session['role'] == "employee":
                return redirect(url_for('employee_dashboard'))
            elif user_type == "employee" and session['role'] == "admin":
                # Admin logging in as employee
                return redirect(url_for('employee_dashboard'))
            else:
                flash("Role mismatch: you selected the wrong login option.", "error")
                return redirect(url_for('login'))
        else:
            flash("Invalid email or password", "error")
            return redirect(url_for('login'))

    return render_template('login.html')


# --- Reset Password ---
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user_id = request.form.get('user_id')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM MaxeloClientTable WHERE id = %s AND email = %s", (user_id, email))
        user = cur.fetchone()

        if user:
            # redirect to reset page form
            cur.close()
            conn.close()
            session['reset_user_id'] = user_id
            return redirect(url_for('reset_password_form'))
        else:
            flash("User ID and Email do not match.", "error")
            cur.close()
            conn.close()
            return redirect(url_for('reset_password'))

    return render_template('reset_password.html')


# --- Reset Password Form ---
@app.route('/reset_password_form', methods=['GET', 'POST'])
def reset_password_form():
    if 'reset_user_id' not in session:
        flash("Please verify your account first.", "error")
        return redirect(url_for('reset_password'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        user_id = session['reset_user_id']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE MaxeloClientTable SET password = %s WHERE id = %s", (new_password, user_id))
        conn.commit()
        cur.close()
        conn.close()

        session.pop('reset_user_id', None)
        flash("Password reset successful!", "success")
        return redirect(url_for('reset_password_successful'))

    return render_template('reset_password_form.html')


# --- Reset Password Successful ---
@app.route('/reset_password_successful')
def reset_password_successful():
    return render_template('reset_password_successful.html')


# --- Admin Dashboard ---
@app.route('/dashboard/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM MaxeloClientTable WHERE role='employee'")
    employee_count = cur.fetchone()[0]
    cur.close()
    conn.close()

    return render_template("admin_dashboard.html",
                           employee_count=employee_count,
                           present_today=0,
                           absent_today=employee_count,
                           current_user={
                               "id": session['user_id'],
                               "full_name": f"{session['user_name']} {session['user_surname']}",
                               "email": session['email'],
                               "last_login": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                           })

# --- Add Employee ---
@app.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    # Check if admin is logged in
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as admin to access this page.', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Get form data
        names = request.form.get('names', '').strip()
        surname = request.form.get('surname', '').strip()
        phone = request.form.get('phoneNumber', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role', 'employee').strip()
        position = request.form.get('position', '').strip()

        if not all([names, surname, email, password, role]):
            flash('Please fill in all required fields.', 'error')
            return redirect(url_for('add_employee'))

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Insert employee
            cur.execute(
                """
                INSERT INTO MaxeloClientTable
                (names, surname, phoneNumber, email, password, role, position)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (names, surname, phone, email, password, role, position)
            )
            conn.commit()
            flash('Employee added successfully!', 'success')
            return redirect(url_for('added_employee_successful'))
        except Exception as e:
            conn.rollback()
            flash('Database error occurred. Please try again.', 'error')
            print(f"Database error: {e}")
        finally:
            cur.close()
            conn.close()

    # GET request renders the add employee form
    return render_template('add_employee.html')


# --- Success Page ---
@app.route('/added-employee-successful')
def added_employee_successful():
    # Check if admin is logged in
    if 'user_id' not in session or session.get('role') != 'admin':
        flash('Please log in as admin to access this page.', 'error')
        return redirect(url_for('login'))

    return render_template('added_employee_successful.html')

# --- Employee Dashboard ---
@app.route('/dashboard/employee')
def employee_dashboard():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # fetch user
    cur.execute("SELECT id, names, surname, email, phoneNumber, role, position FROM MaxeloClientTable WHERE id = %s",
                (session['user_id'],))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        flash("User not found", "danger")
        return redirect(url_for('login'))

    user = {
        "id": row[0],
        "name": row[1],
        "surname": row[2],
        "email": row[3],
        "phoneNumber": row[4],
        "role": row[5],
        "position": row[6]
    }

    # fetch today's attendance
    today_str = date.today().strftime("%Y-%m-%d")
    cur.execute("""
        SELECT clockIn, clockOut, notes
        FROM AttendanceRegister
        WHERE employee_id = %s AND DATE(clockIn) = %s
        ORDER BY id DESC LIMIT 1
    """, (user["id"], today_str))
    attendance = cur.fetchone()

    cur.close()
    conn.close()

    return render_template(
        "employee_dashboard.html",
        user=user,
        today=today_str,
        clock_in_time=attendance[0] if attendance else None,
        clock_out_time=attendance[1] if attendance else None,
        attendance_type=attendance[2] if attendance else None
    )


# --- Clock In ---
@app.route('/clock_in', methods=['POST'])
def clock_in():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    attendance_type = request.form.get("attendanceType")
    notes = request.form.get("notes")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO AttendanceRegister (employee_id, clockIn, notes)
        VALUES (%s, %s, %s)
    """, (session['user_id'], datetime.now(), attendance_type or notes))
    conn.commit()
    cur.close()
    conn.close()

    flash("Clocked in successfully!", "success")
    return redirect(url_for('employee_dashboard'))

# --- Clock Out ---
@app.route('/clock_out', methods=['POST'])
def clock_out():
    if 'user_id' not in session:
        flash("Please log in first", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()

    # Get latest clocked-in record without clockOut
    cur.execute("""
        SELECT id FROM AttendanceRegister
        WHERE employee_id = %s AND clockOut IS NULL
        ORDER BY clockIn DESC LIMIT 1
    """, (session['user_id'],))
    row = cur.fetchone()

    if row:
        attendance_id = row[0]
        cur.execute("""
            UPDATE AttendanceRegister
            SET clockOut = %s
            WHERE id = %s
        """, (datetime.now(), attendance_id))
        conn.commit()
        flash("Clocked out successfully!", "success")
    else:
        flash("No active clock-in found for today.", "warning")

    cur.close()
    conn.close()
    return redirect(url_for('employee_dashboard'))

# --- View Employees ---
@app.route('/view_employees')
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


# --- Employee Register Page ---
@app.route('/register')
def view_register():
    if 'user_id' not in session:
        flash("Please log in first.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    # Fetch attendance and employee role
    cur.execute("""
        SELECT a.id, e.names, e.surname, e.role, a.clockIn, a.clockOut, a.notes
        FROM AttendanceRegister a
        JOIN MaxeloClientTable e ON a.employee_id = e.id
        ORDER BY a.clockIn DESC
    """)
    attendance_records = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('view_employee_register.html', attendance_records=attendance_records)


# --- Edit Employee ---
@app.route('/edit_employee/<int:employee_id>', methods=['GET', 'POST'])
def edit_employee(employee_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Please log in as admin to access this page.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        names = request.form['names']
        surname = request.form['surname']
        phone = request.form['phoneNumber']
        email = request.form['email']
        role = request.form['role']
        position = request.form.get('position', '')

        cur.execute("""
            UPDATE MaxeloClientTable
            SET names=%s, surname=%s, phoneNumber=%s, email=%s, role=%s, position=%s
            WHERE id=%s
        """, (names, surname, phone, email, role, position, employee_id))
        conn.commit()
        cur.close()
        conn.close()
        flash("Employee updated successfully!", "success")
        return redirect(url_for('view_employees'))

    cur.execute("SELECT id, names, surname, email, phoneNumber, role, position FROM MaxeloClientTable WHERE id=%s", (employee_id,))
    emp = cur.fetchone()
    cur.close()
    conn.close()
    if not emp:
        flash("Employee not found.", "error")
        return redirect(url_for('view_employees'))

    employee = {
        "id": emp[0],
        "names": emp[1],
        "surname": emp[2],
        "email": emp[3],
        "phoneNumber": emp[4],
        "role": emp[5],
        "position": emp[6]
    }

    return render_template("edit_employee.html", employee=employee)


# --- Delete Employee ---
@app.route('/delete_employee/<int:employee_id>', methods=['GET'])
def delete_employee(employee_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Please log in as admin to access this page.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM MaxeloClientTable WHERE id=%s", (employee_id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Employee deleted successfully!", "success")
    return redirect(url_for('view_employees'))


# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)
