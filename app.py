import os
import re
import json
import sqlite3
import hashlib
import base64
import datetime
import io
import time
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from gtts import gTTS

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

OWNER_USERNAME = "utkarsh"
OWNER_EMAIL = "utkarsh0510w77@gmail.com"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", OWNER_EMAIL)
SMTP_PASS = os.getenv("SMTP_PASS", "")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://lemon_db_7jr5_user:fCnr4Ag4rcayvFbgZcxeRW02ROKFnm8A@dpg-db4e0i3l550s73besfpg-a.oregon-postgres.render.com/lemon_db_7jr5"
)

app = FastAPI(title="Lemon AI - Study Supercharged Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OTP_STORE = {}

def send_otp_email(to_email: str, otp: str) -> bool:
    if not SMTP_PASS:
        print(f"\n[DEV OTP ALERT] No SMTP_PASS set in environment. Master OTP for {to_email} is: {otp}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🍋 Lemon AI Sovereign Passkey: {otp}"
        msg["From"] = f"Lemon AI Core <{SMTP_USER}>"
        msg["To"] = to_email

        html_body = f"""
        <div style="font-family:'Segoe UI',sans-serif; background:#070a14; color:#f1f5f9; padding:28px; border-radius:16px; border:1px solid rgba(250,204,21,0.3); max-width:460px; margin:auto;">
            <h2 style="color:#facc15; margin:0 0 10px 0;">🍋 Lemon AI Sovereign Passkey</h2>
            <p style="color:#94a3b8; font-size:14px; margin-bottom:18px;">Master identity verification requested for <b>{to_email}</b>.</p>
            <div style="background:#0f172a; border:2px dashed #facc15; padding:16px; text-align:center; border-radius:12px; margin-bottom:18px;">
                <span style="font-size:32px; font-weight:800; letter-spacing:8px; color:#fde047;">{otp}</span>
            </div>
            <p style="color:#64748b; font-size:12px;">Valid for 5 minutes. Master developer bypass (778899) is also recognized.</p>
        </div>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True
    except Exception as e:
        print("[SMTP Error]:", e)
        return False

class DBManager:
    @staticmethod
    def get_conn():
        if POSTGRES_AVAILABLE and DATABASE_URL:
            try:
                url = DATABASE_URL
                if url.startswith("postgres://"):
                    url = url.replace("postgres://", "postgresql://", 1)
                conn = psycopg2.connect(url, connect_timeout=4, sslmode="require")
                return conn, "postgres"
            except Exception:
                pass
        conn = sqlite3.connect("lemon_data.db", timeout=25)
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn, "sqlite"

def init_db():
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        if engine == "postgres":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(50) DEFAULT 'user',
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS site_stats (key VARCHAR(100) PRIMARY KEY, value BIGINT DEFAULT 0);
                INSERT INTO site_stats (key, value) VALUES ('total_visits', 0) ON CONFLICT (key) DO NOTHING;
                CREATE TABLE IF NOT EXISTS announcements (id SERIAL PRIMARY KEY, message TEXT NOT NULL, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS sessions (id SERIAL PRIMARY KEY, user_id INT NOT NULL, title VARCHAR(255) NOT NULL, core_mode VARCHAR(50) DEFAULT 'study', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (id SERIAL PRIMARY KEY, session_id INT NOT NULL, role VARCHAR(50) NOT NULL, content TEXT NOT NULL, mode VARCHAR(50) NOT NULL, emotion VARCHAR(100), image_data TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS complaints (id SERIAL PRIMARY KEY, user_id INT NOT NULL, username VARCHAR(255) NOT NULL, category VARCHAR(100) NOT NULL, message TEXT NOT NULL, image_proof TEXT, status VARCHAR(50) DEFAULT 'Open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS site_stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0);
                INSERT OR IGNORE INTO site_stats (key, value) VALUES ('total_visits', 0);
                CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, core_mode TEXT NOT NULL DEFAULT 'study', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT NOT NULL, emotion TEXT, image_data TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS complaints (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT NOT NULL, category TEXT NOT NULL, message TEXT NOT NULL, image_proof TEXT, status TEXT DEFAULT 'Open', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            """)
        conn.commit()
    finally:
        conn.close()

init_db()

def hash_password(password: str) -> str:
    return hashlib.sha256((password + "lemon_permanent_salt_2026").encode('utf-8')).hexdigest()

def record_visit():
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE site_stats SET value = value + 1 WHERE key = 'total_visits'")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

def update_user_heartbeat(user_id: int):
    if not user_id or user_id <= 0:
        return
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = %s" if engine == "postgres" else "UPDATE users SET last_active = CURRENT_TIMESTAMP WHERE id = ?"
        cur.execute(sql, (user_id,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

STUDY_CORE_METAPROMPT = (
    "You are Lemon — an ultra-intellectual academic mentor and first-principles study engine engineered by Utkarsh Bandhu. "
    "Your mission is to make students thoroughly master competitive concepts (NEET/JEE, Physics derivations, Organic mechanisms, Biology facts). "
    "RULES OF RESPONSE: "
    "1. Explain via First Principles & the Feynman Technique (crisp, intuitive, zero hollow definitions). "
    "2. If an image or written solution is supplied: find the EXACT point where arithmetic, sign conversion, or concept broke. Provide the clean, correct derivation. "
    "3. Highlight High-Yield NCERT points, examiner trap traps, and memory mnemonics. "
    "4. Natural conversational tone: if user uses Hinglish, speak in fluid, razor-sharp, inspiring Hinglish. If English, speak with profound academic articulation."
)

PROMPT_MODES = {
    "study": f"CHAMBER: SOKRATIC ACADEMIC TUTOR & NEET/JEE ENGINE. {STUDY_CORE_METAPROMPT} Focus on conceptual clarity, derivations, and exam mastery.",
    "solver": f"CHAMBER: FIRST-PRINCIPLES NUMERICAL SOLVER. {STUDY_CORE_METAPROMPT} Break down numericals step-by-step with zero skipped calculations.",
    "recall": f"CHAMBER: ACTIVE RECALL & RAPID MCQ DRILL. {STUDY_CORE_METAPROMPT} Drill the user with high-yield questions, verify their answers, highlight traps.",
    "intellect": f"CHAMBER: PURE INTELLECT & EPISTEMIC COGNITION. {STUDY_CORE_METAPROMPT} High-level scientific philosophy and deep cognitive reasoning.",
    "rage": f"CHAMBER: UNCOMPROMISING WARRIOR RIGOR. {STUDY_CORE_METAPROMPT} Crush excuses, eliminate exam procrastination, demand daily consistent execution.",
    "zen": f"CHAMBER: SOMATIC ZEN & EXAM STRESS RELIEF. {STUDY_CORE_METAPROMPT} Decompress mental anxiety, ground attention, restore intellectual clarity."
}

def generate_ai_title(prompt: str, core: str) -> str:
    try:
        res = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Generate a concise 3 word topic title. Return ONLY text with no quotes."},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            max_tokens=20,
            temperature=0.3
        )
        if res.choices and res.choices[0].message.content:
            return res.choices[0].message.content.strip().replace('"', '')[:35]
    except Exception:
        pass
    return f"{core.capitalize()} Session"

def ask_groq_vision_or_llm(user_prompt: str, mode: str, history: list, image_base64: str = None) -> tuple[str, str]:
    instruction = PROMPT_MODES.get(mode, PROMPT_MODES["study"]) + (
        "\nOUTPUT RULE: Line 1 MUST strictly be [EMOTION: <SingleWord>]. "
        "Eligible: Analytical, Insightful, Illuminating, Formidable, Unyielding, Serene, Brilliant."
    )

    clean_image = None
    if image_base64 and isinstance(image_base64, str) and len(image_base64) > 100:
        clean_image = image_base64 if image_base64.startswith("data:image") else f"data:image/jpeg;base64,{image_base64}"

    if clean_image:
        vision_models = ["qwen/qwen3.8-27b", "meta-llama/llama-4-scout-17b-16e-instruct"]
        prompt_text = user_prompt if (user_prompt and len(user_prompt.strip()) > 0) else "Audit this handwritten note, equation or diagram line-by-line and identify all flaws."
        user_content = [
            {"type": "text", "text": f"{instruction}\n\nTask:\n{prompt_text}"},
            {"type": "image_url", "image_url": {"url": clean_image}}
        ]
        for vm in vision_models:
            try:
                chat = client.chat.completions.create(
                    messages=[{"role": "user", "content": user_content}],
                    model=vm,
                    max_tokens=2048,
                    temperature=0.25
                )
                if chat.choices and chat.choices[0].message.content:
                    raw = chat.choices[0].message.content.strip()
                    emotion = "Illuminating"
                    match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw, re.IGNORECASE)
                    if match:
                        emotion = match.group(1).capitalize()
                        raw = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw).strip()
                    return raw, emotion
            except Exception:
                continue
        return "Visual transmission anomaly. Please re-supply image.", "Formidable"

    text_models = ["llama-3.1-8b-instant", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    messages = [{"role": "system", "content": instruction}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_prompt})

    for tm in text_models:
        try:
            chat = client.chat.completions.create(
                messages=messages,
                model=tm,
                max_tokens=2048,
                temperature=0.35
            )
            if chat.choices and chat.choices[0].message.content:
                raw = chat.choices[0].message.content.strip()
                emotion = "Insightful"
                match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw, re.IGNORECASE)
                if match:
                    emotion = match.group(1).capitalize()
                    raw = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw).strip()
                return raw, emotion
        except Exception:
            continue
    return "Cognitive process desynchronized.", "Serene"

# ----------------- OWNER OTP AUTHENTICATION -----------------
@app.post("/api/owner/request-otp")
def request_owner_otp(email: str = Form(...)):
    email_clean = email.strip().lower()
    if email_clean != OWNER_EMAIL.lower():
        return JSONResponse({"status": "error", "message": f"Unauthorized. Only {OWNER_EMAIL} can request Sovereign OTP."}, status_code=403)

    otp = f"{random.randint(100000, 999999)}"
    OTP_STORE[email_clean] = {"otp": otp, "expires_at": time.time() + 300}

    sent = send_otp_email(email_clean, otp)
    return JSONResponse({
        "status": "ok",
        "message": f"OTP transmitted to {email_clean}. (Dev master key: 778899 active)",
        "dev_code": otp if not SMTP_PASS else None
    })

@app.post("/api/owner/verify-otp")
def verify_owner_otp(email: str = Form(...), otp: str = Form(...)):
    email_clean = email.strip().lower()
    otp_clean = otp.strip()

    if otp_clean == "778899":
        return JSONResponse({"status": "ok", "token": "SOVEREIGN_AUTH_UTKARSH_OK", "username": OWNER_USERNAME})

    record = OTP_STORE.get(email_clean)
    if not record:
        return JSONResponse({"status": "error", "message": "OTP not found. Tap 'Send OTP' first."}, status_code=400)

    if time.time() > record["expires_at"]:
        OTP_STORE.pop(email_clean, None)
        return JSONResponse({"status": "error", "message": "OTP expired."}, status_code=400)

    if record["otp"] != otp_clean:
        return JSONResponse({"status": "error", "message": "Incorrect OTP."}, status_code=401)

    OTP_STORE.pop(email_clean, None)
    return JSONResponse({"status": "ok", "token": "SOVEREIGN_AUTH_UTKARSH_OK", "username": OWNER_USERNAME})

# ----------------- AUTH APIS -----------------
@app.post("/api/register")
def register_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    if not username or len(password) < 3:
        return JSONResponse({"status": "error", "message": "Username and password required."}, status_code=400)

    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        pwd_hash = hash_password(password)
        user_role = "owner" if username == OWNER_USERNAME.lower() else "user"
        if engine == "postgres":
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s) RETURNING id", (username, pwd_hash, user_role))
            user_id = cur.fetchone()[0]
        else:
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", (username, pwd_hash, user_role))
            user_id = cur.lastrowid
        conn.commit()
        return JSONResponse({"status": "ok", "user_id": user_id, "username": username, "role": user_role})
    except Exception as e:
        if "unique" in str(e).lower():
            return JSONResponse({"status": "error", "message": "Username already taken."}, status_code=400)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        conn.close()

@app.post("/api/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    pwd_hash = hash_password(password)

    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT id, username, role FROM users WHERE username = %s AND password_hash = %s" if engine == "postgres" else "SELECT id, username, role FROM users WHERE username = ? AND password_hash = ?"
        cur.execute(sql, (username, pwd_hash))
        user = cur.fetchone()
        if user:
            user_role = "owner" if username == OWNER_USERNAME.lower() else user[2]
            return JSONResponse({"status": "ok", "user_id": user[0], "username": user[1], "role": user_role})
        return JSONResponse({"status": "error", "message": "Invalid credentials."}, status_code=401)
    finally:
        conn.close()

@app.post("/api/heartbeat")
def heartbeat(user_id: int = Form(...)):
    update_user_heartbeat(user_id)
    return JSONResponse({"status": "ok"})

@app.get("/api/announcement")
def get_announcement():
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT message FROM announcements WHERE is_active = TRUE ORDER BY id DESC LIMIT 1" if engine == "postgres" else "SELECT message FROM announcements WHERE is_active = 1 ORDER BY id DESC LIMIT 1"
        cur.execute(sql)
        row = cur.fetchone()
        return JSONResponse({"message": row[0] if row else ""})
    finally:
        conn.close()

@app.get("/api/sessions/{user_id}")
def get_user_sessions(user_id: int):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT id, title, core_mode, created_at FROM sessions WHERE user_id = %s ORDER BY id DESC" if engine == "postgres" else "SELECT id, title, core_mode, created_at FROM sessions WHERE user_id = ? ORDER BY id DESC"
        cur.execute(sql, (user_id,))
        rows = cur.fetchall()
        return JSONResponse({"sessions": [{"id": r[0], "title": r[1], "core_mode": r[2], "created_at": str(r[3])} for r in rows]})
    finally:
        conn.close()

@app.get("/api/session-messages/{session_id}")
def get_session_messages(session_id: int):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT role, content, mode, emotion, image_data, timestamp FROM messages WHERE session_id = %s ORDER BY id ASC" if engine == "postgres" else "SELECT role, content, mode, emotion, image_data, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC"
        cur.execute(sql, (session_id,))
        rows = cur.fetchall()
        return JSONResponse({"messages": [{"role": r[0], "content": r[1], "mode": r[2], "emotion": r[3], "image_data": r[4], "timestamp": str(r[5])} for r in rows]})
    finally:
        conn.close()

@app.post("/api/new-core-session")
def new_core_session(user_id: int = Form(...), core_mode: str = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        title = f"{core_mode.capitalize()} Session"
        if engine == "postgres":
            cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (%s, %s, %s) RETURNING id", (user_id, title, core_mode))
            session_id = cur.fetchone()[0]
        else:
            cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (?, ?, ?)", (user_id, title, core_mode))
            session_id = cur.lastrowid
        conn.commit()
        return JSONResponse({"status": "ok", "session_id": session_id, "title": title, "core_mode": core_mode})
    finally:
        conn.close()

@app.post("/api/delete-session")
def delete_session(session_id: int = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM messages WHERE session_id = %s" if engine == "postgres" else "DELETE FROM messages WHERE session_id = ?", (session_id,))
        cur.execute("DELETE FROM sessions WHERE id = %s" if engine == "postgres" else "DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return JSONResponse({"status": "ok"})
    finally:
        conn.close()

@app.post("/api/parse-doc")
async def parse_doc(file: UploadFile = File(...)):
    filename = file.filename.lower()
    content_bytes = await file.read()
    extracted_text = ""

    if filename.endswith(".pdf") and PYPDF_AVAILABLE:
        try:
            reader = PdfReader(io.BytesIO(content_bytes))
            for page in reader.pages[:12]:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception:
            pass
    else:
        try:
            extracted_text = content_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

    extracted_text = extracted_text.strip()[:8000]
    return JSONResponse({"status": "ok", "filename": file.filename, "text": extracted_text})

# ----------------- OWNER TELEMETRY -----------------
@app.get("/api/owner/telemetry")
def get_owner_telemetry(token: str = ""):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT value FROM site_stats WHERE key = 'total_visits'")
        v_row = cur.fetchone()
        total_visits = v_row[0] if v_row else 0

        cur.execute("SELECT id, username, role, last_active, created_at FROM users ORDER BY id DESC")
        users_list = [{"id": u[0], "username": u[1], "role": u[2], "last_active": str(u[3]), "created_at": str(u[4])} for u in cur.fetchall()]

        if engine == "postgres":
            cur.execute("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '15 minutes'")
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE datetime(last_active) >= datetime('now', '-15 minutes')")
        online_count = cur.fetchone()[0]

        cur.execute("SELECT id, username, category, message, image_proof, status, created_at FROM complaints ORDER BY id DESC")
        complaints_list = [{"id": r[0], "username": r[1], "category": r[2], "message": r[3], "image_proof": r[4], "status": r[5] or "Open", "created_at": str(r[6])} for r in cur.fetchall()]

        cur.execute("SELECT core_mode, COUNT(*) FROM sessions GROUP BY core_mode")
        core_dist = {r[0]: r[1] for r in cur.fetchall()}

        cur.execute("SELECT COUNT(*) FROM messages")
        total_messages = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cur.fetchone()[0]

        return JSONResponse({
            "status": "ok",
            "database_engine": engine,
            "total_visits": total_visits,
            "total_users": len(users_list),
            "online_users": online_count,
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "core_distribution": core_dist,
            "users": users_list,
            "complaints": complaints_list
        })
    finally:
        conn.close()

def detect_tts_language(text: str) -> str:
    devanagari = re.search(r'[\u0900-\u097F]', text)
    if devanagari:
        return "hi"
    hinglish_markers = ["hai", "hoon", "aap", "kaise", "kya", "bhai", "karo", "nahi", "accha", "samjha", "dost", "mera", "meri", "hum", "sahi", "galat"]
    words = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
    if len(words.intersection(hinglish_markers)) >= 2:
        return "hi"
    return "en"

def handle_conversation(user_id: int, session_id: int, query: str, mode: str, image_base64: str = None):
    update_user_heartbeat(user_id)
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()

    try:
        user_check = "SELECT id FROM users WHERE id = %s" if engine == "postgres" else "SELECT id FROM users WHERE id = ?"
        cur.execute(user_check, (user_id,))
        if not cur.fetchone():
            if engine == "postgres":
                cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id", (f"user_{user_id}", "guest_pwd"))
                user_id = cur.fetchone()[0]
            else:
                cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (f"user_{user_id}", "guest_pwd"))
                user_id = cur.lastrowid
            conn.commit()

        if not session_id or session_id <= 0:
            title = generate_ai_title(query if query else "Study Analysis", mode)
            if engine == "postgres":
                cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (%s, %s, %s) RETURNING id", (user_id, title, mode))
                session_id = cur.fetchone()[0]
            else:
                cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (?, ?, ?)", (user_id, title, mode))
                session_id = cur.lastrowid
            conn.commit()
        else:
            s_check = "SELECT title, core_mode FROM sessions WHERE id = %s" if engine == "postgres" else "SELECT title, core_mode FROM sessions WHERE id = ?"
            cur.execute(s_check, (session_id,))
            row = cur.fetchone()
            if row:
                title, mode = row[0], row[1]
            else:
                title = generate_ai_title(query if query else "Study Analysis", mode)
                if engine == "postgres":
                    cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (%s, %s, %s) RETURNING id", (user_id, title, mode))
                    session_id = cur.fetchone()[0]
                else:
                    cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (?, ?, ?)", (user_id, title, mode))
                    session_id = cur.lastrowid
                conn.commit()

        clean = query.lower().strip() if query else ""
        creator_triggers = ["who made you", "who created you", "who is your creator", "maker", "developer", "kisne banaya", "utkarsh"]
        if any(trigger in clean for trigger in creator_triggers):
            reply = "I was engineered by Utkarsh Bandhu. He conceptualized and developed my cognitive architecture, instilling my first-principles problem-solving rigor."
            emotion = "Brilliant"
        else:
            h_sql = "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT 8" if engine == "postgres" else "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 8"
            cur.execute(h_sql, (session_id,))
            past_rows = cur.fetchall()
            history = [{"role": r[0], "content": r[1]} for r in reversed(past_rows)]
            reply, emotion = ask_groq_vision_or_llm(query, mode, history, image_base64)

        ins_m = "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_m, (session_id, 'user', query if query else "[Study Artifact Uploaded]", mode, image_base64))
        
        ins_a = "INSERT INTO messages (session_id, role, content, mode, emotion) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, emotion) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_a, (session_id, 'assistant', reply, mode, emotion))
        conn.commit()
    finally:
        conn.close()

    audio_base64 = None
    try:
        speech_clean = re.sub(r'[*#|_>`]', '', reply)
        speech_clean = re.sub(r'\n+', ' ', speech_clean).strip()
        tts_lang = detect_tts_language(speech_clean)
        spoken_snippet = speech_clean[:650]
        reply_audio = "app_reply.mp3"
        tts = gTTS(text=spoken_snippet, lang=tts_lang, slow=False)
        tts.save(reply_audio)
        with open(reply_audio, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        audio_base64 = f"data:audio/mp3;base64,{audio_b64}"
    except Exception:
        pass

    return reply, emotion, session_id, title, mode, audio_base64

@app.post("/text-process")
async def text_process(
    text: str = Form(""),
    user_id: str = Form("1"),
    session_id: str = Form("0"),
    mode: str = Form("study"),
    image_base64: str = Form(None)
):
    u_id = int(user_id) if str(user_id).isdigit() else 1
    s_id = int(session_id) if str(session_id).isdigit() else 0
    img = image_base64 if (image_base64 and image_base64 != "null" and len(image_base64.strip()) > 50) else None

    reply_text, emotion, res_s_id, title, cur_mode, audio_base64 = handle_conversation(u_id, s_id, text, mode, img)
    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": res_s_id,
        "title": title,
        "mode": cur_mode,
        "audio_base64": audio_base64
    })

@app.post("/voice-process")
async def voice_process(
    file: UploadFile = File(...),
    user_id: str = Form("1"),
    session_id: str = Form("0"),
    mode: str = Form("study"),
    image_base64: str = Form(None)
):
    u_id = int(user_id) if str(user_id).isdigit() else 1
    s_id = int(session_id) if str(session_id).isdigit() else 0
    img = image_base64 if (image_base64 and image_base64 != "null" and len(image_base64.strip()) > 50) else None

    temp_audio = "app_input.wav"
    with open(temp_audio, "wb") as f:
        f.write(await file.read())

    user_text = ""
    try:
        with open(temp_audio, "rb") as f:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                response_format="text"
            )
            user_text = str(transcription).strip()
    except Exception:
        pass

    reply_text, emotion, res_s_id, title, cur_mode, audio_base64 = handle_conversation(u_id, s_id, user_text, mode, img)
    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": res_s_id,
        "title": title,
        "mode": cur_mode,
        "audio_base64": audio_base64
    })

@app.post("/read-aloud")
async def read_aloud(text: str = Form(...)):
    speech_clean = re.sub(r'[*#|_>`]', '', text)
    speech_clean = re.sub(r'\n+', ' ', speech_clean).strip()
    tts_lang = detect_tts_language(speech_clean)
    reply_audio = "single_reply.mp3"
    tts = gTTS(text=speech_clean[:700], lang=tts_lang, slow=False)
    tts.save(reply_audio)
    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
    return JSONResponse({"audio_base64": f"data:audio/mp3;base64,{audio_b64}"})

# =====================================================================
# 🛡️ SOVEREIGN OWNER OTP CONSOLE: /owner
# =====================================================================
@app.get("/owner", response_class=HTMLResponse)
async def serve_owner_dashboard():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Lemon AI | Sovereign Command (Utkarsh OTP Protected)</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {{
                --gold: #facc15;
                --gold-glow: rgba(250, 204, 21, 0.4);
                --bg-deep: #05070f;
                --card: rgba(14, 20, 36, 0.94);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-high: #f8fafc;
                --text-muted: #94a3b8;
            }}
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }}
            body {{ background: radial-gradient(circle at 50% 0%, #151b3d 0%, var(--bg-deep) 85%); color: var(--text-high); min-height: 100vh; display: flex; flex-direction: column; }}

            .owner-nav {{
                padding: 16px 28px; background: rgba(9, 13, 24, 0.9); backdrop-filter: blur(20px); border-bottom: 1px solid var(--card-border);
                display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100;
            }}
            .brand {{ display: flex; align-items: center; gap: 12px; }}
            .brand-badge {{ width: 42px; height: 42px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; }}
            .brand-title {{ font-size: 17px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; }}
            .brand-sub {{ font-size: 11px; color: var(--text-muted); }}

            .container {{ padding: 28px; max-width: 1280px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }}

            .metrics-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }}
            .metric-card {{
                background: var(--card); border: 1px solid var(--card-border); border-radius: 20px; padding: 20px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.5); position: relative; overflow: hidden;
            }}
            .metric-title {{ font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px; }}
            .metric-value {{ font-size: 32px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; color: #fff; }}
            .metric-tag {{ font-size: 11px; color: #fde047; margin-top: 6px; font-weight: 600; }}

            .panel {{ background: var(--card); border: 1px solid var(--card-border); border-radius: 22px; padding: 22px; }}
            .search-input {{
                width: 100%; background: rgba(22, 30, 50, 0.8); border: 1px solid var(--card-border);
                border-radius: 12px; padding: 10px 14px; color: #fff; font-size: 13px; outline: none; margin-bottom: 8px;
            }}
            .table-container {{ max-height: 400px; overflow-y: auto; }}
            table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
            th {{ text-align: left; padding: 10px 8px; color: var(--text-muted); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.08); position: sticky; top: 0; background: #0e1424; }}
            td {{ padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }}

            .otp-modal {{ position: fixed; inset: 0; background: rgba(4,6,12,0.96); backdrop-filter: blur(25px); display: flex; align-items: center; justify-content: center; z-index: 500; }}
            .otp-box {{ background: #0c1222; border: 1px solid rgba(250,204,21,0.3); border-radius: 24px; padding: 32px; width: 90%; max-width: 400px; text-align: center; }}
            .action-btn {{ width: 100%; background: linear-gradient(135deg, #facc15, #f59e0b); border: none; border-radius: 12px; padding: 12px; color: #000; font-weight: 700; cursor: pointer; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="otp-modal" id="ownerOtpGate">
            <div class="otp-box">
                <div style="font-size:38px; margin-bottom:8px;">🛡️</div>
                <h2 style="font-family:'Space Grotesk'; font-size:20px; margin-bottom:6px;">Sovereign OTP Access</h2>
                <p style="font-size:12.5px; color:var(--text-muted); margin-bottom:14px;">Master Email: <b>{OWNER_EMAIL}</b></p>
                <div id="otpStatusMsg" style="font-size:12px; color:#4ade80; margin-bottom:10px;">Click below to dispatch OTP to your email.</div>
                
                <button class="action-btn" id="reqOtpBtn" onclick="requestOtp()">📩 Send OTP to My Gmail</button>

                <div id="otpInputArea" style="display:none; margin-top:16px;">
                    <input type="text" id="otpCodeInput" class="search-input" placeholder="Enter 6-digit OTP (or bypass 778899)" maxlength="6" style="text-align:center; font-size:18px; letter-spacing:4px;" />
                    <button class="action-btn" onclick="verifyOtp()">Unlock Sovereign Console</button>
                </div>
                <div id="otpErrMsg" style="color:#f87171; font-size:12px; margin-top:10px; display:none;"></div>
            </div>
        </div>

        <header class="owner-nav">
            <div class="brand">
                <div class="brand-badge">🍋</div>
                <div>
                    <div class="brand-title">Lemon Sovereign Command</div>
                    <div class="brand-sub">Master: <b>Utkarsh Bandhu ({OWNER_EMAIL})</b></div>
                </div>
            </div>
            <button onclick="location.href='/'" style="background:rgba(255,255,255,0.08); border:1px solid var(--card-border); color:#fff; padding:6px 14px; border-radius:14px; font-size:12px; cursor:pointer;">← Return to App</button>
        </header>

        <main class="container">
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Visits</div>
                    <div class="metric-value" id="valVisits">0</div>
                    <div class="metric-tag">● Persistent Hit Counter</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Registered Students</div>
                    <div class="metric-value" id="valUsers">0</div>
                    <div class="metric-tag">● Safe in DB</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Live Active Users</div>
                    <div class="metric-value" id="valOnline" style="color:#4ade80;">0</div>
                    <div class="metric-tag">● Active last 15 min</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Study Sessions</div>
                    <div class="metric-value" id="valSessions">0</div>
                    <div class="metric-tag">● Discussions Created</div>
                </div>
            </div>

            <div class="panel">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                    <h3 style="font-size:15px; color:#facc15;">👥 Registered Students Registry</h3>
                    <button onclick="loadTelemetry()" style="background:none; border:none; color:var(--gold); font-size:12px; cursor:pointer;">↻ Refresh</button>
                </div>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr><th>ID</th><th>Username</th><th>Role</th><th>Last Active</th></tr>
                        </thead>
                        <tbody id="usersTbody">
                            <tr><td colspan="4" style="text-align:center;">Loading telemetry...</td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </main>

        <script>
            let currentToken = localStorage.getItem("lemon_owner_token");

            async function requestOtp() {{
                const btn = document.getElementById("reqOtpBtn");
                btn.innerText = "Transmitting OTP...";
                const fd = new FormData();
                fd.append("email", "{OWNER_EMAIL}");
                try {{
                    const res = await fetch("/api/owner/request-otp", {{ method: "POST", body: fd }});
                    const d = await res.json();
                    document.getElementById("otpStatusMsg").innerText = d.message;
                    document.getElementById("otpInputArea").style.display = "block";
                    btn.innerText = "Re-send OTP";
                }} catch(e) {{
                    document.getElementById("otpErrMsg").innerText = "Failed to request OTP.";
                    document.getElementById("otpErrMsg").style.display = "block";
                }}
            }}

            async function verifyOtp() {{
                const code = document.getElementById("otpCodeInput").value.trim();
                const err = document.getElementById("otpErrMsg");
                const fd = new FormData();
                fd.append("email", "{OWNER_EMAIL}");
                fd.append("otp", code);

                try {{
                    const res = await fetch("/api/owner/verify-otp", {{ method: "POST", body: fd }});
                    const d = await res.json();
                    if (res.ok && d.status === "ok") {{
                        currentToken = d.token;
                        localStorage.setItem("lemon_owner_token", currentToken);
                        document.getElementById("ownerOtpGate").style.display = "none";
                        loadTelemetry();
                    }} else {{
                        err.innerText = d.message || "Invalid OTP code.";
                        err.style.display = "block";
                    }}
                }} catch(e) {{
                    err.innerText = "Verification fault.";
                    err.style.display = "block";
                }}
            }}

            async function loadTelemetry() {{
                try {{
                    const res = await fetch("/api/owner/telemetry?token=" + currentToken);
                    const d = await res.json();
                    if (d.status === "ok") {{
                        document.getElementById("ownerOtpGate").style.display = "none";
                        document.getElementById("valVisits").innerText = d.total_visits;
                        document.getElementById("valUsers").innerText = d.total_users;
                        document.getElementById("valOnline").innerText = d.online_users;
                        document.getElementById("valSessions").innerText = d.total_sessions;

                        const tbody = document.getElementById("usersTbody");
                        tbody.innerHTML = (d.users || []).map(u => `
                            <tr>
                                <td>${{u.id}}</td>
                                <td><b>${{u.username}}</b></td>
                                <td style="color:${{u.role === 'owner' ? '#facc15' : '#94a3b8'}};">${{u.role}}</td>
                                <td style="color:#38bdf8;">${{u.last_active || 'Recent'}}</td>
                            </tr>
                        `).join("");
                    }} else {{
                        document.getElementById("ownerOtpGate").style.display = "flex";
                    }}
                }} catch(e) {{}}
            }}

            if (currentToken) loadTelemetry();
        </script>
    </body>
    </html>
    """

# =====================================================================
# 🌐 MAIN USER INTERFACE: / (STUDY & NEET ENGINE COCKPIT)
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_app():
    record_visit()
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Lemon AI | Supercharged Academic & NEET Study Core</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.45);
                --bg-deep: #070913;
                --card-surface: rgba(18, 24, 38, 0.92);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-high: #f8fafc;
                --text-muted: #94a3b8;
                --code-bg: #0d121f;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; -webkit-tap-highlight-color: transparent; }
            html, body { height: 100%; width: 100%; overflow: hidden; position: fixed; }
            body { 
                background: radial-gradient(circle at 50% 0%, #151a3b 0%, var(--bg-deep) 80%); 
                color: var(--text-high); display: flex; flex-direction: column; 
            }

            ::-webkit-scrollbar { width: 14px; height: 14px; }
            ::-webkit-scrollbar-track { background: rgba(12, 16, 28, 0.75); border-left: 1px solid rgba(255, 255, 255, 0.06); }
            ::-webkit-scrollbar-thumb {
                background: linear-gradient(180deg, #facc15 0%, #ca8a04 100%);
                border-radius: 8px; border: 3px solid rgba(12, 16, 28, 0.85);
            }

            .broadcast-banner {
                display: none; background: linear-gradient(90deg, #f59e0b, #ef4444); color: #000; font-size: 12.5px;
                font-weight: 700; text-align: center; padding: 6px 12px; z-index: 1000;
            }

            .header {
                padding: 12px 18px; display: flex; align-items: center; justify-content: space-between;
                backdrop-filter: blur(20px); background: rgba(11, 15, 25, 0.85); border-bottom: 1px solid var(--card-border); z-index: 10;
                flex-shrink: 0;
            }
            .header-left { display: flex; align-items: center; gap: 12px; }
            .menu-trigger {
                width: 38px; height: 38px; border-radius: 10px; background: rgba(255, 255, 255, 0.08);
                border: 1px solid var(--card-border); color: #fff; font-size: 19px; display: flex;
                align-items: center; justify-content: center; cursor: pointer;
            }
            .brand-badge {
                width: 38px; height: 38px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 10px;
                display: flex; align-items: center; justify-content: center; font-size: 20px;
            }
            .brand-title { font-size: 15px; font-weight: 700; }
            .creator-tag { font-size: 11px; color: var(--text-muted); }
            .creator-tag b { color: #facc15; }

            .study-mode-badge {
                background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.35); color: #fde047;
                padding: 5px 12px; border-radius: 18px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
            }

            .quick-study-bar {
                display: flex; gap: 8px; padding: 8px 18px; background: rgba(11, 16, 28, 0.7);
                border-bottom: 1px solid var(--card-border); overflow-x: auto; flex-shrink: 0;
            }
            .study-chip {
                white-space: nowrap; font-size: 11.5px; font-weight: 600; padding: 5px 12px; border-radius: 14px;
                background: rgba(255,255,255,0.06); border: 1px solid var(--card-border); color: #cbd5e1; cursor: pointer;
                transition: all 0.2s;
            }
            .study-chip:hover { background: rgba(250,204,21,0.15); border-color: var(--primary); color: #fde047; }

            .sidebar-overlay {
                position: fixed; inset: 0; background: rgba(5, 7, 15, 0.75); backdrop-filter: blur(10px);
                z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.3s ease;
            }
            .sidebar-overlay.open { opacity: 1; pointer-events: auto; }

            .sidebar {
                position: fixed; top: 0; left: 0; bottom: 0; width: 320px; background: #0c111e;
                border-right: 1px solid var(--card-border); z-index: 1001; transform: translateX(-100%);
                transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column;
                padding: 18px; box-shadow: 10px 0 35px rgba(0,0,0,0.6);
            }
            .sidebar.open { transform: translateX(0); }

            .sidebar-header {
                display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; padding-bottom: 10px;
                border-bottom: 1px solid var(--card-border);
            }
            .sidebar-close { font-size: 20px; color: var(--text-muted); cursor: pointer; border: none; background: none; }

            .core-btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
            .core-choice {
                background: rgba(30, 41, 59, 0.6); border: 1px solid var(--card-border); color: var(--text-muted);
                padding: 8px 6px; border-radius: 10px; font-size: 11.5px; font-weight: 600; cursor: pointer; text-align: center;
            }
            .core-choice.selected { background: var(--primary); color: #0b0f19; font-weight: 700; border-color: var(--primary); }

            .sessions-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
            .session-item {
                display: flex; align-items: center; justify-content: space-between; padding: 9px 12px;
                background: rgba(30, 41, 59, 0.4); border: 1px solid var(--card-border); border-radius: 12px;
                cursor: pointer;
            }
            .session-item.active { background: rgba(250, 204, 21, 0.12); border-color: rgba(250, 204, 21, 0.3); }

            .chat-container {
                flex: 1; overflow-y: scroll; padding: 20px 18px 30px; display: flex; flex-direction: column; gap: 18px; position: relative;
            }

            .hero-greeting {
                margin: auto; display: flex; flex-direction: column; align-items: center; text-align: center; width: 90%; max-width: 540px;
            }
            .hero-logo {
                width: 72px; height: 72px; border-radius: 22px; background: linear-gradient(135deg, #facc15, #f59e0b);
                display: flex; align-items: center; justify-content: center; font-size: 38px;
                box-shadow: 0 10px 32px var(--primary-glow); margin-bottom: 16px;
            }
            .hero-title {
                font-size: 24px; font-weight: 800; font-family: 'Space Grotesk', sans-serif;
                background: linear-gradient(135deg, #ffffff 40%, #facc15 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                margin-bottom: 6px;
            }

            .bubble-group { display: flex; flex-direction: column; max-width: 86%; animation: popIn 0.3s ease; }
            @keyframes popIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

            .bubble-group.lemon { align-self: flex-start; }
            .bubble-group.user { align-self: flex-end; }

            .bubble { padding: 14px 18px; border-radius: 20px; font-size: 14.5px; line-height: 1.65; word-break: break-word; }
            .bubble.lemon {
                background: var(--card-surface); border: 1px solid var(--card-border); color: #f1f5f9; border-bottom-left-radius: 4px;
            }
            .bubble.user {
                background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-weight: 600; border-bottom-right-radius: 4px;
            }

            .chat-img-thumb { max-width: 260px; border-radius: 12px; margin-bottom: 10px; border: 1px solid rgba(255, 255, 255, 0.2); }

            .camera-modal {
                position: fixed; inset: 0; background: rgba(5,7,15,0.95); z-index: 2500;
                display: none; flex-direction: column; align-items: center; justify-content: center; padding: 20px;
            }
            .camera-box {
                background: var(--card-surface); border: 1px solid var(--card-border); border-radius: 20px;
                padding: 18px; width: 100%; max-width: 440px; display: flex; flex-direction: column; align-items: center; gap: 12px;
            }
            .camera-video { width: 100%; height: 260px; border-radius: 14px; background: #000; object-fit: cover; }
            .camera-ctrls { display: flex; gap: 10px; width: 100%; justify-content: center; }

            .bottom-dock {
                padding: 10px 18px 18px; background: rgba(9, 13, 22, 0.94); backdrop-filter: blur(20px); border-top: 1px solid var(--card-border);
                flex-shrink: 0;
            }
            .dock-status { font-size: 11.5px; color: var(--text-muted); text-align: center; margin-bottom: 6px; min-height: 16px; }
            .input-dock {
                display: flex; align-items: center; background: rgba(24, 32, 50, 0.92); border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 36px; padding: 4px 6px 4px 14px; gap: 6px;
            }
            .input-dock input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14.5px; outline: none; }

            .dock-btn {
                width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
            }
            .cam-btn { background: rgba(255, 255, 255, 0.08); color: #38bdf8; font-size: 16px; }
            .doc-btn { background: rgba(255, 255, 255, 0.08); color: #a78bfa; font-size: 16px; }
            .mic-btn { background: rgba(255, 255, 255, 0.08); color: #facc15; font-size: 17px; }
            .stop-btn { display: none; background: #ef4444; color: #fff; font-size: 14px; font-weight: 700; }
            .send-btn { background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-size: 15px; font-weight: 700; }
        </style>
    </head>
    <body>
        <div class="broadcast-banner" id="globalBanner"></div>

        <div class="camera-modal" id="cameraModal">
            <div class="camera-box">
                <h3 style="font-size:16px;">📷 Optical Problem / Note Scanner</h3>
                <video class="camera-video" id="cameraVideo" autoplay playsinline muted></video>
                <canvas id="cameraCanvas" style="display:none;"></canvas>
                <div class="camera-ctrls">
                    <button onclick="captureSnapshot()" style="background:#facc15; color:#000; border:none; padding:10px 18px; border-radius:12px; font-weight:700; cursor:pointer;">📸 Capture</button>
                    <label style="background:rgba(255,255,255,0.08); color:#fff; padding:10px 18px; border-radius:12px; font-weight:600; cursor:pointer;">
                        📁 File
                        <input type="file" id="fileUploadInput" accept="image/*" style="display:none;" onchange="handleFileUpload(event)">
                    </label>
                    <button onclick="closeCamera()" style="background:#ef4444; color:#fff; border:none; padding:10px 18px; border-radius:12px; cursor:pointer;">✕ Close</button>
                </div>
            </div>
        </div>

        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div>
                    <h3 style="font-size:16px;">Study Chambers</h3>
                    <div style="font-size:11px; color:#94a3b8;">Created by <b style="color:#facc15;">Utkarsh Bandhu</b></div>
                </div>
                <button class="sidebar-close" onclick="closeSidebar()">✕</button>
            </div>

            <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; font-weight:700; margin-bottom:8px;">Academic Modes</div>
            <div class="core-btn-grid">
                <button class="core-choice selected" id="core-study" onclick="switchDedicatedChamber('study')">📚 Socratic Study</button>
                <button class="core-choice" id="core-solver" onclick="switchDedicatedChamber('solver')">🧠 Step Solver</button>
                <button class="core-choice" id="core-recall" onclick="switchDedicatedChamber('recall')">🎯 Active Recall</button>
                <button class="core-choice" id="core-rage" onclick="switchDedicatedChamber('rage')">🔥 Rage Focus</button>
                <button class="core-choice" id="core-zen" onclick="switchDedicatedChamber('zen')">🌿 Zen Relax</button>
                <button class="core-choice" id="core-intellect" onclick="switchDedicatedChamber('intellect')">⚡ Deep Intellect</button>
            </div>

            <div style="font-size:11px; text-transform:uppercase; color:#94a3b8; font-weight:700; margin:14px 0 6px;">Saved Study Sessions</div>
            <div class="sessions-list" id="sessionsList"></div>

            <button onclick="location.href='/owner'" style="margin-top:auto; background:rgba(250,204,21,0.15); border:1px solid rgba(250,204,21,0.4); color:#fde047; padding:9px; border-radius:12px; font-weight:700; font-size:12px; cursor:pointer;">🛡️ Sovereign Owner Console</button>
        </aside>

        <header class="header">
            <div class="header-left">
                <button class="menu-trigger" onclick="openSidebar()">☰</button>
                <div class="brand-badge">🍋</div>
                <div>
                    <div class="brand-title">Lemon AI | Study Core</div>
                    <div class="creator-tag">Master: <b>Utkarsh Bandhu</b></div>
                </div>
            </div>
            <div class="study-mode-badge" id="currentChamberBadge">📚 Socratic Study</div>
        </header>

        <div class="quick-study-bar">
            <div class="study-chip" onclick="quickStudyPrompt('Explain this concept using the Feynman Technique and real-life intuition:')">💡 Feynman Intuition</div>
            <div class="study-chip" onclick="quickStudyPrompt('Generate 3 High-Yield NEET/JEE tricky MCQs on this topic with trap explanations:')">🎯 High-Yield MCQs</div>
            <div class="study-chip" onclick="quickStudyPrompt('Identify the exact calculation/formula error in my attached problem step-by-step:')">🔍 Error Diagnostic</div>
            <div class="study-chip" onclick="quickStudyPrompt('Break down the high-yield NCERT points and common traps for this chapter:')">📖 NCERT Traps</div>
        </div>

        <main class="chat-container" id="chatStream">
            <div class="hero-greeting" id="heroGreeting">
                <div class="hero-logo">🍋</div>
                <div class="hero-title">Academic & NEET Engine Ready</div>
                <div style="font-size:13.5px; color:#94a3b8; max-width:440px; margin-bottom:18px;">
                    Snap questions with 📷 camera, upload PDF notes, or pose complex conceptual doubts.
                </div>
            </div>
        </main>

        <footer class="bottom-dock">
            <div class="dock-status" id="dockStatus">● Study Core Synchronized</div>
            <div class="input-dock">
                <button class="dock-btn cam-btn" onclick="requestCameraAccess()" title="Camera Scan">📷</button>
                <label class="dock-btn doc-btn" style="cursor:pointer;" title="Upload PDF/Notes">
                    📄
                    <input type="file" id="docFileInput" accept=".pdf,.txt,.md" style="display:none;" onchange="handleDocFileUpload(event)">
                </label>
                <input type="text" id="textInput" placeholder="Pose a study doubt, derivation, or snap question..." onkeydown="if(event.key==='Enter') sendTextQuery()" />
                <button class="dock-btn mic-btn" id="micBtn" onclick="requestMicAndRecord()" title="Voice Dictation">🎙️</button>
                <button class="dock-btn stop-btn" id="stopBtn" onclick="stopLemonSpeaking()" title="Stop Audio">⏹</button>
                <button class="dock-btn send-btn" onclick="sendTextQuery()" title="Send">➤</button>
            </div>
        </footer>

        <audio id="audioElement" autoplay></audio>

        <script>
            let currentUserId = localStorage.getItem("lemon_user_id") || "1";
            let currentSessionId = parseInt(localStorage.getItem("lemon_current_session_id") || "0");
            let currentCoreMode = "study";
            let attachedImageBase64 = null;
            let cameraStream = null;

            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const dockStatus = document.getElementById("dockStatus");
            const stopBtn = document.getElementById("stopBtn");
            const audioElement = document.getElementById("audioElement");
            const cameraModal = document.getElementById("cameraModal");
            const cameraVideo = document.getElementById("cameraVideo");
            const cameraCanvas = document.getElementById("cameraCanvas");
            const sidebar = document.getElementById("sidebar");

            function quickStudyPrompt(prefix) {
                textInput.value = prefix + " ";
                textInput.focus();
            }

            function stopLemonSpeaking() {
                if (audioElement) { audioElement.pause(); audioElement.currentTime = 0; }
                stopBtn.style.display = "none";
                dockStatus.innerText = "● Stopped vocalization.";
            }
            audioElement.onplay = () => { stopBtn.style.display = "flex"; };
            audioElement.onended = () => { stopBtn.style.display = "none"; };

            async function requestCameraAccess() {
                dockStatus.innerText = "● Initializing optical sensor...";
                cameraModal.style.display = "flex";

                const tryConstraints = [
                    { video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } } },
                    { video: { facingMode: "user" } },
                    { video: true }
                ];

                let streamActive = false;
                for (const c of tryConstraints) {
                    try {
                        cameraStream = await navigator.mediaDevices.getUserMedia(c);
                        cameraVideo.srcObject = cameraStream;
                        streamActive = true;
                        dockStatus.innerText = "● Optical stream active.";
                        break;
                    } catch (e) {}
                }

                if (!streamActive) {
                    alert("Camera access denied or unavailable. You can upload an image file directly.");
                    closeCamera();
                    document.getElementById("fileUploadInput").click();
                }
            }

            function closeCamera() {
                if (cameraStream) {
                    cameraStream.getTracks().forEach(t => t.stop());
                    cameraStream = null;
                }
                cameraModal.style.display = "none";
                dockStatus.innerText = "● Ready";
            }

            function captureSnapshot() {
                if (!cameraVideo.videoWidth) return;
                cameraCanvas.width = cameraVideo.videoWidth;
                cameraCanvas.height = cameraVideo.videoHeight;
                cameraCanvas.getContext("2d").drawImage(cameraVideo, 0, 0);
                attachedImageBase64 = cameraCanvas.toDataURL("image/jpeg", 0.85);
                closeCamera();
                dockStatus.innerText = "● Image captured. Enter query or press ➤ to audit.";
            }

            function handleFileUpload(e) {
                const file = e.target.files[0];
                if (!file) return;
                const r = new FileReader();
                r.onload = (ev) => {
                    attachedImageBase64 = ev.target.result;
                    closeCamera();
                    dockStatus.innerText = "● Problem photo loaded. Press ➤ to analyze.";
                };
                r.readAsDataURL(file);
            }

            async function handleDocFileUpload(e) {
                const file = e.target.files[0];
                if (!file) return;
                dockStatus.innerText = "● Parsing PDF/Document...";
                const fd = new FormData();
                fd.append("file", file);
                try {
                    const res = await fetch("/api/parse-doc", { method: "POST", body: fd });
                    const d = await res.json();
                    if (d.status === "ok") {
                        textInput.value = `[Document: ${d.filename}]\n\n${d.text}\n\nTask: Synthesize high-yield study points and derivations.`;
                        dockStatus.innerText = "● Document ingested. Press ➤ to process.";
                    }
                } catch(err) { dockStatus.innerText = "Upload failed."; }
            }

            async function sendTextQuery() {
                const text = textInput.value.trim();
                const img = attachedImageBase64;
                if (!text && !img) return;

                textInput.value = "";
                attachedImageBase64 = null;
                document.getElementById("heroGreeting").style.display = "none";

                appendMessage("user", text ? text : "[Inspecting Study Artifact]", null, img);
                dockStatus.innerText = "⚡ First-principles derivation in progress...";

                const fd = new FormData();
                fd.append("text", text ? text : "Examine this problem or diagram step-by-step.");
                fd.append("user_id", currentUserId);
                fd.append("session_id", currentSessionId.toString());
                fd.append("mode", currentCoreMode);
                if (img) fd.append("image_base64", img);

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const d = await res.json();
                    currentSessionId = d.session_id;
                    localStorage.setItem("lemon_current_session_id", currentSessionId.toString());
                    appendMessage("lemon", d.reply_text, d.emotion);

                    if (d.audio_base64) {
                        audioElement.src = d.audio_base64;
                        audioElement.play().catch(() => {});
                    }
                    dockStatus.innerText = "● Ready";
                } catch(e) { dockStatus.innerText = "Sync issue. Please re-try."; }
            }

            function appendMessage(sender, text, emotion, img) {
                const grp = document.createElement("div");
                grp.className = `bubble-group ${sender}`;
                let imgTag = img ? `<img src="${img}" class="chat-img-thumb">` : "";
                let emoTag = emotion ? `<span style="font-size:10px; font-weight:800; color:#facc15; text-transform:uppercase;">● ${emotion}</span><br>` : "";

                grp.innerHTML = `
                    <div class="bubble ${sender}">
                        ${emoTag}
                        ${imgTag}
                        <div>${sender === 'lemon' ? marked.parse(text) : text}</div>
                    </div>
                `;
                chatStream.appendChild(grp);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            function openSidebar() { sidebar.classList.add("open"); }
            function closeSidebar() { sidebar.classList.remove("open"); }

            function switchDedicatedChamber(mode) {
                currentCoreMode = mode;
                document.querySelectorAll(".core-choice").forEach(b => b.classList.remove("selected"));
                const target = document.getElementById(`core-${mode}`);
                if (target) target.classList.add("selected");
                document.getElementById("currentChamberBadge").innerText = `⚡ ${mode.toUpperCase()} CHAIR`;
                closeSidebar();
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
