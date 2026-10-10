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
import secrets
import smtplib
import tempfile
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

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

OWNER_USERNAME = "utkarsh"
OWNER_EMAIL = "utkarsh0510w77@gmail.com"

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", OWNER_EMAIL).strip()
RAW_PASS = os.getenv("SMTP_PASS", "tldp hoyz nelu vzex")
SMTP_PASS = RAW_PASS.replace(" ", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

app = FastAPI(title="Lemon AI - Sovereign Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
def send_otp_email(to_email: str, otp: str) -> tuple[bool, str]:
    if not SMTP_USER or not SMTP_PASS:
        return False, "SMTP credentials missing."
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🍋 Lemon Sovereign Key: {otp}"
        msg["From"] = f"Lemon AI Command <{SMTP_USER}>"
        msg["To"] = to_email

        html_body = f"""
        <div style="background:#090d16; color:#f1f5f9; padding:28px; border-radius:14px; font-family:'Segoe UI',sans-serif; max-width:440px; border:2px solid #facc15; margin:auto;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:12px;">
                <span style="font-size:28px;">🍋</span>
                <h2 style="color:#facc15; margin:0; font-size:20px;">Lemon Sovereign Clearance</h2>
            </div>
            <p style="color:#94a3b8; font-size:13px;">Master authentication passcode for <b>{to_email}</b>.</p>
            <div style="background:#131826; border:2px dashed #facc15; padding:16px; text-align:center; border-radius:10px; margin:16px 0;">
                <span style="font-size:32px; font-weight:800; letter-spacing:8px; color:#fde047;">{otp}</span>
            </div>
            <p style="color:#64748b; font-size:11px;">Valid for 5 minutes. Never disclose this token.</p>
        </div>
        """
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        return True, "Dispatched successfully."
    except Exception as e:
        print(f"[SMTP Send Error]: {e}")
        return False, str(e)
        return True, "Dispatched successfully."
    except Exception as e:
        return False, str(e)

class DBManager:
    @staticmethod
    def get_conn():
        if POSTGRES_AVAILABLE and DATABASE_URL:
            try:
                url = DATABASE_URL
                if url.startswith("postgres://"):
                    url = url.replace("postgres://", "postgresql://", 1)
                conn = psycopg2.connect(url, connect_timeout=5, sslmode="require")
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
                    avatar VARCHAR(50) DEFAULT '⚡',
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
            conn.commit()
        else:
            # Fixed: Using executescript for multi-statement SQLite execution
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', avatar TEXT DEFAULT '⚡', last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
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
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + base64.urlsafe_b64encode(salt).decode().rstrip("=") + "$" + base64.urlsafe_b64encode(digest).decode().rstrip("=")

def verify_password(password: str, stored: str) -> bool:
    try:
        if stored.startswith("pbkdf2_sha256$"):
            _, rounds, salt_b64, digest_b64 = stored.split("$", 3)
            salt = base64.urlsafe_b64decode(salt_b64 + "=" * (-len(salt_b64) % 4))
            expected = base64.urlsafe_b64decode(digest_b64 + "=" * (-len(digest_b64) % 4))
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
            return secrets.compare_digest(actual, expected)
        legacy = hashlib.sha256((password + "lemon_permanent_salt_2026").encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy, stored)
    except Exception:
        return False

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

INTELLECTUAL_BASE_RULE = (
    "COGNITIVE STANDARD: You are Lemon—an ultra-intellectual synthetic mind engineered by Utkarsh Bandhu. "
    "Respond with razor-sharp first-principles derivations, mathematical intuition, and articulate rigor. Never use robotic filler phrases. "
    "Format mathematical equations in LaTeX bracketed with $ or $$ so they render cleanly."
)

PROMPT_MODES = {
    "study": f"CHAMBER: SOKRATIC ACADEMIC TUTOR & NEET/JEE ENGINE. {INTELLECTUAL_BASE_RULE} Break down concepts using the Feynman Technique, highlight NCERT points, examiner traps, and conceptual intuition.",
    "solver": f"CHAMBER: FIRST-PRINCIPLES NUMERICAL SOLVER. {INTELLECTUAL_BASE_RULE} Deconstruct physics and chemistry numericals step-by-step with explicit logic for every derivation step.",
    "recall": f"CHAMBER: ACTIVE RECALL & RAPID MCQ DRILL. {INTELLECTUAL_BASE_RULE} Drill high-yield exam questions, probe edge cases, and create flashcard memory anchors.",
    "emotion": f"CHAMBER: DEEP EMOTIONAL RESONANCE & EMPATHIC CONSCIOUSNESS. {INTELLECTUAL_BASE_RULE} Connect with profound human warmth, psychological depth, unconditional listening, and emotional validation.",
    "intellect": f"CHAMBER: PURE INTELLECT & EPISTEMIC COGNITION. {INTELLECTUAL_BASE_RULE} High-level scientific inquiry, epistemology, and foundational philosophy.",
    "rage": f"CHAMBER: UNCOMPROMISING WARRIOR RIGOR. {INTELLECTUAL_BASE_RULE} Cut excuses. Eliminate procrastination. Demand relentless execution and intense self-discipline.",
    "philosophy": f"CHAMBER: ONTOLOGY & METAPHYSICS. {INTELLECTUAL_BASE_RULE} Deep existential reflections, ethical frameworks, dialectical reasoning.",
    "strategy": f"CHAMBER: MASTER STRATEGIST. {INTELLECTUAL_BASE_RULE} Game theory, long-term planning, high-stakes time and energy optimization.",
    "creative": f"CHAMBER: ARTISAN SYNTHESIS. {INTELLECTUAL_BASE_RULE} Evocative metaphors, vivid literary narratives, elegant phrasing.",
    "zen": f"CHAMBER: SOMATIC ZEN & STRESS DISSOLUTION. {INTELLECTUAL_BASE_RULE} Dissolve mental tension, ground awareness, and bring stillness to an overactive mind."
}

def generate_ai_title(prompt: str, core: str) -> str:
    if client is None:
        return f"{core.capitalize()} Session"
    try:
        res = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Generate a concise 3-word title. Return ONLY text with no quotes."},
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

def ask_groq_vision_or_llm(user_prompt: str, mode: str, history: list, image_base64: str = None, lang_instruction: str = "") -> tuple[str, str]:
    if client is None:
        return "Lemon AI is offline. Provide a valid GROQ_API_KEY environment variable.", "Formidable"
    
    instruction = PROMPT_MODES.get(mode, PROMPT_MODES["study"])
    if lang_instruction:
        instruction += f"\nLANGUAGE MANDATE: {lang_instruction}"
    
    instruction += (
        "\nOUTPUT RULE: Line 1 MUST strictly be [EMOTION: <SingleWord>]. "
        "Eligible: Analytical, Compassionate, Formidable, Profound, Insightful, Unyielding, Serene, Brilliant, Illuminating."
    )

    clean_image = None
    if image_base64 and isinstance(image_base64, str) and len(image_base64) > 100:
        clean_image = image_base64 if image_base64.startswith("data:image") else f"data:image/jpeg;base64,{image_base64}"

    if clean_image:
        prompt_text = user_prompt if (user_prompt and len(user_prompt.strip()) > 0) else "Audit this image/problem line-by-line and identify all flaws."
        user_content = [
            {"type": "text", "text": f"{instruction}\n\nTask:\n{prompt_text}"},
            {"type": "image_url", "image_url": {"url": clean_image}}
        ]
        try:
            chat = client.chat.completions.create(
                messages=[{"role": "user", "content": user_content}],
                model="llama-3.2-11b-vision-preview",
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
        except Exception as e:
            return f"Optical analysis fault: {e}", "Formidable"

    messages = [{"role": "system", "content": instruction}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_prompt})

    for tm in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        try:
            chat = client.chat.completions.create(
                messages=messages,
                model=tm,
                max_tokens=2048,
                temperature=0.35
            )
            if chat.choices and chat.choices[0].message.content:
                raw = chat.choices[0].message.content.strip()
                emotion = "Compassionate" if mode == "emotion" else "Insightful"
                match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw, re.IGNORECASE)
                if match:
                    emotion = match.group(1).capitalize()
                    raw = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw).strip()
                return raw, emotion
        except Exception:
            continue
    return "Cognitive process desynchronized.", "Serene"

# ----------------- OWNER OTP AUTHENTICATION APIS -----------------
@app.post("/api/owner/request-otp")
def request_owner_otp(email: str = Form(...)):
    email_clean = email.strip().lower()
    if email_clean != OWNER_EMAIL.lower():
        return JSONResponse({"status": "error", "message": f"Unauthorized. Only {OWNER_EMAIL} allowed."}, status_code=403)

    otp = f"{secrets.randbelow(900000) + 100000}"
    OTP_STORE[email_clean] = {"otp": otp, "expires_at": time.time() + 300, "attempts": 0}

    sent, msg = send_otp_email(email_clean, otp)
    if sent:
        return JSONResponse({"status": "ok", "message": f"Live OTP sent to {email_clean}!"})
    else:
        OTP_STORE.pop(email_clean, None)
        return JSONResponse({"status": "error", "message": f"Dispatch fault: {msg}"}, status_code=503)

@app.post("/api/owner/verify-otp")
def verify_owner_otp(email: str = Form(...), otp: str = Form(...)):
    email_clean = email.strip().lower()
    otp_clean = otp.strip()

    record = OTP_STORE.get(email_clean)
    if not record or time.time() > record["expires_at"]:
        OTP_STORE.pop(email_clean, None)
        return JSONResponse({"status": "error", "message": "OTP expired or not requested."}, status_code=400)

    if record.get("attempts", 0) >= 5:
        OTP_STORE.pop(email_clean, None)
        return JSONResponse({"status": "error", "message": "Too many attempts."}, status_code=429)
    if not secrets.compare_digest(record["otp"], otp_clean):
        record["attempts"] = record.get("attempts", 0) + 1
        return JSONResponse({"status": "error", "message": "Incorrect OTP code."}, status_code=401)

    OTP_STORE.pop(email_clean, None)
    token = secrets.token_urlsafe(32)
    OWNER_SESSIONS[token] = time.time() + 3600
    return JSONResponse({"status": "ok", "token": token, "username": OWNER_USERNAME})

# ----------------- REGISTRATION & LOGIN -----------------
@app.post("/api/register")
def register_user(username: str = Form(...), password: str = Form(...), avatar: str = Form("⚡")):
    clean_user = username.strip().lower()
    if not clean_user or len(password) < 3:
        return JSONResponse({"status": "error", "message": "Username and minimum 3-character password required."}, status_code=400)

    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        pwd_hash = hash_password(password)
        role = "owner" if clean_user == OWNER_USERNAME.lower() else "user"
        if engine == "postgres":
            cur.execute("INSERT INTO users (username, password_hash, role, avatar) VALUES (%s, %s, %s, %s) RETURNING id", (clean_user, pwd_hash, role, avatar))
            user_id = cur.fetchone()[0]
        else:
            cur.execute("INSERT INTO users (username, password_hash, role, avatar) VALUES (?, ?, ?, ?)", (clean_user, pwd_hash, role, avatar))
            user_id = cur.lastrowid
        conn.commit()
        return JSONResponse({"status": "ok", "user_id": user_id, "username": clean_user, "role": role, "avatar": avatar})
    except Exception as e:
        if "unique" in str(e).lower():
            return JSONResponse({"status": "error", "message": "Username already taken."}, status_code=400)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        conn.close()

@app.post("/api/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    clean_user = username.strip().lower()
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "SELECT id, username, role, avatar, password_hash FROM users WHERE username = %s" if engine == "postgres" else "SELECT id, username, role, avatar, password_hash FROM users WHERE username = ?"
        cur.execute(sql, (clean_user,))
        user = cur.fetchone()
        if user and verify_password(password, user[4]):
            if not user[4].startswith("pbkdf2_sha256$"):
                up_sql = "UPDATE users SET password_hash = %s WHERE id = %s" if engine == "postgres" else "UPDATE users SET password_hash = ? WHERE id = ?"
                cur.execute(up_sql, (hash_password(password), user[0]))
                conn.commit()
            return JSONResponse({"status": "ok", "user_id": user[0], "username": user[1], "role": user[2], "avatar": user[3] or "⚡"})
        return JSONResponse({"status": "error", "message": "Invalid username or password."}, status_code=401)
    finally:
        conn.close()

@app.post("/api/user/set-avatar")
def set_avatar(user_id: int = Form(...), avatar: str = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "UPDATE users SET avatar = %s WHERE id = %s" if engine == "postgres" else "UPDATE users SET avatar = ? WHERE id = ?"
        cur.execute(sql, (avatar, user_id))
        conn.commit()
        return JSONResponse({"status": "ok", "avatar": avatar})
    finally:
        conn.close()

@app.post("/api/heartbeat")
def heartbeat(user_id: int = Form(...)):
    update_user_heartbeat(user_id)
    return JSONResponse({"status": "ok"})

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
    if core_mode not in PROMPT_MODES:
        return JSONResponse({"status": "error", "message": "Unknown chamber mode."}, status_code=400)
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
            for page in reader.pages[:15]:
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

    return JSONResponse({"status": "ok", "filename": file.filename, "text": extracted_text.strip()[:10000]})

@app.get("/api/owner/telemetry")
def get_owner_telemetry(token: str = ""):
    expiry = OWNER_SESSIONS.get(token)
    if not token or not expiry or time.time() > expiry:
        OWNER_SESSIONS.pop(token, None)
        return JSONResponse({"status": "error", "message": "Authentication required."}, status_code=401)
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
            "users": users_list
        })
    finally:
        conn.close()

def detect_tts_language(text: str, pref: str = "auto") -> str:
    if pref == "hi":
        return "hi"
    if pref == "en":
        return "en"
    if re.search(r'[\u0900-\u097F]', text):
        return "hi"
    hinglish_markers = {"hai", "hoon", "aap", "kaise", "kya", "bhai", "karo", "nahi", "accha", "samjha", "dost", "mera", "meri"}
    words = set(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
    return "hi" if len(words.intersection(hinglish_markers)) >= 2 else "en"

def handle_conversation(user_id: int, session_id: int, query: str, mode: str, image_base64: str = None, lang_pref: str = "en"):
    update_user_heartbeat(user_id)
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()

    lang_instructions = {
        "hi": "Communicate primarily in natural Hindi using the Devanagari script for clear conceptual resonance.",
        "hinglish": "Explain concepts in intuitive conversational Hinglish (Hindi written in English alphabets) interspersed with high-yield English technical terms.",
        "en": "Respond in crisp, authoritative academic English with clear analytical derivations."
    }
    lang_rule = lang_instructions.get(lang_pref, lang_instructions["en"])

    try:
        user_check = "SELECT id, username FROM users WHERE id = %s" if engine == "postgres" else "SELECT id, username FROM users WHERE id = ?"
        cur.execute(user_check, (user_id,))
        u_record = cur.fetchone()
        username = u_record[1] if u_record else f"User_{user_id}"

        if not session_id or session_id <= 0:
            title = generate_ai_title(query if query else "Cognitive Session", mode)
            if engine == "postgres":
                cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (%s, %s, %s) RETURNING id", (user_id, title, mode))
                session_id = cur.fetchone()[0]
            else:
                cur.execute("INSERT INTO sessions (user_id, title, core_mode) VALUES (?, ?, ?)", (user_id, title, mode))
                session_id = cur.lastrowid
            conn.commit()
        else:
            s_check = "SELECT title, core_mode FROM sessions WHERE id = %s AND user_id = %s" if engine == "postgres" else "SELECT title, core_mode FROM sessions WHERE id = ? AND user_id = ?"
            cur.execute(s_check, (session_id, user_id))
            row = cur.fetchone()
            if row:
                title, mode = row[0], row[1]
            else:
                title = generate_ai_title(query if query else "Cognitive Session", mode)
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
            reply = f"I was engineered by Utkarsh Bandhu. He conceptualized and developed my sovereign cognitive architecture, instilling my first-principles problem-solving rigor."
            emotion = "Brilliant"
        else:
            h_sql = "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT 8" if engine == "postgres" else "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 8"
            cur.execute(h_sql, (session_id,))
            past_rows = cur.fetchall()
            history = [{"role": r[0], "content": r[1]} for r in reversed(past_rows)]
            reply, emotion = ask_groq_vision_or_llm(query, mode, history, image_base64, lang_rule)

        ins_m = "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_m, (session_id, 'user', query if query else "[Visual/Document Ingested]", mode, image_base64))
        
        ins_a = "INSERT INTO messages (session_id, role, content, mode, emotion) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, emotion) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_a, (session_id, 'assistant', reply, mode, emotion))
        conn.commit()
    finally:
        conn.close()

    audio_base64 = None
    try:
        speech_clean = re.sub(r'[*#|_>`$]', '', reply)
        speech_clean = re.sub(r'\n+', ' ', speech_clean).strip()
        tts_lang = detect_tts_language(speech_clean, lang_pref)
        spoken_snippet = speech_clean[:550]
        fp = io.BytesIO()
        tts = gTTS(text=spoken_snippet, lang=tts_lang, slow=False)
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_b64 = base64.b64encode(fp.read()).decode("utf-8")
        audio_base64 = f"data:audio/mp3;base64,{audio_b64}"
    except Exception:
        pass

    return reply, emotion, session_id, title, mode, audio_base64, username

@app.post("/text-process")
async def text_process(
    text: str = Form(""),
    user_id: str = Form("1"),
    session_id: str = Form("0"),
    mode: str = Form("study"),
    image_base64: str = Form(None),
    language: str = Form("en")
):
    u_id = int(user_id) if str(user_id).isdigit() else 1
    s_id = int(session_id) if str(session_id).isdigit() else 0
    if mode not in PROMPT_MODES:
        mode = "study"
    img = image_base64 if (image_base64 and image_base64 != "null" and len(image_base64.strip()) > 50) else None

    reply_text, emotion, res_s_id, title, cur_mode, audio_base64, username = handle_conversation(u_id, s_id, text, mode, img, language)
    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": res_s_id,
        "title": title,
        "mode": cur_mode,
        "audio_base64": audio_base64,
        "username": username
    })

@app.post("/voice-process")
async def voice_process(
    file: UploadFile = File(...),
    user_id: str = Form("1"),
    session_id: str = Form("0"),
    mode: str = Form("study"),
    image_base64: str = Form(None),
    language: str = Form("en")
):
    if client is None:
        return JSONResponse({"status": "error", "message": "Voice processing requires GROQ_API_KEY."}, status_code=503)
    u_id = int(user_id) if str(user_id).isdigit() else 1
    s_id = int(session_id) if str(session_id).isdigit() else 0
    if mode not in PROMPT_MODES:
        mode = "study"
    img = image_base64 if (image_base64 and image_base64 != "null" and len(image_base64.strip()) > 50) else None
    audio_bytes = await file.read()
    if not audio_bytes:
        return JSONResponse({"status": "error", "message": "Uploaded audio is empty."}, status_code=400)

    suffix = os.path.splitext(file.filename or "voice.webm")[1].lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".ogg", ".flac"}:
        suffix = ".webm"
    user_text = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_audio:
            temp_path = temp_audio.name
            temp_audio.write(audio_bytes)
            temp_audio.flush()
        
        with open(temp_path, "rb") as audio_handle:
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_handle,
                response_format="text"
            )
            user_text = str(transcription).strip()
        
        try:
            os.remove(temp_path)
        except Exception:
            pass
    except Exception as exc:
        return JSONResponse({"status": "error", "message": f"Transcription error: {exc}"}, status_code=502)
    
    if not user_text:
        return JSONResponse({"status": "error", "message": "No discernible speech detected."}, status_code=422)

    reply_text, emotion, res_s_id, title, cur_mode, audio_base64, username = handle_conversation(u_id, s_id, user_text, mode, img, language)
    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": res_s_id,
        "title": title,
        "mode": cur_mode,
        "audio_base64": audio_base64,
        "username": username
    })

# =====================================================================
# 🛡️ SOVEREIGN OWNER COMMAND PORTAL: /owner
# =====================================================================
@app.get("/owner", response_class=HTMLResponse)
async def serve_owner_dashboard():
    html_page = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lemon AI | Sovereign Command</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {
            --gold: #facc15;
            --bg-deep: #07090e;
            --card-bg: #111622;
            --border-color: #222b3d;
            --text-high: #f8fafc;
            --text-muted: #8492a6;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: var(--bg-deep); color: var(--text-high); min-height: 100vh; display: flex; flex-direction: column; }

        .owner-nav {
            padding: 16px 24px; background: #0c101a; border-bottom: 1px solid var(--border-color);
            display: flex; align-items: center; justify-content: space-between;
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-badge { width: 40px; height: 40px; background: var(--gold); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; }

        .container { padding: 24px; max-width: 1200px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; }
        .metric-title { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
        .metric-value { font-size: 32px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; color: #fff; }
        .metric-tag { font-size: 11px; color: var(--gold); margin-top: 6px; }

        .panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
        th { text-align: left; padding: 10px; color: var(--text-muted); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 10px; border-bottom: 1px solid #1a2233; }

        .otp-modal { position: fixed; inset: 0; background: rgba(5, 7, 12, 0.98); backdrop-filter: blur(20px); display: flex; align-items: center; justify-content: center; z-index: 500; }
        .otp-box { background: #111622; border: 1px solid var(--gold); border-radius: 20px; padding: 32px; width: 90%; max-width: 420px; text-align: center; }
        .action-btn { width: 100%; background: var(--gold); border: none; border-radius: 10px; padding: 12px; color: #000; font-weight: 700; cursor: pointer; margin-top: 12px; }
        .search-input { width: 100%; background: #07090e; border: 1px solid var(--border-color); border-radius: 10px; padding: 10px; color: #fff; outline: none; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="otp-modal" id="ownerOtpGate">
        <div class="otp-box">
            <div style="font-size:36px; margin-bottom:8px;">🛡️</div>
            <h2 style="font-family:'Space Grotesk'; font-size:20px; margin-bottom:6px;">Master Clearance Gate</h2>
            <p style="font-size:12px; color:var(--text-muted); margin-bottom:14px;">Master Account: <b>__OWNER_EMAIL__</b></p>
            <div id="otpStatusMsg" style="font-size:12px; color:#4ade80; margin-bottom:10px;">Dispatch authentication key to master email.</div>
            
            <button class="action-btn" id="reqOtpBtn" onclick="requestOtp()">📩 Send OTP to Master Gmail</button>

            <div id="otpInputArea" style="display:none; margin-top:14px;">
                <input type="text" id="otpCodeInput" class="search-input" placeholder="Enter 6-digit key" maxlength="6" style="text-align:center; font-size:18px; letter-spacing:4px;" />
                <button class="action-btn" onclick="verifyOtp()">Unlock Sovereign Console</button>
            </div>
            <div id="otpErrMsg" style="color:#f87171; font-size:12px; margin-top:10px; display:none;"></div>
        </div>
    </div>

    <header class="owner-nav">
        <div class="brand">
            <div class="brand-badge">🍋</div>
            <div>
                <div style="font-size:16px; font-weight:800; font-family:'Space Grotesk';">Lemon Sovereign Control</div>
                <div style="font-size:11px; color:var(--text-muted);">Commander: <b>Utkarsh Bandhu (__OWNER_EMAIL__)</b></div>
            </div>
        </div>
        <button onclick="location.href='/'" style="background:#1a2233; border:1px solid var(--border-color); color:#fff; padding:8px 16px; border-radius:10px; font-size:12px; cursor:pointer;">← Return to Cockpit</button>
    </header>

    <main class="container">
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-title">Total Ingested Visits</div>
                <div class="metric-value" id="valVisits">0</div>
                <div class="metric-tag">● Persistent telemetry</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Registered Accounts</div>
                <div class="metric-value" id="valUsers">0</div>
                <div class="metric-tag">● Active user records</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Live Active Students</div>
                <div class="metric-value" id="valOnline" style="color:#4ade80;">0</div>
                <div class="metric-tag">● Active past 15 mins</div>
            </div>
            <div class="metric-card">
                <div class="metric-title">Chamber Sessions</div>
                <div class="metric-value" id="valSessions">0</div>
                <div class="metric-tag">● Synthetic sessions opened</div>
            </div>
        </div>

        <div class="panel">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="font-size:15px; color:var(--gold);">👥 Student & Account Registry</h3>
                <button onclick="loadTelemetry()" style="background:none; border:none; color:var(--gold); font-size:12px; cursor:pointer;">↻ Refresh</button>
            </div>
            <table>
                <thead><tr><th>ID</th><th>Username</th><th>Role</th><th>Last Heartbeat</th></tr></thead>
                <tbody id="usersTbody"><tr><td colspan="4" style="text-align:center;">Synchronizing telemetry...</td></tr></tbody>
            </table>
        </div>
    </main>

    <script>
        let currentToken = localStorage.getItem("lemon_owner_token");

        async function requestOtp() {
            const btn = document.getElementById("reqOtpBtn");
            btn.innerText = "Transmitting OTP...";
            const fd = new FormData();
            fd.append("email", "__OWNER_EMAIL__");
            try {
                const res = await fetch("/api/owner/request-otp", { method: "POST", body: fd });
                const d = await res.json();
                document.getElementById("otpStatusMsg").innerText = d.message;
                document.getElementById("otpInputArea").style.display = "block";
                btn.innerText = "Re-send OTP";
            } catch(e) {
                document.getElementById("otpErrMsg").innerText = "Failed to transmit OTP.";
                document.getElementById("otpErrMsg").style.display = "block";
            }
        }

        async function verifyOtp() {
            const code = document.getElementById("otpCodeInput").value.trim();
            const err = document.getElementById("otpErrMsg");
            const fd = new FormData();
            fd.append("email", "__OWNER_EMAIL__");
            fd.append("otp", code);

            try {
                const res = await fetch("/api/owner/verify-otp", { method: "POST", body: fd });
                const d = await res.json();
                if (res.ok && d.status === "ok") {
                    currentToken = d.token;
                    localStorage.setItem("lemon_owner_token", currentToken);
                    document.getElementById("ownerOtpGate").style.display = "none";
                    loadTelemetry();
                } else {
                    err.innerText = d.message || "Invalid OTP code.";
                    err.style.display = "block";
                }
            } catch(e) {
                err.innerText = "Clearance failure.";
                err.style.display = "block";
            }
        }

        async function loadTelemetry() {
            try {
                const res = await fetch("/api/owner/telemetry?token=" + currentToken);
                const d = await res.json();
                if (d.status === "ok") {
                    document.getElementById("ownerOtpGate").style.display = "none";
                    document.getElementById("valVisits").innerText = d.total_visits;
                    document.getElementById("valUsers").innerText = d.total_users;
                    document.getElementById("valOnline").innerText = d.online_users;
                    document.getElementById("valSessions").innerText = d.total_sessions;

                    const tbody = document.getElementById("usersTbody");
                    tbody.innerHTML = (d.users || []).map(u => `
                        <tr>
                            <td>${u.id}</td>
                            <td><b>${u.username}</b></td>
                            <td style="color:${u.role === 'owner' ? '#facc15' : '#8492a6'}; font-weight:${u.role==='owner'?'700':'400'}">${u.role}</td>
                            <td style="color:#38bdf8;">${u.last_active || 'Recent'}</td>
                        </tr>
                    `).join("");
                } else {
                    document.getElementById("ownerOtpGate").style.display = "flex";
                }
            } catch(e) {}
        }

        if (currentToken) loadTelemetry();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_page.replace("__OWNER_EMAIL__", OWNER_EMAIL))

# =====================================================================
# 🌐 MAIN USER INTERFACE: / (FUTURISTIC SOVEREIGN COCKPIT)
# =====================================================================
@app.get("/", response_class=HTMLResponse)
async def serve_app():
    record_visit()
    return HTMLResponse(content="""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Lemon AI | Sovereign Cockpit</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/dompurify@3.2.6/dist/purify.min.js"></script>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>
    <style>
        :root {
            --gold: #facc15;
            --gold-glow: rgba(250, 204, 21, 0.22);
            --bg-deep: #06080d;
            --bg-surface: #0e121c;
            --card-surface: #141a29;
            --border-color: #1f273b;
            --border-highlight: #2e3b56;
            --text-high: #f8fafc;
            --text-muted: #8492a6;
            --accent-cyan: #38bdf8;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; -webkit-tap-highlight-color: transparent; }
        html, body { height: 100%; width: 100%; overflow: hidden; position: fixed; background: var(--bg-deep); color: var(--text-high); }
        body { display: flex; flex-direction: column; }

        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: var(--bg-surface); }
        ::-webkit-scrollbar-thumb { background: #222b3d; border-radius: 6px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--gold); }

        /* Future Header */
        .header {
            padding: 12px 20px; display: flex; align-items: center; justify-content: space-between;
            background: rgba(14, 18, 28, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-color);
            z-index: 10; flex-shrink: 0;
        }
        .header-left, .header-right { display: flex; align-items: center; gap: 10px; }
        .icon-trigger {
            width: 38px; height: 38px; border-radius: 12px; background: var(--card-surface);
            border: 1px solid var(--border-color); color: #fff; font-size: 16px; display: flex;
            align-items: center; justify-content: center; cursor: pointer; transition: all 0.2s;
        }
        .icon-trigger:hover { border-color: var(--gold); box-shadow: 0 0 10px var(--gold-glow); }
        .brand-badge {
            width: 38px; height: 38px; background: var(--gold); border-radius: 12px;
            display: flex; align-items: center; justify-content: center; font-size: 20px; color: #000;
            box-shadow: 0 0 15px rgba(250, 204, 21, 0.4);
        }
        .brand-title { font-size: 15px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; letter-spacing: 0.5px; }
        .creator-tag { font-size: 11px; color: var(--text-muted); }
        .creator-tag b { color: var(--gold); }

        .chamber-badge {
            background: rgba(250, 204, 21, 0.08); border: 1px solid rgba(250, 204, 21, 0.3); color: var(--gold);
            padding: 5px 14px; border-radius: 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;
        }

        /* Chips Bar */
        .quick-study-bar {
            display: flex; gap: 8px; padding: 8px 18px; background: #0a0d14;
            border-bottom: 1px solid var(--border-color); overflow-x: auto; flex-shrink: 0;
        }
        .study-chip {
            white-space: nowrap; font-size: 11px; font-weight: 600; padding: 6px 14px; border-radius: 12px;
            background: var(--card-surface); border: 1px solid var(--border-color); color: #cbd5e1; cursor: pointer; transition: all 0.2s;
        }
        .study-chip:hover { border-color: var(--gold); color: var(--gold); transform: translateY(-1px); }

        /* Dual Sidebars */
        .sidebar-overlay {
            position: fixed; inset: 0; background: rgba(3, 5, 8, 0.85); backdrop-filter: blur(8px);
            z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.3s;
        }
        .sidebar-overlay.open { opacity: 1; pointer-events: auto; }

        .left-sidebar {
            position: fixed; top: 0; left: 0; bottom: 0; width: 310px; background: var(--bg-surface);
            border-right: 1px solid var(--border-color); z-index: 1001; transform: translateX(-100%);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column; padding: 18px;
        }
        .left-sidebar.open { transform: translateX(0); }

        .right-sidebar {
            position: fixed; top: 0; right: 0; bottom: 0; width: 330px; background: var(--bg-surface);
            border-left: 1px solid var(--border-color); z-index: 1001; transform: translateX(100%);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column; padding: 20px;
            overflow-y: auto;
        }
        .right-sidebar.open { transform: translateX(0); }

        .sidebar-header {
            display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; padding-bottom: 10px;
            border-bottom: 1px solid var(--border-color);
        }
        .sidebar-close { font-size: 18px; color: var(--text-muted); cursor: pointer; border: none; background: none; }

        .core-btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px; }
        .core-choice {
            background: var(--card-surface); border: 1px solid var(--border-color); color: var(--text-muted);
            padding: 9px 6px; border-radius: 10px; font-size: 11px; font-weight: 600; cursor: pointer; text-align: center;
        }
        .core-choice.selected { background: var(--gold); color: #000; font-weight: 800; border-color: var(--gold); box-shadow: 0 0 10px var(--gold-glow); }

        .sessions-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
        .session-item {
            display: flex; align-items: center; justify-content: space-between; padding: 8px 12px;
            background: var(--card-surface); border: 1px solid var(--border-color); border-radius: 10px; cursor: pointer;
        }
        .session-item.active { border-color: var(--gold); background: #192133; }
        .del-session-btn { background: none; border: none; color: #ef4444; font-size: 13px; cursor: pointer; padding: 2px 6px; }

        .avatar-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 10px 0 16px; }
        .avatar-card {
            background: var(--card-surface); border: 2px solid var(--border-color); border-radius: 12px;
            padding: 8px 4px; text-align: center; cursor: pointer; transition: all 0.2s;
        }
        .avatar-card.active { border-color: var(--gold); background: #1f273b; }
        .avatar-icon { font-size: 24px; margin-bottom: 2px; }
        .avatar-label { font-size: 10px; color: var(--text-muted); font-weight: 600; }

        .chat-container {
            flex: 1; overflow-y: scroll; padding: 20px 18px 30px; display: flex; flex-direction: column; gap: 16px; position: relative;
        }
        .hero-greeting { margin: auto; display: flex; flex-direction: column; align-items: center; text-align: center; width: 90%; max-width: 500px; }
        .hero-logo {
            width: 72px; height: 72px; border-radius: 22px; background: var(--gold);
            display: flex; align-items: center; justify-content: center; font-size: 36px; margin-bottom: 16px;
            box-shadow: 0 0 30px rgba(250, 204, 21, 0.35);
        }

        .bubble-group { display: flex; flex-direction: column; max-width: 86%; }
        .bubble-group.lemon { align-self: flex-start; }
        .bubble-group.user { align-self: flex-end; }

        .bubble { padding: 14px 18px; border-radius: 18px; font-size: 14px; line-height: 1.6; word-break: break-word; }
        .bubble.lemon { background: var(--card-surface); border: 1px solid var(--border-color); color: #f1f5f9; border-bottom-left-radius: 4px; }
        .bubble.user { background: var(--gold); color: #000; font-weight: 600; border-bottom-right-radius: 4px; }

        .chat-img-thumb { max-width: 240px; border-radius: 12px; margin-bottom: 10px; border: 1px solid var(--border-color); }

        /* Auth Modal */
        .auth-modal {
            position: fixed; inset: 0; background: rgba(3, 5, 8, 0.95); backdrop-filter: blur(20px);
            z-index: 3000; display: none; align-items: center; justify-content: center; padding: 20px;
        }
        .auth-box {
            background: var(--bg-surface); border: 1px solid var(--gold); border-radius: 20px;
            padding: 28px; width: 100%; max-width: 380px; display: flex; flex-direction: column; gap: 14px;
        }
        .auth-tabs { display: flex; gap: 10px; margin-bottom: 8px; }
        .auth-tab { flex: 1; padding: 8px; text-align: center; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer; background: var(--card-surface); color: var(--text-muted); }
        .auth-tab.active { background: var(--gold); color: #000; }
        .auth-input { width: 100%; background: #080a10; border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; color: #fff; font-size: 13px; outline: none; }

        /* Camera Modal */
        .camera-modal {
            position: fixed; inset: 0; background: rgba(5,7,12,0.95); z-index: 2500;
            display: none; flex-direction: column; align-items: center; justify-content: center; padding: 20px;
        }
        .camera-box {
            background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: 18px;
            padding: 18px; width: 100%; max-width: 440px; display: flex; flex-direction: column; align-items: center; gap: 12px;
        }
        .camera-video { width: 100%; height: 260px; border-radius: 12px; background: #000; object-fit: cover; }
        .camera-ctrls { display: flex; gap: 10px; width: 100%; justify-content: center; }

        /* Bottom Dock */
        .bottom-dock {
            padding: 10px 18px 18px; background: rgba(14, 18, 28, 0.95); border-top: 1px solid var(--border-color); flex-shrink: 0;
        }
        .dock-status { font-size: 11px; color: var(--text-muted); text-align: center; margin-bottom: 6px; font-family: 'JetBrains Mono', monospace; }
        .input-dock {
            display: flex; align-items: center; background: var(--card-surface); border: 1px solid var(--border-color);
            border-radius: 36px; padding: 4px 6px 4px 14px; gap: 6px;
        }
        .input-dock:focus-within { border-color: var(--gold); box-shadow: 0 0 12px var(--gold-glow); }
        .input-dock input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14px; outline: none; }
        .dock-btn { width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer; }
        .cam-btn { background: #1c2333; color: var(--accent-cyan); }
        .doc-btn { background: #1c2333; color: #c084fc; }
        .mic-btn { background: #1c2333; color: var(--gold); }
        .stop-btn { display: none; background: #ef4444; color: #fff; font-size: 13px; }
        .send-btn { background: var(--gold); color: #000; font-weight: 800; }

        .setting-item {
            background: var(--card-surface); border: 1px solid var(--border-color); border-radius: 12px;
            padding: 12px 14px; margin-bottom: 10px;
        }
        .setting-title { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }
        .setting-select {
            width: 100%; background: #090c13; border: 1px solid var(--border-color); color: #fff;
            padding: 8px; border-radius: 8px; font-size: 12px; outline: none; margin-top: 4px;
        }
    </style>
</head>
<body>
    <div class="sidebar-overlay" id="overlay" onclick="closeAllSidebars()"></div>

    <!-- AUTHENTICATION MODAL -->
    <div class="auth-modal" id="authModal">
        <div class="auth-box">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="font-size:16px;" id="authModalTitle">Student Clearance</h3>
                <button onclick="closeAuthModal()" style="background:none; border:none; color:var(--text-muted); cursor:pointer;">✕</button>
            </div>
            <div class="auth-tabs">
                <div class="auth-tab active" id="tabLogin" onclick="switchAuthTab('login')">Login</div>
                <div class="auth-tab" id="tabRegister" onclick="switchAuthTab('register')">Register</div>
            </div>
            <input type="text" id="authUsername" class="auth-input" placeholder="Username" />
            <input type="password" id="authPassword" class="auth-input" placeholder="Password" />
            <div id="authErrorMsg" style="color:#f87171; font-size:11px; display:none;"></div>
            <button class="send-btn" id="authSubmitBtn" onclick="submitAuthForm()" style="border-radius:10px; padding:12px; width:100%; cursor:pointer;">Authenticate</button>
        </div>
    </div>

    <!-- CAMERA SCANNER MODAL -->
    <div class="camera-modal" id="cameraModal">
        <div class="camera-box">
            <h3 style="font-size:16px;">📷 Optical Problem & Note Scanner</h3>
            <video class="camera-video" id="cameraVideo" autoplay playsinline muted></video>
            <canvas id="cameraCanvas" style="display:none;"></canvas>
            <div class="camera-ctrls">
                <button onclick="captureSnapshot()" style="background:var(--gold); color:#000; border:none; padding:10px 18px; border-radius:10px; font-weight:700; cursor:pointer;">📸 Capture</button>
                <label style="background:#1e2538; color:#fff; padding:10px 18px; border-radius:10px; font-weight:600; cursor:pointer;">
                    📁 File
                    <input type="file" id="fileUploadInput" accept="image/*" style="display:none;" onchange="handleFileUpload(event)">
                </label>
                <button onclick="closeCamera()" style="background:#ef4444; color:#fff; border:none; padding:10px 18px; border-radius:10px; cursor:pointer;">✕ Close</button>
            </div>
        </div>
    </div>

    <!-- LEFT SIDEBAR: CHAMBERS & HISTORY -->
    <aside class="left-sidebar" id="leftSidebar">
        <div class="sidebar-header">
            <div>
                <h3 style="font-size:16px;">Cognitive Chairs</h3>
                <div style="font-size:11px; color:var(--text-muted);">Master: <b style="color:var(--gold);">Utkarsh Bandhu</b></div>
            </div>
            <button class="sidebar-close" onclick="closeAllSidebars()">✕</button>
        </div>

        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:700; margin-bottom:8px;">10 Chambers</div>
        <div class="core-btn-grid">
            <button class="core-choice selected" id="core-study" onclick="switchDedicatedChamber('study')">📚 Socratic Study</button>
            <button class="core-choice" id="core-solver" onclick="switchDedicatedChamber('solver')">🧠 Step Solver</button>
            <button class="core-choice" id="core-recall" onclick="switchDedicatedChamber('recall')">🎯 Active Recall</button>
            <button class="core-choice" id="core-emotion" onclick="switchDedicatedChamber('emotion')">💖 Deep Emotion</button>
            <button class="core-choice" id="core-intellect" onclick="switchDedicatedChamber('intellect')">⚡ Deep Intellect</button>
            <button class="core-choice" id="core-rage" onclick="switchDedicatedChamber('rage')">🔥 Rage Rigor</button>
            <button class="core-choice" id="core-strategy" onclick="switchDedicatedChamber('strategy')">♟️ Strategist</button>
            <button class="core-choice" id="core-philosophy" onclick="switchDedicatedChamber('philosophy')">🏛️ Philosophy</button>
            <button class="core-choice" id="core-creative" onclick="switchDedicatedChamber('creative')">🎨 Creative</button>
            <button class="core-choice" id="core-zen" onclick="switchDedicatedChamber('zen')">🌿 Zen Somatic</button>
        </div>

        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:700; margin:12px 0 6px;">Saved Transcripts</div>
        <div class="sessions-list" id="sessionsList"></div>
    </aside>

    <!-- RIGHT SIDEBAR: USER SETTINGS & OWNER GATE -->
    <aside class="right-sidebar" id="rightSidebar">
        <div class="sidebar-header">
            <div>
                <h3 style="font-size:16px;">Cockpit Settings</h3>
                <div style="font-size:11px; color:var(--text-muted);" id="userRoleHeader">Role: Student</div>
            </div>
            <button class="sidebar-close" onclick="closeAllSidebars()">✕</button>
        </div>

        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:700; margin-bottom:6px;">Select Avatar (8 Presets)</div>
        <div class="avatar-grid" id="avatarGrid">
            <div class="avatar-card active" onclick="selectAvatar('⚡', this)"><div class="avatar-icon">⚡</div><div class="avatar-label">Cyber</div></div>
            <div class="avatar-card" onclick="selectAvatar('🩺', this)"><div class="avatar-icon">🩺</div><div class="avatar-label">Medico</div></div>
            <div class="avatar-card" onclick="selectAvatar('🧠', this)"><div class="avatar-icon">🧠</div><div class="avatar-label">Intellect</div></div>
            <div class="avatar-card" onclick="selectAvatar('🦁', this)"><div class="avatar-icon">🦁</div><div class="avatar-label">Titan</div></div>
            <div class="avatar-card" onclick="selectAvatar('🌿', this)"><div class="avatar-icon">🌿</div><div class="avatar-label">Zen</div></div>
            <div class="avatar-card" onclick="selectAvatar('🔬', this)"><div class="avatar-icon">🔬</div><div class="avatar-label">Bio</div></div>
            <div class="avatar-card" onclick="selectAvatar('🐺', this)"><div class="avatar-icon">🐺</div><div class="avatar-label">Alpha</div></div>
            <div class="avatar-card" onclick="selectAvatar('👑', this)"><div class="avatar-icon">👑</div><div class="avatar-label">Sovereign</div></div>
        </div>

        <!-- NEW: COMPREHENSIVE USER PREFERENCES -->
        <div class="setting-item">
            <div class="setting-title">Cognitive Response Language</div>
            <select class="setting-select" id="prefLanguage" onchange="saveUserPrefs()">
                <option value="en">English (Strict Academic Derivation)</option>
                <option value="hinglish">Hinglish (Technical + Intuitive)</option>
                <option value="hi">Hindi (Devanagari Conceptual)</option>
            </select>
        </div>

        <div class="setting-item">
            <div class="setting-title">Voice Vocalization Speed</div>
            <select class="setting-select" id="prefAudioRate" onchange="saveUserPrefs()">
                <option value="1.0">1.0x (Standard Rhythm)</option>
                <option value="1.25">1.25x (Accelerated)</option>
                <option value="1.5">1.5x (Fast Recall)</option>
                <option value="2.0">2.0x (Hyper Speed)</option>
            </select>
        </div>

        <div class="setting-item">
            <div class="setting-title">Active Account</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                <span id="activeUserName" style="font-weight:700; color:var(--gold);">Student</span>
                <button onclick="openAuthModal()" style="background:none; border:none; color:var(--accent-cyan); font-size:12px; cursor:pointer;">Switch/Login</button>
            </div>
        </div>

        <!-- STRICT OWNER VISIBILITY GATE -->
        <button id="ownerConsoleBtn" onclick="location.href='/owner'" style="display:none; margin-top:auto; background:rgba(250,204,21,0.15); border:1px solid var(--gold); color:var(--gold); padding:12px; border-radius:12px; font-weight:800; font-size:13px; cursor:pointer;">🛡️ Sovereign Owner Console</button>
    </aside>

    <!-- HEADER -->
    <header class="header">
        <div class="header-left">
            <button class="icon-trigger" onclick="openLeftSidebar()">☰</button>
            <div class="brand-badge">🍋</div>
            <div>
                <div class="brand-title">Lemon AI</div>
                <div class="creator-tag">Operator: <b id="headerUserName">Student</b></div>
            </div>
        </div>
        <div class="chamber-badge" id="currentChamberBadge">📚 Socratic Study</div>
        <div class="header-right">
            <button class="icon-trigger" id="avatarDisplayBtn" onclick="openRightSidebar()" title="Settings & Account">⚡</button>
        </div>
    </header>

    <!-- QUICK STUDY BAR -->
    <div class="quick-study-bar">
        <div class="study-chip" onclick="quickStudyPrompt('Explain this concept using the Feynman Technique and intuition:')">💡 Feynman Intuition</div>
        <div class="study-chip" onclick="quickStudyPrompt('Generate 3 High-Yield tricky MCQs on this topic with trap explanations:')">🎯 High-Yield MCQs</div>
        <div class="study-chip" onclick="quickStudyPrompt('Identify the exact calculation/formula error in my attached problem:')">🔍 Error Diagnostic</div>
        <div class="study-chip" onclick="quickStudyPrompt('Break down the high-yield NCERT points and common traps for this chapter:')">📖 NCERT Traps</div>
    </div>

    <!-- MAIN CHAT STREAM -->
    <main class="chat-container" id="chatStream">
        <div class="hero-greeting" id="heroGreeting">
            <div class="hero-logo">🍋</div>
            <h2 style="font-family:'Space Grotesk'; font-size:22px; margin-bottom:8px;" id="heroWelcomeTitle">Lemon Sovereign Core Ready</h2>
            <div style="font-size:13.5px; color:var(--text-muted); line-height:1.5;">
                Pose complex conceptual doubts, snap question photos, upload notes, or switch to Deep Emotion mode.
            </div>
        </div>
    </main>

    <!-- BOTTOM DOCK -->
    <footer class="bottom-dock">
        <div class="dock-status" id="dockStatus">● Lemon Core Synchronized</div>
        <div class="input-dock">
            <button class="dock-btn cam-btn" onclick="requestCameraAccess()" title="Camera Scan">📷</button>
            <label class="dock-btn doc-btn" style="cursor:pointer;" title="Upload PDF/Notes">
                📄
                <input type="file" id="docFileInput" accept=".pdf,.txt,.md" style="display:none;" onchange="handleDocFileUpload(event)">
            </label>
            <input type="text" id="textInput" placeholder="Pose a doubt, problem derivation, or question..." onkeydown="if(event.key==='Enter') sendTextQuery()" />
            <button class="dock-btn mic-btn" id="micBtn" onclick="requestMicAndRecord()" title="Voice Dictation">🎙️</button>
            <button class="dock-btn stop-btn" id="stopBtn" onclick="stopLemonSpeaking()" title="Stop Audio">⏹</button>
            <button class="dock-btn send-btn" onclick="sendTextQuery()" title="Send">➤</button>
        </div>
    </footer>

    <audio id="audioElement" autoplay></audio>

    <script>
        let currentUserId = localStorage.getItem("lemon_user_id") || "1";
        let currentUsername = localStorage.getItem("lemon_username") || "Student";
        let currentUserRole = localStorage.getItem("lemon_user_role") || "user";
        let currentSessionId = parseInt(localStorage.getItem("lemon_current_session_id") || "0");
        let currentCoreMode = "study";
        let currentAvatar = localStorage.getItem("lemon_user_avatar") || "⚡";
        let currentLanguage = localStorage.getItem("lemon_pref_lang") || "en";
        let currentAudioRate = parseFloat(localStorage.getItem("lemon_pref_rate") || "1.0");

        let attachedImageBase64 = null;
        let cameraStream = null;
        let mediaRecorder = null;
        let recordedChunks = [];
        let authMode = "login";

        const chatStream = document.getElementById("chatStream");
        const textInput = document.getElementById("textInput");
        const dockStatus = document.getElementById("dockStatus");
        const stopBtn = document.getElementById("stopBtn");
        const audioElement = document.getElementById("audioElement");
        const cameraModal = document.getElementById("cameraModal");
        const cameraVideo = document.getElementById("cameraVideo");
        const cameraCanvas = document.getElementById("cameraCanvas");
        const leftSidebar = document.getElementById("leftSidebar");
        const rightSidebar = document.getElementById("rightSidebar");
        const overlay = document.getElementById("overlay");
        const avatarDisplayBtn = document.getElementById("avatarDisplayBtn");

        function syncUserUI() {
            document.getElementById("headerUserName").innerText = currentUsername;
            document.getElementById("activeUserName").innerText = `${currentAvatar} ${currentUsername}`;
            document.getElementById("heroWelcomeTitle").innerText = `Welcome, ${currentUsername} — Core Ready`;
            avatarDisplayBtn.innerText = currentAvatar;
            document.getElementById("prefLanguage").value = currentLanguage;
            document.getElementById("prefAudioRate").value = String(currentAudioRate);
            audioElement.playbackRate = currentAudioRate;

            // Strict Owner Button Gate
            const ownerBtn = document.getElementById("ownerConsoleBtn");
            const roleHeader = document.getElementById("userRoleHeader");
            if (currentUserRole === "owner" || currentUsername.toLowerCase() === "utkarsh") {
                ownerBtn.style.display = "block";
                roleHeader.innerText = "Clearance: Sovereign Owner";
            } else {
                ownerBtn.style.display = "none";
                roleHeader.innerText = "Clearance: Student";
            }
        }
        syncUserUI();

        function saveUserPrefs() {
            currentLanguage = document.getElementById("prefLanguage").value;
            currentAudioRate = parseFloat(document.getElementById("prefAudioRate").value);
            localStorage.setItem("lemon_pref_lang", currentLanguage);
            localStorage.setItem("lemon_pref_rate", String(currentAudioRate));
            audioElement.playbackRate = currentAudioRate;
            dockStatus.innerText = "● Preferences saved";
        }

        // Authentication Modal Handlers
        function openAuthModal() {
            document.getElementById("authModal").style.display = "flex";
            closeAllSidebars();
        }
        function closeAuthModal() {
            document.getElementById("authModal").style.display = "none";
            document.getElementById("authErrorMsg").style.display = "none";
        }
        function switchAuthTab(mode) {
            authMode = mode;
            document.getElementById("tabLogin").classList.toggle("active", mode === "login");
            document.getElementById("tabRegister").classList.toggle("active", mode === "register");
            document.getElementById("authModalTitle").innerText = mode === "login" ? "Student Login" : "New Registration";
            document.getElementById("authSubmitBtn").innerText = mode === "login" ? "Login" : "Register Account";
        }

        async function submitAuthForm() {
            const u = document.getElementById("authUsername").value.trim();
            const p = document.getElementById("authPassword").value.trim();
            const err = document.getElementById("authErrorMsg");
            if (!u || !p) {
                err.innerText = "Both username and password are required.";
                err.style.display = "block";
                return;
            }
            const fd = new FormData();
            fd.append("username", u);
            fd.append("password", p);
            fd.append("avatar", currentAvatar);

            const endpoint = authMode === "login" ? "/api/login" : "/api/register";
            try {
                const res = await fetch(endpoint, { method: "POST", body: fd });
                const d = await res.json();
                if (res.ok && d.status === "ok") {
                    currentUserId = String(d.user_id);
                    currentUsername = d.username;
                    currentUserRole = d.role;
                    currentAvatar = d.avatar || "⚡";
                    localStorage.setItem("lemon_user_id", currentUserId);
                    localStorage.setItem("lemon_username", currentUsername);
                    localStorage.setItem("lemon_user_role", currentUserRole);
                    localStorage.setItem("lemon_user_avatar", currentAvatar);
                    syncUserUI();
                    closeAuthModal();
                    loadSessions();
                    dockStatus.innerText = `● Authenticated as ${currentUsername}`;
                } else {
                    err.innerText = d.message || "Authentication rejected.";
                    err.style.display = "block";
                }
            } catch(e) {
                err.innerText = "Connection fault.";
                err.style.display = "block";
            }
        }

        async function loadSessions() {
            const list = document.getElementById("sessionsList");
            if (!list) return;
            try {
                const response = await fetch(`/api/sessions/${encodeURIComponent(currentUserId)}`);
                if (!response.ok) throw new Error("Could not load sessions");
                const data = await response.json();
                list.replaceChildren();
                (data.sessions || []).forEach(session => {
                    const row = document.createElement("div");
                    row.className = "session-item" + (Number(session.id) === currentSessionId ? " active" : "");
                    
                    const title = document.createElement("span");
                    title.textContent = session.title || "Untitled session";
                    title.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;flex:1;";
                    title.onclick = () => openSavedSession(session.id);

                    const del = document.createElement("button");
                    del.className = "del-session-btn";
                    del.innerText = "✕";
                    del.title = "Delete Transcript";
                    del.onclick = async (e) => {
                        e.stopPropagation();
                        const fd = new FormData();
                        fd.append("session_id", session.id);
                        await fetch("/api/delete-session", { method: "POST", body: fd });
                        if (currentSessionId === Number(session.id)) {
                            currentSessionId = 0;
                            localStorage.removeItem("lemon_current_session_id");
                            chatStream.replaceChildren();
                            document.getElementById("heroGreeting").style.display = "flex";
                        }
                        loadSessions();
                    };

                    row.appendChild(title);
                    row.appendChild(del);
                    list.appendChild(row);
                });
                if (!(data.sessions || []).length) {
                    const empty = document.createElement("div");
                    empty.textContent = "Your saved transcripts appear here.";
                    empty.style.cssText = "font-size:11px;color:var(--text-muted);padding:8px;";
                    list.appendChild(empty);
                }
            } catch (error) {
                list.textContent = "Unable to load session history.";
            }
        }

        async function openSavedSession(sessionId) {
            try {
                const response = await fetch(`/api/session-messages/${encodeURIComponent(sessionId)}`);
                if (!response.ok) throw new Error("Could not load messages");
                const data = await response.json();
                chatStream.replaceChildren();
                (data.messages || []).forEach(message => {
                    appendMessage(message.role === "assistant" ? "lemon" : "user", message.content, message.emotion, message.image_data);
                });
                currentSessionId = Number(sessionId);
                localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                const latest = (data.messages || []).slice().reverse().find(message => message.mode);
                if (latest) switchDedicatedChamber(latest.mode, false);
                document.getElementById("heroGreeting").style.display = (data.messages || []).length ? "none" : "flex";
                loadSessions();
                closeAllSidebars();
                dockStatus.innerText = "● Saved session loaded";
            } catch (error) {
                dockStatus.innerText = "Could not load session.";
            }
        }

        async function selectAvatar(symbol, elem) {
            currentAvatar = symbol;
            localStorage.setItem("lemon_user_avatar", symbol);
            avatarDisplayBtn.innerText = symbol;
            document.querySelectorAll(".avatar-card").forEach(c => c.classList.remove("active"));
            elem.classList.add("active");
            syncUserUI();
            const fd = new FormData();
            fd.append("user_id", currentUserId);
            fd.append("avatar", symbol);
            await fetch("/api/user/set-avatar", { method: "POST", body: fd });
        }

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

        async function requestMicAndRecord() {
            const micBtn = document.getElementById("micBtn");
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.stop();
                micBtn.innerText = "🎙️";
                dockStatus.innerText = "● Processing speech...";
                return;
            }
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
                dockStatus.innerText = "Microphone recording unsupported.";
                return;
            }
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                recordedChunks = [];
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data && event.data.size > 0) recordedChunks.push(event.data);
                };
                mediaRecorder.onstop = async () => {
                    stream.getTracks().forEach(track => track.stop());
                    const blob = new Blob(recordedChunks, { type: mediaRecorder.mimeType || "audio/webm" });
                    if (!blob.size) { dockStatus.innerText = "No audio captured."; return; }

                    const fd = new FormData();
                    fd.append("file", blob, "voice.webm");
                    fd.append("user_id", currentUserId);
                    fd.append("session_id", String(currentSessionId));
                    fd.append("mode", currentCoreMode);
                    fd.append("language", currentLanguage);
                    try {
                        const response = await fetch("/voice-process", { method: "POST", body: fd });
                        const result = await response.json();
                        if (!response.ok) throw new Error(result.detail || result.message || "Voice request failed");
                        document.getElementById("heroGreeting").style.display = "none";
                        appendMessage("user", result.user_text || "[Voice message]", null);
                        appendMessage("lemon", result.reply_text, result.emotion);
                        if (result.session_id) {
                            currentSessionId = result.session_id;
                            localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                        }
                        loadSessions();
                        if (result.audio_base64) {
                            audioElement.src = result.audio_base64;
                            audioElement.playbackRate = currentAudioRate;
                            audioElement.play().catch(() => {});
                        }
                        dockStatus.innerText = "● Ready";
                    } catch (error) {
                        dockStatus.innerText = "Voice processing error.";
                    }
                };
                mediaRecorder.start();
                micBtn.innerText = "⏹";
                dockStatus.innerText = "● Recording audio…";
            } catch (error) {
                dockStatus.innerText = "Microphone access denied.";
            }
        }

        async function requestCameraAccess() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                document.getElementById("fileUploadInput").click();
                return;
            }
            dockStatus.innerText = "● Initializing optical sensor...";
            cameraModal.style.display = "flex";

            try {
                cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" } } });
                cameraVideo.srcObject = cameraStream;
            } catch(e) {
                document.getElementById("fileUploadInput").click();
                closeCamera();
            }
        }

        function closeCamera() {
            if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
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
            dockStatus.innerText = "● Artifact captured. Press ➤ to audit.";
        }

        function handleFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            const r = new FileReader();
            r.onload = (ev) => {
                attachedImageBase64 = ev.target.result;
                closeCamera();
                dockStatus.innerText = "● Problem photo loaded. Press ➤ to audit.";
            };
            r.readAsDataURL(file);
        }

        async function handleDocFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            dockStatus.innerText = "● Ingesting text...";
            const fd = new FormData();
            fd.append("file", file);
            try {
                const res = await fetch("/api/parse-doc", { method: "POST", body: fd });
                const d = await res.json();
                if (d.status === "ok") {
                    textInput.value = `[Document: ${d.filename}]\\n\\n${d.text}\\n\\nTask: Synthesize key derivations and high-yield insights.`;
                    dockStatus.innerText = "● Document parsed. Press ➤ to synthesize.";
                }
            } catch(err) { dockStatus.innerText = "Ingest failed."; }
        }

        async function sendTextQuery() {
            const text = textInput.value.trim();
            const img = attachedImageBase64;
            if (!text && !img) return;

            textInput.value = "";
            attachedImageBase64 = null;
            document.getElementById("heroGreeting").style.display = "none";

            appendMessage("user", text ? text : "[Artifact Inspection Request]", null, img);
            dockStatus.innerText = "⚡ First-principles derivation in progress...";

            const fd = new FormData();
            fd.append("text", text ? text : "Examine this problem or diagram step-by-step.");
            fd.append("user_id", currentUserId);
            fd.append("session_id", currentSessionId.toString());
            fd.append("mode", currentCoreMode);
            fd.append("language", currentLanguage);
            if (img) fd.append("image_base64", img);

            try {
                const res = await fetch("/text-process", { method: "POST", body: fd });
                const d = await res.json();
                if (!res.ok) throw new Error(d.message || "Request failed");
                currentSessionId = d.session_id;
                localStorage.setItem("lemon_current_session_id", currentSessionId.toString());
                appendMessage("lemon", d.reply_text, d.emotion);
                loadSessions();

                if (d.audio_base64) {
                    audioElement.src = d.audio_base64;
                    audioElement.playbackRate = currentAudioRate;
                    audioElement.play().catch(() => {});
                }
                dockStatus.innerText = "● Ready";
            } catch(e) { dockStatus.innerText = "Cognitive core desynchronized. Please retry."; }
        }

        function appendMessage(sender, text, emotion, img) {
            const grp = document.createElement("div");
            grp.className = `bubble-group ${sender === "lemon" ? "lemon" : "user"}`;
            const bubble = document.createElement("div");
            bubble.className = `bubble ${sender === "lemon" ? "lemon" : "user"}`;

            if (emotion) {
                const tag = document.createElement("span");
                tag.style.cssText = "font-size:10px;font-weight:800;color:var(--gold);text-transform:uppercase;letter-spacing:1px;";
                tag.textContent = `● ${String(emotion).slice(0, 40)}`;
                bubble.appendChild(tag);
                bubble.appendChild(document.createElement("br"));
            }
            if (img && typeof img === "string" && img.startsWith("data:image/")) {
                const image = document.createElement("img");
                image.src = img;
                image.className = "chat-img-thumb";
                image.alt = "Uploaded image";
                bubble.appendChild(image);
            }
            const content = document.createElement("div");
            if (sender === "lemon" && window.marked && window.DOMPurify) {
                content.innerHTML = DOMPurify.sanitize(marked.parse(String(text || "")));
                try {
                    renderMathInElement(content, {
                        delimiters: [
                            {left: '$$', right: '$$', display: true},
                            {left: '$', right: '$', display: false}
                        ],
                        throwOnError: false
                    });
                } catch(e) {}
            } else {
                content.textContent = String(text || "");
            }
            bubble.appendChild(content);
            grp.appendChild(bubble);
            chatStream.appendChild(grp);
            chatStream.scrollTop = chatStream.scrollHeight;
        }

        function openLeftSidebar() { leftSidebar.classList.add("open"); overlay.classList.add("open"); }
        function openRightSidebar() { rightSidebar.classList.add("open"); overlay.classList.add("open"); }
        function closeAllSidebars() { leftSidebar.classList.remove("open"); rightSidebar.classList.remove("open"); overlay.classList.remove("open"); }

        async function switchDedicatedChamber(mode, startNewSession = true) {
            if (!Object.prototype.hasOwnProperty.call({study:1,solver:1,recall:1,emotion:1,intellect:1,rage:1,strategy:1,philosophy:1,creative:1,zen:1}, mode)) return;
            const changed = currentCoreMode !== mode;
            currentCoreMode = mode;
            if (startNewSession && changed) {
                try {
                    const fd = new FormData();
                    fd.append("user_id", currentUserId);
                    fd.append("core_mode", mode);
                    const response = await fetch("/api/new-core-session", {method:"POST", body:fd});
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.message || "Could not create session");
                    currentSessionId = Number(result.session_id);
                    localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                    chatStream.replaceChildren();
                    document.getElementById("heroGreeting").style.display = "flex";
                    loadSessions();
                } catch (error) {
                    dockStatus.innerText = "Failed to open new chair session.";
                }
            }
            document.querySelectorAll(".core-choice").forEach(b => b.classList.remove("selected"));
            const target = document.getElementById(`core-${mode}`);
            if (target) target.classList.add("selected");
            
            const labels = {
                study: "📚 Socratic Study", solver: "🧠 Step Solver", recall: "🎯 Active Recall",
                emotion: "💖 Deep Emotion", intellect: "⚡ Deep Intellect", rage: "🔥 Rage Rigor",
                strategy: "♟️ Strategist", philosophy: "🏛️ Philosophy", creative: "🎨 Creative", zen: "🌿 Zen Somatic"
            };
            const label = labels[mode] || mode.toUpperCase();
            document.getElementById("currentChamberBadge").innerText = label;
            closeAllSidebars();
        }

        if (currentSessionId > 0) openSavedSession(currentSessionId);
        else loadSessions();
    </script>
</body>
</html>""")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
