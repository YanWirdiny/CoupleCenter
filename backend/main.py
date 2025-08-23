from flask import Flask, request, render_template, redirect, url_for, session, abort
from flask_cors import CORS
from flask_dance.contrib.google import make_google_blueprint, google
import os   
from dotenv import load_dotenv
import secrets
load_dotenv()  # Load environment variables from .env file
# --- SQLite setup for WordsTogether (text sharing) ---
import sqlite3
# --- SQLite setup for WordsTogether (text sharing) ---
WORDS_DB_PATH = os.path.join(os.path.dirname(__file__), 'WordsTogether.db')

def init_words_db():
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_words_db()  # Initialize WordsTogether DB on startup

def get_words():
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, text FROM words ORDER BY id DESC LIMIT 20')
    words = c.fetchall()
    conn.close()
    return words

def add_word(text):
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO words (text) VALUES (?)', (text,))
    conn.commit()
    conn.close()

def delete_word(word_id):
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM words WHERE id=?', (word_id,))
    conn.commit()
    conn.close()

# --- SQLite setup for gallery ---
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), 'gallery.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        note TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

init_db()  # Initialize DB on startup

def get_images():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, filename, note FROM images ORDER BY id DESC LIMIT 10')
    images = c.fetchall()
    conn.close()
    return images

def add_image(filename, note):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO images (filename, note) VALUES (?, ?)', (filename, note))
    conn.commit()
    conn.close()

def delete_image(image_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT filename FROM images WHERE id=?', (image_id,))
    row = c.fetchone()
    if row:
        filename = row[0]
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        c.execute('DELETE FROM images WHERE id=?', (image_id,))
        conn.commit()
    conn.close()


app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a random secret key
CORS(app)  # Enable CORS for cross-origin requests

# Helper: login_required decorator
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Only redirect if NOT logged in
        if not session.get("google_oauth_token"):
            return redirect(url_for("errorLogin"))
        return f(*args, **kwargs)
    return decorated_function

# Error login route
@app.route("/errorLogin")
def errorLogin():
    return render_template("errorLogin.html")

google_bp = make_google_blueprint(
    client_id=os.getenv("Client_ID"),
    client_secret=os.getenv("Client_Secret"),
    redirect_to="ask_girlfriend",
    scope=[
        "openid",
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email"
    ]
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- Flask-Dance & OAuth setup notes ---
# 1. .env file must have no spaces around '=' and no quotes around values.
#    Example:
#    Client_ID=your-client-id
#    Client_Secret=your-client-secret
# 2. If you get 'redirect_uri_mismatch', add BOTH http://localhost:5000/login/google/authorized AND http://127.0.0.1:5000/login/google/authorized to Google Cloud Console.
# 3. Use endpoint name (not URL) for redirect_to, e.g. 'homepage' for @app.route('/')
# 4. Always restart Flask after changing .env or Google settings.
# 5. If you get 'invalid_client', double-check your client ID/secret and .env formatting.
# 6. For local development, Google treats 'localhost' and '127.0.0.1' as different, so add both as redirect URIs.
# 7. Your Flask route for login should use endpoint names, not URLs, for redirect_to.
# 8. If you change ports, update the redirect URI in Google Cloud Console to match.
# 9. After updating .env or Google settings, restart your Flask app to reload changes.
# 10. For production, use a strong, random secret key and keep it secret.
#
# These comments are for future reference and learning. You can always revisit them if you encounter similar issues.

# Homepage endpoint
@app.route('/')
def homepage():
    return render_template('index.html')  # Serve the homepage template

# "Will You Be My Girlfriend" endpoint
@app.route('/ask-girl', methods=['GET', 'POST'])
@login_required
def ask_girlfriend():
    if request.method == 'POST':
        answer = request.form.get('answer')
        if answer == 'yes':
            response = "Congratulations! She said YES! 🎉"
        elif answer == 'no':
            response = "Sorry, she said NO. 😢"
        else:
            response = "Invalid response."
        return render_template('ask_girlfriend.html', response=response)
    return render_template('ask_girlfriend.html')  # Serve the form template

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/gallery', methods=['GET', 'POST'])
@login_required
def gallery():
    error = None
    if request.method == 'POST':
        if 'delete_id' in request.form:
            delete_image(request.form['delete_id'])
            return redirect(url_for('gallery'))
        images = get_images()
        if len(images) >= 10:
            error = 'Maximum of 10 images allowed.'
        else:
            file = request.files.get('image')
            note = request.form.get('note')
            if file and allowed_file(file.filename):
                filename = secrets.token_hex(8) + '_' + file.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                add_image(filename, note)
                return redirect(url_for('gallery'))
            else:
                error = 'Invalid file type.'
    images = get_images()
    return render_template('Gallery.html', images=images, error=error)

# WordsTogether text sharing route
@app.route('/words-together', methods=['GET', 'POST'])
@login_required
def words_together():
    error = None
    if request.method == 'POST':
        if 'delete_id' in request.form:
            delete_word(request.form['delete_id'])
            return redirect(url_for('words_together'))
        text = request.form.get('text')
        if text and len(text.strip()) > 0:
            add_word(text.strip())
            return redirect(url_for('words_together'))
        else:
            error = 'Text cannot be empty.'
    words = get_words()
    return render_template('WordsTogether.html', words=words, error=error)

@app.route("/login")
def login():
    return redirect(url_for("google.login"))

@app.route("/profile")
@login_required
def profile():
    resp = google.get("/oauth2/v2/userinfo")
    assert resp.ok, resp.text
    return resp.json()

# Logout route for Google OAuth
@app.route("/logout")
def logout():
    # Remove the OAuth token from the session
    if "google_oauth_token" in session:
        del session["google_oauth_token"]
    session.clear()  # Clear all session data
    return redirect(url_for("homepage"))  # Redirect to homepage after logout


if __name__ == '__main__':
    app.run(debug=True)