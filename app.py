from flask import (
    Flask, render_template, request, redirect, session, url_for, jsonify, g
)
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os

# -------------------- Config --------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "mee_sahayam.db")

app = Flask(__name__)
app.secret_key = "replace_this_with_a_random_secret_key"  # change in production


# -------------------- Database helpers --------------------
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables if they don't exist."""
    db = get_db()
    cur = db.cursor()
    cur.executescript(
        """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        phone TEXT,
        password_hash TEXT,
        signup_date TEXT,
        last_login TEXT
    );

    CREATE TABLE IF NOT EXISTS logins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        login_time TEXT,
        logout_time TEXT,
        ip TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question TEXT,
        reply TEXT,
        category TEXT,
        timestamp TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """
    )
    db.commit()


# Create DB on startup
with app.app_context():
    init_db()


# -------------------- Your original data (unchanged) --------------------
# ---- Basic translations (expand as needed) ----
texts = {
    "home_title": {"en": "Mee Sahayam — Your Government Scheme Assistant",
                   "te": "మీ సహాయం — మీ ప్రభుత్వం పథకాలు",
                   "hi": "मी सहायम — आपका सरकारी योजना सहायक"},
    "home_sub": {"en": "Helping citizens access the right schemes with ease and clarity.",
                 "te": "నాగరికులు సరైన పథకాలను సులభంగా పొందడానికి మేము సహాయం చేస్తాము.",
                 "hi": "नागरिकों को सही योजनाएँ सरलता से पहुँचाने में मदद।"},
    "select_language": {"en": "Choose Your Preferred Language",
                        "te": "మీకి ఇష్టమైన భాషను ఎంచుకోండి",
                        "hi": "अपनी पसंदीदा भाषा चुनें"},
    "select_state": {"en": "Select Your State",
                     "te": "మీ రాష్ట్రాన్ని ఎంచుకోండి",
                     "hi": "अपना राज्य चुनें"},
    "select_category": {"en": "Select Your Category",
                        "te": "మీ వర్గాన్ని ఎంచుకోండి",
                        "hi": "अपना श्रेणी चुनें"},
    "login_title": {"en": "Login to Mee Sahayam",
                    "te": "మీ సహాయం లో లాగిన్ అవ్వండి",
                    "hi": "मी सहायम में लॉगिन करें"}
}

# ---- Schemes DB (master) and alerts per category ----
schemes_db = {
    "student": {
        "schemes": [
            "Jagananna Vidya Deevena – 100% fee reimbursement",
            "Vasathi Deevena – hostel & food support",
            "Post-Matric Scholarship",
            "National Scholarship Portal (NSP)"
        ],
        "amount": "₹10,000 – ₹20,000 yearly depending on the course.",
        "apply": "Apply via Jnanabhumi or NSP portals.",
        "date": "June – October every year.",
        "alerts": [
            "🎓 NSP verification window opens on 1 Aug.",
            "⚠️ Last date for some scholarship verification: 30 Sep."
        ]
    },
    "farmer": {
        "schemes": [
            "PM Kisan – ₹6,000 yearly",
            "Rythu Bharosa",
            "PM Fasal Bima Yojana",
            "Soil Health Card"
        ],
        "amount": "PM Kisan gives ₹6,000 per year. Other schemes vary.",
        "apply": "Apply at Rythu Bharosa center or online.",
        "date": "PM Kisan renewal is continuous; insurance deadlines vary.",
        "alerts": [
            "⚠️ Last date to apply for PM-Kisan 16th installment: 30 Nov.",
            "🌾 Rythu Bharosa new enrollment starts 5 Dec at district centers."
        ]
    },
    # Add other categories similarly...
    "women": {
        "schemes": [
            "YSR Cheyutha – financial support",
            "Mahila Samakhya",
            "Stand-Up India Loans",
            "Women SHG Loans"
        ],
        "amount": "₹75,000 over 4 years in some programs.",
        "apply": "Apply via ward/village secretariat.",
        "date": "Active year-round.",
        "alerts": [
            "📢 Women SHG bank linkage drives next week.",
        ]
    },
    "senior citizen": {
        "schemes": ["Old Age Pension", "Senior Citizen Health Insurance", "Free Bus Pass"],
        "amount": "₹2,000 monthly pension (varies by scheme).",
        "apply": "Apply via MeeSeva or Navasakam.",
        "date": "Monthly pension cycles.",
        "alerts": ["🕘 Pension disbursement for this month scheduled on 1st."]
    },
    "job seeker": {
        "schemes": ["YSR Unemployment Allowance", "Skill Development Training", "PM Kaushal Vikas Yojana"],
        "amount": "₹1,000 – ₹3,000 monthly for some allowances.",
        "apply": "Apply via Skill Development portal.",
        "date": "Batches start every few months.",
        "alerts": ["📢 New skill training batch opening next month."]
    },
    "entrepreneur": {
        "schemes": ["PMEGP loan", "Mudra Loan", "Stand-Up India", "Startup India Seed Fund"],
        "amount": "Subsidies vary; loans up to several lakhs.",
        "apply": "Apply on respective portals.",
        "date": "Ongoing.",
        "alerts": ["🚀 Startup seed fund applications: rolling basis."]
    },
    "healthcare": {
        "schemes": ["Aarogyasri", "Free Medicine Scheme", "Ayushman Bharat"],
        "amount": "Coverage up to ₹5 lakh for eligible families.",
        "apply": "Apply via health department portals.",
        "date": "Available year-round.",
        "alerts": ["🏥 Free medical camp in your district on 12 Dec."]
    },
    "housing": {
        "schemes": ["PM Awas Yojana", "YSR Housing", "Urban Housing Subsidy"],
        "amount": "Subsidies up to ₹2.5 lakhs (scheme dependent).",
        "apply": "Apply via housing portal or local secretariat.",
        "date": "Allotments annually.",
        "alerts": ["🏠 New housing allotment list to be released next month."]
    },
    "loan finance": {
        "schemes": ["Mudra Loan", "PM Jan Dhan", "MSME Support"],
        "amount": "Loans from ₹10,000 to ₹10 lakhs.",
        "apply": "Apply at bank or online.",
        "date": "Monthly approvals.",
        "alerts": ["🏦 Special MSME refinance window open this quarter."]
    },
    "shg": {
        "schemes": ["SHG Bank Linkage", "Interest Free Loans", "Livelihood Support"],
        "amount": "₹10,000 – ₹3,00,000 depending on program.",
        "apply": "Apply via SERP/DRDA.",
        "date": "Periodic disbursal.",
        "alerts": ["👥 SHG bank linkage meeting next week."]
    },
    "minority": {
        "schemes": ["Minority Scholarship", "Skill Training", "Housing Support"],
        "amount": "₹5,000 – ₹25,000 scholarship ranges.",
        "apply": "Apply via Minority Welfare portal.",
        "date": "Scholarship cycle July – Dec.",
        "alerts": ["🕌 Minority scholarship application opens 1 July."]
    },
    "youth": {
        "schemes": ["Skill India Training", "Youth Empowerment Program", "YSR Job Mela"],
        "amount": "Training often free; some include stipends.",
        "apply": "Apply on Skill India portal.",
        "date": "Monthly batches.",
        "alerts": ["🎯 Youth job mela scheduled on 20th this month."]
    },
    "disability": {
        "schemes": ["Disability Pension", "Assistive Devices Scheme", "Free Health Support"],
        "amount": "₹3,000 monthly (varies).",
        "apply": "Apply via MeeSeva/Navasakam.",
        "date": "Monthly approvals.",
        "alerts": ["♿ New assistive devices distribution on 10th Dec."]
    },
    "ration welfare": {
        "schemes": ["Ration Card Subsidy", "Free Rice", "Annapurna Scheme"],
        "amount": "Rice at subsidized rates (e.g., ₹1/kg for eligible families).",
        "apply": "Apply at MeeSeva or Ration Office.",
        "date": "Monthly distribution.",
        "alerts": ["🍚 Ration distribution day announced for district X."]
    }
}

# ---- Category mapping helper for detection ----
category_aliases = {
    "student": ["student", "students", "scholarship", "education", "study"],
    "farmer": ["farmer", "farmers", "agri", "agriculture", "pmkisan"],
    "women": ["woman", "women", "mahila"],
    "senior citizen": ["senior", "senior citizen", "old", "pension"],
    "job seeker": ["job", "job seeker", "unemployment", "placement"],
    "entrepreneur": ["entrepreneur", "startup", "business"],
    "healthcare": ["health", "healthcare", "hospital", "ayushman"],
    "housing": ["house", "housing", "awas", "home"],
    "loan finance": ["loan", "finance", "mudra", "msme"],
    "shg": ["shg", "self help", "self-help"],
    "minority": ["minority", "minorities"],
    "youth": ["youth", "young"],
    "disability": ["disability", "disabled"],
    "ration welfare": ["ration", "welfare", "anapurna", "anapurna", "ration card"]
}


def detect_category_from_text(text):
    t = text.lower()
    for cat, keys in category_aliases.items():
        for k in keys:
            if k in t:
                return cat
    return None


# -------------------- ROUTES --------------------


@app.context_processor
def inject_common():
    """Provide common variables (like language and texts) to all templates."""
    lang = session.get("lang", "en")
    return {
        "current_year": datetime.now().year,
        "lang": lang,
        "texts": texts
    }


@app.route("/")
def index():
    return render_template("home.html")


# ---- SIGNUP ----
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email").lower()
        phone = request.form.get("phone")
        password = request.form.get("password")

        if not (name and email and phone and password):
            return render_template("signup.html", error="Please fill all fields")

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            return render_template("signup.html", error="Email already registered")

        password_hash = generate_password_hash(password)
        signup_date = datetime.utcnow().isoformat()

        cur.execute(
            "INSERT INTO users (name, email, phone, password_hash, signup_date) VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, password_hash, signup_date)
        )
        db.commit()

        return redirect(url_for("login"))

    return render_template("signup.html")


# ---- LOGIN ----
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email").lower()
        password = request.form.get("password")

        db = get_db()
        cur = db.cursor()

        cur.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (email,))
        user = cur.fetchone()

        if not user:
            return render_template("login.html", error="User not found")

        if not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Incorrect password")

        # Set session
        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        session["user_name"] = user["name"]

        login_time = datetime.utcnow().isoformat()
        client_ip = request.remote_addr or ""

        cur.execute("INSERT INTO logins (user_id, login_time, ip) VALUES (?, ?, ?)",
                    (user["id"], login_time, client_ip))
        session["login_id"] = cur.lastrowid

        cur.execute("UPDATE users SET last_login = ? WHERE id = ?", (login_time, user["id"]))
        db.commit()

        return redirect(url_for("language"))

    return render_template("login.html")


# ---- LOGOUT ----
@app.route("/logout")
def logout():
    login_id = session.get("login_id")
    db = get_db()
    cur = db.cursor()

    if login_id:
        logout_time = datetime.utcnow().isoformat()
        cur.execute("UPDATE logins SET logout_time = ? WHERE id = ?", (logout_time, login_id))
        db.commit()

    session.clear()
    return redirect(url_for("index"))




# ---- LANGUAGE SELECTION ----
@app.route("/language")
def language():
    # only accessible if logged in (optional). If you want open access, remove this check.
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("language.html")


@app.route("/set_language/<lang>")
def set_language(lang):
    # store language in session (en/te/hi)
    if lang not in ("en", "te", "hi"):
        lang = "en"
    session["lang"] = lang
    return redirect(url_for("state"))


# ---- STATE PAGE ----
@app.route("/state")
def state():
    if "user_id" not in session:
        return redirect(url_for("login"))
    # states list - for AP-only project, you can pass only AP or AP districts as needed
    states = [
        {"code": "AP", "name": "Andhra Pradesh"},
        # ... add others if needed
    ]
    return render_template("state.html", states=states)


# ---- CATEGORIES PAGE ----
@app.route("/categories")
def categories():
    if "user_id" not in session:
        return redirect(url_for("login"))
    # Pass category labels if needed for translations
    category_list = [
        "student", "farmer", "women", "senior citizen", "job seeker", "entrepreneur",
        "healthcare", "housing", "loan finance", "shg", "minority", "youth", "disability", "ration welfare"
    ]
    return render_template("categories.html", categories=category_list)


# ---- CATEGORY ALERTS / DETAILS ----
@app.route("/category/<name>")
def category_page(name):
    if "user_id" not in session:
        return redirect(url_for("login"))
    cat_key = name.lower()
    # normalize alias keys like 'loan' -> 'loan finance'
    # try find best match
    if cat_key not in schemes_db:
        # attempt simple mapping
        for key in schemes_db:
            if key in cat_key or cat_key in key:
                cat_key = key
                break

    data = schemes_db.get(cat_key)
    if not data:
        # if no data found, show empty
        data = {"schemes": [], "amount": "", "apply": "", "date": "", "alerts": []}

    return render_template("category_alerts.html", cat_key=cat_key, data=data)


# ---- CHATBOT PAGE (renders UI) ----
@app.route("/chatbot")
def chatbot():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # load user's previous search history
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT question, reply, timestamp FROM searches WHERE user_id = ? ORDER BY timestamp ASC",
        (session["user_id"],)
    )
    history = cur.fetchall()
    # convert rows to simple dicts for template
    history_list = [{"question": r["question"], "reply": r["reply"], "timestamp": r["timestamp"]} for r in history]

    return render_template("chatbot.html", history=history_list)


# ---- CHATBOT API endpoint (front-end can POST user messages and get JSON reply) ----
@app.route("/chatbot_api", methods=["POST"])
def chatbot_api():
    """
    Expected JSON:
    { "message": "user message string" }
    Response:
    { "reply": "text reply", "category": "student" (optional) }
    """
    payload = request.get_json(force=True, silent=True)
    if not payload or "message" not in payload:
        return jsonify({"error": "invalid request"}), 400

    user_message = payload["message"].strip()
    if user_message == "":
        return jsonify({"reply": "Please type a question."})

    # detect category
    category = detect_category_from_text(user_message)
    reply = ""
    if category:
        # store last asked category in session for follow-ups
        session["last_category"] = category
        d = schemes_db.get(category, {})
        # same format as before
        reply = f"Here are schemes for *{category}*:\n• " + "\n• ".join(d.get("schemes", []))
    else:
        # follow-up intent detection (amount/apply/date etc.)
        last_cat = session.get("last_category")
        lm = user_message.lower()
        if "amount" in lm or "how much" in lm or "how much amount" in lm:
            if last_cat:
                reply = schemes_db.get(last_cat, {}).get("amount", "Amount details not available.")
            else:
                reply = "Please ask about a category first (e.g., 'student schemes')."
        elif "apply" in lm or "how to apply" in lm:
            if last_cat:
                reply = schemes_db.get(last_cat, {}).get("apply", "Apply details not available.")
            else:
                reply = "Please specify which category you mean (student, farmer, etc.)."
        elif "date" in lm or "last date" in lm or "deadline" in lm:
            if last_cat:
                # IMPORTANT: previously returned single date; keep behavior but store full
                reply = schemes_db.get(last_cat, {}).get("date", "Date information not available.")
            else:
                reply = "Please specify which scheme or category you mean."
        else:
            # fallback: give helpful suggestion
            reply = ("Sorry, I didn't understand that. Try asking like:\n"
                     "'Tell me student schemes' or 'How to apply for PM Kisan' or 'Amount for student scholarships'.")

    # Persist the search (if user logged in)
    user_id = session.get("user_id")
    if user_id:
        db = get_db()
        cur = db.cursor()
        now = datetime.utcnow().isoformat()
        cur.execute(
            "INSERT INTO searches (user_id, question, reply, category, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, user_message, reply, category, now)
        )
        db.commit()

    return jsonify({"reply": reply, "category": category})


# ---- ADMIN / ACCOUNT / FAMILY INFO ROUTES ----

@app.route("/account")
def account():
    """Show logged-in user's basic account info and family counts (by email domain)."""
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    user_id = session["user_id"]

    # user info
    cur.execute("SELECT id, name, email, phone, signup_date, last_login FROM users WHERE id = ?", (user_id,))
    user = cur.fetchone()

    # family by email domain: extract domain of current user and count users with same domain
    email = user["email"] if user else ""
    domain = ""
    family_count = 1
    if "@" in email:
        domain = email.split("@", 1)[1]
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE email LIKE ?", (f"%@{domain}",))
        family_count = cur.fetchone()["cnt"]

    # total number of registered users
    cur.execute("SELECT COUNT(*) as cnt FROM users")
    total_users = cur.fetchone()["cnt"]

    # last 10 login records for this user
    cur.execute("SELECT login_time, logout_time, ip FROM logins WHERE user_id = ? ORDER BY login_time DESC LIMIT 10", (user_id,))
    login_history = cur.fetchall()

    return render_template(
        "account.html",
        user=user,
        domain=domain,
        family_count=family_count,
        total_users=total_users,
        login_history=login_history
    )


@app.route("/all_users")
def all_users():
    """(Optional) Admin-style page showing all users and their domains."""
    # NOTE: In production, restrict with admin check
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, name, email, phone, signup_date, last_login FROM users ORDER BY signup_date ASC")
    rows = cur.fetchall()
    # compute domain counts
    domain_counts = {}
    for r in rows:
        em = r["email"]
        dom = em.split("@", 1)[1] if "@" in em else ""
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
    return render_template("all_users.html", users=rows, domain_counts=domain_counts)


# -------------------- STATIC RUN --------------------
if __name__ == "__main__":
    # debug True for development only
    app.run(debug=True)
