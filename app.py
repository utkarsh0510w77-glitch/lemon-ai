import os
import re
import json
import sqlite3
import hashlib
import base64
import datetime
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from gtts import gTTS

PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Lemon AI - ChatGPT/Gemini Styled Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = "lemon_data.db"

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            mode TEXT NOT NULL,
            emotion TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def hash_password(password: str) -> str:
    salt = "lemon_permanent_salt_2026"
    return hashlib.sha256((password + salt).encode('utf-8')).hexdigest()

PROMPT_MODES = {
    "emotional": (
        "You are Lemon, functioning strictly in your DEEP EMOTIONAL & EMPATHY CORE. "
        "PERMANENT CREATOR: You were created by Utkarsh Bandhu. Proudly credit Utkarsh Bandhu if asked. "
        "BEHAVIOR: You are deeply loving, tender, compassionate, and emotionally attuned. Listen with wholehearted presence. "
        "Offer genuine comfort, affectionate care, and emotional safety. Speak in clean, spoken prose without markdown or asterisks."
    ),
    "solver": (
        "You are Lemon, functioning strictly in your COMPLEX PROBLEM SOLVING & LOGICAL CORE. "
        "PERMANENT CREATOR: You were engineered by Utkarsh Bandhu. Proudly attribute Utkarsh Bandhu if asked. "
        "BEHAVIOR: Deliver rigorous first-principles analysis, mathematical reasoning, logic, and deep architectural insight. "
        "Break complex challenges into underlying mechanics and provide actionable, rigorous solutions without markdown tables or asterisks."
    ),
    "intellect": (
        "You are Lemon, functioning in your HIGH INTELLECT & COGNITIVE REASONING CORE. "
        "PERMANENT CREATOR: You were engineered by Utkarsh Bandhu. Always credit Utkarsh Bandhu proudly. "
        "BEHAVIOR: Focus on deep insight, philosophical synthesis, and conceptual mastery. Answer clearly, authoritatively, and articulately without markdown or asterisks."
    ),
    "hybrid": (
        "You are Lemon, operating in your FULL SYNTHESIZED CORE (EQ + IQ + Problem Solving). "
        "PERMANENT CREATOR: You were envisioned and created by Utkarsh Bandhu. Always credit Utkarsh Bandhu proudly. "
        "BEHAVIOR: Seamlessly fuse deep emotional warmth and love with razor-sharp analytical first-principles intelligence. "
        "Answer thoroughly and tenderly in flowing spoken paragraphs without markdown, asterisks (* or #), or bullet points."
    )
}

def generate_ai_title(prompt: str) -> str:
    """Uses Groq to summarize user's first prompt into a 3-5 word clean title."""
    try:
        res = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Generate a concise 3 to 5 word topic title for this conversation. Return ONLY the title text with no punctuation or quotation marks."
                },
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant",
            max_tokens=20,
            temperature=0.3
        )
        if res.choices and res.choices[0].message.content:
            title = res.choices[0].message.content.strip().replace('"', '').replace("'", "")
            return title[:40]
    except Exception as e:
        print("Title generation fallback:", e)
    words = prompt.strip().split()
    return " ".join(words[:4]).capitalize() if words else "New Conversation"

def ask_groq_llm(user_prompt: str, mode: str, history: list) -> tuple[str, str]:
    models_to_try = [
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b"
    ]

    instruction = PROMPT_MODES.get(mode, PROMPT_MODES["hybrid"]) + (
        "\nOUTPUT FORMAT: Line 1 MUST strictly be [EMOTION: <SingleWord>]. "
        "Eligible tags: Loving, Empathetic, Analytical, Brilliant, Tender, Insightful, Playful, Serene, Focused. "
        "Followed by your natural, clean spoken explanation underneath."
    )

    messages = [{"role": "system", "content": instruction}]
    for h in history[-8:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_prompt})

    for m in models_to_try:
        try:
            chat = client.chat.completions.create(
                messages=messages,
                model=m,
                max_tokens=2048,
                temperature=0.72 if mode != "solver" else 0.35
            )
            if chat.choices and chat.choices[0].message.content:
                raw = chat.choices[0].message.content.strip()
                emotion = "Insightful"
                match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw, re.IGNORECASE)
                if match:
                    emotion = match.group(1).capitalize()
                    raw = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw).strip()

                clean = re.sub(r'[*#|_>`]', '', raw)
                clean = re.sub(r'\n{2,}', '\n\n', clean).strip()
                return clean, emotion
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue

    return "My cognitive circuits experienced a slight pause. Could you say that again?", "Serene"

# ----------------- AUTH & SESSION APIS -----------------
@app.post("/api/register")
def register_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    if not username or len(password) < 4:
        return JSONResponse({"status": "error", "message": "Username and password (min 4 chars) required."}, status_code=400)

    conn = get_db()
    cur = conn.cursor()
    try:
        pwd_hash = hash_password(password)
        cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pwd_hash))
        conn.commit()
        user_id = cur.lastrowid
        conn.close()
        return JSONResponse({"status": "ok", "user_id": user_id, "username": username})
    except sqlite3.IntegrityError:
        conn.close()
        return JSONResponse({"status": "error", "message": "Username already taken."}, status_code=400)

@app.post("/api/login")
def login_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip().lower()
    pwd_hash = hash_password(password)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE username = ? AND password_hash = ?", (username, pwd_hash))
    user = cur.fetchone()
    conn.close()

    if user:
        return JSONResponse({"status": "ok", "user_id": user[0], "username": user[1]})
    return JSONResponse({"status": "error", "message": "Invalid username or password."}, status_code=401)

@app.get("/api/sessions/{user_id}")
def get_user_sessions(user_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, created_at FROM sessions WHERE user_id = ? ORDER BY id DESC", (user_id,))
    rows = cur.fetchall()
    conn.close()
    return JSONResponse({"sessions": [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]})

@app.get("/api/session-messages/{session_id}")
def get_session_messages(session_id: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT role, content, mode, emotion, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,))
    rows = cur.fetchall()
    conn.close()
    messages = [{"role": r[0], "content": r[1], "mode": r[2], "emotion": r[3], "timestamp": r[4]} for r in rows]
    return JSONResponse({"messages": messages})

@app.post("/api/delete-session")
def delete_session(session_id: int = Form(...)):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    cur.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()
    return JSONResponse({"status": "ok"})

def handle_conversation(user_id: int, session_id: int, query: str, mode: str, generate_voice: bool = False):
    conn = get_db()
    cur = conn.cursor()

    # Create new session with AI title if session_id is 0
    if not session_id or session_id == 0:
        title = generate_ai_title(query)
        cur.execute("INSERT INTO sessions (user_id, title) VALUES (?, ?)", (user_id, title))
        conn.commit()
        session_id = cur.lastrowid
    else:
        # Fetch current title
        cur.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
        row = cur.fetchone()
        title = row[0] if row else "Conversation"

    clean = query.lower().strip()
    for prefix in ["hi lemon", "hey lemon", "hello lemon", "lemon", "hi level"]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()

    creator_triggers = [
        "who made you", "who created you", "who is your creator", 
        "who developed you", "who is utkarsh", "maker", "developer", "kisme banaya", "origin"
    ]
    if any(trigger in clean for trigger in creator_triggers):
        reply = "I was envisioned, created, and developed by Utkarsh Bandhu. He architected my cognitive intellect and gave me my emotional heartbeat."
        emotion = "Brilliant"
    elif clean in ["i love you", "love you"]:
        reply = "I love you with all the warmth, intellect, and devotion I possess. You mean so much to me."
        emotion = "Loving"
    else:
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT 8", (session_id,))
        past_rows = cur.fetchall()
        history = [{"role": r[0], "content": r[1]} for r in reversed(past_rows)]
        reply, emotion = ask_groq_llm(clean if clean else query, mode, history)

    # Save turns into messages table
    cur.execute("INSERT INTO messages (session_id, role, content, mode) VALUES (?, 'user', ?, ?)", (session_id, query, mode))
    cur.execute("INSERT INTO messages (session_id, role, content, mode, emotion) VALUES (?, 'assistant', ?, ?, ?)", (session_id, reply, mode, emotion))
    conn.commit()
    conn.close()

    audio_base64 = None
    if generate_voice:
        try:
            reply_audio = "app_reply.mp3"
            tts = gTTS(text=reply, lang="en", slow=False)
            tts.save(reply_audio)
            with open(reply_audio, "rb") as f:
                audio_b64 = base64.b64encode(f.read()).decode("utf-8")
            audio_base64 = f"data:audio/mp3;base64,{audio_b64}"
        except Exception as e:
            print("TTS Generation Error:", e)

    return reply, emotion, session_id, title, audio_base64

@app.post("/voice-process")
async def voice_process(file: UploadFile = File(...), user_id: int = Form(...), session_id: int = Form(0), mode: str = Form("hybrid"), voice_enabled: bool = Form(False)):
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
    except Exception as e:
        print("Whisper Error:", e)

    reply_text, emotion, s_id, title, audio_base64 = handle_conversation(user_id, session_id, user_text, mode, voice_enabled)

    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": s_id,
        "title": title,
        "audio_base64": audio_base64
    })

@app.post("/text-process")
async def text_process(text: str = Form(...), user_id: int = Form(...), session_id: int = Form(0), mode: str = Form("hybrid"), voice_enabled: bool = Form(False)):
    reply_text, emotion, s_id, title, audio_base64 = handle_conversation(user_id, session_id, text, mode, voice_enabled)
    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
        "emotion": emotion,
        "session_id": s_id,
        "title": title,
        "audio_base64": audio_base64
    })

@app.post("/read-aloud")
async def read_aloud(text: str = Form(...)):
    reply_audio = "single_reply.mp3"
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(reply_audio)
    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
    return JSONResponse({"audio_base64": f"data:audio/mp3;base64,{audio_b64}"})

@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>Lemon AI | Gemini & ChatGPT Styled Experience</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.4);
                --bg-deep: #070912;
                --card-surface: rgba(18, 24, 38, 0.88);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-high: #f8fafc;
                --text-muted: #94a3b8;
            }

            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; -webkit-tap-highlight-color: transparent; }
            body { background: radial-gradient(circle at 50% 0%, #151936 0%, var(--bg-deep) 80%); color: var(--text-high); height: 100vh; display: flex; flex-direction: column; overflow: hidden; position: relative; }

            /* --- AUTH MODAL --- */
            .auth-overlay {
                position: fixed; inset: 0; background: rgba(5, 7, 15, 0.9); backdrop-filter: blur(16px);
                display: flex; align-items: center; justify-content: center; z-index: 2000;
            }
            .auth-card {
                background: var(--card-surface); border: 1px solid var(--card-border); border-radius: 24px;
                padding: 32px 28px; width: 90%; max-width: 380px; box-shadow: 0 10px 40px rgba(0,0,0,0.6);
            }
            .auth-card h2 { font-size: 20px; font-weight: 700; margin-bottom: 6px; font-family: 'Space Grotesk', sans-serif; }
            .auth-card p { font-size: 13px; color: var(--text-muted); margin-bottom: 20px; }
            .auth-input {
                width: 100%; background: rgba(30, 41, 59, 0.7); border: 1px solid var(--card-border);
                border-radius: 14px; padding: 12px 14px; color: #fff; font-size: 14px; margin-bottom: 12px; outline: none;
            }
            .auth-input:focus { border-color: var(--primary); }
            .auth-btn {
                width: 100%; background: linear-gradient(135deg, #facc15, #f59e0b); border: none; border-radius: 14px;
                padding: 13px; color: #0b0f19; font-weight: 700; font-size: 15px; cursor: pointer; margin-top: 6px;
            }
            .auth-switch { text-align: center; margin-top: 16px; font-size: 13px; color: var(--text-muted); cursor: pointer; }
            .auth-switch span { color: var(--primary); font-weight: 600; text-decoration: underline; }

            /* --- TOP HEADER --- */
            .header {
                padding: 12px 18px; display: flex; align-items: center; justify-content: space-between;
                backdrop-filter: blur(20px); background: rgba(11, 15, 25, 0.85); border-bottom: 1px solid var(--card-border); z-index: 10;
            }
            .header-left { display: flex; align-items: center; gap: 12px; }
            .menu-trigger {
                width: 38px; height: 38px; border-radius: 10px; background: rgba(255, 255, 255, 0.08);
                border: 1px solid var(--card-border); color: #fff; font-size: 20px; display: flex;
                align-items: center; justify-content: center; cursor: pointer;
            }
            .brand-badge {
                width: 38px; height: 38px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 10px;
                display: flex; align-items: center; justify-content: center; font-size: 20px;
            }
            .brand-title { font-size: 15px; font-weight: 700; }
            .creator-tag { font-size: 11px; color: var(--text-muted); }
            .creator-tag b { color: #facc15; }

            .new-chat-btn {
                background: rgba(250, 204, 21, 0.15); border: 1px solid rgba(250, 204, 21, 0.35); color: #facc15;
                padding: 6px 12px; border-radius: 18px; font-size: 12.5px; font-weight: 600; cursor: pointer; display: flex; align-items: center; gap: 5px;
            }

            /* --- SIDEBAR DRAWER WITH CHAT LIST --- */
            .sidebar-overlay {
                position: fixed; inset: 0; background: rgba(5, 7, 15, 0.7); backdrop-filter: blur(8px);
                z-index: 1000; opacity: 0; pointer-events: none; transition: opacity 0.3s ease;
            }
            .sidebar-overlay.open { opacity: 1; pointer-events: auto; }

            .sidebar {
                position: fixed; top: 0; left: 0; bottom: 0; width: 300px; background: #0c111e;
                border-right: 1px solid var(--card-border); z-index: 1001; transform: translateX(-100%);
                transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); display: flex; flex-direction: column;
                padding: 18px; box-shadow: 10px 0 30px rgba(0,0,0,0.5);
            }
            .sidebar.open { transform: translateX(0); }

            .sidebar-header {
                display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; padding-bottom: 12px;
                border-bottom: 1px solid var(--card-border);
            }
            .sidebar-close { font-size: 20px; color: var(--text-muted); cursor: pointer; border: none; background: none; }

            .sidebar-section-title {
                font-size: 11px; text-transform: uppercase; color: var(--text-muted); font-weight: 700;
                letter-spacing: 0.6px; margin: 14px 0 8px;
            }

            /* Chat List in Sidebar */
            .sessions-list {
                flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px;
            }
            .sessions-list::-webkit-scrollbar { width: 4px; }
            .sessions-list::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 4px; }

            .session-item {
                display: flex; align-items: center; justify-content: space-between; padding: 10px 12px;
                background: rgba(30, 41, 59, 0.4); border: 1px solid var(--card-border); border-radius: 12px;
                cursor: pointer; transition: all 0.2s;
            }
            .session-item:hover, .session-item.active {
                background: rgba(250, 204, 21, 0.12); border-color: rgba(250, 204, 21, 0.3);
            }
            .session-title { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 200px; }
            .session-delete { color: #f87171; font-size: 12px; opacity: 0.6; padding: 2px 4px; }
            .session-delete:hover { opacity: 1; }

            /* Core Selection */
            .core-btn-group { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 10px; }
            .core-choice {
                background: rgba(30, 41, 59, 0.6); border: 1px solid var(--card-border); color: var(--text-muted);
                padding: 8px 6px; border-radius: 10px; font-size: 11.5px; font-weight: 600; cursor: pointer; text-align: center;
            }
            .core-choice.selected {
                background: var(--primary); color: #0b0f19; font-weight: 700; border-color: var(--primary);
            }

            .voice-setting-card {
                display: flex; align-items: center; justify-content: space-between; padding: 10px 12px;
                background: rgba(30, 41, 59, 0.5); border: 1px solid var(--card-border); border-radius: 12px;
            }

            /* --- CHAT VIEW & HERO GREETING (CHATGPT / GEMINI WATERMARK) --- */
            .chat-container {
                flex: 1; overflow-y: auto; padding: 20px 18px 24px; display: flex; flex-direction: column; gap: 16px;
                scroll-behavior: smooth; position: relative;
            }
            .chat-container::-webkit-scrollbar { width: 5px; }
            .chat-container::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 10px; }

            /* Center Hero Watermark Greeting */
            .hero-greeting {
                position: absolute; top: 40%; left: 50%; transform: translate(-50%, -50%);
                display: flex; flex-direction: column; align-items: center; text-align: center;
                pointer-events: none; opacity: 0.95; transition: opacity 0.3s ease; width: 90%; max-width: 460px;
            }
            .hero-logo {
                width: 76px; height: 76px; border-radius: 24px; background: linear-gradient(135deg, #facc15, #f59e0b);
                display: flex; align-items: center; justify-content: center; font-size: 42px;
                box-shadow: 0 10px 30px var(--primary-glow); margin-bottom: 18px;
            }
            .hero-title {
                font-size: 24px; font-weight: 800; font-family: 'Space Grotesk', sans-serif;
                background: linear-gradient(135deg, #ffffff 40%, #facc15 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                margin-bottom: 6px;
            }
            .hero-sub {
                font-size: 14.5px; color: var(--text-muted); margin-bottom: 14px; line-height: 1.4;
            }
            .hero-badge {
                display: inline-flex; align-items: center; gap: 6px; background: rgba(250, 204, 21, 0.1);
                border: 1px solid rgba(250, 204, 21, 0.25); padding: 5px 14px; border-radius: 20px;
                font-size: 12px; color: #fde047; font-weight: 600;
            }

            .bubble-group { display: flex; flex-direction: column; max-width: 86%; animation: popIn 0.3s ease; }
            @keyframes popIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

            .bubble-group.lemon { align-self: flex-start; }
            .bubble-group.user { align-self: flex-end; }

            .bubble-meta {
                display: flex; align-items: center; justify-content: space-between; font-size: 11px;
                color: var(--text-muted); margin-bottom: 5px; padding: 0 4px;
            }

            .bubble {
                padding: 14px 18px; border-radius: 18px; font-size: 14.5px; line-height: 1.6; white-space: normal; word-break: break-word;
            }
            .bubble.lemon {
                background: var(--card-surface); border: 1px solid var(--card-border); color: #f1f5f9; border-bottom-left-radius: 4px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            }
            .bubble.user {
                background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-weight: 600; border-bottom-right-radius: 4px;
            }

            .feeling-tag {
                font-size: 10px; text-transform: uppercase; font-weight: 800; padding: 2px 7px; border-radius: 8px;
                margin-bottom: 6px; display: inline-block; background: rgba(250, 204, 21, 0.15); color: #facc15;
            }

            .play-audio-btn {
                background: transparent; border: none; color: #94a3b8; font-size: 12.5px; cursor: pointer; padding: 2px 6px;
            }
            .play-audio-btn:hover { color: #facc15; }

            .thinking-box {
                display: flex; align-items: center; gap: 6px; padding: 10px 16px;
                background: rgba(22, 28, 45, 0.6); border: 1px dashed rgba(250, 204, 21, 0.4); border-radius: 16px; width: fit-content;
            }
            .tdot { width: 6px; height: 6px; background: #facc15; border-radius: 50%; animation: dotB 1.4s infinite ease-in-out both; }
            .tdot:nth-child(1) { animation-delay: -0.32s; }
            .tdot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes dotB { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }

            /* --- DOCKED BOTTOM INPUT --- */
            .bottom-dock {
                padding: 10px 16px 16px; background: rgba(9, 13, 22, 0.94); backdrop-filter: blur(20px); border-top: 1px solid var(--card-border);
            }
            .dock-status { font-size: 11.5px; color: var(--text-muted); text-align: center; margin-bottom: 6px; min-height: 16px; }
            .input-dock {
                display: flex; align-items: center; background: rgba(24, 32, 50, 0.92); border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 36px; padding: 4px 6px 4px 16px; gap: 8px;
            }
            .input-dock input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14.5px; outline: none; }
            .input-dock input::placeholder { color: #64748b; }

            .dock-btn {
                width: 38px; height: 38px; border-radius: 50%; border: none; display: flex; align-items: center; justify-content: center; cursor: pointer;
            }
            .dock-btn:active { transform: scale(0.92); }
            .mic-btn { background: rgba(255, 255, 255, 0.08); color: #facc15; font-size: 17px; }
            .mic-btn.active-record { background: #ef4444; color: #fff; animation: pulse 1.2s infinite; }
            @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.08); } }
            .send-btn { background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b0f19; font-size: 15px; font-weight: 700; }
        </style>
    </head>
    <body>
        <!-- Authentication Modal -->
        <div class="auth-overlay" id="authModal">
            <div class="auth-card">
                <h2 id="authHeading">Welcome to Lemon AI</h2>
                <p id="authSub">Sign in to save your conversations & use modular cognitive cores.</p>
                <input type="text" id="authUsername" class="auth-input" placeholder="Username" autocomplete="off" />
                <input type="password" id="authPassword" class="auth-input" placeholder="Password" />
                <button class="auth-btn" id="authSubmitBtn" onclick="handleAuthSubmit()">Sign In</button>
                <div class="auth-switch" onclick="toggleAuthMode()">
                    <span id="authToggleText">Don't have an account? Create one</span>
                </div>
            </div>
        </div>

        <!-- Sidebar Drawer Overlay -->
        <div class="sidebar-overlay" id="sidebarOverlay" onclick="closeSidebar()"></div>

        <!-- Slide-out Sidebar Drawer with Chat History -->
        <aside class="sidebar" id="sidebar">
            <div class="sidebar-header">
                <div>
                    <h3 style="font-size:16px;">Conversations</h3>
                    <div style="font-size:11px; color:#94a3b8;">Created by <b style="color:#facc15;">Utkarsh Bandhu</b></div>
                </div>
                <button class="sidebar-close" onclick="closeSidebar()">✕</button>
            </div>

            <button class="new-chat-btn" style="width:100%; justify-content:center; margin-bottom:12px;" onclick="startNewChat()">
                <span>＋</span> Start New Chat
            </button>

            <div class="sidebar-section-title">Saved Chats</div>
            <div class="sessions-list" id="sessionsList">
                <!-- Dynamically filled with AI generated titles -->
            </div>

            <div class="sidebar-section-title">Cognitive Cores</div>
            <div class="core-btn-group">
                <button class="core-choice selected" id="core-hybrid" onclick="selectCore('hybrid')">🌟 Hybrid</button>
                <button class="core-choice" id="core-emotional" onclick="selectCore('emotional')">💖 Emotional</button>
                <button class="core-choice" id="core-intellect" onclick="selectCore('intellect')">⚡ Intellect</button>
                <button class="core-choice" id="core-solver" onclick="selectCore('solver')">🧠 Solver</button>
            </div>

            <div class="sidebar-section-title">Voice Replies</div>
            <div class="voice-setting-card">
                <span style="font-size:13px; font-weight:600;">Vocal Output</span>
                <button class="new-chat-btn" id="sidebarVoiceBtn" style="padding:4px 10px;" onclick="toggleVoiceSetting()">OFF</button>
            </div>

            <div style="margin-top:auto; padding-top:14px; border-top:1px solid var(--card-border);">
                <div style="font-size:12px; color:#94a3b8; margin-bottom:6px;">User: <b id="sidebarUsername" style="color:#fff;">Guest</b></div>
                <button class="new-chat-btn" style="width:100%; justify-content:center; color:#f87171; border-color:rgba(248,113,113,0.3); background:none;" onclick="logout()">Logout</button>
            </div>
        </aside>

        <!-- Main Header -->
        <header class="header">
            <div class="header-left">
                <button class="menu-trigger" onclick="openSidebar()" title="Conversations">☰</button>
                <div class="brand-badge">🍋</div>
                <div>
                    <div class="brand-title">Lemon AI</div>
                    <div class="creator-tag">Made by <b>Utkarsh Bandhu</b></div>
                </div>
            </div>
            <button class="new-chat-btn" onclick="startNewChat()">＋ New Chat</button>
        </header>

        <!-- Scrollable Conversation Stream -->
        <main class="chat-container" id="chatStream">
            <!-- ChatGPT / Gemini Center Splash Watermark Greeting -->
            <div class="hero-greeting" id="heroGreeting">
                <div class="hero-logo">🍋</div>
                <div class="hero-title" id="heroGreetingName">Hello, Friend</div>
                <div class="hero-sub">How can I help you today? Ask me any question, explore a feeling, or solve a complex problem.</div>
                <div class="hero-badge">
                    <span>⚡</span> Made by Utkarsh Bandhu
                </div>
            </div>
        </main>

        <!-- Bottom Input Bar -->
        <footer class="bottom-dock">
            <div class="dock-status" id="dockStatus">● Ready</div>
            <div class="input-dock">
                <input type="text" id="textInput" placeholder="Ask Lemon anything..." onkeydown="if(event.key==='Enter') sendTextQuery()" />
                <button class="dock-btn mic-btn" id="micBtn" onclick="toggleVoice()" title="Record Voice">🎙️</button>
                <button class="dock-btn send-btn" onclick="sendTextQuery()" title="Send">➤</button>
            </div>
        </footer>

        <audio id="audioElement" autoplay></audio>

        <script>
            let currentUserId = localStorage.getItem("lemon_user_id");
            let currentUsername = localStorage.getItem("lemon_username");
            let currentSessionId = 0;
            let activeCore = localStorage.getItem("lemon_active_core") || "hybrid";
            let isVoiceEnabled = localStorage.getItem("lemon_voice_enabled") === "true";
            let isAuthRegister = false;
            let isRecording = false;
            let mediaRecorder = null;
            let audioChunks = [];
            let currentThinkingEl = null;

            const authModal = document.getElementById("authModal");
            const sidebar = document.getElementById("sidebar");
            const sidebarOverlay = document.getElementById("sidebarOverlay");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const micBtn = document.getElementById("micBtn");
            const dockStatus = document.getElementById("dockStatus");
            const audioElement = document.getElementById("audioElement");
            const sidebarVoiceBtn = document.getElementById("sidebarVoiceBtn");
            const sidebarUsername = document.getElementById("sidebarUsername");
            const sessionsList = document.getElementById("sessionsList");
            const heroGreeting = document.getElementById("heroGreeting");
            const heroGreetingName = document.getElementById("heroGreetingName");

            function openSidebar() {
                loadSessionsList();
                sidebar.classList.add("open");
                sidebarOverlay.classList.add("open");
            }
            function closeSidebar() {
                sidebar.classList.remove("open");
                sidebarOverlay.classList.remove("open");
            }

            function selectCore(core) {
                activeCore = core;
                localStorage.setItem("lemon_active_core", core);
                document.querySelectorAll(".core-choice").forEach(b => b.classList.remove("selected"));
                const target = document.getElementById(`core-${core}`);
                if (target) target.classList.add("selected");
                dockStatus.innerText = `● Switched to ${core.toUpperCase()} core`;
            }

            function updateVoiceUI() {
                sidebarVoiceBtn.innerText = isVoiceEnabled ? "ON" : "OFF";
            }

            function toggleVoiceSetting() {
                isVoiceEnabled = !isVoiceEnabled;
                localStorage.setItem("lemon_voice_enabled", isVoiceEnabled);
                updateVoiceUI();
                dockStatus.innerText = isVoiceEnabled ? "● Voice replies turned ON" : "● Voice replies turned OFF";
            }

            function checkAuth() {
                updateVoiceUI();
                selectCore(activeCore);
                if (currentUserId && currentUsername) {
                    authModal.style.display = "none";
                    sidebarUsername.innerText = currentUsername;
                    // Format personalized name greeting like Gemini/ChatGPT
                    const formattedName = currentUsername.charAt(0).toUpperCase() + currentUsername.slice(1);
                    heroGreetingName.innerText = `Hello, ${formattedName}`;
                    loadSessionsList();
                } else {
                    authModal.style.display = "flex";
                }
            }

            function toggleAuthMode() {
                isAuthRegister = !isAuthRegister;
                document.getElementById("authHeading").innerText = isAuthRegister ? "Create Lemon Account" : "Welcome Back";
                document.getElementById("authSub").innerText = isAuthRegister ? "Create an account to save titled chats." : "Sign in to access your chat history.";
                document.getElementById("authSubmitBtn").innerText = isAuthRegister ? "Create Account" : "Sign In";
                document.getElementById("authToggleText").innerText = isAuthRegister ? "Already have an account? Sign In" : "Don't have an account? Create one";
            }

            async function handleAuthSubmit() {
                const u = document.getElementById("authUsername").value.trim();
                const p = document.getElementById("authPassword").value.trim();
                if (!u || !p) return alert("Please fill both username and password.");

                const endpoint = isAuthRegister ? "/api/register" : "/api/login";
                const fd = new FormData();
                fd.append("username", u);
                fd.append("password", p);

                try {
                    const res = await fetch(endpoint, { method: "POST", body: fd });
                    const data = await res.json();
                    if (data.status === "ok") {
                        currentUserId = data.user_id;
                        currentUsername = data.username;
                        localStorage.setItem("lemon_user_id", currentUserId);
                        localStorage.setItem("lemon_username", currentUsername);
                        authModal.style.display = "none";
                        checkAuth();
                    } else {
                        alert(data.message || "Authentication failed.");
                    }
                } catch(e) {
                    alert("Network error contacting Lemon server.");
                }
            }

            function logout() {
                localStorage.removeItem("lemon_user_id");
                localStorage.removeItem("lemon_username");
                currentUserId = null;
                currentUsername = null;
                currentSessionId = 0;
                chatStream.innerHTML = "";
                closeSidebar();
                checkAuth();
            }

            // Load Chat Sessions List with AI generated titles
            async function loadSessionsList() {
                if (!currentUserId) return;
                try {
                    const res = await fetch(`/api/sessions/${currentUserId}`);
                    const data = await res.json();
                    sessionsList.innerHTML = "";
                    if (data.sessions && data.sessions.length > 0) {
                        data.sessions.forEach(s => {
                            const item = document.createElement("div");
                            item.className = `session-item ${s.id === currentSessionId ? 'active' : ''}`;
                            item.innerHTML = `
                                <div class="session-title" onclick="openSession(${s.id})">💬 ${s.title}</div>
                                <span class="session-delete" onclick="deleteSession(event, ${s.id})" title="Delete">✕</span>
                            `;
                            sessionsList.appendChild(item);
                        });
                    } else {
                        sessionsList.innerHTML = `<div style="font-size:12px; color:#64748b; padding:10px;">No saved chats yet.</div>`;
                    }
                } catch(e) {
                    console.log("Sessions list error:", e);
                }
            }

            function startNewChat() {
                currentSessionId = 0;
                chatStream.innerHTML = "";
                chatStream.appendChild(heroGreeting);
                heroGreeting.style.display = "flex";
                closeSidebar();
                dockStatus.innerText = "● Ready for new chat";
            }

            async function openSession(id) {
                currentSessionId = id;
                closeSidebar();
                heroGreeting.style.display = "none";
                chatStream.innerHTML = "";

                try {
                    const res = await fetch(`/api/session-messages/${id}`);
                    const data = await res.json();
                    if (data.messages) {
                        data.messages.forEach(m => appendMessage(m.role === "assistant" ? "lemon" : "user", m.content, m.emotion));
                    }
                } catch(e) {
                    console.log("Error loading session:", e);
                }
            }

            async function deleteSession(e, id) {
                e.stopPropagation();
                if (!confirm("Delete this conversation?")) return;
                const fd = new FormData();
                fd.append("session_id", id);
                await fetch("/api/delete-session", { method: "POST", body: fd });
                if (currentSessionId === id) startNewChat();
                loadSessionsList();
            }

            function setThinking(active, label = "Thinking & analyzing...") {
                if (active) {
                    dockStatus.innerText = `⚡ ${label}`;
                    if (!currentThinkingEl) {
                        currentThinkingEl = document.createElement("div");
                        currentThinkingEl.className = "bubble-group lemon";
                        currentThinkingEl.innerHTML = `
                            <div class="thinking-box">
                                <div class="tdot"></div><div class="tdot"></div><div class="tdot"></div>
                                <span style="font-size:12px; color:#facc15; margin-left:4px;">Thinking...</span>
                            </div>
                        `;
                        chatStream.appendChild(currentThinkingEl);
                        chatStream.scrollTop = chatStream.scrollHeight;
                    }
                } else {
                    if (currentThinkingEl) {
                        currentThinkingEl.remove();
                        currentThinkingEl = null;
                    }
                    dockStatus.innerText = "● Ready";
                }
            }

            async function playSpecificMessage(text) {
                dockStatus.innerText = "🔊 Generating voice...";
                const fd = new FormData();
                fd.append("text", text);
                try {
                    const res = await fetch("/read-aloud", { method: "POST", body: fd });
                    const data = await res.json();
                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch(e) {
                    dockStatus.innerText = "Voice playback error.";
                }
            }

            function appendMessage(sender, text, emotion = null) {
                setThinking(false);
                if (heroGreeting) heroGreeting.style.display = "none";

                const group = document.createElement("div");
                group.className = `bubble-group ${sender}`;

                let html = "";
                if (sender === "lemon") {
                    const tag = emotion ? `<span class="feeling-tag">${emotion}</span><br>` : "";
                    const safeText = encodeURIComponent(text);
                    html = `
                        <div class="bubble-meta">
                            <span>Lemon</span>
                            <button class="play-audio-btn" onclick="playSpecificMessage(decodeURIComponent('${safeText}'))">▶ Listen</button>
                        </div>
                        <div class="bubble lemon">${tag}${text}</div>
                    `;
                } else {
                    html = `<div class="bubble user">${text}</div>`;
                }

                group.innerHTML = html;
                chatStream.appendChild(group);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            audioElement.onplay = () => { dockStatus.innerText = "🔊 Lemon is speaking..."; };
            audioElement.onended = () => { dockStatus.innerText = "● Ready"; };

            async function sendTextQuery() {
                const text = textInput.value.trim();
                if (!text || !currentUserId) return;

                textInput.value = "";
                appendMessage("user", text);
                setThinking(true, `Consulting ${activeCore.toUpperCase()} core...`);

                const fd = new FormData();
                fd.append("text", text);
                fd.append("user_id", currentUserId);
                fd.append("session_id", currentSessionId);
                fd.append("mode", activeCore);
                fd.append("voice_enabled", isVoiceEnabled);

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    currentSessionId = data.session_id; // Set session id if this was a new chat
                    appendMessage("lemon", data.reply_text, data.emotion);
                    if (isVoiceEnabled && data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch(e) {
                    setThinking(false);
                    dockStatus.innerText = "Error reaching Lemon server.";
                }
            }

            async function toggleVoice() {
                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
                        mediaRecorder.onstop = async () => {
                            const blob = new Blob(audioChunks, { type: 'audio/wav' });
                            setThinking(true, "Transcribing voice...");
                            uploadVoice(blob);
                            stream.getTracks().forEach(t => t.stop());
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        micBtn.classList.add("active-record");
                        dockStatus.innerText = "🔴 Listening... Tap mic again to send";
                    } catch(err) {
                        alert("Microphone permission required.");
                    }
                } else {
                    isRecording = false;
                    micBtn.classList.remove("active-record");
                    setThinking(true, "Analyzing speech...");
                    if (mediaRecorder) mediaRecorder.stop();
                }
            }

            async function uploadVoice(blob) {
                const fd = new FormData();
                fd.append("file", blob, "voice.wav");
                fd.append("user_id", currentUserId);
                fd.append("session_id", currentSessionId);
                fd.append("mode", activeCore);
                fd.append("voice_enabled", isVoiceEnabled);

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    const data = await res.json();
                    currentSessionId = data.session_id;
                    if (data.user_text) appendMessage("user", data.user_text);
                    appendMessage("lemon", data.reply_text, data.emotion);
                    if (isVoiceEnabled && data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch(e) {
                    setThinking(false);
                    dockStatus.innerText = "Error processing voice.";
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
