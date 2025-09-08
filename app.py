# app.py
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import os
import smtplib
from email.message import EmailMessage
import secrets
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here'

# --- Email Configuration (set as environment variables) ---
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# --- Database Setup ---
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            temp_password INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS scores (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            game_type TEXT NOT NULL,
            score INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Puzzle Logic ---
def get_all_riddles():
    return [
        {"puzzle": "I have cities, but no houses. I have mountains, but no trees. I have water, but no fish. What am I?", "options": ["A map", "A globe", "A book", "A movie"], "answer": "A map"},
        {"puzzle": "What has an eye but cannot see?", "options": ["A storm", "A needle", "A hurricane", "A mirror"], "answer": "A needle"},
        {"puzzle": "What gets wet while drying?", "options": ["A towel", "A sponge", "A dish"], "answer": "A towel"},
        {"puzzle": "What has a neck but no head?", "options": ["A bottle", "A shirt", "A giraffe"], "answer": "A bottle"},
        {"puzzle": "What has an eye but no nose?", "options": ["A needle", "A potato", "A storm"], "answer": "A needle"}
    ]

# --- Authentication and Page Navigation Routes ---
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['user_id'] = user['id']
            # Check if this is a temporary password login
            if user['temp_password'] == 1:
                return redirect(url_for('change_password_required'))
            conn.close()
            return redirect(url_for('dashboard'))
        conn.close()
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256:150000')
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, email, password, temp_password) VALUES (?, ?, ?, ?)', (username, email, hashed_password, 0))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username or email already exists')
        finally:
            conn.close()
    return render_template('register.html')
    
# --- FORGOT PASSWORD ROUTE ---
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        
        if user:
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for i in range(12))
            
            hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256:150000')
            conn.execute('UPDATE users SET password = ?, temp_password = ? WHERE email = ?', (hashed_password, 1, email))
            conn.commit()

            msg = EmailMessage()
            msg['Subject'] = 'Password Recovery for Your Account'
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email
            
            body = f"""
Hello {user['username']},

You requested a password reset for your account.

Your new temporary password is: {new_password}

Please use this to log in and change your password as soon as possible.

Thank you,
Your Game Team
"""
            msg.set_content(body)

            try:
                with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
                    smtp.starttls()
                    smtp.login("sach8084@gmail.com", "ywjp jkmn bdlc ecup")
                    smtp.send_message(msg)
                
                conn.close()
                return render_template('forgot_password.html', message='An email has been sent to your address with your new password.')

            except smtplib.SMTPAuthenticationError:
                conn.close()
                return render_template('forgot_password.html', error='Failed to send email. Please check your email credentials and app password.')
            except Exception as e:
                conn.close()
                return render_template('forgot_password.html', error=f'Failed to send email. Error: {e}. Please try again later.')
        
        else:
            conn.close()
            return render_template('forgot_password.html', error='Email not found.')

    return render_template('forgot_password.html')

# --- New Route for Password Change ---
@app.route('/change_password_required', methods=['GET', 'POST'])
def change_password_required():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            return render_template('change_password.html', error="Passwords do not match.")
        
        if len(new_password) < 6:
            return render_template('change_password.html', error="Password must be at least 6 characters.")

        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256:150000')
        conn = get_db_connection()
        conn.execute('UPDATE users SET password = ?, temp_password = ? WHERE id = ?', (hashed_password, 0, session['user_id']))
        conn.commit()
        conn.close()

        return redirect(url_for('dashboard'))
    
    return render_template('change_password.html')

# --- Remaining Routes ---
@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Check if a password change is required
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()

    if user and user['temp_password'] == 1:
        return redirect(url_for('change_password_required'))

    return render_template('dashboard.html', username=session['username'])

# ... (rest of your routes) ...
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('user_id', None)
    session.pop('used_puzzles', None)
    return redirect(url_for('login'))

@app.route('/game_board/<string:game_type>')
def game_board(game_type):
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # You might want to add a check here as well to be safe
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if user and user['temp_password'] == 1:
        return redirect(url_for('change_password_required'))
        
    return render_template('game_board.html', game_type=game_type)
    
@app.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    if user and user['temp_password'] == 1:
        return redirect(url_for('change_password_required'))

    conn = get_db_connection()
    top_scores = conn.execute('''
        SELECT u.username, s.game_type, SUM(s.score) as total_score
        FROM scores s JOIN users u ON s.user_id = u.id
        GROUP BY u.username, s.game_type
        ORDER BY total_score DESC
        LIMIT 10
    ''').fetchall()
    conn.close()
    return render_template('leaderboard.html', scores=top_scores)
    
@app.route('/get_puzzle', methods=['GET'])
def get_puzzle():
    puzzle_type = request.args.get('type')
    
    if 'used_puzzles' not in session:
        session['used_puzzles'] = {}
    if puzzle_type not in session['used_puzzles']:
        session['used_puzzles'][puzzle_type] = []

    all_puzzles = []
    if puzzle_type == 'riddle':
        all_puzzles = get_all_riddles()
    return jsonify(random.choice(all_puzzles))

if __name__ == '__main__':
    if not os.path.exists('users.db'):
        init_db()
    app.run(debug=True, port=5000)