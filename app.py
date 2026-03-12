from flask import Flask, request, render_template, redirect, url_for, session, make_response
import os
import datetime
import sqlite3

# Try to import psycopg2 for production (PostgreSQL)
try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

app = Flask(__name__)
app.secret_key = "secure_trust_bank_key"

# Admin credentials (change this to your own secret password)
ADMIN_PASSWORD = "adminbank"

DATABASE_URL = os.environ.get('DATABASE_URL')
USE_POSTGRES = bool(DATABASE_URL) and HAS_PSYCOPG2

# SQLite database file path (for local development)
SQLITE_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bank.db')


def get_db_connection():
    if USE_POSTGRES:
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except psycopg2.Error as e:
            print(f"PostgreSQL connection error: {e}")
            raise
    else:
        conn = sqlite3.connect(SQLITE_DB)
        conn.row_factory = sqlite3.Row
        return conn


def db_execute(cursor, query, params=None):
    """Execute a query, handling placeholder differences between SQLite and PostgreSQL."""
    if not USE_POSTGRES:
        # Convert PostgreSQL %s placeholders to SQLite ? placeholders
        query = query.replace('%s', '?')
    if params:
        cursor.execute(query, params)
    else:
        cursor.execute(query)
    return cursor


def init_sqlite_db():
    """Create tables in SQLite for local development."""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            balance REAL DEFAULT 1000
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            timestamp TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()


def init_postgres_db():
    """Create tables and seed data in PostgreSQL for production."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                balance REAL DEFAULT 1000
            )
        ''')
        
        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                timestamp TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        conn.commit()
        
        # Check if we need to seed data
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        if user_count == 0:
            # Seed default users
            cursor.execute("INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)", 
                          ('admin', 'SuperSecretAdminP@ssw0rd', 1500000))
            cursor.execute("INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)", 
                          ('student', 'password123', 500))
            cursor.execute("INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)", 
                          ('johndoe', 'secure55', 3000))
            conn.commit()
        
        conn.close()
        print("  * PostgreSQL database initialized successfully")
    except Exception as e:
        print(f"  * Error initializing PostgreSQL database: {e}")


# Initialize database on startup
if not USE_POSTGRES:
    init_sqlite_db()
    print("  * Running with SQLite (local development mode)")
    print(f"  * Database file: {SQLITE_DB}")
else:
    init_postgres_db()
    print("  * Running with PostgreSQL (production mode)")


@app.route('/')
def index():
    return render_template('index.html')


# 1. SQL Injection (Login Bypass) & Insecure "Remember Me"
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Auto-login if "Remember Me" cookies exist
    if 'user_id' not in session and request.cookies.get('bank_username') and request.cookies.get('bank_password'):
        username = request.cookies.get('bank_username')
        password = request.cookies.get('bank_password')
        conn = get_db_connection()
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cursor = conn.cursor()
        
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        try:
            cursor.execute(query)
            user = cursor.fetchone()
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        conn = get_db_connection()
        if USE_POSTGRES:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        else:
            cursor = conn.cursor()
        
        # VULNERABILITY: String concatenation allows SQL Injection
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        try:
            cursor.execute(query)
            user = cursor.fetchone()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                
                response = make_response(redirect(url_for('dashboard')))
                if remember:
                    response.set_cookie('bank_username', username, max_age=30*24*60*60)
                    response.set_cookie('bank_password', password, max_age=30*24*60*60)
                
                return response
            else:
                error = 'Invalid username or password'
        except Exception as e:
            conn.rollback()
            error = f"Database error: {str(e)}"
            
        conn.close()
        
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            error = "Username and password are required."
        else:
            conn = get_db_connection()
            if USE_POSTGRES:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            else:
                cursor = conn.cursor()
            
            db_execute(cursor, "SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                error = f"Username '{username}' is already taken."
            else:
                if USE_POSTGRES:
                    db_execute(cursor, "INSERT INTO users (username, password, balance) VALUES (%s, %s, %s) RETURNING id", (username, password, 1000))
                    user_id = cursor.fetchone()['id']
                else:
                    db_execute(cursor, "INSERT INTO users (username, password, balance) VALUES (%s, %s, %s)", (username, password, 1000))
                    user_id = cursor.lastrowid
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_execute(cursor, "INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', 1000, 'Welcome Bonus Deposit', %s)", (user_id, now_str))
                
                conn.commit()
                conn.close()
                session['user_id'] = user_id
                session['username'] = username
                return redirect(url_for('dashboard'))
            
            conn.close()
            
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('login')))
    response.set_cookie('bank_username', '', expires=0)
    response.set_cookie('bank_password', '', expires=0)
    return response

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    if USE_POSTGRES:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        cursor = conn.cursor()
    
    db_execute(cursor, "SELECT id, username, balance FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    db_execute(cursor, "SELECT * FROM transactions WHERE user_id = %s ORDER BY timestamp DESC LIMIT 20", (session['user_id'],))
    transactions = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, transactions=transactions)

# Admin Login Page
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('admin_username', '')
        password = request.form.get('admin_password', '')
        if username == 'admin46' and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('db_admin'))
        else:
            error = 'Invalid admin credentials.'
    return render_template('admin_login.html', error=error)

@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('dashboard'))

# Database Admin Panel - View all tables and records
@app.route('/db_admin')
def db_admin():
    # Only allow authenticated admins
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    
    active_table = request.args.get('table', 'users')
    
    conn = get_db_connection()
    if USE_POSTGRES:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        cursor = conn.cursor()
    
    # Discover all tables in the database
    if USE_POSTGRES:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' ORDER BY table_name
        """)
        tables = [row['table_name'] for row in cursor.fetchall()]
    else:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = [row['name'] for row in cursor.fetchall()]
    
    # Default to first table if active_table doesn't exist
    if active_table not in tables and tables:
        active_table = tables[0]
    
    # Fetch columns and rows for the active table
    columns = []
    rows = []
    if active_table and active_table in tables:
        if USE_POSTGRES:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_schema = 'public' AND table_name = %s 
                ORDER BY ordinal_position
            """, (active_table,))
            columns = [row['column_name'] for row in cursor.fetchall()]
        else:
            cursor.execute(f'PRAGMA table_info("{active_table}")')
            columns = [row['name'] for row in cursor.fetchall()]
        
        cursor.execute(f'SELECT * FROM "{active_table}" ORDER BY id DESC')
        rows = cursor.fetchall()
    
    # Compute stats
    stats = {'total_users': 0, 'total_transactions': 0, 'total_balance': 0}
    try:
        if 'users' in tables:
            cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(balance), 0) as total FROM users")
            result = cursor.fetchone()
            stats['total_users'] = result['cnt'] if USE_POSTGRES else result[0]
            stats['total_balance'] = float(result['total'] if USE_POSTGRES else result[1])
        if 'transactions' in tables:
            cursor.execute("SELECT COUNT(*) as cnt FROM transactions")
            result = cursor.fetchone()
            stats['total_transactions'] = result['cnt'] if USE_POSTGRES else result[0]
    except Exception:
        pass
    
    conn.close()
    
    return render_template('db_admin.html', 
                           tables=tables, 
                           active_table=active_table, 
                           columns=columns, 
                           rows=rows, 
                           stats=stats)

# 2. CSRF (Bank Transfer)
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    message = None
    if request.method == 'POST' or request.args.get('amount'):
        amount = request.form.get('amount') or request.args.get('amount')
        to_user = request.form.get('to_user') or request.args.get('to_user')
        
        try:
            amount = int(amount)
            if amount <= 0:
                message = "Transfer amount must be positive."
            else:
                conn = get_db_connection()
                if USE_POSTGRES:
                    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                else:
                    cursor = conn.cursor()
                
                db_execute(cursor, "SELECT balance FROM users WHERE id = %s", (session['user_id'],))
                sender = cursor.fetchone()
                
                if sender['balance'] <= 0 or sender['balance'] < amount:
                    message = "Invalid funds for this transfer."
                elif to_user == session['username']:
                    message = "You cannot transfer money to your own account."
                else:
                    db_execute(cursor, "SELECT id FROM users WHERE username = %s", (to_user,))
                    recipient = cursor.fetchone()
                    
                    if not recipient:
                        message = f"Recipient '{to_user}' not found."
                    else:
                        db_execute(cursor, "UPDATE users SET balance = balance - %s WHERE id = %s", (amount, session['user_id']))
                        db_execute(cursor, "UPDATE users SET balance = balance + %s WHERE username = %s", (amount, to_user))
                        
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        db_execute(cursor, "INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'DEBIT', %s, %s, %s)", 
                                       (session['user_id'], amount, f'Transfer to {to_user}', now_str))
                        
                        db_execute(cursor, "INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', %s, %s, %s)", 
                                       (recipient['id'], amount, f'Transfer from {session["username"]}', now_str))
                        
                        conn.commit()
                        message = f"Successfully transferred ${amount} to {to_user}."
                
                conn.close()
        except ValueError:
            message = "Invalid amount. Please enter a number."
        except Exception as e:
            message = "An error occurred during the transfer."
            
    return render_template('transfer.html', message=message)

@app.route('/add_funds', methods=['GET', 'POST'])
def add_funds():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    message = None
    if request.method == 'POST':
        amount = request.form.get('amount')
        try:
            amount = int(amount)
            if amount <= 0:
                message = "Amount must be positive."
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                db_execute(cursor, "UPDATE users SET balance = balance + %s WHERE id = %s", (amount, session['user_id']))
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                db_execute(cursor, "INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', %s, %s, %s)", 
                               (session['user_id'], amount, 'Added Funds via Deposit', now_str))
                
                conn.commit()
                conn.close()
                return redirect(url_for('dashboard'))
        except ValueError:
            message = "Invalid amount. Please enter a number."
        except Exception as e:
            message = "An error occurred during the deposit."
            
    return render_template('add_funds.html', message=message)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
