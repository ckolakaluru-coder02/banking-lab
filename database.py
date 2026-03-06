import sqlite3
import datetime

def init_db():
    conn = sqlite3.connect('vulnerable.db')
    cursor = conn.cursor()

    # Drop old tables to reset schema
    cursor.execute('DROP TABLE IF EXISTS users')
    cursor.execute('DROP TABLE IF EXISTS transactions')

    # Create users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            balance INTEGER DEFAULT 1000
        )
    ''')

    # Create transactions table
    cursor.execute('''
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,          -- 'CREDIT' or 'DEBIT'
            amount INTEGER NOT NULL,
            description TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # Insert fake bank users
    cursor.execute("INSERT INTO users (id, username, password, balance) VALUES (1, 'admin', 'SuperSecretAdminP@ssw0rd', 1500000)")
    cursor.execute("INSERT INTO users (id, username, password, balance) VALUES (2, 'student', 'password123', 500)")
    cursor.execute("INSERT INTO users (id, username, password, balance) VALUES (3, 'johndoe', 'secure55', 3000)")

    # Insert fake transactions to prepopulate dashboards
    now = datetime.datetime.now()
    
    # Admin transactions
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (1, 'CREDIT', 1500000, 'Initial Corporate Deposit', ?)", ((now - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),))
    
    # Student transactions
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'CREDIT', 1000, 'Student Loan Disbursement', ?)", ((now - datetime.timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S"),))
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'DEBIT', 150, 'University Bookstore', ?)", ((now - datetime.timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S"),))
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (2, 'DEBIT', 350, 'Campus Housing', ?)", ((now - datetime.timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S"),))

    # JohnDoe transactions
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (3, 'CREDIT', 4000, 'Payroll Direct Deposit', ?)", ((now - datetime.timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),))
    cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (3, 'DEBIT', 1000, 'Rent Payment', ?)", ((now - datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S"),))

    conn.commit()
    conn.close()
    print("Bank Database initialized with transactions successfully.")

if __name__ == '__main__':
    init_db()
