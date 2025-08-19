import sqlite3, os
from datetime import datetime

# Single connection shared across the backend
_DB_PATH = os.getenv('WHERESMYJOBAT_DB_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'wheresmyjobat.db'))
conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, created_at TEXT)')
cursor.execute('''CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    company TEXT,
    position TEXT,
    stage TEXT,
    date_added TEXT,
    UNIQUE(user_id, company, position)
)''')
conn.commit()


def ensure_user(email: str) -> int:
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute('INSERT INTO users (email, created_at) VALUES (?, ?)', (email, datetime.now().isoformat()))
    conn.commit()
    print(f"✅ New user {email} added to DB")
    return cursor.lastrowid


def get_user_applications(user_id: int):
    cursor.execute('SELECT id, company, position, stage, date_added FROM applications WHERE user_id = ?', (user_id,))
    return [
        {"id": r[0], "company": r[1], "position": r[2], "stage": r[3], "date_added": r[4]}
        for r in cursor.fetchall()
    ]


def save_application(user_id: int, company: str, position: str, stage: str):
    cursor.execute(
        'SELECT id, stage FROM applications WHERE user_id = ? AND lower(company) = lower(?) AND lower(position) = lower(?)',
        (user_id, company, position),
    )
    row = cursor.fetchone()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if row:
        if stage != row[1]:
            cursor.execute('UPDATE applications SET stage = ?, date_added = ? WHERE id = ?', (stage, now, row[0]))
            conn.commit()
    else:
        cursor.execute(
            'INSERT INTO applications (user_id, company, position, stage, date_added) VALUES (?, ?, ?, ?, ?)',
            (user_id, company, position, stage, now),
        )
        conn.commit()
        print('✅ New application saved to DB') 