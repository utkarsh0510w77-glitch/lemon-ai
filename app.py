import os
import re
import json
import sqlite3
import hashlib
import base64
import datetime
import io
import time
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

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://lemon_db_7jr5_user:fCnr4Ag4rcayvFbgZcxeRW02ROKFnm8A@dpg-db4e0i3l550s73besfpg-a.oregon-postgres.render.com/lemon_db_7jr5"
)

app = FastAPI(title="Lemon AI - Sovereign Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            except Exception as e:
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
                CREATE TABLE IF NOT EXISTS site_stats (
                    key VARCHAR(100) PRIMARY KEY,
                    value BIGINT DEFAULT 0
                );
                INSERT INTO site_stats (key, value) VALUES ('total_visits', 0) ON CONFLICT (key) DO NOTHING;
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    message TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    core_mode VARCHAR(50) DEFAULT 'intellect',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    session_id INT NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    mode VARCHAR(50) NOT NULL,
                    emotion VARCHAR(100),
                    image_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS complaints (
                    id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    category VARCHAR(100) NOT NULL,
                    message TEXT NOT NULL,
                    image_proof TEXT,
                    status VARCHAR(50) DEFAULT 'Open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS site_stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0);
                INSERT OR IGNORE INTO site_stats (key, value) VALUES ('total_visits', 0);
                CREATE TABLE IF NOT EXISTS announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    core_mode TEXT NOT NULL DEFAULT 'intellect',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    emotion TEXT,
                    image_data TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    category TEXT NOT NULL,
                    message TEXT NOT NULL,
                    image_proof TEXT,
                    status TEXT DEFAULT 'Open',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        conn.commit()
    finally:
        conn.close()

init_db()

def hash_password(password: str) -> str:
    salt = "lemon_permanent_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

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
    "COGNITIVE STANDARD & METAPROMPT: "
    "You are Lemon—an ultra-intellectual synthetic mind engineered by Utkarsh Bandhu. "
    "NEVER act like a generic bot. Never use boilerplate lines. Answer with deep self-reflective intellect and rigorous first-principles reasoning. "
    "LANGUAGE: Mirror user (Hinglish/English/Hindi natural adaptation)."
)

PROMPT_MODES = {
    "intellect": "CHAMBER: PURE INTELLECT & EPISTEMIC COGNITION. " + INTELLECTUAL_BASE_RULE,
    "rage": "CHAMBER: RAGE & WARRIOR DISCIPLINE. " + INTELLECTUAL_BASE_RULE + " Demand unyielding focus and blunt truth.",
    "solver": "CHAMBER: COMPLEX PROBLEM SOLVER. " + INTELLECTUAL_BASE_RULE,
    "philosophy": "CHAMBER: EXISTENTIAL PHILOSOPHY. " + INTELLECTUAL_BASE_RULE,
    "study": "CHAMBER: SOKRATIC ACADEMIC TUTOR. " + INTELLECTUAL_BASE_RULE,
    "strategy": "CHAMBER: MASTER STRATEGIST. " + INTELLECTUAL_BASE_RULE,
    "creative": "CHAMBER: VISIONARY ARTISAN. " + INTELLECTUAL_BASE_RULE,
    "emotional": "CHAMBER: DEEP EMPATHIC RESONANCE. " + INTELLECTUAL_BASE_RULE,
    "zen": "CHAMBER: SOMATIC ZEN. " + INTELLECTUAL_BASE_RULE,
    "hybrid": "CHAMBER: TOTAL SYNTHESIS. " + INTELLECTUAL_BASE_RULE
}

def generate_ai_title(prompt: str, core: str) -> str:
    try:
        res = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Generate a concise 3 to 4 word topic title. Return ONLY text."},
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
    instruction = PROMPT_MODES.get(mode, PROMPT_MODES["intellect"]) + (
        "\nOUTPUT FORMAT: Line 1 MUST strictly be [EMOTION: <SingleWord>]. "
        "Eligible: Analytical, Formidable, Profound, Insightful, Unyielding, Serene, Brilliant."
    )

    clean_image = None
    if image_base64 and isinstance(image_base64, str) and len(image_base64) > 100:
        clean_image = image_base64 if image_base64.startswith("data:image") else f"data:image/jpeg;base64,{image_base64}"

    if clean_image:
        vision_models = ["qwen/qwen3.8-27b", "meta-llama/llama-4-scout-17b-16e-instruct"]
        prompt_text = user_prompt if (user_prompt and len(user_prompt.strip()) > 0) else "Audit this image line-by-line and correct any flaws."
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
                    emotion = "Analytical"
                    match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw, re.IGNORECASE)
                    if match:
                        emotion = match.group(1).capitalize()
                        raw = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw).strip()
                    return raw, emotion
            except Exception:
                continue
        return "Visual transmission processing anomaly.", "Formidable"

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
                temperature=0.4
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
    return "Cognitive process briefly desynchronized. Restate your premise.", "Serene"

@app.post("/api/register")
def register_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    if not username or len(password) < 3:
        return JSONResponse({"status": "error", "message": "Username and password (min 3 chars) required."}, status_code=400)

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
            upd_sql = "UPDATE users SET last_active = CURRENT_TIMESTAMP, role = %s WHERE id = %s" if engine == "postgres" else "UPDATE users SET last_active = CURRENT_TIMESTAMP, role = ? WHERE id = ?"
            cur.execute(upd_sql, (user_role, user[0]))
            conn.commit()
            return JSONResponse({"status": "ok", "user_id": user[0], "username": user[1], "role": user_role})
        
        check_sql = "SELECT id FROM users WHERE username = %s" if engine == "postgres" else "SELECT id FROM users WHERE username = ?"
        cur.execute(check_sql, (username,))
        if not cur.fetchone():
            return JSONResponse({"status": "not_found", "message": "Account not registered."}, status_code=404)
        return JSONResponse({"status": "error", "message": "Invalid password."}, status_code=401)
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
        messages = [{"role": r[0], "content": r[1], "mode": r[2], "emotion": r[3], "image_data": r[4], "timestamp": str(r[5])} for r in rows]
        return JSONResponse({"messages": messages})
    finally:
        conn.close()

@app.post("/api/new-core-session")
def new_core_session(user_id: int = Form(...), core_mode: str = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        title = f"{core_mode.capitalize()} Chamber"
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
        sql_m = "DELETE FROM messages WHERE session_id = %s" if engine == "postgres" else "DELETE FROM messages WHERE session_id = ?"
        sql_s = "DELETE FROM sessions WHERE id = %s" if engine == "postgres" else "DELETE FROM sessions WHERE id = ?"
        cur.execute(sql_m, (session_id,))
        cur.execute(sql_s, (session_id,))
        conn.commit()
        return JSONResponse({"status": "ok"})
    finally:
        conn.close()

@app.post("/api/complaints/submit")
def submit_complaint(
    user_id: int = Form(...),
    username: str = Form(...),
    category: str = Form("General Feedback"),
    message: str = Form(...),
    image_proof: str = Form(None)
):
    msg = message.strip()
    if not msg:
        return JSONResponse({"status": "error", "message": "Message required."}, status_code=400)

    img_data = image_proof if (image_proof and len(image_proof.strip()) > 50) else None
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "INSERT INTO complaints (user_id, username, category, message, image_proof) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO complaints (user_id, username, category, message, image_proof) VALUES (?, ?, ?, ?, ?)"
        cur.execute(sql, (user_id, username, category, msg, img_data))
        conn.commit()
        return JSONResponse({"status": "ok", "message": "Feedback received."})
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
            for page in reader.pages[:10]:
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

    extracted_text = extracted_text.strip()[:6000]
    return JSONResponse({"status": "ok", "filename": file.filename, "text": extracted_text})

# ----------------- BULLETPROOF OWNER TELEMETRY -----------------
@app.get("/api/owner/telemetry")
def get_owner_telemetry(user_id: int = 0, username: str = ""):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        # 1. Total Visits
        cur.execute("SELECT value FROM site_stats WHERE key = 'total_visits'")
        v_row = cur.fetchone()
        total_visits = v_row[0] if v_row else 0

        # 2. Registered Users
        cur.execute("SELECT id, username, role, last_active, created_at FROM users ORDER BY id DESC")
        users_list = [{"id": u[0], "username": u[1], "role": u[2], "last_active": str(u[3]), "created_at": str(u[4])} for u in cur.fetchall()]

        # 3. Online Users Count
        if engine == "postgres":
            cur.execute("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '15 minutes'")
        else:
            cur.execute("SELECT COUNT(*) FROM users WHERE datetime(last_active) >= datetime('now', '-15 minutes')")
        online_count = cur.fetchone()[0]

        # 4. Complaints
        cur.execute("SELECT id, username, category, message, image_proof, status, created_at FROM complaints ORDER BY id DESC")
        complaints_list = [{"id": r[0], "username": r[1], "category": r[2], "message": r[3], "image_proof": r[4], "status": r[5] or "Open", "created_at": str(r[6])} for r in cur.fetchall()]

        # 5. Core Mode Distribution
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
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        conn.close()

@app.post("/api/owner/announcement/set")
def set_announcement(message: str = Form(...), username: str = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        msg = message.strip()
        if engine == "postgres":
            cur.execute("UPDATE announcements SET is_active = FALSE")
            if msg:
                cur.execute("INSERT INTO announcements (message, is_active) VALUES (%s, TRUE)", (msg,))
        else:
            cur.execute("UPDATE announcements SET is_active = 0")
            if msg:
                cur.execute("INSERT INTO announcements (message, is_active) VALUES (?, 1)", (msg,))
        conn.commit()
        return JSONResponse({"status": "ok"})
    finally:
        conn.close()

@app.post("/api/owner/user/delete")
def delete_user_by_owner(target_user_id: int = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "DELETE FROM users WHERE id = %s" if engine == "postgres" else "DELETE FROM users WHERE id = ?"
        cur.execute(sql, (target_user_id,))
        conn.commit()
        return JSONResponse({"status": "ok"})
    finally:
        conn.close()

@app.post("/api/owner/complaint/status")
def update_complaint_status(complaint_id: int = Form(...), new_status: str = Form(...)):
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "UPDATE complaints SET status = %s WHERE id = %s" if engine == "postgres" else "UPDATE complaints SET status = ? WHERE id = ?"
        cur.execute(sql, (new_status, complaint_id))
        conn.commit()
        return JSONResponse({"status": "ok"})
    finally:
        conn.close()

def detect_tts_language(text: str) -> str:
    devanagari = re.search(r'[\u0900-\u097F]', text)
    if devanagari:
        return "hi"
    hinglish_markers = ["hai", "hoon", "aap", "kaise", "kya", "bhai", "karo", "nahi", "accha", "samjha", "dost", "mera", "meri", "hum", "sahi", "galat", "dimag"]
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
            title = generate_ai_title(query if query else "Image Analysis", mode)
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
                title = generate_ai_title(query if query else "Image Analysis", mode)
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
            reply = "I was engineered by Utkarsh Bandhu. He conceptualized and developed my cognitive architecture, instilling both my intellectual rigor and analytical capacity."
            emotion = "Brilliant"
        else:
            h_sql = "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT 8" if engine == "postgres" else "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 8"
            cur.execute(h_sql, (session_id,))
            past_rows = cur.fetchall()
            history = [{"role": r[0], "content": r[1]} for r in reversed(past_rows)]
            reply, emotion = ask_groq_vision_or_llm(query, mode, history, image_base64)

        ins_m = "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_m, (session_id, 'user', query if query else "[Visual Data Transmitted]", mode, image_base64))
        
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
    mode: str = Form("intellect"),
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
    mode: str = Form("intellect"),
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
# 🛡️ SOVEREIGN COMMAND PORTAL: /owner
# =====================================================================
@app.get("/owner", response_class=HTMLResponse)
async def serve_owner_dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Lemon AI | Sovereign Command Center</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
        <style>
            :root {
                --gold: #facc15;
                --gold-glow: rgba(250, 204, 21, 0.4);
                --bg-deep: #05070f;
                --card: rgba(14, 20, 36, 0.92);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-high: #f8fafc;
                --text-muted: #94a3b8;
                --red: #ef4444;
            }
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
            body { background: radial-gradient(circle at 50% 0%, #151b3d 0%, var(--bg-deep) 85%); color: var(--text-high); min-height: 100vh; display: flex; flex-direction: column; }
            
            ::-webkit-scrollbar { width: 14px; height: 14px; }
            ::-webkit-scrollbar-track { background: rgba(12, 16, 28, 0.75); border-left: 1px solid rgba(255, 255, 255, 0.06); }
            ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, #facc15 0%, #ca8a04 100%); border-radius: 8px; border: 3px solid rgba(12, 16, 28, 0.85); }

            .owner-nav {
                padding: 16px 28px; background: rgba(9, 13, 24, 0.9); backdrop-filter: blur(20px); border-bottom: 1px solid var(--card-border);
                display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100;
            }
            .brand { display: flex; align-items: center; gap: 12px; }
            .brand-badge { width: 42px; height: 42px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 22px; }
            .brand-title { font-size: 17px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; }
            .brand-sub { font-size: 11px; color: var(--text-muted); }
            .status-pill { display: inline-flex; align-items: center; gap: 6px; background: rgba(34, 197, 94, 0.15); border: 1px solid rgba(34, 197, 94, 0.4); color: #4ade80; padding: 5px 12px; border-radius: 20px; font-size: 12px; font-weight: 700; }
            .dot-pulse { width: 8px; height: 8px; background: #22c55e; border-radius: 50%; box-shadow: 0 0 8px #22c55e; }

            .container { padding: 28px; max-width: 1300px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 24px; }

            .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 16px; }
            .metric-card {
                background: var(--card); border: 1px solid var(--card-border); border-radius: 20px; padding: 20px;
                box-shadow: 0 8px 30px rgba(0,0,0,0.5); position: relative; overflow: hidden;
            }
            .metric-card::after { content: ''; position: absolute; top: 0; right: 0; width: 60px; height: 60px; background: radial-gradient(circle, var(--gold-glow) 0%, transparent 70%); }
            .metric-title { font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px; }
            .metric-value { font-size: 32px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; color: #fff; }
            .metric-tag { font-size: 11px; color: #fde047; margin-top: 6px; font-weight: 600; }

            .broadcast-card {
                background: linear-gradient(135deg, rgba(250, 204, 21, 0.08), rgba(20, 28, 48, 0.8));
                border: 1px solid rgba(250, 204, 21, 0.3); border-radius: 20px; padding: 20px; display: flex; flex-direction: column; gap: 10px;
            }
            .broadcast-input-box { display: flex; gap: 10px; }
            .broadcast-input-box input {
                flex: 1; background: rgba(0, 0, 0, 0.4); border: 1px solid var(--card-border); border-radius: 12px;
                padding: 12px 14px; color: #fff; font-size: 14px; outline: none;
            }
            .broadcast-input-box input:focus { border-color: var(--gold); }
            .broadcast-btn {
                background: linear-gradient(135deg, #facc15, #f59e0b); border: none; border-radius: 12px; padding: 0 20px;
                color: #000; font-weight: 700; cursor: pointer; font-size: 13.5px;
            }

            .sections-split { display: grid; grid-template-columns: 1.3fr 1fr; gap: 20px; }
            @media (max-width: 900px) { .sections-split { grid-template-columns: 1fr; } }

            .panel {
                background: var(--card); border: 1px solid var(--card-border); border-radius: 22px; padding: 22px;
                display: flex; flex-direction: column; gap: 14px; box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            }
            .panel-header { display: flex; align-items: center; justify-content: space-between; }
            .panel-title { font-size: 15px; font-weight: 700; color: #facc15; text-transform: uppercase; letter-spacing: 0.5px; }

            .search-input {
                width: 100%; background: rgba(22, 30, 50, 0.8); border: 1px solid var(--card-border);
                border-radius: 12px; padding: 10px 14px; color: #fff; font-size: 13px; outline: none; margin-bottom: 6px;
            }
            .search-input:focus { border-color: var(--gold); }

            .table-container { max-height: 400px; overflow-y: auto; }
            table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
            th { text-align: left; padding: 10px 8px; color: var(--text-muted); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.08); position: sticky; top: 0; background: #0e1424; }
            td { padding: 10px 8px; border-bottom: 1px solid rgba(255,255,255,0.04); }
            tr:hover td { background: rgba(250, 204, 21, 0.05); }

            .complaint-box {
                background: rgba(20, 28, 48, 0.6); border: 1px solid var(--card-border); border-radius: 14px;
                padding: 14px; display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;
            }
            .complaint-top { display: flex; justify-content: space-between; align-items: center; }
            .badge-cat { font-size: 10px; background: rgba(250, 204, 21, 0.15); color: #fde047; padding: 2px 7px; border-radius: 6px; font-weight: 700; }
            .trouble-thumb {
                max-width: 180px; max-height: 120px; border-radius: 8px; border: 1px solid rgba(250, 204, 21, 0.3);
                cursor: pointer; object-fit: cover; margin-top: 6px; display: block;
            }

            .action-btn-sm {
                background: rgba(255,255,255,0.08); border: 1px solid var(--card-border); border-radius: 8px;
                color: #fff; padding: 3px 8px; font-size: 11px; cursor: pointer;
            }
            .action-btn-sm:hover { background: var(--gold); color: #000; }
            .action-btn-del { color: #f87171; border-color: rgba(248,113,113,0.3); }
            .action-btn-del:hover { background: #ef4444; color: #fff; }
        </style>
    </head>
    <body>
        <header class="owner-nav">
            <div class="brand">
                <div class="brand-badge">🍋</div>
                <div>
                    <div class="brand-title">Lemon Sovereign Command</div>
                    <div class="brand-sub">Master Mind: <b>Utkarsh Bandhu</b></div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:14px;">
                <div class="status-pill"><div class="dot-pulse"></div> Verified Owner Session</div>
                <button onclick="location.href='/'" style="background:rgba(255,255,255,0.08); border:1px solid var(--card-border); color:#fff; padding:6px 14px; border-radius:14px; font-size:12px; cursor:pointer;">← Return to App</button>
            </div>
        </header>

        <main class="container">
            <div class="broadcast-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <b style="font-size:13.5px; color:#fde047;">📢 Push Global Announcement Banner to All Users</b>
                    <span style="font-size:11px; color:#94a3b8;">Instantly renders at top of every user's screen</span>
                </div>
                <div class="broadcast-input-box">
                    <input type="text" id="broadcastInput" placeholder="Type live alert (e.g. '🔥 New Vision Core v2 deployed! Upload math problems now')..." />
                    <button class="broadcast-btn" onclick="publishAnnouncement()">Transmit Alert</button>
                    <button class="broadcast-btn" style="background:#ef4444; color:#fff;" onclick="clearAnnouncement()">Clear</button>
                </div>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-title">Total Visits</div>
                    <div class="metric-value" id="valVisits">0</div>
                    <div class="metric-tag">● Persistent Hit Counter</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Registered Users</div>
                    <div class="metric-value" id="valUsers">0</div>
                    <div class="metric-tag">● Safe in DB</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Live Active Users</div>
                    <div class="metric-value" id="valOnline" style="color:#4ade80;">0</div>
                    <div class="metric-tag">● Active in last 15 mins</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Complaints / Reports</div>
                    <div class="metric-value" id="valComplaints" style="color:#f87171;">0</div>
                    <div class="metric-tag">● With Trouble Photos</div>
                </div>
                <div class="metric-card">
                    <div class="metric-title">Total Conversations</div>
                    <div class="metric-value" id="valSessions">0</div>
                    <div class="metric-tag">● Total Sessions Generated</div>
                </div>
            </div>

            <div class="sections-split">
                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">👥 Registered Accounts Registry</div>
                        <span id="userCountBadge" style="font-size:11px; color:var(--text-muted);"></span>
                    </div>
                    <input type="text" id="userSearch" class="search-input" placeholder="Search by username..." oninput="filterUsers()" />
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Username</th>
                                    <th>Privilege</th>
                                    <th>Last Active</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody id="usersTbody">
                                <tr><td colspan="5" style="text-align:center;">Loading users...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>

                <div class="panel">
                    <div class="panel-header">
                        <div class="panel-title">🚨 Complaints & Bug Feed (Trouble Photos)</div>
                        <button onclick="loadTelemetry()" style="background:none; border:none; color:var(--gold); font-size:12px; cursor:pointer;">↻ Refresh</button>
                    </div>
                    <div class="table-container" id="complaintsList">
                        Loading reports...
                    </div>
                </div>
            </div>
        </main>

        <script>
            let fullUsersData = [];

            async function loadTelemetry() {
                try {
                    const res = await fetch('/api/owner/telemetry?username=utkarsh');
                    const d = await res.json();
                    
                    if (d.status !== "ok") {
                        alert(d.message || "Failed to load telemetry.");
                        return;
                    }

                    document.getElementById("valVisits").innerText = d.total_visits;
                    document.getElementById("valUsers").innerText = d.total_users;
                    document.getElementById("valOnline").innerText = d.online_users;
                    document.getElementById("valComplaints").innerText = d.complaints.length;
                    document.getElementById("valSessions").innerText = d.total_sessions;

                    fullUsersData = d.users || [];
                    renderUsersTable(fullUsersData);

                    const cBox = document.getElementById("complaintsList");
                    if (d.complaints && d.complaints.length > 0) {
                        cBox.innerHTML = d.complaints.map(c => `
                            <div class="complaint-box">
                                <div class="complaint-top">
                                    <b style="color:#fde047;">${c.username}</b>
                                    <div>
                                        <span class="badge-cat">${c.category}</span>
                                        <span style="font-size:10px; margin-left:6px; color:${c.status === 'Resolved' ? '#4ade80' : '#f87171'};">[${c.status}]</span>
                                    </div>
                                </div>
                                <div style="font-size:12.5px; color:#e2e8f0; margin-top:2px;">${c.message}</div>
                                ${c.image_proof ? `
                                    <div style="margin-top:6px;">
                                        <a href="${c.image_proof}" target="_blank" title="Click to view full photo">
                                            <img src="${c.image_proof}" class="trouble-thumb" alt="Trouble photo">
                                        </a>
                                        <span style="font-size:10px; color:#94a3b8;">📷 Click thumbnail to inspect full resolution</span>
                                    </div>
                                ` : ''}
                                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                                    <span style="font-size:10px; color:var(--text-muted);">${c.created_at}</span>
                                    <div>
                                        <button class="action-btn-sm" onclick="setComplaintStatus(${c.id}, 'Resolved')">✓ Resolve</button>
                                        <button class="action-btn-sm action-btn-del" onclick="setComplaintStatus(${c.id}, 'Dismissed')">✕ Dismiss</button>
                                    </div>
                                </div>
                            </div>
                        `).join("");
                    } else {
                        cBox.innerHTML = "<div style='font-size:12px; color:var(--text-muted); padding:10px;'>No pending reports.</div>";
                    }
                } catch(e) {
                    console.error("Telemetry error:", e);
                }
            }

            function renderUsersTable(list) {
                const tbody = document.getElementById("usersTbody");
                document.getElementById("userCountBadge").innerText = `${list.length} accounts found`;
                if (list.length === 0) {
                    tbody.innerHTML = "<tr><td colspan='5' style='text-align:center;'>No matching users.</td></tr>";
                    return;
                }
                tbody.innerHTML = list.map(u => `
                    <tr>
                        <td style="color:#94a3b8;">${u.id}</td>
                        <td><b>${u.username}</b></td>
                        <td><span style="color:${u.role === 'owner' ? '#facc15' : '#94a3b8'}; font-weight:${u.role === 'owner' ? '700' : '400'};">${u.role}</span></td>
                        <td style="color:#38bdf8; font-size:11.5px;">${u.last_active || 'Recent'}</td>
                        <td>
                            ${u.username.toLowerCase() !== 'utkarsh' ? `
                                <button class="action-btn-sm action-btn-del" onclick="deleteUserByOwner(${u.id}, '${u.username}')">Purge</button>
                            ` : '<span style="font-size:11px; color:#facc15;">Master</span>'}
                        </td>
                    </tr>
                `).join("");
            }

            function filterUsers() {
                const q = document.getElementById("userSearch").value.toLowerCase();
                const filtered = fullUsersData.filter(u => u.username.toLowerCase().includes(q));
                renderUsersTable(filtered);
            }

            async function publishAnnouncement() {
                const msg = document.getElementById("broadcastInput").value.trim();
                if (!msg) return alert("Enter announcement text.");
                const fd = new FormData();
                fd.append("message", msg);
                fd.append("username", "utkarsh");
                await fetch("/api/owner/announcement/set", { method: "POST", body: fd });
                alert("Announcement broadcasted successfully to all users!");
            }

            async function clearAnnouncement() {
                const fd = new FormData();
                fd.append("message", "");
                fd.append("username", "utkarsh");
                await fetch("/api/owner/announcement/set", { method: "POST", body: fd });
                document.getElementById("broadcastInput").value = "";
                alert("Announcement cleared.");
            }

            async function deleteUserByOwner(id, name) {
                if (!confirm(`Permanently purge account: ${name}?`)) return;
                const fd = new FormData();
                fd.append("target_user_id", id);
                await fetch("/api/owner/user/delete", { method: "POST", body: fd });
                loadTelemetry();
            }

            async function setComplaintStatus(id, status) {
                const fd = new FormData();
                fd.append("complaint_id", id);
                fd.append("new_status", status);
                await fetch("/api/owner/complaint/status", { method: "POST", body: fd });
                loadTelemetry();
            }

            setInterval(loadTelemetry, 25000);
            loadTelemetry();
        </script>
    </body>
    </html>
    """

# =====================================================================
# 🌐 MAIN USER INTERFACE: /
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
        <title>Lemon AI | Sovereign Intellect & Cognitive Chambers</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.45);
                --rage-red: #ef4444;
                --bg-deep: #070913;
                --card-surface: rgba(18, 24, 38, 0.90);
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
            ::-webkit-scrollbar-thumb:hover { background: linear-gradient(180deg, #fde047 0%, #eab308 100%); border-width: 2px; }

            .broadcast-banner {
                display: none; background: linear-gradient(90deg, #f59e0b, #ef4444); color: #000; font-size: 12.5px;
                font-weight: 700; text-align: center; padding: 6px 12px; z-index: 1000;
            }

            .overlay-modal {
                position: fixed; inset: 0; background: rgba(5, 7, 15, 0.94); backdrop-filter: blur(20px);
                display: none; align-items: center; justify-content: center; z-index: 3000;
            }
            .modal-card {
                background: var(--card-surface); border: 1px solid var(--card-border); border-radius: 24px;
                padding: 30px 26px; width: 90%; max-width: 440px; box-shadow: 0 10px 40px rgba(0,0,0,0.85);
            }
            .modal-card h2 { font-size: 20px; font-weight: 700; margin-bottom: 6px; font-family: 'Space Grotesk', sans-serif; }
            .modal-card p { font-size: 13px; color: var(--text-muted); margin-bottom: 16px; line-height: 1.4; }
            .styled-input, .styled-textarea, .styled-select {
                width: 100%; background: rgba(30, 41, 59, 0.8); border: 1px solid var(--card-border);
                border-radius: 14px; padding: 12px 14px; color: #fff; font-size: 14px; margin-bottom: 12px; outline: none;
            }
            .styled-textarea { height: 85px; resize: none; }
            .styled-input:focus, .styled-textarea:focus { border-color: var(--primary); }
            .action-submit-btn {
                width: 100%; background: linear-gradient(135deg, #facc15, #f59e0b); border: none; border-radius: 14px;
                padding: 13px; color: #0b0f19; font-weight: 700; font-size: 14.5px; cursor: pointer;
            }

            .proof-preview-bar {
                display: none; align-items: center; justify-content: space-between; padding: 6px 12px;
                background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(250, 204, 21, 0.3); border-radius: 12px; margin-bottom: 12px;
            }
            .proof-preview-bar img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; }
            .proof-remove { color: #f87171; cursor: pointer; font-size: 13px; font-weight: 700; }

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

            .current-chamber-pill {
                background: rgba(250, 204, 21, 0.12); border: 1px solid rgba(250, 204, 21, 0.35); color: #fde047;
                padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
            }

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

            .sidebar-section-title {
                font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;
                letter-spacing: 0.6px; margin: 10px 0 6px;
            }

            .core-btn-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
            .core-choice {
                background: rgba(30, 41, 59, 0.6); border: 1px solid var(--card-border); color: var(--text-muted);
                padding: 8px 6px; border-radius: 10px; font-size: 11.5px; font-weight: 600; cursor: pointer; text-align: center;
                display: flex; align-items: center; justify-content: center; gap: 4px; transition: all 0.2s;
            }
            .core-choice:hover { background: rgba(250, 204, 21, 0.15); color: #fff; }
            .core-choice.selected { background: var(--primary); color: #0b0f19; font-weight: 700; border-color: var(--primary); }

            .sessions-list { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
            .session-item {
                display: flex; align-items: center; justify-content: space-between; padding: 9px 12px;
                background: rgba(30, 41, 59, 0.4); border: 1px solid var(--card-border); border-radius: 12px;
                cursor: pointer; transition: all 0.2s;
            }
            .session-item:hover, .session-item.active { background: rgba(250, 204, 21, 0.12); border-color: rgba(250, 204, 21, 0.3); }
            .session-title { font-size: 12.5px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 190px; }
            .session-delete { color: #f87171; font-size: 13px; opacity: 0.6; padding: 2px 6px; }
            .session-delete:hover { opacity: 1; }

            .owner-menu-btn {
                display: none; background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.4);
                color: #fde047; padding: 9px; border-radius: 12px; font-weight: 800; font-size: 12.5px;
                text-align: center; cursor: pointer; margin-bottom: 8px;
            }
            .feedback-menu-btn {
                background: rgba(255, 255, 255, 0.06); border: 1px solid var(--card-border);
                color: #cbd5e1; padding: 8px; border-radius: 12px; font-weight: 600; font-size: 12px;
                text-align: center; cursor: pointer; margin-bottom: 8px;
            }

            .chat-container {
                flex: 1; overflow-y: scroll; padding: 20px 18px 30px; display: flex; flex-direction: column; gap: 18px; position: relative;
            }

            .hero-greeting {
                margin: auto; display: flex; flex-direction: column; align-items: center; text-align: center; width: 90%; max-width: 540px;
            }
            .hero-logo {
                width: 76px; height: 76px; border-radius: 24px; background: linear-gradient(135deg, #facc15, #f59e0b);
                display: flex; align-items: center; justify-content: center; font-size: 40px;
                box-shadow: 0 10px 32px var(--primary-glow); margin-bottom: 16px;
            }
            .hero-title {
                font-size: 25px; font-weight: 800; font-family: 'Space Grotesk', sans-serif;
                background: linear-gradient(135deg, #ffffff 40%, #facc15 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                margin-bottom: 6px;
            }
            .hero-sub { font-size: 14px; color: var(--text-muted); margin-bottom: 12px; line-height: 1.5; }
            .hero-badge {
                display: inline-flex; align-items: center; gap: 6px; background: rgba(250, 204, 21, 0.1);
                border: 1px solid rgba(250, 204, 21, 0.25); padding: 5px 14px; border-radius: 20px;
                font-size: 12px; color: #fde047; font-weight: 600; margin-bottom: 22px;
            }

            .bubble-group { display: flex; flex-direction: column; max-width: 86%; animation: popIn 0.3s ease; }
            @keyframes popIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

            .bubble-group.lemon { align-self: flex-start; }
            .bubble-group.user { align-self: flex-end; }

            .bubble { padding: 14px 18px; border-radius: 20px; font-size: 14.5px; line-height: 1.65; word-break: break-word; }
            .bubble.lemon {
                background: var(--card-surface); border: 1px solid var(--card-border); color: #f1f5f9; border-bottom-left-radius: 4px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }
            .bubble.user {
                background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-weight: 600; border-bottom-right-radius: 4px;
                box-shadow: 0 4px 16px var(--primary-glow);
            }

            .chat-img-thumb { max-width: 260px; border-radius: 12px; margin-bottom: 10px; border: 1px solid rgba(255, 255, 255, 0.2); display: block; }

            .bubble.lemon h1, .bubble.lemon h2, .bubble.lemon h3 { margin: 10px 0 6px; font-size: 15.5px; color: #fde047; font-weight: 700; }
            .bubble.lemon p { margin-bottom: 8px; }
            .bubble.lemon pre {
                background: var(--code-bg); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
                padding: 12px; overflow-x: auto; font-family: 'JetBrains Mono', monospace; font-size: 13px; margin: 10px 0;
            }
            .bubble.lemon code { font-family: 'JetBrains Mono', monospace; background: rgba(255,255,255,0.08); padding: 2px 5px; border-radius: 4px; font-size: 13px; }
            .bubble.lemon pre code { background: none; padding: 0; }

            .message-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); }
            .msg-action-btn {
                background: rgba(255,255,255,0.06); border: 1px solid var(--card-border); border-radius: 12px;
                color: #94a3b8; font-size: 11.5px; padding: 3px 8px; cursor: pointer; display: flex; align-items: center; gap: 4px;
            }
            .msg-action-btn:hover { background: rgba(250, 204, 21, 0.15); color: #facc15; }

            .feeling-tag { font-size: 10px; text-transform: uppercase; font-weight: 800; padding: 2px 7px; border-radius: 8px; margin-bottom: 6px; display: inline-block; background: rgba(250, 204, 21, 0.15); color: #facc15; }

            .thinking-box {
                display: flex; align-items: center; gap: 6px; padding: 10px 16px;
                background: rgba(22, 28, 45, 0.6); border: 1px dashed rgba(250, 204, 21, 0.4); border-radius: 16px; width: fit-content;
            }
            .tdot { width: 6px; height: 6px; background: #facc15; border-radius: 50%; animation: dotB 1.4s infinite ease-in-out both; }
            .tdot:nth-child(1) { animation-delay: -0.32s; }
            .tdot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes dotB { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

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

            .img-preview-bar {
                display: none; align-items: center; gap: 10px; padding: 6px 14px; margin-bottom: 6px;
                background: rgba(24, 32, 50, 0.95); border: 1px solid rgba(250, 204, 21, 0.4); border-radius: 16px; width: fit-content;
            }
            .img-preview-bar img { width: 40px; height: 40px; border-radius: 8px; object-fit: cover; }
            .img-preview-bar span { font-size: 12.5px; color: #facc15; font-weight: 600; }
            .img-remove-btn { color: #f87171; cursor: pointer; font-size: 15px; font-weight: 700; }

            .bottom-dock {
                padding: 10px 18px 18px; background: rgba(9, 13, 22, 0.94); backdrop-filter: blur(20px); border-top: 1px solid var(--card-border);
                flex-shrink: 0;
            }
            .dock-status { font-size: 11.5px; color: var(--text-muted); text-align: center; margin-bottom: 6px; min-height: 16px; }
            .input-dock {
                display: flex; align-items: center; background: rgba(24, 32, 50, 0.92); border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 36px; padding: 4px 6px 4px 14px; gap: 6px; box-shadow: 0 10px 30px rgba(0,0,0,0.45);
            }
            .input-dock input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14.5px; outline: none; }
            .input-dock input::placeholder { color: #64748b; }

            .dock-btn {
                width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
            }
            .dock-btn:active { transform: scale(0.92); }
            .cam-btn { background: rgba(255, 255, 255, 0.08); color: #38bdf8; font-size: 16px; }
            .doc-btn { background: rgba(255, 255, 255, 0.08); color: #a78bfa; font-size: 16px; }
            .mic-btn { background: rgba(255, 255, 255, 0.08); color: #facc15; font-size: 17px; }
            .mic-btn.active-record { background: #ef4444; color: #fff; animation: pulse 1.2s infinite; }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
            .stop-btn {
                display: none; background: #ef4444; color: #fff; font-size: 14px; font-weight: 700; width: 38px; height: 38px; border-radius: 50%;
            }
            .send-btn { background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-size: 15px; font-weight: 700; }
        </style>
    </head>
    <body>
        <div class="broadcast-banner" id="globalBanner"></div>

        <div class="camera-modal" id="cameraModal">
            <div class="camera-box">
                <h3 style="font-size:16px;">📷 Optical Inspection (Vision)</h3>
                <video class="camera-video" id="cameraVideo" autoplay playsinline muted></video>
                <canvas id="cameraCanvas" style="display:none;"></canvas>
                <div class="camera-ctrls">
                    <button class="action-submit-btn" style="width:auto; padding:10px 20px;" onclick="captureSnapshot()">📸 Capture</button>
                    <label class="action-submit-btn" style="width:auto; padding:10px 20px; cursor:pointer; background:rgba(255,255,255,0.08); color:#fff;">
                        📁 Upload
                        <input type="file" id="fileUploadInput" accept="image/*" style="display:none;" onchange="handleFileUpload(event)">
                    </label>
                    <button class="action-submit-btn" style="width:auto; padding:10px 20px; background:#ef4444; color:#fff;" onclick="closeCamera()">✕ Cancel</button>
                </div>
            </div>
        </div>

        <div class="overlay-modal" id="authModal" style="display:none;">
            <div class="modal-card">
                <h2 id="authHeading">Access Lemon AI</h2>
                <p id="authSub">Sign in or create account to preserve isolated cognitive chambers.</p>
                <div class="auth-error" id="authErrorMsg"></div>
                <input type="text" id="authUsername" class="styled-input" placeholder="Username" autocomplete="off" />
                <input type="password" id="authPassword" class="styled-input" placeholder="Password" />
                <button class="action-submit-btn" id="authSubmitBtn" onclick="handleAuthSubmit()">Enter System</button>
                <div style="text-align:center; margin-top:14px; font-size:13px; color:var(--text-muted); cursor:pointer;" onclick="toggleAuthMode()">
                    <span id="authToggleText" style="color:var(--primary); font-weight:600; text-decoration:underline;">No account? Create one</span>
                </div>
            </div>
        </div>

        <div class="overlay-modal" id="feedbackModal">
            <div class="modal-card">
                <h2>💬 Report Issue / Feedback</h2>
                <p>Submit bugs, errors, or feedback directly to Utkarsh Bandhu.</p>
                <select id="feedbackCategory" class="styled-select">
                    <option value="Bug / Error">Bug / App Error</option>
                    <option value="Vision Problem">Camera / Vision Mistake</option>
                    <option value="Voice Synthesis">Voice / Audio Issue</option>
                    <option value="General Feedback">General Feedback</option>
                </select>
                <textarea id="feedbackMessage" class="styled-textarea" placeholder="Explain the trouble or issue in detail..."></textarea>
                
                <div class="proof-preview-bar" id="reportProofBar">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <img id="reportProofThumb" src="" alt="trouble proof">
                        <span style="font-size:12px; color:#facc15;">Photo Attached</span>
                    </div>
                    <span class="proof-remove" onclick="clearReportPhoto()">✕ Remove</span>
                </div>

                <label class="action-submit-btn" style="display:flex; align-items:center; justify-content:center; gap:6px; background:rgba(255,255,255,0.08); color:#fde047; margin-bottom:12px; cursor:pointer; font-size:13px; padding:10px;">
                    <span>📷 Attach Photo of Trouble</span>
                    <input type="file" id="reportPhotoInput" accept="image/*" style="display:none;" onchange="handleReportPhotoUpload(event)">
                </label>

                <div style="display:flex; gap:10px;">
                    <button class="action-submit-btn" onclick="sendComplaint()">Submit Report</button>
                    <button class="action-submit-btn" style="background:rgba(255,255,255,0.08); color:#fff;" onclick="closeFeedbackModal()">Cancel</button>
                </div>
            </div>
        </div>

        <div class="sidebar-overlay" id="sidebarOverlay" onclick="closeSidebar()"></div>

        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div>
                    <h3 style="font-size:16px;">Cognitive Chambers</h3>
                    <div style="font-size:11px; color:#94a3b8;">Created by <b style="color:#facc15;">Utkarsh Bandhu</b></div>
                </div>
                <button class="sidebar-close" onclick="closeSidebar()">✕</button>
            </div>

            <button class="owner-menu-btn" id="ownerMenuBtn" onclick="location.href='/owner'">🛡️ Open Sovereign Portal</button>
            <button class="feedback-menu-btn" onclick="openFeedbackModal()">💬 Report Issue / Feedback</button>

            <div class="sidebar-section-title">Launch Specific Chamber</div>
            <div class="core-btn-grid">
                <button class="core-choice" id="core-intellect" onclick="switchDedicatedChamber('intellect')">⚡ Intellect</button>
                <button class="core-choice" id="core-rage" onclick="switchDedicatedChamber('rage')">🔥 Rage</button>
                <button class="core-choice" id="core-solver" onclick="switchDedicatedChamber('solver')">🧠 Solver</button>
                <button class="core-choice" id="core-study" onclick="switchDedicatedChamber('study')">📚 Study</button>
                <button class="core-choice" id="core-philosophy" onclick="switchDedicatedChamber('philosophy')">🌌 Philosophy</button>
                <button class="core-choice" id="core-strategy" onclick="switchDedicatedChamber('strategy')">🛡️ Strategy</button>
                <button class="core-choice" id="core-creative" onclick="switchDedicatedChamber('creative')">🎨 Creative</button>
                <button class="core-choice" id="core-emotional" onclick="switchDedicatedChamber('emotional')">💖 Emotional</button>
                <button class="core-choice" id="core-zen" onclick="switchDedicatedChamber('zen')">🌿 Zen</button>
                <button class="core-choice" id="core-hybrid" onclick="switchDedicatedChamber('hybrid')">🌟 Hybrid</button>
            </div>

            <div class="sidebar-section-title">Saved Discussions</div>
            <div class="sessions-list" id="sessionsList"></div>

            <div style="margin-top:auto; padding-top:12px; border-top:1px solid var(--card-border);">
                <div style="font-size:12px; color:#94a3b8; margin-bottom:6px;">Signed in: <b id="sidebarUsername" style="color:#fff;">Guest</b></div>
                <button class="action-submit-btn" style="width:100%; padding:8px; font-size:12px; color:#f87171; border:1px solid rgba(248,113,113,0.3); background:none;" onclick="logout()">Terminate Session</button>
            </div>
        </aside>

        <header class="header">
            <div class="header-left">
                <button class="menu-trigger" onclick="openSidebar()" title="Chambers & History">☰</button>
                <div class="brand-badge">🍋</div>
                <div>
                    <div class="brand-title">Lemon AI</div>
                    <div class="creator-tag">Engineered by <b>Utkarsh Bandhu</b></div>
                </div>
            </div>
            <div style="display:flex; align-items:center; gap:8px;">
                <button onclick="exportCurrentChat()" style="background:rgba(255,255,255,0.06); border:1px solid var(--card-border); color:#fde047; padding:5px 12px; border-radius:14px; font-size:11.5px; font-weight:700; cursor:pointer;" title="Download Conversation as Markdown Note">💾 Export</button>
                <div class="current-chamber-pill" id="currentChamberBadge">⚡ INTELLECT</div>
            </div>
        </header>

        <main class="chat-container" id="chatStream">
            <div class="hero-greeting" id="heroGreeting">
                <div class="hero-logo">🍋</div>
                <div class="hero-title" id="heroGreetingName">Intellect Awaiting Inquiry</div>
                <div class="hero-sub" id="heroGreetingSub">Pure cognitive architecture. Select any chamber to activate dedicated first-principles reasoning.</div>
                <div class="hero-badge">
                    <span>⚡</span> Architected by Utkarsh Bandhu
                </div>
            </div>
        </main>

        <footer class="bottom-dock">
            <div class="img-preview-bar" id="imgPreviewBar">
                <img id="imgPreviewThumb" src="" alt="preview">
                <span id="imgPreviewLabel">Visual Artifact Attached</span>
                <span class="img-remove-btn" onclick="clearAttachedImage()">✕</span>
            </div>

            <div class="dock-status" id="dockStatus">● Chamber Ready</div>
            <div class="input-dock">
                <button class="dock-btn cam-btn" onclick="requestCameraAccess()" title="Camera / Optical Inspection">📷</button>
                <label class="dock-btn doc-btn" style="cursor:pointer;" title="Upload PDF or Document Code">
                    📄
                    <input type="file" id="docFileInput" accept=".pdf,.txt,.py,.js,.cpp,.c,.md" style="display:none;" onchange="handleDocFileUpload(event)">
                </label>
                <input type="text" id="textInput" placeholder="Pose an inquiry, attach code or PDF..." onkeydown="if(event.key==='Enter') sendTextQuery()" />
                <button class="dock-btn mic-btn" id="micBtn" onclick="requestMicAndRecord()" title="Microphone">🎙️</button>
                <button class="dock-btn stop-btn" id="stopBtn" onclick="stopLemonSpeaking()" title="Stop Speaking">⏹</button>
                <button class="dock-btn send-btn" onclick="sendTextQuery()" title="Send">➤</button>
            </div>
        </footer>

        <audio id="audioElement" autoplay></audio>

        <script>
            let currentUserId = localStorage.getItem("lemon_user_id");
            let currentUsername = localStorage.getItem("lemon_username") || "Thinker";
            let currentUserRole = localStorage.getItem("lemon_user_role") || "user";
            let currentSessionId = parseInt(localStorage.getItem("lemon_current_session_id") || "0");
            let currentCoreMode = localStorage.getItem("lemon_active_core") || "intellect";
            let isAuthRegister = false;
            let isRecording = false;
            let mediaRecorder = null;
            let audioChunks = [];
            let currentThinkingEl = null;

            let attachedImageBase64 = null;
            let reportPhotoBase64 = null;
            let cameraStream = null;

            const authModal = document.getElementById("authModal");
            const authErrorMsg = document.getElementById("authErrorMsg");
            const authHeading = document.getElementById("authHeading");
            const authSub = document.getElementById("authSub");
            const authSubmitBtn = document.getElementById("authSubmitBtn");
            const authToggleText = document.getElementById("authToggleText");

            const feedbackModal = document.getElementById("feedbackModal");
            const reportProofBar = document.getElementById("reportProofBar");
            const reportProofThumb = document.getElementById("reportProofThumb");
            const ownerMenuBtn = document.getElementById("ownerMenuBtn");

            const sidebar = document.getElementById("sidebar");
            const sidebarOverlay = document.getElementById("sidebarOverlay");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const micBtn = document.getElementById("micBtn");
            const stopBtn = document.getElementById("stopBtn");
            const dockStatus = document.getElementById("dockStatus");
            const audioElement = document.getElementById("audioElement");
            const sidebarUsername = document.getElementById("sidebarUsername");
            const sessionsList = document.getElementById("sessionsList");
            const heroGreeting = document.getElementById("heroGreeting");
            const heroGreetingName = document.getElementById("heroGreetingName");
            const heroGreetingSub = document.getElementById("heroGreetingSub");
            const currentChamberBadge = document.getElementById("currentChamberBadge");
            const globalBanner = document.getElementById("globalBanner");

            const cameraModal = document.getElementById("cameraModal");
            const cameraVideo = document.getElementById("cameraVideo");
            const cameraCanvas = document.getElementById("cameraCanvas");
            const imgPreviewBar = document.getElementById("imgPreviewBar");
            const imgPreviewThumb = document.getElementById("imgPreviewThumb");

            function stopLemonSpeaking() {
                if (audioElement) {
                    audioElement.pause();
                    audioElement.currentTime = 0;
                }
                setThinking(false);
                stopBtn.style.display = "none";
                dockStatus.innerText = "● Stopped vocalization.";
            }

            audioElement.onplay = () => { stopBtn.style.display = "flex"; };
            audioElement.onended = () => { stopBtn.style.display = "none"; };
            audioElement.onpause = () => { stopBtn.style.display = "none"; };

            async function fetchAnnouncement() {
                try {
                    const res = await fetch("/api/announcement");
                    const d = await res.json();
                    if (d.message) {
                        globalBanner.innerText = "📢 " + d.message;
                        globalBanner.style.display = "block";
                    } else {
                        globalBanner.style.display = "none";
                    }
                } catch(e) {}
            }
            setInterval(fetchAnnouncement, 20000);
            fetchAnnouncement();

            function sendHeartbeat() {
                if (currentUserId) {
                    const fd = new FormData();
                    fd.append("user_id", currentUserId);
                    fetch("/api/heartbeat", { method: "POST", body: fd }).catch(() => {});
                }
            }
            setInterval(sendHeartbeat, 60000);

            async function handleDocFileUpload(e) {
                const file = e.target.files[0];
                if (!file) return;
                dockStatus.innerText = "● Parsing document artifact...";
                const fd = new FormData();
                fd.append("file", file);

                try {
                    const res = await fetch("/api/parse-doc", { method: "POST", body: fd });
                    const d = await res.json();
                    if (d.status === "ok") {
                        textInput.value = `[Document Analyzed: ${d.filename}]\n\n${d.text}\n\nTask: Analyze and synthesize key takeaways.`;
                        dockStatus.innerText = "● Document ingested. Hit ➤ to process.";
                    } else {
                        alert(d.message || "Failed to parse document.");
                        dockStatus.innerText = "● Document parse error.";
                    }
                } catch(err) {
                    alert("Document upload fault.");
                }
            }

            async function exportCurrentChat() {
                if (!currentSessionId) return alert("Open a chat session first to export.");
                try {
                    const res = await fetch(`/api/session-messages/${currentSessionId}`);
                    const d = await res.json();
                    if (!d.messages || d.messages.length === 0) return alert("Chat has no messages to export.");

                    let md = `# Lemon AI Session Export\n**Architect:** Utkarsh Bandhu\n**Chamber:** ${currentCoreMode.toUpperCase()}\n**Timestamp:** ${new Date().toLocaleString()}\n\n---\n\n`;
                    d.messages.forEach(m => {
                        md += `### ${m.role === 'assistant' ? 'Lemon (' + m.mode.toUpperCase() + ')' : 'User'}\n${m.content}\n\n`;
                    });

                    const blob = new Blob([md], { type: "text/markdown" });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = `lemon_${currentCoreMode}_session_${currentSessionId}.md`;
                    a.click();
                    URL.revokeObjectURL(url);
                } catch(e) {
                    alert("Export fault.");
                }
            }

            function openFeedbackModal() { closeSidebar(); feedbackModal.style.display = "flex"; }
            function closeFeedbackModal() {
                feedbackModal.style.display = "none";
                document.getElementById("feedbackMessage").value = "";
                clearReportPhoto();
            }

            function handleReportPhotoUpload(e) {
                const file = e.target.files[0];
                if (!file) return;
                const r = new FileReader();
                r.onload = async (event) => {
                    reportPhotoBase64 = await resizeImage(event.target.result, 800, 800, 0.75);
                    reportProofThumb.src = reportPhotoBase64;
                    reportProofBar.style.display = "flex";
                };
                r.readAsDataURL(file);
            }

            function clearReportPhoto() {
                reportPhotoBase64 = null;
                reportProofBar.style.display = "none";
                document.getElementById("reportPhotoInput").value = "";
            }

            async function sendComplaint() {
                const cat = document.getElementById("feedbackCategory").value;
                const msg = document.getElementById("feedbackMessage").value.trim();
                if (!msg) return alert("Please enter trouble details.");

                const fd = new FormData();
                fd.append("user_id", currentUserId || 0);
                fd.append("username", currentUsername || "Anonymous");
                fd.append("category", cat);
                fd.append("message", msg);
                if (reportPhotoBase64) fd.append("image_proof", reportPhotoBase64);

                try {
                    const res = await fetch("/api/complaints/submit", { method: "POST", body: fd });
                    const d = await res.json();
                    if (d.status === "ok") {
                        alert("Your issue and photo report were delivered directly to Utkarsh.");
                        closeFeedbackModal();
                    } else {
                        alert(d.message || "Failed.");
                    }
                } catch(e) { alert("Submission error."); }
            }

            async function requestCameraAccess() {
                dockStatus.innerText = "● Requesting optical camera...";
                cameraModal.style.display = "flex";
                const constraintsList = [
                    { video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } } },
                    { video: { facingMode: "user" } },
                    { video: true }
                ];
                let acquired = false;
                for (const c of constraintsList) {
                    try {
                        cameraStream = await navigator.mediaDevices.getUserMedia(c);
                        cameraVideo.srcObject = cameraStream;
                        acquired = true;
                        dockStatus.innerText = "● Camera verified & active.";
                        break;
                    } catch (e) {}
                }
                if (!acquired) {
                    alert("Camera permission declined or not found. You can upload an image directly.");
                    closeCamera();
                    document.getElementById("fileUploadInput").click();
                }
            }
            function closeCamera() {
                if (cameraStream) { cameraStream.getTracks().forEach(t => t.stop()); cameraStream = null; }
                cameraModal.style.display = "none";
                dockStatus.innerText = "● Ready";
            }
            function resizeImage(source, maxWidth = 1024, maxHeight = 1024, quality = 0.8) {
                return new Promise((resolve) => {
                    const img = new Image();
                    img.onload = () => {
                        let width = img.width, height = img.height;
                        if (width > height) {
                            if (width > maxWidth) { height = Math.round((height * maxWidth) / width); width = maxWidth; }
                        } else {
                            if (height > maxHeight) { width = Math.round((width * maxHeight) / height); height = maxHeight; }
                        }
                        const canvas = document.createElement("canvas");
                        canvas.width = width; canvas.height = height;
                        canvas.getContext("2d").drawImage(img, 0, 0, width, height);
                        resolve(canvas.toDataURL("image/jpeg", quality));
                    };
                    img.src = source;
                });
            }
            async function captureSnapshot() {
                if (!cameraVideo.videoWidth) return;
                cameraCanvas.width = cameraVideo.videoWidth; cameraCanvas.height = cameraVideo.videoHeight;
                cameraCanvas.getContext("2d").drawImage(cameraVideo, 0, 0);
                const rawB64 = cameraCanvas.toDataURL("image/jpeg", 0.9);
                const opt = await resizeImage(rawB64);
                setAttachedImage(opt);
                closeCamera();
            }
            function handleFileUpload(e) {
                const file = e.target.files[0];
                if (!file) return;
                const r = new FileReader();
                r.onload = async (event) => {
                    const opt = await resizeImage(event.target.result);
                    setAttachedImage(opt);
                    closeCamera();
                };
                r.readAsDataURL(file);
            }
            function setAttachedImage(b64) {
                attachedImageBase64 = b64;
                imgPreviewThumb.src = b64;
                imgPreviewBar.style.display = "flex";
                dockStatus.innerText = "● Visual artifact attached.";
            }
            function clearAttachedImage() {
                attachedImageBase64 = null;
                imgPreviewBar.style.display = "none";
                dockStatus.innerText = "● Ready";
            }

            async function requestMicAndRecord() {
                if (!isRecording) {
                    dockStatus.innerText = "● Requesting microphone...";
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];
                        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
                        mediaRecorder.onstop = async () => {
                            const blob = new Blob(audioChunks, { type: 'audio/wav' });
                            setThinking(true, "Transcribing voice articulation...");
                            uploadVoice(blob);
                            stream.getTracks().forEach(t => t.stop());
                        };
                        mediaRecorder.start();
                        isRecording = true;
                        micBtn.classList.add("active-record");
                        dockStatus.innerText = "🔴 Listening... Tap mic to transmit.";
                    } catch (err) {
                        alert("Microphone permission denied.");
                        dockStatus.innerText = "● Mic access denied.";
                    }
                } else {
                    isRecording = false;
                    micBtn.classList.remove("active-record");
                    setThinking(true, "Processing voice input...");
                    if (mediaRecorder) mediaRecorder.stop();
                }
            }

            async function switchDedicatedChamber(mode) {
                currentCoreMode = mode;
                localStorage.setItem("lemon_active_core", mode);
                updateChamberUI();

                if (currentUserId) {
                    const fd = new FormData();
                    fd.append("user_id", currentUserId);
                    fd.append("core_mode", mode);
                    try {
                        const res = await fetch("/api/new-core-session", { method: "POST", body: fd });
                        const data = await res.json();
                        currentSessionId = data.session_id;
                        localStorage.setItem("lemon_current_session_id", currentSessionId.toString());
                        chatStream.innerHTML = "";
                        heroGreeting.style.display = "flex";
                        heroGreetingName.innerText = `${mode.toUpperCase()} Chamber Activated`;
                        heroGreetingSub.innerText = `Dedicated cognitive isolation mode: ${mode.toUpperCase()}. Previous core contexts will not bleed into this session.`;
                        closeSidebar();
                        loadSessionsList();
                        dockStatus.innerText = `● Session bound to ${mode.toUpperCase()}`;
                    } catch(e) {}
                }
            }

            function updateChamberUI() {
                document.querySelectorAll(".core-choice").forEach(b => b.classList.remove("selected"));
                const target = document.getElementById(`core-${currentCoreMode}`);
                if (target) target.classList.add("selected");
                currentChamberBadge.innerText = `⚡ ${currentCoreMode.toUpperCase()}`;
            }

            function checkAuth() {
                updateChamberUI();
                if (currentUserId && currentUserId !== "null" && currentUserId !== "undefined") {
                    authModal.style.display = "none";
                    sidebarUsername.innerText = currentUsername;
                    heroGreetingName.innerText = `Welcome, ${currentUsername}!`;

                    if (currentUsername.toLowerCase() === "utkarsh" || currentUserRole === "owner") {
                        ownerMenuBtn.style.display = "block";
                    } else {
                        ownerMenuBtn.style.display = "none";
                    }
                    sendHeartbeat();
                    initHistory();
                } else {
                    authModal.style.display = "flex";
                }
            }

            function toggleAuthMode() {
                isAuthRegister = !isAuthRegister;
                authErrorMsg.style.display = "none";
                if (isAuthRegister) {
                    authHeading.innerText = "Create Identity";
                    authSub.innerText = "Register to preserve dedicated chambers permanently.";
                    authSubmitBtn.innerText = "Create Account";
                    authToggleText.innerText = "Already registered? Sign In";
                } else {
                    authHeading.innerText = "Access Lemon AI";
                    authSub.innerText = "Sign in to access your persistent cognitive sessions.";
                    authSubmitBtn.innerText = "Enter System";
                    authToggleText.innerText = "No account? Create one";
                }
            }

            async function handleAuthSubmit() {
                const u = document.getElementById("authUsername").value.trim();
                const p = document.getElementById("authPassword").value.trim();
                authErrorMsg.style.display = "none";
                if (!u || !p) {
                    authErrorMsg.innerText = "Username and password required.";
                    authErrorMsg.style.display = "block";
                    return;
                }

                const endpoint = isAuthRegister ? "/api/register" : "/api/login";
                const fd = new FormData();
                fd.append("username", u);
                fd.append("password", p);
                authSubmitBtn.innerText = "Synchronizing...";
                try {
                    const res = await fetch(endpoint, { method: "POST", body: fd });
                    const data = await res.json();
                    authSubmitBtn.innerText = isAuthRegister ? "Create Account" : "Enter System";

                    if (res.ok && data.status === "ok") {
                        currentUserId = data.user_id.toString();
                        currentUsername = data.username;
                        currentUserRole = data.role || "user";
                        localStorage.setItem("lemon_user_id", currentUserId);
                        localStorage.setItem("lemon_username", currentUsername);
                        localStorage.setItem("lemon_user_role", currentUserRole);
                        authModal.style.display = "none";
                        checkAuth();
                    } else if (res.status === 404 && !isAuthRegister) {
                        toggleAuthMode();
                        authErrorMsg.innerText = "User not found. Click 'Create Account' below.";
                        authErrorMsg.style.display = "block";
                    } else {
                        authErrorMsg.innerText = data.message || "Authentication error.";
                        authErrorMsg.style.display = "block";
                    }
                } catch(err) {
                    authSubmitBtn.innerText = isAuthRegister ? "Create Account" : "Enter System";
                    authErrorMsg.innerText = "Server reachability issue.";
                    authErrorMsg.style.display = "block";
                }
            }

            function logout() {
                localStorage.removeItem("lemon_user_id");
                localStorage.removeItem("lemon_username");
                localStorage.removeItem("lemon_user_role");
                localStorage.removeItem("lemon_current_session_id");
                currentUserId = null;
                currentUsername = "Thinker";
                currentUserRole = "user";
                currentSessionId = 0;
                chatStream.innerHTML = "";
                closeSidebar();
                checkAuth();
            }

            function openSidebar() { loadSessionsList(); sidebar.classList.add("open"); sidebarOverlay.classList.add("open"); }
            function closeSidebar() { sidebar.classList.remove("open"); sidebarOverlay.classList.remove("open"); }

            async function initHistory() {
                if (!currentUserId) return;
                try {
                    const res = await fetch(`/api/sessions/${currentUserId}`);
                    const data = await res.json();
                    await loadSessionsList();

                    if (currentSessionId && currentSessionId !== 0) {
                        await openSession(currentSessionId);
                    } else if (data.sessions && data.sessions.length > 0) {
                        await openSession(data.sessions[0].id);
                    } else {
                        switchDedicatedChamber(currentCoreMode);
                    }
                } catch(e) {}
            }

            async function loadSessionsList() {
                if (!currentUserId) return;
                try {
                    const res = await fetch(`/api/sessions/${currentUserId}`);
                    const data = await res.json();
                    sessionsList.innerHTML = "";
                    const list = data.sessions || [];

                    if (list.length > 0) {
                        list.forEach(s => {
                            const item = document.createElement("div");
                            item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
                            item.innerHTML = `
                                <div class="session-title" onclick="openSession(${s.id})">💬 ${s.title}</div>
                                <span class="session-delete" onclick="deleteSession(event, ${s.id})" title="Delete">✕</span>
                            `;
                            sessionsList.appendChild(item);
                        });
                    } else {
                        sessionsList.innerHTML = `<div style="font-size:12px; color:#64748b; padding:10px;">No preserved sessions.</div>`;
                    }
                } catch(e) {}
            }

            async function openSession(id) {
                currentSessionId = id;
                localStorage.setItem("lemon_current_session_id", id.toString());
                closeSidebar();
                heroGreeting.style.display = "none";
                chatStream.innerHTML = "";

                try {
                    const res = await fetch(`/api/session-messages/${id}`);
                    const data = await res.json();
                    if (data.messages && data.messages.length > 0) {
                        data.messages.forEach(m => appendMessage(m.role === "assistant" ? "lemon" : "user", m.content, m.emotion, m.image_data));
                        const lastMsg = data.messages[data.messages.length - 1];
                        if (lastMsg && lastMsg.mode) {
                            currentCoreMode = lastMsg.mode;
                            localStorage.setItem("lemon_active_core", currentCoreMode);
                            updateChamberUI();
                        }
                    }
                } catch(e) {}
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            async function deleteSession(e, id) {
                e.stopPropagation();
                if (!confirm("Permanently purge this discussion chamber?")) return;
                const fd = new FormData();
                fd.append("session_id", id);
                await fetch("/api/delete-session", { method: "POST", body: fd });
                if (currentSessionId === id) switchDedicatedChamber(currentCoreMode);
                loadSessionsList();
            }

            function setThinking(active, label = "Executing first-principles synthesis...") {
                if (active) {
                    dockStatus.innerText = `⚡ ${label}`;
                    stopBtn.style.display = "flex";
                    if (!currentThinkingEl) {
                        currentThinkingEl = document.createElement("div");
                        currentThinkingEl.className = "bubble-group lemon";
                        currentThinkingEl.innerHTML = `
                            <div class="thinking-box">
                                <div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>
                                <span style="font-size:12px; color:#facc15; margin-left:4px;">Synthesizing...</span>
                            </div>
                        `;
                        chatStream.appendChild(currentThinkingEl);
                        chatStream.scrollTop = chatStream.scrollHeight;
                    }
                } else {
                    if (currentThinkingEl) { currentThinkingEl.remove(); currentThinkingEl = null; }
                    dockStatus.innerText = "● Chamber Active";
                }
            }

            async function playSpecificMessage(text) {
                dockStatus.innerText = "🔊 Vocalizing...";
                stopBtn.style.display = "flex";
                const fd = new FormData();
                fd.append("text", text);
                try {
                    const res = await fetch("/read-aloud", { method: "POST", body: fd });
                    const data = await res.json();
                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch(e) { dockStatus.innerText = "Audio playback fault."; }
            }

            function copyMessage(text, btn) {
                navigator.clipboard.writeText(text);
                const original = btn.innerText;
                btn.innerText = "✓ Copied";
                setTimeout(() => { btn.innerText = original; }, 1800);
            }

            function appendMessage(sender, text, emotion = null, imageData = null) {
                setThinking(false);
                if (heroGreeting) heroGreeting.style.display = "none";

                const group = document.createElement("div");
                group.className = `bubble-group ${sender}`;
                let html = "";
                let imgTag = imageData ? `<img src="${imageData}" class="chat-img-thumb" alt="analyzed visual artifact">` : "";

                if (sender === "lemon") {
                    const tag = emotion ? `<span class="feeling-tag">${emotion}</span><br>` : "";
                    const safeRaw = encodeURIComponent(text);
                    const formattedContent = marked.parse(text);

                    html = `
                        <div class="bubble-meta">
                            <span>Lemon (${currentCoreMode.toUpperCase()})</span>
                        </div>
                        <div class="bubble lemon">
                            ${tag}
                            ${imgTag}
                            <div>${formattedContent}</div>
                            <div class="message-actions">
                                <button class="msg-action-btn" onclick="playSpecificMessage(decodeURIComponent('${safeRaw}'))">🔊 Vocalize</button>
                                <button class="msg-action-btn" onclick="copyMessage(decodeURIComponent('${safeRaw}'), this)">📋 Copy</button>
                            </div>
                        </div>
                    `;
                } else {
                    html = `
                        <div class="bubble user">
                            ${imgTag}
                            <div>${text}</div>
                        </div>
                    `;
                }
                group.innerHTML = html;
                chatStream.appendChild(group);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            async function sendTextQuery() {
                const text = textInput.value.trim();
                const imageToSend = attachedImageBase64;
                if (!text && !imageToSend) return;

                textInput.value = "";
                appendMessage("user", text ? text : "Examine this visual artifact and provide exhaustive intellectual audit.", null, imageToSend);
                setThinking(true, imageToSend ? "Vision: Inspecting artifacts..." : `Engaging ${currentCoreMode.toUpperCase()} synthesis...`);

                const fd = new FormData();
                fd.append("text", text ? text : "Perform rigorous diagnostic inspection of this image.");
                fd.append("user_id", currentUserId.toString());
                fd.append("session_id", (currentSessionId || 0).toString());
                fd.append("mode", currentCoreMode);
                if (imageToSend) fd.append("image_base64", imageToSend);

                clearAttachedImage();

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    const data = await res.json();
                    currentSessionId = data.session_id;
                    localStorage.setItem("lemon_current_session_id", currentSessionId.toString());

                    appendMessage("lemon", data.reply_text, data.emotion);
                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play().catch(e => {});
                    }
                } catch(e) {
                    setThinking(false);
                    dockStatus.innerText = "Network sync fault. Re-transmit.";
                }
            }

            async function uploadVoice(blob) {
                const imageToSend = attachedImageBase64;
                clearAttachedImage();

                const fd = new FormData();
                fd.append("file", blob, "voice.wav");
                fd.append("user_id", currentUserId.toString());
                fd.append("session_id", (currentSessionId || 0).toString());
                fd.append("mode", currentCoreMode);
                if (imageToSend) fd.append("image_base64", imageToSend);

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    if (!res.ok) throw new Error("HTTP " + res.status);
                    const data = await res.json();
                    currentSessionId = data.session_id;
                    localStorage.setItem("lemon_current_session_id", currentSessionId.toString());

                    if (data.user_text) appendMessage("user", data.user_text, null, imageToSend);
                    appendMessage("lemon", data.reply_text, data.emotion);

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play().catch(e => {});
                    }
                } catch(e) {
                    setThinking(false);
                    dockStatus.innerText = "Voice transmission fault.";
                }
            }

            checkAuth();
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
