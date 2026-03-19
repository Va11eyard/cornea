import sqlite3
import hashlib
from datetime import datetime

DB_PATH = "cornea.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'doctor',
            full_name TEXT,
            email TEXT,
            phone TEXT,
            clinic TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tissue_processing_options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            patient_code TEXT,
            clinic TEXT,
            doctor_name TEXT,
            doctor_email TEXT,
            doctor_phone TEXT,
            cornea_count INTEGER NOT NULL,
            min_cell_count INTEGER NOT NULL DEFAULT 2000,
            max_donor_age INTEGER,
            max_days_since_death INTEGER,
            amphoterycin_b TEXT DEFAULT 'Нет',
            tissue_processing TEXT,
            additional_processing TEXT,
            optical_diameter REAL,
            needed_before TEXT,
            is_urgent INTEGER DEFAULT 0,
            comments TEXT,
            status TEXT DEFAULT 'новая',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Create default admin
    admin_exists = c.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()
    if not admin_exists:
        c.execute("""
            INSERT INTO users (username, password_hash, role, full_name)
            VALUES (?, ?, 'admin', 'Администратор')
        """, ('admin', hash_password('admin123')))

    # Default tissue processing options
    opts = c.execute("SELECT COUNT(*) FROM tissue_processing_options").fetchone()[0]
    if opts == 0:
        default_opts = [
            'Стандартная',
            'DSAEK',
            'DMEK',
            'PKP',
            'DALK',
        ]
        for opt in default_opts:
            c.execute("INSERT INTO tissue_processing_options (label) VALUES (?)", (opt,))

    conn.commit()
    conn.close()
