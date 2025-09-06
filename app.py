# app.py
from flask import Flask, request, jsonify, session, render_template, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import os
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here'

# --- Email Configuration ---
EMAIL_ADDRESS = os.environ.get('EMAIL_USER')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASS')

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
            password TEXT NOT NULL
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

def get_all_logic_puzzles():
    return [
        {"puzzle": "I am an odd number. Take away one letter and I become even. What am I?", "options": ["Nine", "Seven", "Five"], "answer": "Seven"},
        {"puzzle": "A man is in a room. There are no windows and no doors. The only thing in the room is a table and a saw. The man gets out. How?", "options": ["He saws the table in half", "He saws the room in half", "He saws the table in half and put two halves together", "He saws the table in half, and two halves make a whole, and he climbs out a hole"], "answer": "He saws the table in half, and two halves make a whole, and he climbs out a hole"},
    ]

def get_all_word_puzzles():
    return [
        {"puzzle": "What five-letter word becomes shorter when you add two letters to it?", "options": ["Short", "Longer", "Shortest"], "answer": "Short"},
        {"puzzle": "I am a word of five letters. If you take away my last letter, I am a three-letter word. If you take away my last two letters, I am a five-letter word. What am I?", "options": ["Three", "Start", "Empty", "Queue"], "answer": "Empty"},
    ]

def get_all_spatial_puzzles():
    return [
        {"puzzle": "I am tall when I am young, and I am short when I am old. What am I?", "options": ["A tree", "A candle", "A pencil"], "answer": "A candle"},
        {"puzzle": "What can you catch, but not throw?", "options": ["A ball", "A cold", "A fish"], "answer": "A cold"},
    ]

# --- Routes for Authentication and Page Navigation ---
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
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['user_id'] = user['id']
            return redirect(url_for('dashboard'))
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
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, hashed_password))
            conn.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Username or email already exists')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        if user:
            msg = EmailMessage()
            msg.set_content(f"Hello {user['username']},\n\nYour username is: {user['username']}\n\nThis is a password reset email. In a real application, you would be provided with a link to reset your password. For this demo, please contact support.\n\nThank you!")
            msg['Subject'] = 'Password Recovery'
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email
            
            try:
                with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                    smtp.send_message(msg)
                return render_template('forgot_password.html', message='An email has been sent to your address with recovery instructions.')
            except Exception as e:
                return render_template('forgot_password.html', error=f'Failed to send email. Error: {e}')

        return render_template('forgot_password.html', error='Email not found.')
    return render_template('forgot_password.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['username'])

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
    return render_template('game_board.html', game_type=game_type)

@app.route('/leaderboard')
def leaderboard():
    if 'username' not in session:
        return redirect(url_for('login'))
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

# --- Puzzle API Endpoints ---
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
    elif puzzle_type == 'logic':
        all_puzzles = get_all_logic_puzzles()
    elif puzzle_type == 'word':
        all_puzzles = get_all_word_puzzles()
    elif puzzle_type == 'spatial':
        all_puzzles = get_all_spatial_puzzles()
    else:
        return jsonify({"error": "Invalid puzzle type"}), 400

    available_puzzles = [p for p in all_puzzles if p['puzzle'] not in session['used_puzzles'][puzzle_type]]

    if not available_puzzles:
        return jsonify({"game_over": True})

    chosen_puzzle = random.choice(available_puzzles)
    
    session['used_puzzles'][puzzle_type].append(chosen_puzzle['puzzle'])
    session.modified = True
    
    return jsonify({
        "puzzle": chosen_puzzle["puzzle"],
        "options": chosen_puzzle["options"],
        "answer": chosen_puzzle["answer"]
    })

@app.route('/check_answer', methods=['POST'])
def check_answer():
    data = request.json
    player_guess = data.get('guess').lower().strip()
    correct_answer = data.get('answer').lower().strip()
    game_type = data.get('game_type')
    user_id = session.get('user_id')
    
    is_correct = player_guess == correct_answer
    
    if is_correct and user_id:
        conn = get_db_connection()
        conn.execute('INSERT INTO scores (user_id, game_type, score) VALUES (?, ?, ?)', (user_id, game_type, 1))
        conn.commit()
        conn.close()

    return jsonify({"is_correct": is_correct})

@app.route('/reset_game', methods=['POST'])
def reset_game():
    puzzle_type = request.json.get('type')
    if 'used_puzzles' in session and puzzle_type in session['used_puzzles']:
        session['used_puzzles'][puzzle_type] = []
        session.modified = True
        return jsonify({"message": "Game reset successfully"})
    return jsonify({"message": "Nothing to reset"})

if __name__ == '__main__':
    if not os.path.exists('users.db'):
        init_db()
    app.run(debug=True, port=5000)