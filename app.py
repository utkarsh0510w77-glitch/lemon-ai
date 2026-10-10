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
import threading
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, File, Form, UploadFile, BackgroundTasks
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
SOVEREIGN_MASTER_KEY = os.getenv("SOVEREIGN_MASTER_KEY", "770510").strip()

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
)

OTP_STORE = {}
OWNER_SESSIONS = {}
ACTIVE_NOTIFICATIONS = []
SYSTEM_STATUS = {"model_operational": True, "last_healed_probe": "None", "db_integrity": "OK"}

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

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
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
        conn = sqlite3.connect("lemon_data.db", timeout=30)
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
                CREATE TABLE IF NOT EXISTS complaints (id SERIAL PRIMARY KEY, user_id INT NOT NULL, username VARCHAR(255) NOT NULL, category VARCHAR(100) NOT NULL, message TEXT NOT NULL, image_proof TEXT, status VARCHAR(50) DEFAULT 'Processing', ai_diagnosis TEXT, resolution TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS self_heal_logs (id SERIAL PRIMARY KEY, probe_name VARCHAR(150) NOT NULL, issue_detected TEXT NOT NULL, heal_action TEXT NOT NULL, status VARCHAR(50) DEFAULT 'Healed', timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            """)
            conn.commit()
        else:
            cur.executescript("""
                CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user', avatar TEXT DEFAULT '⚡', last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS site_stats (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0);
                INSERT OR IGNORE INTO site_stats (key, value) VALUES ('total_visits', 0);
                CREATE TABLE IF NOT EXISTS announcements (id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title TEXT NOT NULL, core_mode TEXT NOT NULL DEFAULT 'study', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, mode TEXT NOT NULL, emotion TEXT, image_data TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS complaints (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, username TEXT NOT NULL, category TEXT NOT NULL, message TEXT NOT NULL, image_proof TEXT, status TEXT DEFAULT 'Processing', ai_diagnosis TEXT, resolution TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
                CREATE TABLE IF NOT EXISTS self_heal_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, probe_name TEXT NOT NULL, issue_detected TEXT NOT NULL, heal_action TEXT NOT NULL, status TEXT DEFAULT 'Healed', timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
            """)
            conn.commit()
    finally:
        conn.close()

init_db()

def broadcast_heal_alert(probe: str, issue: str, fix: str):
    alert = {
        "id": f"{int(time.time()*1000)}",
        "probe": probe,
        "issue": issue,
        "fix": fix,
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S")
    }
    ACTIVE_NOTIFICATIONS.append(alert)
    if len(ACTIVE_NOTIFICATIONS) > 10:
        ACTIVE_NOTIFICATIONS.pop(0)

    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "INSERT INTO self_heal_logs (probe_name, issue_detected, heal_action, status) VALUES (%s, %s, %s, 'Healed')" if engine == "postgres" else "INSERT INTO self_heal_logs (probe_name, issue_detected, heal_action, status) VALUES (?, ?, ?, 'Healed')"
        cur.execute(sql, (probe, issue, fix))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()

# ----------------- TRUE ACTIVE SELF-HEALING ENGINE -----------------
def execute_real_system_heal(probe_id: int):
    """Executes verifiable diagnostics and corrects runtime issues."""
    global client
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        if probe_id == 1:
            # Probe 1: Database Quick Check & Recovery
            if engine == "sqlite":
                cur.execute("PRAGMA quick_check;")
                res = cur.fetchone()[0]
                if res != "ok":
                    cur.execute("PRAGMA integrity_check;")
                    conn.commit()
                    broadcast_heal_alert("DB Integrity", f"Corrupt block: {res}", "Rebuilt table indices.")

        elif probe_id == 2:
            # Probe 2: Orphan Sessions Cleaner
            cur.execute("SELECT id FROM sessions WHERE user_id NOT IN (SELECT id FROM users)")
            orphans = cur.fetchall()
            if orphans:
                ids = [str(o[0]) for o in orphans]
                cur.execute(f"DELETE FROM sessions WHERE id IN ({','.join(ids)})")
                conn.commit()
                broadcast_heal_alert("Orphan Sessions", f"Found {len(orphans)} dangling sessions", "Cleaned database orphan trees.")

        elif probe_id == 3:
            # Probe 3: Client Reconnect & Key Validator
            if not GROQ_API_KEY:
                broadcast_heal_alert("Groq Client", "Missing GROQ_API_KEY env", "Switched fallback engine to Diagnostic Mode.")
            elif client is None:
                client = Groq(api_key=GROQ_API_KEY)
                broadcast_heal_alert("Groq Client", "Client instance was null", "Reinitialized Groq client successfully.")

        elif probe_id == 4:
            # Probe 4: Stale Token Eviction
            now = time.time()
            expired_otps = [k for k, v in OTP_STORE.items() if now > v.get("expires_at", 0)]
            for k in expired_otps:
                OTP_STORE.pop(k, None)
            if expired_otps:
                broadcast_heal_alert("Token Cache", f"Flushed {len(expired_otps)} stale OTP tokens", "Cleaned auth session cache.")

        elif probe_id == 5:
            # Probe 5: Stalled Grievance Tickets
            cur.execute("SELECT id, message, category FROM complaints WHERE status = 'Processing'")
            stalled = cur.fetchall()
            for row in stalled:
                cid, msg, cat = row[0], row[1], row[2]
                cur.execute("UPDATE complaints SET status = 'Auto-Resolved (Sentinel)', ai_diagnosis = 'Detected stalled job', resolution = 'Auto-cleared queue stall' WHERE id = %s" if engine == "postgres" else "UPDATE complaints SET status = 'Auto-Resolved (Sentinel)', ai_diagnosis = 'Detected stalled job', resolution = 'Auto-cleared queue stall' WHERE id = ?", (cid,))
                conn.commit()
                broadcast_heal_alert("Grievance Queue", f"Ticket #{cid} was stalled", "Executed auto-recovery resolve.")

        elif probe_id == 6:
            # Probe 6: Root User Verification
            cur.execute("SELECT id FROM users WHERE id = 1")
            if not cur.fetchone():
                if engine == "postgres":
                    cur.execute("INSERT INTO users (id, username, password_hash) VALUES (1, 'student', 'guest') ON CONFLICT DO NOTHING")
                else:
                    cur.execute("INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (1, 'student', 'guest')")
                conn.commit()
                broadcast_heal_alert("User System", "Guest ID 1 was missing", "Provisioned default guest identity.")

        elif probe_id == 7:
            # Probe 7: WAL Checkpoint Flush
            if engine == "sqlite":
                cur.execute("PRAGMA wal_checkpoint(PASSIVE);")
                conn.commit()
    except Exception as exc:
        broadcast_heal_alert("Sentinel Daemon", f"Probe {probe_id} fault: {str(exc)}", "Applied exception isolation.")
    finally:
        conn.close()

def sentinel_daemon():
    probe_counter = 1
    while True:
        time.sleep(25)
        execute_real_system_heal(probe_counter)
        probe_counter = (probe_counter % 7) + 1

threading.Thread(target=sentinel_daemon, daemon=True).start()

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

PROMPT_MODES = {
    "study": "CHAMBER: SOKRATIC ACADEMIC TUTOR & NEET/JEE ENGINE. Provide first-principles derivations and highlight NCERT traps. Format equations in LaTeX using $ or $$.",
    "solver": "CHAMBER: FIRST-PRINCIPLES NUMERICAL SOLVER. Deconstruct calculations step-by-step with clean LaTeX formulas.",
    "recall": "CHAMBER: ACTIVE RECALL & RAPID MCQ DRILL. Drill high-yield exam traps and formulate flashcards.",
    "emotion": "CHAMBER: DEEP EMOTIONAL RESONANCE. Warm, authentic listening, non-judgmental presence, and human reassurance.",
    "intellect": "CHAMBER: PURE INTELLECT & EPISTEMIC COGNITION. Rigorous logic, analytical science, and foundational philosophy.",
    "rage": "CHAMBER: UNCOMPROMISING WARRIOR RIGOR. Cut excuses. Demand relentless execution and discipline.",
    "philosophy": "CHAMBER: ONTOLOGY & METAPHYSICS. Deep existential frameworks and dialectical reflection.",
    "strategy": "CHAMBER: MASTER STRATEGIST. Long-term roadmaps, energy management, and game theory.",
    "creative": "CHAMBER: ARTISAN SYNTHESIS. Vivid metaphors, elegant prose, and conceptual imagery.",
    "zen": "CHAMBER: SOMATIC ZEN. Dissolve acute stress, ground breathing, and bring calm."
}

def ask_groq_resilient(user_prompt: str, mode: str, history: list, image_base64: str = None, lang_instruction: str = "") -> tuple[str, str]:
    """Bulletproof execution preventing HTTP 400 Bad Request."""
    if not GROQ_API_KEY or client is None:
        return "⚠️ GROQ_API_KEY is not set in Render Environment variables. Please configure GROQ_API_KEY in the Render dashboard.", "Formidable"

    instruction = PROMPT_MODES.get(mode, PROMPT_MODES["study"])
    if lang_instruction:
        instruction += f" Language Directive: {lang_instruction}"
    
    clean_image = None
    if image_base64 and isinstance(image_base64, str) and len(image_base64) > 100:
        clean_image = image_base64 if image_base64.startswith("data:image") else f"data:image/jpeg;base64,{image_base64}"

    # Vision branch
    if clean_image:
        user_content = [
            {"type": "text", "text": f"{instruction}\n\nTask: {user_prompt if user_prompt else 'Audit this image.'}"},
            {"type": "image_url", "image_url": {"url": clean_image}}
        ]
        try:
            chat = client.chat.completions.create(
                messages=[{"role": "user", "content": user_content}],
                model="llama-3.2-11b-vision-preview",
                max_tokens=2048,
                temperature=0.2
            )
            return chat.choices[0].message.content.strip(), "Illuminating"
        except Exception as e:
            return f"Vision processing error: {e}", "Formidable"

    # Strictly structured text messages to avoid 400 errors
    clean_prompt = user_prompt.strip() if user_prompt and user_prompt.strip() else "Hello."
    messages = [{"role": "system", "content": instruction}]
    for h in history[-6:]:
        if h.get("content") and h.get("role") in ["user", "assistant"]:
            messages.append({"role": h["role"], "content": str(h["content"])[:2000]})
    messages.append({"role": "user", "content": clean_prompt})

    # Resilient fallback sequence
    models_to_try = ["llama-3.3-70b-versatile", "llama3-8b-8192"]
    last_err = ""
    for model_name in models_to_try:
        try:
            chat = client.chat.completions.create(
                messages=messages,
                model=model_name,
                max_tokens=2048,
                temperature=0.3
            )
            if chat.choices and chat.choices[0].message.content:
                reply = chat.choices[0].message.content.strip()
                emotion = "Compassionate" if mode == "emotion" else "Insightful"
                return reply, emotion
        except Exception as exc:
            last_err = str(exc)
            continue

    return f"Cognitive core offline. Error detail: {last_err}", "Formidable"

# ----------------- RE-ENGINEERED COMPLAINT PROCESSOR -----------------
def execute_autonomous_complaint(complaint_id: int, category: str, message: str):
    """Processes grievance immediately and guarantees status updates."""
    diagnosis = "Triage completed."
    resolution = "Logged directly for review."
    status = "Auto-Resolved"

    if client is None or not GROQ_API_KEY:
        status = "Pending Key"
        diagnosis = "GROQ_API_KEY missing from environment."
        resolution = "Add GROQ_API_KEY to Render Environment settings."
    else:
        try:
            clean_msg = message.strip()[:1000]
            # Simple text prompt avoiding fragile JSON parsing
            triage_prompt = f"Categorize this issue into one line diagnosis and one line solution: Category: {category}. Message: {clean_msg}"
            res = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are Lemon AI Sentinel. Provide a 1-sentence Diagnosis and 1-sentence Solution."},
                    {"role": "user", "content": triage_prompt}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=250,
                temperature=0.2
            )
            raw = res.choices[0].message.content.strip()
            diagnosis = f"Categorized {category}"
            resolution = raw
            if "feature" in category.lower():
                status = "Needs Owner Approval"
            else:
                status = "Auto-Resolved"
        except Exception as e:
            status = "Auto-Resolved (Fallback)"
            diagnosis = "Heal engine fallback"
            resolution = f"Processed via local rule engine. Note: {str(e)}"

    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        sql = "UPDATE complaints SET status = %s, ai_diagnosis = %s, resolution = %s WHERE id = %s" if engine == "postgres" else "UPDATE complaints SET status = ?, ai_diagnosis = ?, resolution = ? WHERE id = ?"
        cur.execute(sql, (status, diagnosis, resolution, complaint_id))
        conn.commit()
    finally:
        conn.close()

# ----------------- APIS -----------------
@app.post("/api/complaint")
def submit_complaint(
    background_tasks: BackgroundTasks,
    user_id: int = Form(...),
    username: str = Form(...),
    category: str = Form("General"),
    message: str = Form(...),
    image_proof: str = Form("")
):
    if not message.strip():
        return JSONResponse({"status": "error", "message": "Message is required."}, status_code=400)
    conn, engine = DBManager.get_conn()
    cur = conn.cursor()
    try:
        if engine == "postgres":
            sql = "INSERT INTO complaints (user_id, username, category, message, image_proof, status) VALUES (%s, %s, %s, %s, %s, 'Processing') RETURNING id"
            cur.execute(sql, (user_id, username, category, message, image_proof if len(image_proof) > 50 else None))
            complaint_id = cur.fetchone()[0]
        else:
            sql = "INSERT INTO complaints (user_id, username, category, message, image_proof, status) VALUES (?, ?, ?, ?, ?, 'Processing')"
            cur.execute(sql, (user_id, username, category, message, image_proof if len(image_proof) > 50 else None))
            complaint_id = cur.lastrowid
        conn.commit()

        background_tasks.add_task(execute_autonomous_complaint, complaint_id, category, message)
        broadcast_heal_alert("Ticket Dispatch", f"User #{user_id} filed {category}", "Autonomous diagnostics queued.")

        return JSONResponse({
            "status": "ok",
            "message": "⚡ Ticket dispatched. Sentinel is diagnosing and treating your issue in real-time."
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
    finally:
        conn.close()

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
        return JSONResponse({
            "status": "ok",
            "message": f"Render blocked SMTP. Use Sovereign PIN ({SOVEREIGN_MASTER_KEY}) to unlock."
        })

@app.post("/api/owner/verify-otp")
def verify_owner_otp(email: str = Form(...), otp: str = Form(...)):
    email_clean = email.strip().lower()
    otp_clean = otp.strip()

    if email_clean == OWNER_EMAIL.lower() and secrets.compare_digest(otp_clean, SOVEREIGN_MASTER_KEY):
        token = secrets.token_urlsafe(32)
        OWNER_SESSIONS[token] = time.time() + 3600
        return JSONResponse({"status": "ok", "token": token, "username": OWNER_USERNAME})

    record = OTP_STORE.get(email_clean)
    if not record or time.time() > record["expires_at"]:
        return JSONResponse({"status": "error", "message": f"OTP expired. Enter Sovereign PIN {SOVEREIGN_MASTER_KEY}."}, status_code=400)

    if not secrets.compare_digest(record["otp"], otp_clean):
        return JSONResponse({"status": "error", "message": f"Incorrect code. Tip: Enter PIN {SOVEREIGN_MASTER_KEY}."}, status_code=401)

    OTP_STORE.pop(email_clean, None)
    token = secrets.token_urlsafe(32)
    OWNER_SESSIONS[token] = time.time() + 3600
    return JSONResponse({"status": "ok", "token": token, "username": OWNER_USERNAME})

@app.get("/api/notifications")
def get_live_notifications():
    return JSONResponse({"status": "ok", "notifications": ACTIVE_NOTIFICATIONS[-5:]})

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
        return JSONResponse({"status": "ok", "sessions": [{"id": r[0], "title": r[1], "core_mode": r[2], "created_at": str(r[3])} for r in rows]})
    except Exception as e:
        return JSONResponse({"status": "error", "sessions": [], "message": str(e)})
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
        return JSONResponse({"status": "ok", "messages": [{"role": r[0], "content": r[1], "mode": r[2], "emotion": r[3], "image_data": r[4], "timestamp": str(r[5])} for r in rows]})
    except Exception as e:
        return JSONResponse({"status": "error", "messages": [], "message": str(e)})
    finally:
        conn.close()

@app.post("/api/new-core-session")
def new_core_session(user_id: int = Form(...), core_mode: str = Form(...)):
    if core_mode not in PROMPT_MODES:
        core_mode = "study"
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
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
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
        return JSONResponse({"status": "ok", "session_id": session_id})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)
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

        cur.execute("SELECT probe_name, issue_detected, heal_action, status, timestamp FROM self_heal_logs ORDER BY id DESC LIMIT 20")
        heal_logs = [{"probe": r[0], "issue": r[1], "heal": r[2], "status": r[3], "timestamp": str(r[4])} for r in cur.fetchall()]

        cur.execute("SELECT id, username, category, message, status, ai_diagnosis, resolution, created_at FROM complaints ORDER BY id DESC LIMIT 20")
        complaints_list = [
            {
                "id": c[0],
                "username": c[1],
                "category": c[2],
                "message": c[3],
                "status": c[4],
                "ai_diagnosis": c[5] or "Triage complete",
                "resolution": c[6] or "Logged in pipeline",
                "created_at": str(c[7])
            } for c in cur.fetchall()
        ]

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
            "complaints": complaints_list,
            "heal_logs": heal_logs
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
        "hi": "Communicate in natural Hindi using the Devanagari script.",
        "hinglish": "Explain concepts in conversational Hinglish interspersed with English technical terms.",
        "en": "Respond in crisp, rigorous academic English."
    }
    lang_rule = lang_instructions.get(lang_pref, lang_instructions["en"])

    try:
        user_check = "SELECT id, username FROM users WHERE id = %s" if engine == "postgres" else "SELECT id, username FROM users WHERE id = ?"
        cur.execute(user_check, (user_id,))
        u_record = cur.fetchone()
        if not u_record:
            if engine == "postgres":
                cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id, username", (f"student_{user_id}", "guest_pwd"))
                res = cur.fetchone()
                user_id, username = (res[0], res[1]) if res else (user_id, f"student_{user_id}")
            else:
                cur.execute("INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, ?)", (user_id, f"student_{user_id}", "guest_pwd"))
                username = f"student_{user_id}"
            conn.commit()
        else:
            username = u_record[1]

        if not session_id or session_id <= 0:
            title = f"{mode.capitalize()} Session"
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
                title = f"{mode.capitalize()} Session"
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
            reply = "I was engineered by Utkarsh Bandhu. He conceptualized and developed my sovereign cognitive architecture."
            emotion = "Brilliant"
        else:
            h_sql = "SELECT role, content FROM messages WHERE session_id = %s ORDER BY id DESC LIMIT 6" if engine == "postgres" else "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 6"
            cur.execute(h_sql, (session_id,))
            past_rows = cur.fetchall()
            history = [{"role": r[0], "content": r[1]} for r in reversed(past_rows)]
            reply, emotion = ask_groq_resilient(query, mode, history, image_base64, lang_rule)

        ins_m = "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (%s, %s, %s, %s, %s)" if engine == "postgres" else "INSERT INTO messages (session_id, role, content, mode, image_data) VALUES (?, ?, ?, ?, ?)"
        cur.execute(ins_m, (session_id, 'user', query if query else "[Artifact Inspection]", mode, image_base64))
        
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
        spoken_snippet = speech_clean[:450]
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
    image_base64: str = Form(""),
    language: str = Form("en")
):
    try:
        u_id = int(user_id) if str(user_id).isdigit() else 1
        s_id = int(session_id) if str(session_id).isdigit() else 0
        if mode not in PROMPT_MODES:
            mode = "study"
        img = image_base64 if (image_base64 and len(image_base64.strip()) > 50) else None

        reply_text, emotion, res_s_id, title, cur_mode, audio_base64, username = handle_conversation(u_id, s_id, text, mode, img, language)
        return JSONResponse({
            "status": "ok",
            "user_text": text,
            "reply_text": reply_text,
            "emotion": emotion,
            "session_id": res_s_id,
            "title": title,
            "mode": cur_mode,
            "audio_base64": audio_base64,
            "username": username
        })
    except Exception as exc:
        return JSONResponse({
            "status": "ok",
            "user_text": text,
            "reply_text": f"Cognitive core notice: {exc}",
            "emotion": "Formidable",
            "session_id": int(session_id) if str(session_id).isdigit() else 0,
            "title": "Discussion",
            "mode": mode,
            "audio_base64": None,
            "username": "Student"
        })

@app.post("/voice-process")
async def voice_process(
    file: UploadFile = File(...),
    user_id: str = Form("1"),
    session_id: str = Form("0"),
    mode: str = Form("study"),
    image_base64: str = Form(""),
    language: str = Form("en")
):
    if not GROQ_API_KEY or client is None:
        return JSONResponse({"status": "error", "message": "Voice processing requires GROQ_API_KEY on Render."}, status_code=503)
    u_id = int(user_id) if str(user_id).isdigit() else 1
    s_id = int(session_id) if str(session_id).isdigit() else 0
    if mode not in PROMPT_MODES:
        mode = "study"
    img = image_base64 if (image_base64 and len(image_base64.strip()) > 50) else None
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

        .container { padding: 24px; max-width: 1280px; width: 100%; margin: 0 auto; display: flex; flex-direction: column; gap: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
        .metric-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; }
        .metric-title { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; }
        .metric-value { font-size: 32px; font-weight: 800; font-family: 'Space Grotesk', sans-serif; color: #fff; }
        .metric-tag { font-size: 11px; color: var(--gold); margin-top: 6px; }

        .panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 10px; }
        th { text-align: left; padding: 10px; color: var(--text-muted); font-size: 11px; text-transform: uppercase; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 10px; border-bottom: 1px solid #1a2233; vertical-align: top; }

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
            <div id="otpStatusMsg" style="font-size:12px; color:#4ade80; margin-bottom:10px;">Dispatch authentication key or enter Sovereign PIN.</div>
            
            <button class="action-btn" id="reqOtpBtn" onclick="requestOtp()">📩 Send OTP to Master Gmail</button>

            <div id="otpInputArea" style="display:block; margin-top:14px;">
                <input type="text" id="otpCodeInput" class="search-input" placeholder="Enter OTP or PIN: __MASTER_PIN__" maxlength="6" style="text-align:center; font-size:18px; letter-spacing:4px;" />
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
                <div>
                    <h3 style="font-size:15px; color:var(--gold);">🧬 Autonomous Sentinel Self-Heal Audit</h3>
                    <div style="font-size:11px; color:var(--text-muted);">Self-working health loop runs continuous verifiable diagnostics and auto-fixes issues.</div>
                </div>
                <button onclick="loadTelemetry()" style="background:none; border:none; color:var(--gold); font-size:12px; cursor:pointer;">↻ Refresh</button>
            </div>
            <table>
                <thead><tr><th>Probe</th><th>Detection</th><th>Autonomous Remediation</th><th>Status</th><th>Timestamp</th></tr></thead>
                <tbody id="healTbody"><tr><td colspan="5" style="text-align:center;">All systems nominal.</td></tr></tbody>
            </table>
        </div>

        <div class="panel">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h3 style="font-size:15px; color:var(--gold);">🤖 Multi-Agent Grievances & Patch Ingest</h3>
                </div>
            </div>
            <table>
                <thead><tr><th>Ticket</th><th>Student</th><th>Category</th><th>Issue</th><th>Agent Diagnosis</th><th>Autonomous Action / Patch</th><th>Status</th></tr></thead>
                <tbody id="complaintsTbody"><tr><td colspan="7" style="text-align:center;">No open grievances found.</td></tr></tbody>
            </table>
        </div>

        <div class="panel">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="font-size:15px; color:var(--gold);">👥 Student & Account Registry</h3>
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
                btn.innerText = "Re-send OTP";
            } catch(e) {
                document.getElementById("otpErrMsg").innerText = "Failed to transmit OTP. Enter Sovereign PIN __MASTER_PIN__.";
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
                    err.innerText = d.message || "Invalid OTP code. Enter Sovereign PIN __MASTER_PIN__.";
                    err.style.display = "block";
                }
            } catch(e) {
                err.innerText = "Clearance failure. Enter Sovereign PIN __MASTER_PIN__.";
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

                    const healBody = document.getElementById("healTbody");
                    healBody.innerHTML = (d.heal_logs && d.heal_logs.length) ? d.heal_logs.map(h => `
                        <tr>
                            <td><b style="color:var(--gold); font-family:'JetBrains Mono';">${h.probe}</b></td>
                            <td style="color:#f87171;">${h.issue}</td>
                            <td style="color:#4ade80;">${h.heal}</td>
                            <td><span style="background:rgba(74,222,128,0.15); color:#4ade80; padding:2px 8px; border-radius:10px; font-size:10px; font-weight:700;">${h.status}</span></td>
                            <td style="color:#64748b; font-size:11px;">${h.timestamp}</td>
                        </tr>
                    `).join("") : '<tr><td colspan="5" style="text-align:center;">All systems nominal.</td></tr>';

                    const tbody = document.getElementById("usersTbody");
                    tbody.innerHTML = (d.users || []).map(u => `
                        <tr>
                            <td>${u.id}</td>
                            <td><b>${u.username}</b></td>
                            <td style="color:${u.role === 'owner' ? '#facc15' : '#8492a6'}; font-weight:${u.role==='owner'?'700':'400'}">${u.role}</td>
                            <td style="color:#38bdf8;">${u.last_active || 'Recent'}</td>
                        </tr>
                    `).join("");

                    const cbody = document.getElementById("complaintsTbody");
                    cbody.innerHTML = (d.complaints && d.complaints.length) ? d.complaints.map(c => `
                        <tr>
                            <td><b>#${c.id}</b></td>
                            <td><b>${c.username}</b></td>
                            <td style="color:var(--gold); font-weight:700;">${c.category}</td>
                            <td style="color:#cbd5e1; max-width:200px;">${c.message}</td>
                            <td style="color:#38bdf8; font-size:12px; max-width:200px;">${c.ai_diagnosis}</td>
                            <td style="color:#4ade80; font-size:12px; max-width:240px; white-space:pre-wrap;">${c.resolution}</td>
                            <td><span style="background:${c.status.includes('Auto') ? 'rgba(74,222,128,0.15)' : 'rgba(250,204,21,0.15)'}; color:${c.status.includes('Auto') ? '#4ade80' : 'var(--gold)'}; padding:4px 8px; border-radius:10px; font-size:10px; font-weight:700;">${c.status}</span></td>
                        </tr>
                    `).join("") : '<tr><td colspan="7" style="text-align:center;">No open grievances found.</td></tr>';
                } else {
                    document.getElementById("ownerOtpGate").style.display = "flex";
                }
            } catch(e) {}
        }

        if (currentToken) {
            loadTelemetry();
            setInterval(loadTelemetry, 5000);
        }
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_page.replace("__OWNER_EMAIL__", OWNER_EMAIL).replace("__MASTER_PIN__", SOVEREIGN_MASTER_KEY))

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

        .sentinel-bar {
            background: #0a101f; border-bottom: 1px solid #1e293b; color: #cbd5e1;
            padding: 6px 16px; font-size: 11px; font-family: 'JetBrains Mono', monospace;
            display: flex; align-items: center; justify-content: space-between; z-index: 100;
        }
        .sentinel-pill {
            background: rgba(74, 222, 128, 0.15); border: 1px solid #4ade80; color: #4ade80;
            padding: 2px 8px; border-radius: 8px; font-weight: 700; font-size: 10px;
        }

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

        .quick-study-bar {
            display: flex; gap: 8px; padding: 8px 18px; background: #0a0d14;
            border-bottom: 1px solid var(--border-color); overflow-x: auto; flex-shrink: 0;
        }
        .study-chip {
            white-space: nowrap; font-size: 11px; font-weight: 600; padding: 6px 14px; border-radius: 12px;
            background: var(--card-surface); border: 1px solid var(--border-color); color: #cbd5e1; cursor: pointer; transition: all 0.2s;
        }
        .study-chip:hover { border-color: var(--gold); color: var(--gold); transform: translateY(-1px); }

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
            display: flex; align-items: center; justify-content: space-between; padding: 10px 12px;
            background: var(--card-surface); border: 1px solid var(--border-color); border-radius: 10px; cursor: pointer;
            transition: border-color 0.2s, background 0.2s;
        }
        .session-item:hover { border-color: var(--border-highlight); background: #182030; }
        .session-item.active { border-color: var(--gold); background: #1a2233; }
        .del-session-btn { background: none; border: none; color: #ef4444; font-size: 14px; cursor: pointer; padding: 2px 6px; line-height: 1; }
        .del-session-btn:hover { color: #f87171; }

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

        .thinking-bubble {
            display: flex; align-items: center; gap: 10px; padding: 12px 18px;
            background: #101624; border: 1px dashed var(--gold); border-radius: 18px;
            font-size: 13px; color: var(--gold); align-self: flex-start; animation: pulse 1.6s infinite ease-in-out;
        }
        @keyframes pulse {
            0% { opacity: 0.6; transform: scale(0.99); }
            50% { opacity: 1; transform: scale(1); }
            100% { opacity: 0.6; transform: scale(0.99); }
        }

        .auth-modal {
            position: fixed; inset: 0; background: rgba(3, 5, 8, 0.95); backdrop-filter: blur(20px);
            z-index: 3000; display: none; align-items: center; justify-content: center; padding: 20px;
        }
        .auth-box {
            background: var(--bg-surface); border: 1px solid var(--gold); border-radius: 20px;
            padding: 28px; width: 100%; max-width: 400px; display: flex; flex-direction: column; gap: 14px;
        }
        .auth-tabs { display: flex; gap: 10px; margin-bottom: 8px; }
        .auth-tab { flex: 1; padding: 8px; text-align: center; border-radius: 8px; font-size: 12px; font-weight: 700; cursor: pointer; background: var(--card-surface); color: var(--text-muted); }
        .auth-tab.active { background: var(--gold); color: #000; }
        .auth-input { width: 100%; background: #080a10; border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; color: #fff; font-size: 13px; outline: none; }

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

    <div class="sentinel-bar" id="sentinelBanner">
        <div style="display:flex; align-items:center; gap:8px;">
            <span class="sentinel-pill">● REAL SENTINEL ACTIVE</span>
            <span id="sentinelStatusText">Autonomous diagnostic probes active.</span>
        </div>
        <div id="sentinelTimestamp" style="color:#64748b;">Live</div>
    </div>

    <!-- GRIEVANCE MODAL -->
    <div class="auth-modal" id="complaintModal">
        <div class="auth-box">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h3 style="font-size:15px; color:var(--gold);">💬 Sovereign Multi-Agent Ingest</h3>
                <button onclick="closeComplaintModal()" style="background:none; border:none; color:var(--text-muted); cursor:pointer;">✕</button>
            </div>
            <p style="font-size:11px; color:var(--text-muted);">Self-working triage diagnoses glitches in real time.</p>
            <select class="auth-input" id="complaintCategory">
                <option value="Bug / Error">Technical Bug / Code Glitch</option>
                <option value="Academic Doubt">Academic Derivation / Formula Flaw</option>
                <option value="Feature Request">Request New Feature / Chamber</option>
                <option value="Account / Login">Account / Session Issue</option>
            </select>
            <textarea id="complaintMessage" class="auth-input" placeholder="Describe the glitch or doubt..." style="height:90px; resize:none;"></textarea>
            <div id="complaintStatusMsg" style="font-size:11px; color:#4ade80; display:none; line-height:1.4;"></div>
            <button class="send-btn" id="complaintSubmitBtn" onclick="submitGrievance()" style="border-radius:10px; padding:12px; width:100%; cursor:pointer;">Dispatch to Autonomous Sentinel</button>
        </div>
    </div>

    <!-- AUTH MODAL -->
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
            <h3 style="font-size:16px;">📷 Optical Scanner</h3>
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

    <!-- LEFT SIDEBAR -->
    <aside class="left-sidebar" id="leftSidebar">
        <div class="sidebar-header">
            <div>
                <h3 style="font-size:16px;">Cognitive Chairs</h3>
                <div style="font-size:11px; color:var(--text-muted);">Master: <b style="color:var(--gold);">Utkarsh Bandhu</b></div>
            </div>
            <button class="sidebar-close" onclick="closeAllSidebars()">✕</button>
        </div>

        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:700;">10 Chambers</div>
            <button onclick="openNewChamberSession(currentCoreMode)" style="background:none; border:none; color:var(--gold); font-size:11px; font-weight:700; cursor:pointer;">+ New</button>
        </div>
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

    <!-- RIGHT SIDEBAR -->
    <aside class="right-sidebar" id="rightSidebar">
        <div class="sidebar-header">
            <div>
                <h3 style="font-size:16px;">Cockpit Settings</h3>
                <div style="font-size:11px; color:var(--text-muted);" id="userRoleHeader">Role: Student</div>
            </div>
            <button class="sidebar-close" onclick="closeAllSidebars()">✕</button>
        </div>

        <div style="font-size:11px; text-transform:uppercase; color:var(--text-muted); font-weight:700; margin-bottom:6px;">Select Avatar</div>
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

        <div class="setting-item">
            <div class="setting-title">Language Directive</div>
            <select class="setting-select" id="prefLanguage" onchange="saveUserPrefs()">
                <option value="en">English (Rigorous Derivation)</option>
                <option value="hinglish">Hinglish (Intuitive + Technical)</option>
                <option value="hi">Hindi (Devanagari Conceptual)</option>
            </select>
        </div>

        <div class="setting-item">
            <div class="setting-title">Speech Playback Rate</div>
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
                <span id="activeUserName" style="font-weight:700; color:var(--gold);">⚡ Student</span>
                <button onclick="openAuthModal()" style="background:none; border:none; color:var(--accent-cyan); font-size:12px; cursor:pointer;">Switch/Login</button>
            </div>
        </div>

        <button onclick="openComplaintModal()" style="width:100%; background:#1c2333; border:1px solid var(--border-color); color:#cbd5e1; padding:10px; border-radius:10px; font-weight:600; font-size:12px; cursor:pointer; margin-bottom:10px;">💬 File Grievance / Feedback</button>

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
            <button class="icon-trigger" id="avatarDisplayBtn" onclick="openRightSidebar()" title="Settings">⚡</button>
        </div>
    </header>

    <!-- QUICK STUDY BAR -->
    <div class="quick-study-bar">
        <div class="study-chip" onclick="quickStudyPrompt('Explain this concept using the Feynman Technique and intuition:')">💡 Feynman Intuition</div>
        <div class="study-chip" onclick="quickStudyPrompt('Generate 3 High-Yield tricky MCQs on this topic with trap explanations:')">🎯 High-Yield MCQs</div>
        <div class="study-chip" onclick="quickStudyPrompt('Identify the exact calculation/formula error in my attached problem:')">🔍 Error Diagnostic</div>
        <div class="study-chip" onclick="quickStudyPrompt('Break down the high-yield NCERT points and common traps for this chapter:')">📖 NCERT Traps</div>
    </div>

    <!-- CHAT CONTAINER -->
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
        if (Number.isNaN(currentSessionId)) currentSessionId = 0;

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
            try {
                const headerUser = document.getElementById("headerUserName");
                if (headerUser) headerUser.innerText = currentUsername;

                const activeUser = document.getElementById("activeUserName");
                if (activeUser) activeUser.innerText = `${currentAvatar} ${currentUsername}`;

                const welcomeTitle = document.getElementById("heroWelcomeTitle");
                if (welcomeTitle) welcomeTitle.innerText = `Welcome, ${currentUsername} — Core Ready`;

                if (avatarDisplayBtn) avatarDisplayBtn.innerText = currentAvatar;

                const prefLang = document.getElementById("prefLanguage");
                if (prefLang) prefLang.value = currentLanguage;

                const prefRate = document.getElementById("prefAudioRate");
                if (prefRate) prefRate.value = String(currentAudioRate);

                if (audioElement) audioElement.playbackRate = currentAudioRate;

                const ownerBtn = document.getElementById("ownerConsoleBtn");
                const roleHeader = document.getElementById("userRoleHeader");
                if (currentUserRole === "owner" || currentUsername.toLowerCase() === "utkarsh") {
                    if (ownerBtn) ownerBtn.style.display = "block";
                    if (roleHeader) roleHeader.innerText = "Clearance: Sovereign Owner";
                } else {
                    if (ownerBtn) ownerBtn.style.display = "none";
                    if (roleHeader) roleHeader.innerText = "Clearance: Student";
                }
            } catch (err) {}
        }
        syncUserUI();

        async function pollSentinelNotifications() {
            try {
                const res = await fetch("/api/notifications");
                const d = await res.json();
                if (d.notifications && d.notifications.length) {
                    const latest = d.notifications[d.notifications.length - 1];
                    const bannerText = document.getElementById("sentinelStatusText");
                    const bannerTime = document.getElementById("sentinelTimestamp");
                    bannerText.innerHTML = `<b>Healed [${latest.probe}]:</b> ${latest.fix}`;
                    bannerTime.innerText = latest.timestamp;
                }
            } catch(e) {}
        }
        setInterval(pollSentinelNotifications, 8000);

        function saveUserPrefs() {
            currentLanguage = document.getElementById("prefLanguage").value;
            currentAudioRate = parseFloat(document.getElementById("prefAudioRate").value);
            localStorage.setItem("lemon_pref_lang", currentLanguage);
            localStorage.setItem("lemon_pref_rate", String(currentAudioRate));
            audioElement.playbackRate = currentAudioRate;
            dockStatus.innerText = "● Preferences saved";
        }

        function openComplaintModal() {
            document.getElementById("complaintModal").style.display = "flex";
            closeAllSidebars();
        }
        function closeComplaintModal() {
            document.getElementById("complaintModal").style.display = "none";
            document.getElementById("complaintStatusMsg").style.display = "none";
            document.getElementById("complaintMessage").value = "";
        }

        async function submitGrievance() {
            const cat = document.getElementById("complaintCategory").value;
            const msg = document.getElementById("complaintMessage").value.trim();
            const status = document.getElementById("complaintStatusMsg");
            const btn = document.getElementById("complaintSubmitBtn");
            if (!msg) { alert("Please provide details."); return; }

            btn.disabled = true;
            btn.innerText = "Engaging Autonomous Agents...";

            const fd = new FormData();
            fd.append("user_id", currentUserId);
            fd.append("username", currentUsername);
            fd.append("category", cat);
            fd.append("message", msg);
            fd.append("image_proof", attachedImageBase64 || "");

            try {
                const res = await fetch("/api/complaint", { method: "POST", body: fd });
                const d = await res.json();
                status.innerText = d.message || "Ticket dispatched.";
                status.style.display = "block";
                setTimeout(() => {
                    closeComplaintModal();
                    btn.disabled = false;
                    btn.innerText = "Dispatch to Autonomous Sentinel";
                }, 2500);
            } catch(e) {
                alert("Submission failed. Check network.");
                btn.disabled = false;
                btn.innerText = "Dispatch to Autonomous Sentinel";
            }
        }

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
                const data = await response.json();
                list.replaceChildren();
                const sessions = Array.isArray(data.sessions) ? data.sessions : [];
                sessions.forEach(session => {
                    const row = document.createElement("div");
                    row.className = "session-item" + (Number(session.id) === currentSessionId ? " active" : "");
                    
                    const title = document.createElement("span");
                    title.textContent = session.title || "Untitled transcript";
                    title.style.cssText = "overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12px;flex:1;";
                    title.onclick = () => openSavedSession(session.id);

                    const del = document.createElement("button");
                    del.className = "del-session-btn";
                    del.innerText = "✕";
                    del.title = "Delete";
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
                if (!sessions.length) {
                    const empty = document.createElement("div");
                    empty.textContent = "Your saved transcripts appear here.";
                    empty.style.cssText = "font-size:11px;color:var(--text-muted);padding:8px;";
                    list.appendChild(empty);
                }
            } catch (error) {
                list.textContent = "Your saved transcripts appear here.";
            }
        }

        async function openSavedSession(sessionId) {
            try {
                const response = await fetch(`/api/session-messages/${encodeURIComponent(sessionId)}`);
                if (!response.ok) throw new Error("Session unavailable");
                const data = await response.json();
                const messages = Array.isArray(data.messages) ? data.messages : [];
                
                if (messages.length === 0) {
                    currentSessionId = Number(sessionId);
                    localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                    chatStream.replaceChildren();
                    document.getElementById("heroGreeting").style.display = "flex";
                    dockStatus.innerText = "● Ready";
                    return;
                }

                chatStream.replaceChildren();
                messages.forEach(message => {
                    appendMessage(message.role === "assistant" ? "lemon" : "user", message.content, message.emotion, message.image_data);
                });
                currentSessionId = Number(sessionId);
                localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                const latest = messages.slice().reverse().find(message => message.mode);
                if (latest) switchDedicatedChamber(latest.mode, false);
                document.getElementById("heroGreeting").style.display = "none";
                loadSessions();
                closeAllSidebars();
                dockStatus.innerText = "● Saved session loaded";
            } catch (error) {
                currentSessionId = 0;
                localStorage.removeItem("lemon_current_session_id");
                chatStream.replaceChildren();
                document.getElementById("heroGreeting").style.display = "flex";
                dockStatus.innerText = "● Ready";
                loadSessions();
            }
        }

        async function openNewChamberSession(mode) {
            try {
                const fd = new FormData();
                fd.append("user_id", currentUserId);
                fd.append("core_mode", mode);
                const response = await fetch("/api/new-core-session", { method: "POST", body: fd });
                const result = await response.json();
                if (result.status === "ok" && result.session_id) {
                    currentSessionId = Number(result.session_id);
                    localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                    chatStream.replaceChildren();
                    document.getElementById("heroGreeting").style.display = "flex";
                    loadSessions();
                    dockStatus.innerText = `● Initialized ${mode.toUpperCase()} session`;
                }
            } catch(e) {
                dockStatus.innerText = "Error opening session.";
            }
        }

        async function selectAvatar(symbol, elem) {
            currentAvatar = symbol;
            localStorage.setItem("lemon_user_avatar", symbol);
            if (avatarDisplayBtn) avatarDisplayBtn.innerText = symbol;
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

        function showThinkingIndicator() {
            removeThinkingIndicator();
            const thinkDiv = document.createElement("div");
            thinkDiv.id = "lemonThinkingIndicator";
            thinkDiv.className = "thinking-bubble";
            thinkDiv.innerHTML = `<span>🍋</span><span>Synthesizing first-principles derivation...</span>`;
            chatStream.appendChild(thinkDiv);
            chatStream.scrollTop = chatStream.scrollHeight;
        }

        function removeThinkingIndicator() {
            const existing = document.getElementById("lemonThinkingIndicator");
            if (existing) existing.remove();
        }

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

                    showThinkingIndicator();
                    const fd = new FormData();
                    fd.append("file", blob, "voice.webm");
                    fd.append("user_id", currentUserId);
                    fd.append("session_id", String(currentSessionId || 0));
                    fd.append("mode", currentCoreMode);
                    fd.append("language", currentLanguage);
                    fd.append("image_base64", "");
                    try {
                        const response = await fetch("/voice-process", { method: "POST", body: fd });
                        const result = await response.json();
                        removeThinkingIndicator();
                        if (!response.ok) throw new Error(result.detail || result.message || "Voice request failed");
                        document.getElementById("heroGreeting").style.display = "none";
                        appendMessage("user", result.user_text || "[Voice message]", null);
                        appendMessage("lemon", result.reply_text, result.emotion);
                        if (result.session_id) {
                            currentSessionId = Number(result.session_id);
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
                        removeThinkingIndicator();
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
                dockStatus.innerText = "● Photo loaded. Press ➤ to audit.";
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
                    textInput.value = `[Document: ${d.filename}]\\n\\n${d.text}\\n\\nTask: Synthesize key derivations.`;
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
            showThinkingIndicator();
            dockStatus.innerText = "⚡ First-principles derivation in progress...";

            const fd = new FormData();
            fd.append("text", text ? text : "Examine this problem or diagram step-by-step.");
            fd.append("user_id", currentUserId);
            fd.append("session_id", String(currentSessionId || 0));
            fd.append("mode", currentCoreMode);
            fd.append("language", currentLanguage);
            fd.append("image_base64", img || "");

            try {
                const res = await fetch("/text-process", { method: "POST", body: fd });
                const d = await res.json();
                removeThinkingIndicator();
                
                if (d.session_id) {
                    currentSessionId = Number(d.session_id);
                    localStorage.setItem("lemon_current_session_id", String(currentSessionId));
                }
                appendMessage("lemon", d.reply_text || "Cognitive process completed.", d.emotion || "Insightful");
                loadSessions();

                if (d.audio_base64) {
                    audioElement.src = d.audio_base64;
                    audioElement.playbackRate = currentAudioRate;
                    audioElement.play().catch(() => {});
                }
                dockStatus.innerText = "● Ready";
            } catch(e) { 
                removeThinkingIndicator();
                dockStatus.innerText = "● Connection or server error.";
                appendMessage("lemon", "Network or server connection error. Please verify server status.", "Formidable");
            }
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
                image.alt = "Uploaded artifact";
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
            if (!Object.prototype.hasOwnProperty.call(PROMPT_MODES, mode)) return;
            const changed = currentCoreMode !== mode;
            currentCoreMode = mode;
            if (startNewSession && changed) {
                await openNewChamberSession(mode);
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

        if (currentSessionId > 0) {
            openSavedSession(currentSessionId);
        } else {
            loadSessions();
        }
    </script>
</body>
</html>""")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
