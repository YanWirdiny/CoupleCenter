from flask import Flask, request, render_template, redirect, url_for, session, abort
from flask_cors import CORS
from flask_dance.contrib.google import make_google_blueprint, google
import os   
from dotenv import load_dotenv
import secrets
import replicate


load_dotenv()  # Load environment variables from .env file
# --- SQLite setup for WordsTogether (text sharing) ---
import sqlite3
# --- SQLite setup for WordsTogether (text sharing) ---
WORDS_DB_PATH = os.path.join(os.path.dirname(__file__), 'WordsTogether.db')

def init_words_db():
    conn = sqlite3.connect('WordsTogether.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            couple_id INTEGER,
            FOREIGN KEY (couple_id) REFERENCES couples(id)
        )
    ''')
    conn.commit()
    conn.close()

init_words_db()  # Initialize WordsTogether DB on startup

def get_words(couple_id):
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, text FROM words WHERE couple_id=? ORDER BY id DESC LIMIT 20', (couple_id,))
    words = c.fetchall()
    conn.close()
    return words

def add_word(text, couple_id):
    conn = sqlite3.connect(WORDS_DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO words (text, couple_id) VALUES (?, ?)', (text, couple_id))
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
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            note TEXT,
            couple_id INTEGER,
            FOREIGN KEY (couple_id) REFERENCES couples(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()  # Initialize DB on startup

def get_images(couple_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, filename, note FROM images WHERE couple_id=? ORDER BY id DESC LIMIT 10', (couple_id,))
    images = c.fetchall()
    conn.close()
    return images

def add_image(filename, note, couple_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO images (filename, note, couple_id) VALUES (?, ?, ?)', (filename, note, couple_id))
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
    redirect_to="homepage",
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
    logged_in = bool(session.get("google_oauth_token"))
    if logged_in and not session.get('couple_id'):
        # Get user info from Google
        resp = google.get("/oauth2/v2/userinfo")
        email = resp.json().get("email")
        couple_id = get_or_create_couple(email)
        session['couple_id'] = couple_id
        session['user_email'] = email

    couple_id = session.get('couple_id')
    partner_email = None
    if couple_id:
        conn = sqlite3.connect('couples.db')
        c = conn.cursor()
        c.execute('SELECT user2_email FROM couples WHERE id=?', (couple_id,))
        row = c.fetchone()
        partner_email = row[0] if row and row[0] else None
        conn.close()

    features = [
        {
            "title": "Gallery",
            "desc": "Upload and view pictures with notes as flashcards.",
            "link": url_for('gallery')
        },
        {
            "title": "Words Together",
            "desc": "Share and view messages with your partner.",
            "link": url_for('words_together')
        },
      
    ]
    return render_template(
        'index.html',
        logged_in=logged_in,
        features=features,
        partner_email=partner_email,
        couple_id=couple_id
    )

# "Will You Be My Girlfriend" endpoint
@app.route('/ask-girl', methods=['GET', 'POST'])
@login_required
def ask_girlfriend():
    show_animation = False
    response = None
    if request.method == 'POST':
        answer = request.form.get('answer')
        if answer == 'yes':
            response = "Congratulations! She said YES! 🎉"
            show_animation = True
        elif answer == 'no':
            response = "Sorry, she said NO. 😢"
        else:
            response = "Invalid response."
        return render_template('ask_girlfriend.html', response=response, show_animation=show_animation)
    return render_template('ask_girlfriend.html', response=response, show_animation=show_animation)

# "Will You Be My Boyfriend" endpoint
@app.route('/ask-boyfriend', methods=['GET', 'POST'])
@login_required
def ask_boyfriend():
    show_animation = False
    response = None
    if request.method == 'POST':
        answer = request.form.get('answer')
        if answer == 'yes':
            response = "Congratulations! He said YES! 🎉"
            show_animation = True
        elif answer == 'no':
            response = "Sorry, he said NO. 😢"
        else:
            response = "Invalid response."
        return render_template('ask_boyfriend.html', response=response, show_animation=show_animation)
    return render_template('ask_boyfriend.html', response=response, show_animation=show_animation)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/gallery', methods=['GET', 'POST'])
@login_required
def gallery():
    error = None
    couple_id = session.get('couple_id')
    if request.method == 'POST':
        if 'delete_id' in request.form:
            delete_image(request.form['delete_id'])
            return redirect(url_for('gallery'))
        images = get_images(couple_id)
        if len(images) >= 10:
            error = 'Maximum of 10 images allowed.'
        else:
            file = request.files.get('image')
            note = request.form.get('note')
            if file and allowed_file(file.filename):
                filename = secrets.token_hex(8) + '_' + file.filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                add_image(filename, note, couple_id)
                return redirect(url_for('gallery'))
            else:
                error = 'Invalid file type.'
    images = get_images(couple_id)
    return render_template('Gallery.html', images=images, error=error)

# WordsTogether text sharing route
@app.route('/words-together', methods=['GET', 'POST'])
@login_required
def words_together():
    error = None
    couple_id = session.get('couple_id')
    if request.method == 'POST':
        if 'delete_id' in request.form:
            delete_word(request.form['delete_id'])
            return redirect(url_for('words_together'))
        text = request.form.get('text')
        if text and len(text.strip()) > 0:
            add_word(text.strip(), couple_id)
            return redirect(url_for('words_together'))
        else:
            error = 'Text cannot be empty.'
    words = get_words(couple_id)
    return render_template('WordsTogether.html', words=words, error=error)

@app.route("/login")
def login():
    return redirect(url_for("google.login"))

@app.route("/profile")
@login_required
def profile():
    resp = google.get("/oauth2/v2/userinfo")
    email = resp.json().get("email")
    couple_id = get_or_create_couple(email)
    session['couple_id'] = couple_id
    session['user_email'] = email

    # Get partner info from DB
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    c.execute('SELECT user1_email, user2_email FROM couples WHERE id=?', (couple_id,))
    row = c.fetchone()
    conn.close()
    user1_email, user2_email = row if row else (None, None)

    return render_template(
        "profile.html",
        user_email=email,
        user1_email=user1_email,
        user2_email=user2_email,
        couple_id=couple_id
    )

# Logout route for Google OAuth
@app.route("/logout")
def logout():
    # Remove the OAuth token from the session
    if "google_oauth_token" in session:
        del session["google_oauth_token"]
    session.clear()  # Clear all session data
    return redirect(url_for("homepage"))  # Redirect to homepage after logout

# --- Couples database setup ---
def init_couples_db():
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS couples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1_email TEXT NOT NULL,
            user2_email TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Call this function at startup
init_couples_db()

def get_or_create_couple(email):
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    # Check if email is already user1 or user2
    c.execute('SELECT id FROM couples WHERE user1_email=? OR user2_email=?', (email, email))
    row = c.fetchone()
    if row:
        couple_id = row[0]
    else:
        # Create new couple with user1_email
        c.execute('INSERT INTO couples (user1_email) VALUES (?)', (email,))
        couple_id = c.lastrowid
        conn.commit()
    conn.close()
    return couple_id

def add_partner_to_couple(couple_id, partner_email):
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    c.execute('UPDATE couples SET user2_email=? WHERE id=?', (partner_email, couple_id))
    conn.commit()
    conn.close()

# --- Database migration to add couple_id to words table ---
def update_partner_session(couple_id):
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    c.execute('SELECT user2_email FROM couples WHERE id=?', (couple_id,))
    row = c.fetchone()
    session['partner_email'] = row[0] if row and row[0] else None
    conn.close()

@app.route('/add-partner', methods=['POST'])
@login_required
def add_partner():
    partner_email = request.form.get('partner_email')
    couple_id = session.get('couple_id')
    if couple_id and partner_email:
        add_partner_to_couple(couple_id, partner_email)
        session['partner_email'] = partner_email  # <-- Set in session for template logic
    return redirect(url_for('homepage'))

@app.route('/partner-management', methods=['GET', 'POST'])
@login_required
def partner_management():
    couple_id = session.get('couple_id')
    user_email = session.get('user_email')
    partner_email = None

    # Fetch partner email from DB
    conn = sqlite3.connect('couples.db')
    c = conn.cursor()
    c.execute('SELECT user1_email, user2_email FROM couples WHERE id=?', (couple_id,))
    row = c.fetchone()
    conn.close()
    user1_email, user2_email = row if row else (None, None)
    if user_email == user1_email:
        partner_email = user2_email
    else:
        partner_email = user1_email

    # Remove partner logic
    if request.method == 'POST' and 'remove_partner' in request.form:
        # Delete all shared data
        conn = sqlite3.connect('gallery.db')
        c = conn.cursor()
        c.execute('DELETE FROM images WHERE couple_id=?', (couple_id,))
        conn.commit()
        conn.close()

        conn = sqlite3.connect('WordsTogether.db')
        c = conn.cursor()
        c.execute('DELETE FROM words WHERE couple_id=?', (couple_id,))
        conn.commit()
        conn.close()

        # Remove partner from couples table
        conn = sqlite3.connect('couples.db')
        c = conn.cursor()
        c.execute('UPDATE couples SET user2_email=NULL WHERE id=?', (couple_id,))
        conn.commit()
        conn.close()
        session['partner_email'] = None
        return redirect(url_for('partner_management'))

    return render_template(
        'partner_management.html',
        user_email=user_email,
        partner_email=partner_email,
        couple_id=couple_id
    )

# route for OurStory page
@app.route('/our-story', methods=['GET', 'POST'])
@login_required
def our_story():
    # Simple hardcoded story text for demonstration
    story_text = ("""07/30
I Have sometimes a lot of word to share and I feel that I don’t structure things well my mind is like a ball in closed space rebounding everywhere. Thinking abut everything about past present future where things get fully not linear. Few Days ago I got back in contact with someone I have shared a lot of memories with. I honestly can not understand the process of us starting talking again and since I'm not a fan or a believer in destiny, I can only say it is the work of God. And I firmly believe it since I never miss a day praying on that. I have been doing a lot but I think there is more to come specially from me. It is very hard to describe what I am feeling since is such a mix of feelings. I am firstly happy extremely happy waking up feeling so alive, and so good as and this warm feeling in my stomach I prayed so much for it to happen. And. You give that to me. That feeling of completeness and assurance. I'm feeling so good and happy but foremost I am feeling grateful for everything even and specially the smallest one our flirts our updates our humor our sarcasms, just right now you told me that you will do anything to have quality time with and that’s only mean the word to me you are nice extremely nice and I feel so me with you I feel that I am Yan. Im not trying to impress you intellectually or materialistically or more I just being me and showing you my world my universe what I like and listen to yours. I know you so we’ll what you like what thrive you but in the same time I feel you are a lot to know you have a lot to make me discover and you have a lot to make me know about you about us cause I feel there is a learning form each other and I love that I just love that.
08/20
I Have been going through a lot this week with work. Responsibility and more and I think it will be also the case for this week I have. A lot of pressure going on that sphere to be honest but I know with God there will be a way through and I will do Good. I want to attack a difficult subject. Today when it about relationship in general but also in our case. I feel it’s an important subject that I need to point out since I want to. Treat this place like a. Diary board for me and for us. The question of inspiring and losing identity through a relationship. I think this is something I am very expose to as a human since I feel I lived it a lot. First I want to make some context. I love hard I love extremely hard. And I sometime put that first involuntarily because thing are so binary in my head. The way that if its not first its last then. But Unfortunately life is not like that I need to be able to juggle Between more than one thing. I am still afraid that like I lost myself. Through the relationship and be drunk and love type of thing. Which Is. A sabotage type of reaction cause nobody need or want someone who only is interested. About love cause life is made of a whole bunch of things I know that I still need to to improve. Bette rot make time for myself to have my own. Hobbies to take care of myself physically. Emotionally and morally and not rely on. My partner for. That. Taking care of myself constantly but also there is the thing I should not exclude my person from. That growth. Cause she is my first fan you are my FIRST FAN my cheerleader. Being a man is a path that I am acknowledging. Day by day cause there is os much to learn to it but ik solving things is part of it and finding a good life balance is the whole point of life. Adulting is always good to and its better when your a loved. I feel loved but I will not use this love as a fuel 
it motivate me to do those things. But rather as an appreciation and as way of showing me that my effort are seen by my lover (YOU) and are appreciated at their worth its also a way to say don’t worry even when you are failing or are blocked at things I am still here for you. To support you until you solve them cause I believe in you Yes I see your love as a way of believing in me and I want to make my love scream the same thing a way to support you and to make you feel you can do everything and you have a safe place to come to resource yourself and. Get. Back chasing and realizing your dreams.
08/28
Is this the feeling of being in love? Love is very unique since it can never be explained. To be honest. I may describe what I feel in my stomach how my brain react when I see you how my mood is when I'm around you joking and laughing it still. Is very far away of the feeling that burn inside me towards that person in particular. I think one of the best way even very selfish to describe it is by comparing what I felt for others and its so different. The consideration I have. For you the care the importance you have naturally in my hear its so unique that I feel I can try again and again but it will never get accurate but, I feel that is the whole point is to never feel like communicate it fully since its always growing and by consequent always more to share.

I want to do a big thing to ask you out to do it the most special way but honestly I want to ask just you I just want to pop up the question I want to look you in the eyes and pop up the question. But good things take time and I will take all time I have with you. Patience will always. Be the best for us it will grow our love. Always. I love you.

.""" )
    
    return render_template('our_story.html', story_text=story_text)


# route for generating invitation card using Replicate API
@app.route('/generate-invitation', methods=['GET', 'POST'])
@login_required
def generate_invitation():
    image_url = None
    error = None
    if request.method == 'POST':
        prompt = request.form.get('prompt', 'Romantic date night invitation card')
        try:
            # Generate a single image using Replicate (Stable Diffusion)
            output = replicate.run(
                "prunaai/flux.1-dev:970a966e3a5d8aa9a4bf13d395cf49c975dc4726e359f982fb833f9b100f75d5",
                input={"prompt": prompt}
            )
            # output is a list, but we only want the first image
            if output and isinstance(output, list) and len(output) > 0:
                image_url = output[0]
            else:
                error = "No image generated. Try a different prompt."
        except Exception as e:
            error = f"Error generating image: {str(e)}"
    return render_template('generate_invitation.html', image_url=image_url, error=error)

if __name__ == "__main__":
    app.run(debug=True)