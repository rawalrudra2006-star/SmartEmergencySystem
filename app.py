
from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================================
# APP CONFIGURATION
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "smart-emergency-secret-key-change-this"
)

DATABASE = "emergency.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# CURRENT TIME
# =========================================================

def current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def init_db():

    conn = get_db()

    # USERS TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # EMERGENCIES TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emergencies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emergency_type TEXT NOT NULL,
            description TEXT,
            latitude REAL,
            longitude REAL,
            severity TEXT,
            alert_type TEXT DEFAULT 'REPORT',
            status TEXT DEFAULT 'NEW',
            user_id INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    # ACTIVITY LOG TABLE
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            activity TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            created_at TEXT NOT NULL
        )
    """)

    # DATABASE MIGRATION
    columns = conn.execute(
        "PRAGMA table_info(emergencies)"
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "status" not in column_names:
        conn.execute("""
            ALTER TABLE emergencies
            ADD COLUMN status TEXT DEFAULT 'NEW'
        """)

    if "user_id" not in column_names:
        conn.execute("""
            ALTER TABLE emergencies
            ADD COLUMN user_id INTEGER
        """)

    conn.commit()
    conn.close()


# =========================================================
# ACTIVITY LOGGER
# =========================================================

def log_activity(
    user_id,
    activity,
    latitude=None,
    longitude=None
):

    conn = get_db()

    conn.execute("""
        INSERT INTO activity_logs
        (
            user_id,
            activity,
            latitude,
            longitude,
            created_at
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        user_id,
        activity,
        latitude,
        longitude,
        current_time()
    ))

    conn.commit()
    conn.close()


# =========================================================
# AI SEVERITY CLASSIFICATION
# =========================================================

def classify_severity(
    emergency_type,
    description
):

    emergency_type = str(
        emergency_type or ""
    )

    description = str(
        description or ""
    )

    text = (
        emergency_type + " " + description
    ).lower()

    # CRITICAL
    critical_words = [
        "death",
        "dead",
        "unconscious",
        "not breathing",
        "massive bleeding",
        "building collapse",
        "people trapped",
        "major fire",
        "explosion",
        "critical",
        "dying"
    ]

    for word in critical_words:
        if word in text:
            return "CRITICAL"

    # HIGH
    high_words = [
        "fire",
        "accident",
        "bleeding",
        "injury",
        "heart attack",
        "stroke",
        "severe pain",
        "burn",
        "serious injury"
    ]

    for word in high_words:
        if word in text:
            return "HIGH"

    # MEDIUM
    medium_words = [
        "hurt",
        "pain",
        "minor accident",
        "fever",
        "small injury",
        "minor"
    ]

    for word in medium_words:
        if word in text:
            return "MEDIUM"

    # DEFAULT BASED ON TYPE
    if emergency_type in [
        "Fire",
        "Accident",
        "Medical"
    ]:
        return "HIGH"

    return "LOW"


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# REGISTER PAGE
# =========================================================

@app.route("/register")
def register():
    return render_template("register.html")


# =========================================================
# REGISTER USER
# =========================================================

@app.route("/register", methods=["POST"])
def register_user():

    data = request.get_json(silent=True) or {}

    name = str(
        data.get("name", "")
    ).strip()

    email = str(
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    # VALIDATION

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "All fields are required."
        }), 400

    if len(name) < 2:
        return jsonify({
            "success": False,
            "message": "Name must contain at least 2 characters."
        }), 400

    if "@" not in email:
        return jsonify({
            "success": False,
            "message": "Please enter a valid email address."
        }), 400

    if len(password) < 6:
        return jsonify({
            "success": False,
            "message": "Password must be at least 6 characters."
        }), 400

    password_hash = generate_password_hash(password)

    conn = get_db()

    try:

        cursor = conn.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                created_at
            )
            VALUES (?, ?, ?, ?)
        """, (
            name,
            email,
            password_hash,
            current_time()
        ))

        conn.commit()

        user_id = cursor.lastrowid

        conn.close()

        return jsonify({
            "success": True,
            "message": "Registration successful.",
            "user_id": user_id
        })

    except sqlite3.IntegrityError:

        conn.close()

        return jsonify({
            "success": False,
            "message": "This email is already registered."
        }), 409


# =========================================================
# LOGIN PAGE
# =========================================================

@app.route("/login")
def login():
    return render_template("login.html")


# =========================================================
# LOGIN USER
# =========================================================

@app.route("/login", methods=["POST"])
def login_user():

    data = request.get_json(silent=True) or {}

    email = str(
        data.get("email", "")
    ).strip().lower()

    password = str(
        data.get("password", "")
    )

    if not email or not password:
        return jsonify({
            "success": False,
            "message": "Email and password are required."
        }), 400

    conn = get_db()

    user = conn.execute("""
        SELECT *
        FROM users
        WHERE email = ?
    """, (
        email,
    )).fetchone()

    conn.close()

    if not user:
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    if not check_password_hash(
        user["password"],
        password
    ):
        return jsonify({
            "success": False,
            "message": "Invalid email or password."
        }), 401

    # CREATE SESSION

    session.clear()

    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]

    # ACTIVITY

    log_activity(
        user["id"],
        "LOGIN"
    )

    return jsonify({
        "success": True,
        "message": "Login successful.",
        "redirect": "/dashboard"
    })


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    user_id = session.get("user_id")

    if user_id:
        log_activity(
            user_id,
            "LOGOUT"
        )

    session.clear()

    return redirect("/login")


# =========================================================
# USER DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        user_email=session.get("user_email")
    )


# =========================================================
# NORMAL EMERGENCY REPORT
# =========================================================

@app.route("/report", methods=["POST"])
def report_emergency():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    emergency_type = str(
        data.get("emergency_type", "")
    ).strip()

    description = str(
        data.get("description", "")
    ).strip()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    user_id = session.get("user_id")

    if not emergency_type:
        return jsonify({
            "success": False,
            "message": "Emergency type is required."
        }), 400

    if not description:
        return jsonify({
            "success": False,
            "message": "Please describe the emergency."
        }), 400

    severity = classify_severity(
        emergency_type,
        description
    )

    conn = get_db()

    conn.execute("""
        INSERT INTO emergencies
        (
            emergency_type,
            description,
            latitude,
            longitude,
            severity,
            alert_type,
            status,
            user_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        emergency_type,
        description,
        latitude,
        longitude,
        severity,
        "REPORT",
        "NEW",
        user_id,
        current_time()
    ))

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "EMERGENCY_REPORT",
        latitude,
        longitude
    )

    return jsonify({
        "success": True,
        "message": "Emergency report saved successfully.",
        "severity": severity,
        "status": "NEW"
    })


# =========================================================
# SOS ALERT
# =========================================================

@app.route("/sos", methods=["POST"])
def sos_alert():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    data = request.get_json(silent=True) or {}

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    user_id = session.get("user_id")

    conn = get_db()

    conn.execute("""
        INSERT INTO emergencies
        (
            emergency_type,
            description,
            latitude,
            longitude,
            severity,
            alert_type,
            status,
            user_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "SOS",
        "Emergency SOS Alert",
        latitude,
        longitude,
        "CRITICAL",
        "SOS",
        "NEW",
        user_id,
        current_time()
    ))

    conn.commit()
    conn.close()

    log_activity(
        user_id,
        "SOS",
        latitude,
        longitude
    )

    return jsonify({
        "success": True,
        "message": "SOS alert saved successfully.",
        "severity": "CRITICAL",
        "status": "NEW"
    })


# =========================================================
# USER EMERGENCY HISTORY
# =========================================================

@app.route("/my_emergencies")
def my_emergencies():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    user_id = session.get("user_id")

    conn = get_db()

    emergencies = conn.execute("""
        SELECT *
        FROM emergencies
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        user_id,
    )).fetchall()

    conn.close()

    result = []

    for emergency in emergencies:

        result.append({
            "id": emergency["id"],
            "emergency_type": emergency["emergency_type"],
            "description": emergency["description"],
            "latitude": emergency["latitude"],
            "longitude": emergency["longitude"],
            "severity": emergency["severity"],
            "alert_type": emergency["alert_type"],
            "status": emergency["status"],
            "created_at": emergency["created_at"]
        })

    return jsonify({
        "success": True,
        "emergencies": result
    })


# =========================================================
# USER ACTIVITY HISTORY
# =========================================================

@app.route("/my_activity")
def my_activity():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Please login first."
        }), 401

    user_id = session.get("user_id")

    conn = get_db()

    activities = conn.execute("""
        SELECT *
        FROM activity_logs
        WHERE user_id = ?
        ORDER BY id DESC
    """, (
        user_id,
    )).fetchall()

    conn.close()

    result = []

    for activity in activities:

        result.append({
            "activity": activity["activity"],
            "latitude": activity["latitude"],
            "longitude": activity["longitude"],
            "created_at": activity["created_at"]
        })

    return jsonify({
        "success": True,
        "activities": result
    })


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin")
def admin():

    conn = get_db()

    emergencies = conn.execute("""
        SELECT
            emergencies.*,
            users.name AS user_name,
            users.email AS user_email
        FROM emergencies
        LEFT JOIN users
        ON emergencies.user_id = users.id
        ORDER BY emergencies.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        emergencies=emergencies
    )


# =========================================================
# ADMIN ACTIVITY LOG
# =========================================================

@app.route("/admin/activity")
def admin_activity():

    conn = get_db()

    activities = conn.execute("""
        SELECT
            activity_logs.*,
            users.name AS user_name,
            users.email AS user_email
        FROM activity_logs
        LEFT JOIN users
        ON activity_logs.user_id = users.id
        ORDER BY activity_logs.id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "activity.html",
        activities=activities
    )


# =========================================================
# UPDATE EMERGENCY STATUS
# =========================================================

@app.route("/update_status", methods=["POST"])
def update_status():

    data = request.get_json(silent=True) or {}

    emergency_id = data.get("id")

    status = str(
        data.get("status", "")
    ).strip()

    allowed_statuses = [
        "NEW",
        "IN PROGRESS",
        "RESOLVED"
    ]

    if not emergency_id:
        return jsonify({
            "success": False,
            "message": "Emergency ID is required."
        }), 400

    if status not in allowed_statuses:
        return jsonify({
            "success": False,
            "message": "Invalid status."
        }), 400

    conn = get_db()

    emergency = conn.execute("""
        SELECT id
        FROM emergencies
        WHERE id = ?
    """, (
        emergency_id,
    )).fetchone()

    if not emergency:

        conn.close()

        return jsonify({
            "success": False,
            "message": "Emergency not found."
        }), 404

    conn.execute("""
        UPDATE emergencies
        SET status = ?
        WHERE id = ?
    """, (
        status,
        emergency_id
    ))

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Emergency status updated.",
        "status": status
    })


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    init_db()

    app.run(
        debug=True
    )

