# SecureTrust Bank (Vulnerable Web App Lab)

> [!CAUTION]
> **WARNING:** This application is intentionally vulnerable and designed purely for educational purposes and ethical hacking practice. Do **NOT** deploy this code to a production environment or expose it to the internet. Doing so will result in immediate compromise of your system.

This project is a Python Flask-based banking web application ("SecureTrust Bank") that demonstrates **exactly two** classic web vulnerabilities:
1. **SQL Injection (SQLi)**
2. **Cross-Site Request Forgery (CSRF)**

## Installation and Execution

1. Clone or download this repository.
2. Navigate to the project directory:
   ```bash
   cd attack
   ```
3. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Initialize the SQLite database (this creates `vulnerable.db` and populates it with dummy users like `admin` and `student`):
   ```bash
   python database.py
   ```
5. Start the Flask development server:
   ```bash
   python app.py
   ```
6. Open your web browser and navigate to `http://127.0.0.1:5000`.

---

## Vulnerability Modules & Walkthrough

Below is a guide on how to exploit and fix the two vulnerabilities present in this lab.

### 1. SQL Injection (Login Bypass)
- **Location:** `/login`
- **Description:** The bank's login form takes the username and password from the user and directly concatenates them into the SQL query used to authenticate the user.
- **Exploitation:**
  - Navigate to the login page.
  - Enter the following payload in the **User ID / Username** field: `admin' -- `
  - Leave the password blank (or type anything).
  - Click Login.
  - **Why it works:** The query becomes `SELECT * FROM users WHERE username = 'admin' -- ' AND password = '...'`. The `--` comments out the rest of the query (the password check), effectively logging you into the admin's bank account.
- **How to Fix:** Use parameterized queries (prepared statements) instead of string concatenation in `app.py`.
  ```python
  # Vulnerable:
  query = f"SELECT * FROM users WHERE username = '{username}' AND password = '{password}'"
  cursor.execute(query)
  
  # Secure:
  cursor.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
  ```

### 2. CSRF (Cross-Site Request Forgery)
- **Location:** `/transfer`
- **Description:** The bank transfer endpoint accepts requests to transfer money (via both GET and POST parameters) without checking the origin of the request or requiring an anti-forgery token.
- **Exploitation:**
  - Log in to your account normally (e.g., username `student`, password `password123` - or use SQLi to log in).
  - Open a new browser tab and paste this URL directly into the address bar: `http://127.0.0.1:5000/transfer?amount=100&to_user=admin`
  - The transfer goes through automatically because you are authenticated. A real attacker would embed an invisible image on a malicious website like this:
    `<img src="http://127.0.0.1:5000/transfer?amount=100&to_user=Attacker" style="display:none;">`
  - When the victim visits the attacker's site while logged into the bank, their browser automatically sends the request and their money is stolen.
- **How to Fix:** 
  1. Only accept state-changing requests via POST methods (reject GET transfers).
  2. Implement a synchronizer token pattern (an anti-CSRF token) that is generated on the server, embedded in the form as a hidden field, and verified when the form is submitted. In Flask, `Flask-WTF` handles this automatically.

---

## Cloud Deployment (Render / Heroku)

> [!CAUTION]
> Deploying this to the public internet means **anyone can hack this application and potentially the underlying container**. 

This repository is pre-configured with a `Procfile` and `gunicorn` for easy deployment to free PaaS providers like [Render](https://render.com/) or [Heroku](https://www.heroku.com/).

### Deployment Steps (e.g. Render):
1. Initialize a Git repository in this folder and push your code to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   # Add your GitHub remote repository and push
   ```
2. Create an account on **Render.com**.
3. Create a **New Web Service** and link your GitHub repository.
4. Wait for Render to build the python environment.
5. The included `Procfile` configuration (`web: python database.py && gunicorn app:app`) tells the server to automatically generate the database on startup and then run the app using a production WSGI server.
6. Once deployed, the lab will be successfully live on the public internet on your unique URL!
