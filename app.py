from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "super_secret_key"

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
conn = sqlite3.connect("database.db")
c = conn.cursor()

try:
    c.execute("ALTER TABLE users ADD COLUMN photo TEXT")
    print("Columna photo agregada")
except:
    print("La columna ya existe")

conn.commit()
conn.close()



# =========================
# DATABASE INIT
# =========================

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        password TEXT,
        premium INTEGER DEFAULT 0,
        likes INTEGER DEFAULT 5
    )
    """)

    # PROFILES
    c.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        age INTEGER,
        bio TEXT,
        photo TEXT
    )
    """)

    # LIKES
    c.execute("""
    CREATE TABLE IF NOT EXISTS likes_table (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_user INTEGER,
        profile INTEGER
    )
    """)

    # MATCHES
    c.execute("""
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user1 INTEGER,
        user2 INTEGER
    )
    """)

    # MESSAGES
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        sender_id INTEGER,
        text TEXT
    )
    """)

    # Insert fake profiles if empty
    c.execute("SELECT COUNT(*) FROM profiles")
    count = c.fetchone()[0]

    if count == 0:
        fake_profiles = [
            ("Valeria", 23, "Amante del café ☕", "https://picsum.photos/400/600?1"),
            ("Camila", 25, "Fitness & viajes ✈️", "https://picsum.photos/400/600?2"),
            ("Sofía", 24, "Fan del cine 🎬", "https://picsum.photos/400/600?3"),
            ("Natalia", 27, "Busco algo serio 💕", "https://picsum.photos/400/600?4")
        ]

        for p in fake_profiles:
            c.execute("INSERT INTO profiles (name, age, bio, photo) VALUES (?,?,?,?)", p)

    conn.commit()
    conn.close()


init_db()


# =========================
# ROUTES
# =========================

@app.route("/upload_photo", methods=["POST"])
def upload_photo():
    if "user_id" not in session:
        return redirect("/")

    file = request.files["photo"]

    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("UPDATE users SET photo=? WHERE id=?", (filename, session["user_id"]))
        conn.commit()
        conn.close()

    return redirect("/profile")
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["POST"])
def register():
    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    try:
        c.execute("INSERT INTO users (email, password) VALUES (?,?)", (email, password))
        conn.commit()
    except:
        return "Usuario ya existe"

    conn.close()
    return redirect("/")


@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    user = c.fetchone()

    conn.close()

    if user:
        session["user_id"] = user[0]
        return redirect("/swipe")
    else:
        return "Credenciales incorrectas"


@app.route("/swipe")
def swipe():
    if "user_id" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT id, name, age, bio, photo FROM profiles ORDER BY RANDOM() LIMIT 1")
    profile = c.fetchone()

    conn.close()

    return render_template("swipe.html", profile=profile)

@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT email, premium, likes FROM users WHERE id=?", (user_id,))
    user = c.fetchone()

    conn.close()

    return render_template("profile.html", user=user)

@app.route("/like/<int:profile_id>")
def like(profile_id):
    if "user_id" not in session:
        return jsonify({"status": "error"})

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT premium, likes FROM users WHERE id=?", (user_id,))
    user = c.fetchone()

    premium = user[0]
    likes = user[1]

    if premium == 0 and likes <= 0:
        conn.close()
        return jsonify({"status": "no_likes"})

    if premium == 0:
        likes -= 1
        c.execute("UPDATE users SET likes=? WHERE id=?", (likes, user_id))

    # Save like
    c.execute("INSERT INTO likes_table (from_user, profile) VALUES (?,?)",
              (user_id, profile_id))

    # 30% fake match
    if random.randint(1, 100) <= 30:
        c.execute("INSERT INTO matches (user1, user2) VALUES (?,?)",
                  (user_id, profile_id))
        conn.commit()
        conn.close()
        return jsonify({"status": "match", "likes": likes})

    conn.commit()
    conn.close()

    return jsonify({"status": "liked", "likes": likes})


@app.route("/matches")
def matches_view():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT * FROM matches WHERE user1=? OR user2=?", (user_id, user_id))
    matches = c.fetchall()

    conn.close()

    return render_template("matches.html", matches=matches)


@app.route("/chat/<int:match_id>", methods=["GET", "POST"])
def chat(match_id):
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    if request.method == "POST":
        text = request.form["text"]
        c.execute("INSERT INTO messages (match_id, sender_id, text) VALUES (?,?,?)",
                  (match_id, user_id, text))
        conn.commit()

    c.execute("SELECT sender_id, text FROM messages WHERE match_id=?", (match_id,))
    messages = c.fetchall()

    conn.close()

    return render_template("chat.html", messages=messages, match_id=match_id)

@app.route("/get_messages/<int:match_id>")
def get_messages(match_id):
    if "user_id" not in session:
        return jsonify([])

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT sender_id, text FROM messages WHERE match_id=? ORDER BY id ASC", (match_id,))
    messages = c.fetchall()

    conn.close()

    return jsonify(messages)


@app.route("/send_message/<int:match_id>", methods=["POST"])
def send_message(match_id):
    if "user_id" not in session:
        return jsonify({"status": "error"})

    user_id = session["user_id"]
    text = request.json.get("text")

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("INSERT INTO messages (match_id, sender_id, text) VALUES (?,?,?)",
              (match_id, user_id, text))
    conn.commit()
    conn.close()

    return jsonify({"status": "sent"})

@app.route("/premium")
def premium():
    if "user_id" not in session:
        return redirect("/")

    return render_template("premium.html")


@app.route("/activate_premium")
def activate_premium():
    if "user_id" not in session:
        return redirect("/")

    user_id = session["user_id"]

    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("UPDATE users SET premium=1 WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/swipe")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
