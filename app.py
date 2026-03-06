from flask import Flask, request, render_template, redirect, url_for, session, make_response
import sqlite3
import datetime

app = Flask(__name__)
app.secret_key = "secure_trust_bank_key"

def get_db_connection():
    conn = sqlite3.connect('vulnerable.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

# 1. SQL Injection (Login Bypass) & 2. Insecure "Remember Me"
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Auto-login if "Remember Me" cookies exist
    if 'user_id' not in session and request.cookies.get('bank_username') and request.cookies.get('bank_password'):
        username = request.cookies.get('bank_username')
        password = request.cookies.get('bank_password')
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Still vulnerable to SQLi on cookie login!
        query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
        try:
            cursor.execute(query)
            user = cursor.fetchone()
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                return redirect(url_for('dashboard'))
        except Exception:
            pass # Silently fail and show login screen if cookie login fails
        finally:
            conn.close()

    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        conn = get_db_connection()
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
                # VULNERABILITY: Storing credentials over cookies in plain text
                if remember:
                    # Extremely insecure: Setting cookies without Secure or HttpOnly and in plain text
                    response.set_cookie('bank_username', username, max_age=30*24*60*60)
                    response.set_cookie('bank_password', password, max_age=30*24*60*60)
                
                return response
            else:
                error = 'Invalid username or password'
        except Exception as e:
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
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                error = f"Username '{username}' is already taken."
            else:
                # Create user with initial $1000 balance
                cursor.execute("INSERT INTO users (username, password, balance) VALUES (?, ?, ?)", (username, password, 1000))
                # Get new user ID
                user_id = cursor.lastrowid
                
                # Add a sign-up bonus transaction note
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (?, 'CREDIT', 1000, 'Welcome Bonus Deposit', ?)", (user_id, now_str))
                
                conn.commit()
                conn.close()
                # Log them in automatically
                session['user_id'] = user_id
                session['username'] = username
                return redirect(url_for('dashboard'))
            
            conn.close()
            
    return render_template('register.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('login')))
    # Clear vulnerable "Remember Me" cookies on logout
    response.set_cookie('bank_username', '', expires=0)
    response.set_cookie('bank_password', '', expires=0)
    return response

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch user data for balance display
    cursor.execute("SELECT id, username, balance FROM users WHERE id = ?", (session['user_id'],))
    user = cursor.fetchone()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    # 2. Fetch transaction history 
    cursor.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 20", (session['user_id'],))
    transactions = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', user=user, transactions=transactions)

# 3. CSRF (Bank Transfer)
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    message = None
    if request.method == 'POST' or request.args.get('amount'):
        # VULNERABILITY: Accepts GET and POST without any CSRF tokens
        amount = request.form.get('amount') or request.args.get('amount')
        to_user = request.form.get('to_user') or request.args.get('to_user')
        
        try:
            amount = int(amount)
            if amount <= 0:
                message = "Transfer amount must be positive."
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Check current user balance
                cursor.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],))
                sender = cursor.fetchone()
                
                if sender['balance'] <= 0 or sender['balance'] < amount:
                    message = "Invalid funds for this transfer."
                elif to_user == session['username']:
                    message = "You cannot transfer money to your own account."
                else:
                    # Start transaction logic
                    cursor.execute("SELECT id FROM users WHERE username = ?", (to_user,))
                    recipient = cursor.fetchone()
                    
                    if not recipient:
                        message = f"Recipient '{to_user}' not found."
                    else:
                        # Update Balances
                        cursor.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, session['user_id']))
                        cursor.execute("UPDATE users SET balance = balance + ? WHERE username = ?", (amount, to_user))
                        
                        # Record Transactions in the ledger
                        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Log debit for sender
                        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (?, 'DEBIT', ?, ?, ?)", 
                                       (session['user_id'], amount, f'Transfer to {to_user}', now_str))
                        
                        # Log credit for receiver
                        cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (?, 'CREDIT', ?, ?, ?)", 
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
                
                # Update Balance
                cursor.execute("UPDATE users SET balance = balance + ? WHERE id = ?", (amount, session['user_id']))
                
                # Record Transaction
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("INSERT INTO transactions (user_id, type, amount, description, timestamp) VALUES (?, 'CREDIT', ?, ?, ?)", 
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
