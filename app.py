from flask import Flask, request, render_template, redirect, url_for, session, make_response
import psycopg2
import psycopg2.extras
import os
import datetime

app = Flask(__name__)
app.secret_key = "secure_trust_bank_key"

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# 1. SQL Injection (Login Bypass) & Insecure "Remember Me"
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Auto-login if "Remember Me" cookies exist
    if 'user_id' not in session and request.cookies.get('bank_username') and request.cookies.get('bank_password'):
        username = request.cookies.get('bank_username')
        password = request.cookies.get('bank_password')
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
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
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
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
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                error = f"Username '{username}' is already taken."
            else:
                cursor.execute("INSERT INTO users (username, password, balance) VALUES (%s, %s, %s) RETURNING id", (username, password, 1000))
                user_id = cursor.fetchone()['id']
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', 1000, 'Welcome Bonus Deposit', %s)", (user_id, now_str))
                
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
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cursor.execute("SELECT id, username, balance FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    cursor.execute("SELECT * FROM transactions WHERE user_id = %s ORDER BY timestamp DESC LIMIT 20", (session['user_id'],))
    transactions = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, transactions=transactions)

# Hidden Route to view all registered users and their plaintext passwords
@app.route('/admin_view_users')
def admin_view_users():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT * FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    conn.close()
    
    html = "<h2>Registered Users Database</h2><table border='1' cellpadding='10'>"
    html += "<tr><th>ID</th><th>Username</th><th>Password (Plaintext)</th><th>Balance</th></tr>"
    for user in users:
        html += f"<tr><td>{user['id']}</td><td>{user['username']}</td><td>{user['password']}</td><td>${user['balance']}</td></tr>"
    html += "</table>"
    
    return html

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
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                
                cursor.execute("SELECT balance FROM users WHERE id = %s", (session['user_id'],))
                sender = cursor.fetchone()
                
                if sender['balance'] <= 0 or sender['balance'] < amount:
                    message = "Invalid funds for this transfer."
                elif to_user == session['username']:
                    message = "You cannot transfer money to your own account."
                else:
                    cursor.execute("SELECT id FROM users WHERE username = %s", (to_user,))
                    recipient = cursor.fetchone()
                    
                    if not recipient:
                        message = f"Recipient '{to_user}' not found."
                    else:
                        cursor.execute("UPDATE users SET balance = balance - %s WHERE id = %s", (amount, session['user_id']))
                        cursor.execute("UPDATE users SET balance = balance + %s WHERE username = %s", (amount, to_user))
                        
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'DEBIT', %s, %s, %s)", 
                                       (session['user_id'], amount, f'Transfer to {to_user}', now_str))
                        
                        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', %s, %s, %s)", 
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
                
                cursor.execute("UPDATE users SET balance = balance + %s WHERE id = %s", (amount, session['user_id']))
                
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (%s, 'CREDIT', %s, %s, %s)", 
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
