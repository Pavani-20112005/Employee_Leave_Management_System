from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
from datetime import datetime, date, timedelta
import hashlib
import os
import secrets
from functools import wraps

app = Flask(__name__)
app.secret_key = os.urandom(32)
DB = "employee_leave.db"

# Security constants
SALT_LENGTH = 32
SESSION_TIMEOUT = 3600

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(SALT_LENGTH)
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${hashed}"

def verify_password(password, stored_hash):
    try:
        salt, hash_value = stored_hash.split('$')
        return hash_password(password, salt) == stored_hash
    except:
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        
        last_activity = session.get('last_activity')
        if last_activity:
            try:
                if isinstance(last_activity, str):
                    last_activity = datetime.fromisoformat(last_activity)
                elapsed = (datetime.now() - last_activity).total_seconds()
                if elapsed > SESSION_TIMEOUT:
                    session.clear()
                    flash('Session expired. Please login again.', 'error')
                    return redirect(url_for('login'))
            except:
                session.clear()
                flash('Session expired. Please login again.', 'error')
                return redirect(url_for('login'))
        
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first.', 'error')
            return redirect(url_for('login'))
        if session.get('role') not in ['admin', 'manager']:
            flash('Manager access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def init_db():
    conn = get_db()
    
    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            department TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            reason TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
        )
    """)
    
    # Check if users exist
    count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if count == 0:
        admin_password = hash_password("Admin@123")
        conn.execute(
            "INSERT INTO users(username, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ("admin", "admin@example.com", admin_password, "admin", 1)
        )
        
        manager_password = hash_password("Manager@123")
        conn.execute(
            "INSERT INTO users(username, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ("manager", "manager@example.com", manager_password, "manager", 1)
        )
        
        employee_password = hash_password("Employee@123")
        conn.execute(
            "INSERT INTO users(username, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)",
            ("employee", "employee@example.com", employee_password, "employee", 1)
        )
    
    # Demo employees
    count = conn.execute("SELECT COUNT(*) AS c FROM employees").fetchone()["c"]
    if count == 0:
        conn.executemany(
            "INSERT INTO employees(name, email, department, role) VALUES (?, ?, ?, ?)",
            [
                ("Pavani", "pavani@example.com", "IT", "Software Trainee"),
                ("Rahul", "rahul@example.com", "Finance", "Analyst"),
                ("Anjali", "anjali@example.com", "HR", "HR Executive"),
                ("Priya", "priya@example.com", "Marketing", "Marketing Manager"),
                ("Arjun", "arjun@example.com", "IT", "Senior Developer"),
            ],
        )
    
    # Add sample leave requests for demo
    emp_count = conn.execute("SELECT COUNT(*) AS c FROM leave_requests").fetchone()["c"]
    if emp_count == 0:
        # Get employee IDs
        pavani = conn.execute("SELECT id FROM employees WHERE email='pavani@example.com'").fetchone()
        rahul = conn.execute("SELECT id FROM employees WHERE email='rahul@example.com'").fetchone()
        
        if pavani and rahul:
            # Add some sample leave requests
            conn.execute("""
                INSERT INTO leave_requests(employee_id, leave_type, start_date, end_date, reason, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (pavani['id'], 'Casual', '2026-09-01', '2026-09-02', 'Family event', 'Approved'))
            
            conn.execute("""
                INSERT INTO leave_requests(employee_id, leave_type, start_date, end_date, reason, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (rahul['id'], 'Sick', '2026-09-05', '2026-09-06', 'Doctor appointment', 'Pending'))
    
    conn.commit()
    conn.close()

@app.route("/")
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route("/login", methods=["GET", "POST"])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        
        if not username or not password:
            flash("Please enter both username and password.", "error")
            return render_template("login.html")
        
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND is_active = 1",
            (username,)
        ).fetchone()
        conn.close()
        
        if user and verify_password(password, user["password_hash"]):
            session.clear()
            session['user_id'] = user["id"]
            session['username'] = user["username"]
            session['role'] = user["role"]
            session['last_activity'] = datetime.now().isoformat()
            
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role = request.form.get("role", "employee")
        
        if not all([username, email, password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("register.html")
        
        if len(username) < 3:
            flash("Username must be at least 3 characters.", "error")
            return render_template("register.html")
        
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("register.html")
        
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("register.html")
        
        if not any(c.isupper() for c in password):
            flash("Password must contain at least one uppercase letter.", "error")
            return render_template("register.html")
        if not any(c.islower() for c in password):
            flash("Password must contain at least one lowercase letter.", "error")
            return render_template("register.html")
        if not any(c.isdigit() for c in password):
            flash("Password must contain at least one number.", "error")
            return render_template("register.html")
        
        conn = get_db()
        try:
            existing = conn.execute(
                "SELECT id FROM users WHERE username = ? OR email = ?",
                (username, email)
            ).fetchone()
            if existing:
                flash("Username or email already exists.", "error")
                conn.close()
                return render_template("register.html")
            
            if role == 'admin' and session.get('role') != 'admin':
                flash("Only admins can create admin accounts.", "error")
                conn.close()
                return render_template("register.html")
            
            password_hash = hash_password(password)
            conn.execute(
                "INSERT INTO users(username, email, password_hash, role, is_active) VALUES (?, ?, ?, ?, ?)",
                (username, email, password_hash, role, 1)
            )
            conn.commit()
            conn.close()
            
            flash("Registration successful! Please login.", "success")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username or email already exists.", "error")
            conn.close()
            return render_template("register.html")
    
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    
    # Get employee ID from email
    employee = conn.execute(
        "SELECT id FROM employees WHERE email = ?", 
        (user['email'],)
    ).fetchone()
    
    # Initialize stats
    stats = {}
    recent = []
    
    if session.get('role') in ['admin', 'manager']:
        # MANAGER/ADMIN DASHBOARD - Shows ALL data
        stats = {
            "employees": conn.execute("SELECT COUNT(*) c FROM employees").fetchone()["c"],
            "pending": conn.execute("SELECT COUNT(*) c FROM leave_requests WHERE status='Pending'").fetchone()["c"],
            "approved": conn.execute("SELECT COUNT(*) c FROM leave_requests WHERE status='Approved'").fetchone()["c"],
            "rejected": conn.execute("SELECT COUNT(*) c FROM leave_requests WHERE status='Rejected'").fetchone()["c"],
        }
        recent = conn.execute("""
            SELECT l.id, e.name, l.leave_type, l.start_date, l.end_date, l.status
            FROM leave_requests l
            JOIN employees e ON e.id = l.employee_id
            ORDER BY l.id DESC LIMIT 10
        """).fetchall()
    else:
        # EMPLOYEE DASHBOARD - Shows ONLY their own data
        if employee:
            emp_id = employee['id']
            stats = {
                "total": conn.execute(
                    "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=?", 
                    (emp_id,)
                ).fetchone()["c"],
                "pending": conn.execute(
                    "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=? AND status='Pending'", 
                    (emp_id,)
                ).fetchone()["c"],
                "approved": conn.execute(
                    "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=? AND status='Approved'", 
                    (emp_id,)
                ).fetchone()["c"],
                "rejected": conn.execute(
                    "SELECT COUNT(*) c FROM leave_requests WHERE employee_id=? AND status='Rejected'", 
                    (emp_id,)
                ).fetchone()["c"],
            }
            recent = conn.execute("""
                SELECT l.id, e.name, l.leave_type, l.start_date, l.end_date, l.status
                FROM leave_requests l
                JOIN employees e ON e.id = l.employee_id
                WHERE l.employee_id = ?
                ORDER BY l.id DESC LIMIT 10
            """, (emp_id,)).fetchall()
        else:
            # No employee record found for this user
            stats = {"total": 0, "pending": 0, "approved": 0, "rejected": 0}
            recent = []
    
    conn.close()
    return render_template(
        "dashboard.html", 
        stats=stats, 
        recent=recent, 
        user=session,
        role=session.get('role', 'employee')
    )

@app.route("/employees")
@login_required
@manager_required
def employees():
    q = request.args.get("q", "").strip()
    conn = get_db()
    if q:
        rows = conn.execute("""
            SELECT * FROM employees
            WHERE name LIKE ? OR department LIKE ? OR role LIKE ?
            ORDER BY id DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM employees ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("employees.html", employees=rows, q=q, user=session)

@app.route("/employees/add", methods=["GET", "POST"])
@login_required
@manager_required
def add_employee():
    if request.method == "POST":
        data = (
            request.form["name"].strip(),
            request.form["email"].strip(),
            request.form["department"].strip(),
            request.form["role"].strip(),
        )
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO employees(name,email,department,role) VALUES (?,?,?,?)", data
            )
            conn.commit()
            conn.close()
            flash("Employee added successfully.", "success")
            return redirect(url_for("employees"))
        except sqlite3.IntegrityError:
            flash("Employee with this email already exists.", "error")
            conn.close()
            return redirect(url_for("add_employee"))
    return render_template("employee_form.html", user=session)

@app.route("/employees/delete/<int:employee_id>", methods=["POST"])
@login_required
@admin_required
def delete_employee(employee_id):
    conn = get_db()
    conn.execute("DELETE FROM employees WHERE id=?", (employee_id,))
    conn.commit()
    conn.close()
    flash("Employee deleted successfully.", "success")
    return redirect(url_for("employees"))

@app.route("/leave", methods=["GET", "POST"])
@login_required
def leave():
    conn = get_db()
    
    if request.method == "POST":
        employee_id = request.form["employee_id"]
        leave_type = request.form["leave_type"]
        start_date = request.form["start_date"]
        end_date = request.form["end_date"]
        reason = request.form["reason"].strip()

        if end_date < start_date:
            flash("End date cannot be before start date.", "error")
            conn.close()
            return redirect(url_for("leave"))

        conn.execute("""
            INSERT INTO leave_requests(employee_id, leave_type, start_date, end_date, reason)
            VALUES (?, ?, ?, ?, ?)
        """, (employee_id, leave_type, start_date, end_date, reason))
        conn.commit()
        conn.close()
        flash("Leave request submitted successfully.", "success")
        return redirect(url_for("dashboard"))

    # Show employees based on role
    if session.get('role') in ['admin', 'manager']:
        employee_rows = conn.execute("SELECT id,name FROM employees ORDER BY name").fetchall()
        leave_rows = conn.execute("""
            SELECT l.*, e.name
            FROM leave_requests l JOIN employees e ON e.id=l.employee_id
            ORDER BY l.id DESC
        """).fetchall()
    else:
        # Employee can only request for themselves
        user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
        employee_rows = conn.execute(
            "SELECT id,name FROM employees WHERE email = ? ORDER BY name",
            (user['email'],)
        ).fetchall()
        leave_rows = conn.execute("""
            SELECT l.*, e.name
            FROM leave_requests l JOIN employees e ON e.id=l.employee_id
            WHERE e.email = ?
            ORDER BY l.id DESC
        """, (user['email'],)).fetchall()
    
    conn.close()
    return render_template("leave.html", employees=employee_rows, leaves=leave_rows, today=date.today().isoformat(), user=session)

@app.route("/leave/<int:leave_id>/<action>", methods=["POST"])
@login_required
@manager_required
def update_leave(leave_id, action):
    if action not in ("approve", "reject"):
        return redirect(url_for("leave"))
    status = "Approved" if action == "approve" else "Rejected"
    conn = get_db()
    conn.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, leave_id))
    conn.commit()
    conn.close()
    flash(f"Leave request {status.lower()} successfully.", "success")
    return redirect(url_for("leave"))

@app.route("/profile")
@login_required
def profile():
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
    conn.close()
    return render_template("profile.html", user=user)

@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        if not all([current_password, new_password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("change_password.html")
        
        if new_password != confirm_password:
            flash("New passwords do not match.", "error")
            return render_template("change_password.html")
        
        if len(new_password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template("change_password.html")
        
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE id=?", (session['user_id'],)).fetchone()
        
        if not verify_password(current_password, user["password_hash"]):
            flash("Current password is incorrect.", "error")
            conn.close()
            return render_template("change_password.html")
        
        new_hash = hash_password(new_password)
        conn.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, session['user_id']))
        conn.commit()
        conn.close()
        
        flash("Password changed successfully.", "success")
        return redirect(url_for('profile'))
    
    return render_template("change_password.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)