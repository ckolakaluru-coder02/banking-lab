import os
import psycopg2
import datetime

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables (PostgreSQL syntax)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 1000
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id),
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            description TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insert dummy users only if they don't exist yet
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, balance) VALUES ('admin', 'SuperSecretAdminP@ssw0rd', 1500000)")
        cursor.execute("INSERT INTO users (username, password, balance) VALUES ('student', 'password123', 500)")
        cursor.execute("INSERT INTO users (username, password, balance) VALUES ('johndoe', 'secure55', 3000)")

        now = datetime.datetime.now()

        # Admin transactions
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (1, 'CREDIT', 1500000, 'Initial Corporate Deposit', %s)", ((now - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),))

        # Student transactions
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'CREDIT', 1000, 'Student Loan Disbursement', %s)", ((now - datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'DEBIT', 150, 'University Bookstore', %s)", ((now - datetime.timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S"),))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'DEBIT', 350, 'Campus Housing', %s)", ((now - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),))

        # JohnDoe transactions
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (3, 'CREDIT', 4000, 'Payroll Direct Deposit', %s)", ((now - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),))
        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (3, 'DEBIT', 1000, 'Rent Payment', %s)", ((now - datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),))

    conn.commit()
    conn.close()
    print("PostgreSQL Database initialized successfully.")

if __name__ == '__main__':
    init_db()
