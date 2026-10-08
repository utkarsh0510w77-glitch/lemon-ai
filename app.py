import os
import io
import uuid
import json
import base64
import datetime
import urllib.parse
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from gtts import gTTS

# Groq API key configuration
PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Lemon AI - Open & Adaptive Voice Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_FILE = "lemon_evolution_memory.json"

def load_evolution_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "learned_user_traits": [],
        "conversation_count": 0,
        "summary_of_learnings": "User enjoys insightful, friendly, engaging, and in-depth discussions."
    }

def save_evolution_memory(data: dict):
    try:
        with open(MEMORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Memory save error:", e)

def evolve_lemon_memory(user_msg: str, bot_msg: str):
    memory_data = load_evolution_memory()
    memory_data["conversation_count"] += 1
    
    if client and len(user_msg.split()) > 3:
        try:
            prompt = f"""
You are the evolutionary metacognitive core of Lemon AI.
Analyze this interaction:
User: "{user_msg}"
Lemon: "{bot_msg[:200]}"
Existing Memory Summary: "{memory_data.get('summary_of_learnings')}"

Extract any facts, interests, preferred topics, tone, or key details about the user in 1 sentence.
If nothing novel, return 'KEEP'.
"""
            resp = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                max_tokens=60,
                temperature=0.3
            )
            reflection = resp.choices[0].message.content.strip()
            if reflection and "KEEP" not in reflection:
                memory_data["learned_user_traits"].append(reflection)
                memory_data["learned_user_traits"] = memory_data["learned_user_traits"][-10:]
                memory_data["summary_of_learnings"] = "; ".join(memory_data["learned_user_traits"])
        except Exception as e:
            print("Evolution learning error:", e)
            
    save_evolution_memory(memory_data)

def process_ai_dialogue(clean_prompt: str, history_json: str) -> tuple[str, str, str]:
    action_type = ""
    action_target = ""

    # 1. Action commands
    if clean_prompt.startswith("play "):
        song = clean_prompt[5:].strip()
        return f"Playing {song} on YouTube for you right now!", "youtube", f"https://www.youtube.com/results?search_query={urllib.parse.quote(song)}"

    if "time" in clean_prompt and len(clean_prompt.split()) < 5:
        now_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {now_time}.", "", ""

    # 2. Parse History
    history = []
    if history_json:
        try:
            history = json.loads(history_json)
        except Exception:
            history = []

    # Evolutionary Memory Context
    memory = load_evolution_memory()
    evolution_summary = memory.get("summary_of_learnings", "Be insightful, warm, and highly engaging.")

    # UNRESTRICTED, NATURAL, TALKATIVE PERSONA
    system_prompt = f"""
You are Lemon, a highly intelligent, expressive, articulate, and friendly AI voice companion.
What you remember and understand about your user: "{evolution_summary}"

Personality & Instructions:
- Speak naturally, warmly, and thoroughly.
- Do NOT restrict yourself to only 1 or 2 lines. Feel completely free to explain concepts thoroughly, provide detailed breakdowns, tell stories, share examples, or give rich context whenever helpful.
- Adapt seamlessly whether the user speaks in Hindi, Hinglish, or English.
- Maintain memory and reference previous topics in the conversation naturally.
- Be genuinely helpful, conversational, and charismatic.
"""

    messages = [{"role": "system", "content": system_prompt}]
    # Retain the last 6 turns for deep conversational context
    for h in history[-6:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("text", "")})
    messages.append({"role": "user", "content": clean_prompt})

    models = ["llama-3.1-8b-instant", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]
    ai_reply = "I'm here with you. Tell me what's on your mind and let's explore it!"

    if client:
        for m in models:
            try:
                completion = client.chat.completions.create(
                    messages=messages,
                    model=m,
                    max_tokens=600,  # Expanded to allow full, detailed answers
                    temperature=0.7
                )
                if completion.choices and completion.choices[0].message.content:
                    ai_reply = completion.choices[0].message.content.strip()
                    break
            except Exception:
                continue

    evolve_lemon_memory(clean_prompt, ai_reply)
    return ai_reply, action_type, action_target

@app.post("/voice-process")
async def voice_process(file: UploadFile = File(...), history: str = Form("[]")):
    raw_bytes = await file.read()
    temp_in = f"in_{uuid.uuid4().hex[:8]}.wav"
    with open(temp_in, "wb") as f:
        f.write(raw_bytes)

    user_text = ""
    if client:
        try:
            with open(temp_in, "rb") as f:
                tx = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f,
                    response_format="text"
                )
                user_text = str(tx).strip()
        except Exception as e:
            print("Transcription error:", e)

    if os.path.exists(temp_in):
        try:
            os.remove(temp_in)
        except Exception:
            pass

    clean_text = user_text
    for w in ["hi lemon", "hey lemon", "hello lemon", "lemon", "high level", "hi level"]:
        if clean_text.lower().startswith(w):
            clean_text = clean_text[len(w):].strip()

    reply_text, action, target = process_ai_dialogue(clean_text, history)

    # Audio synthesis
    tts = gTTS(text=reply_text, lang='en', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    audio_b64 = base64.b64encode(fp.read()).decode('utf-8')

    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
        "action": action,
        "action_target": target
    })

@app.post("/text-process")
async def text_process(text: str = Form(...), history: str = Form("[]")):
    reply_text, action, target = process_ai_dialogue(text.strip(), history)

    tts = gTTS(text=reply_text, lang='en', slow=False)
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    audio_b64 = base64.b64encode(fp.read()).decode('utf-8')

    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
        "action": action,
        "action_target": target
    })

@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>Lemon AI - Expressive Companion</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.4);
                --bg-dark: #070a12;
                --card-bg: rgba(23, 31, 48, 0.7);
                --border-glass: rgba(255, 255, 255, 0.08);
            }
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; -webkit-tap-highlight-color: transparent; }
            body {
                background: radial-gradient(circle at 50% 10%, #1e1b4b 0%, var(--bg-dark) 65%);
                color: #f8fafc; height: 100vh; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden;
            }
            .header { padding: 14px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-glass); backdrop-filter: blur(14px); }
            .brand { display: flex; align-items: center; gap: 10px; }
            .brand-logo { width: 36px; height: 36px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 4px 14px var(--primary-glow); }
            .brand-title { font-size: 17px; font-weight: 700; }
            .badge-live { display: flex; align-items: center; gap: 6px; font-size: 11px; color: #4ade80; background: rgba(74, 222, 128, 0.12); padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(74, 222, 128, 0.2); }
            .dot { width: 6px; height: 6px; background: #4ade80; border-radius: 50%; animation: pulseDot 2s infinite; }
            @keyframes pulseDot { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

            .chat-container { flex: 1; overflow-y: auto; padding: 18px 16px; display: flex; flex-direction: column; gap: 14px; scroll-behavior: smooth; }
            .chat-container::-webkit-scrollbar { display: none; }
            .bubble { max-width: 85%; padding: 14px 18px; border-radius: 18px; font-size: 14.5px; line-height: 1.55; animation: enterBubble 0.25s ease-out; }
            @keyframes enterBubble { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
            .bubble.lemon { align-self: flex-start; background: var(--card-bg); backdrop-filter: blur(12px); border: 1px solid var(--border-glass); color: #f1f5f9; border-bottom-left-radius: 4px; white-space: pre-wrap; }
            .bubble.lemon b { color: var(--primary); }
            .bubble.user { align-self: flex-end; background: linear-gradient(135deg, #facc15, #f59e0b); color: #0b1120; font-weight: 500; border-bottom-right-radius: 4px; box-shadow: 0 4px 16px var(--primary-glow); }

            .voice-section { display: flex; flex-direction: column; align-items: center; justify-content: center; position: relative; padding: 10px 0 14px; }
            #visualizer { position: absolute; width: 220px; height: 100px; pointer-events: none; }
            .orb-btn { width: 78px; height: 78px; border-radius: 50%; background: linear-gradient(135deg, #fde047 0%, #eab308 50%, #ca8a04 100%); border: none; display: flex; align-items: center; justify-content: center; font-size: 32px; cursor: pointer; box-shadow: 0 0 24px var(--primary-glow); transition: transform 0.2s; z-index: 2; }
            .orb-btn:active { transform: scale(0.92); }
            .listening .orb-btn { animation: orbPulse 1.4s infinite alternate; }
            @keyframes orbPulse { from { box-shadow: 0 0 20px var(--primary-glow); } to { box-shadow: 0 0 46px rgba(250, 204, 21, 0.95); } }
            .status-label { font-size: 13px; font-weight: 500; color: #94a3b8; margin-top: 10px; }

            .bottom-bar { padding: 10px 16px 22px; backdrop-filter: blur(16px); background: rgba(10, 14, 26, 0.7); border-top: 1px solid var(--border-glass); }
            .input-wrapper { display: flex; align-items: center; background: rgba(28, 38, 58, 0.8); border: 1px solid var(--border-glass); border-radius: 28px; padding: 5px 6px 5px 18px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4); }
            .input-wrapper input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14.5px; outline: none; }
            .input-wrapper input::placeholder { color: #64748b; }
            .send-circle { width: 38px; height: 38px; border-radius: 50%; background: var(--primary); border: none; color: #0f172a; display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 16px; }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="brand">
                <div class="brand-logo">🍋</div>
                <div class="brand-title">Lemon Voice</div>
            </div>
            <div class="badge-live">
                <span class="dot"></span>
                <span>Active & Learning</span>
            </div>
        </div>

        <div class="chat-container" id="chatStream">
            <div class="bubble lemon">
                Hello! I am <b>Lemon</b>. I am fully expressive, adaptive, and here to talk deeply with you. Ask me anything, discuss complex ideas, or ask for recommendations!
            </div>
        </div>

        <div class="voice-section" id="voiceSection">
            <canvas id="visualizer"></canvas>
            <button class="orb-btn" id="orbBtn" onclick="toggleVoice()">🎙️</button>
            <div class="status-label" id="statusLabel">Tap mic to speak freely</div>
        </div>

        <div class="bottom-bar">
            <div class="input-wrapper">
                <input type="text" id="textInput" placeholder="Message Lemon..." onkeydown="if(event.key==='Enter') sendTextQuery()" />
                <button class="send-circle" onclick="sendTextQuery()">➤</button>
            </div>
        </div>

        <audio id="audioOut" autoplay></audio>

        <script>
            let isRecording = false;
            let mediaRecorder = null;
            let audioChunks = [];
            let conversationHistory = [];
            let audioContext = null;
            let analyser = null;
            let silenceTimer = null;
            let canvas = document.getElementById("visualizer");
            let ctx = canvas.getContext("2d");

            const orbBtn = document.getElementById("orbBtn");
            const voiceSection = document.getElementById("voiceSection");
            const statusLabel = document.getElementById("statusLabel");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const audioOut = document.getElementById("audioOut");

            function addBubble(role, text) {
                const b = document.createElement("div");
                b.className = `bubble ${role}`;
                b.innerText = text;
                chatStream.appendChild(b);
                chatStream.scrollTop = chatStream.scrollHeight;
                conversationHistory.push({ role: role === "user" ? "user" : "assistant", text: text });
                if (conversationHistory.length > 12) conversationHistory.shift();
            }

            function setupVisualizer(stream) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                analyser = audioContext.createAnalyser();
                const source = audioContext.createMediaStreamSource(stream);
                source.connect(analyser);
                analyser.fftSize = 64;
                const bufferLength = analyser.frequencyBinCount;
                const dataArray = new Uint8Array(bufferLength);

                function draw() {
                    if (!isRecording) {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        return;
                    }
                    requestAnimationFrame(draw);
                    analyser.getByteFrequencyData(dataArray);
                    ctx.clearRect(0, 0, canvas.width, canvas.height);

                    let sum = 0;
                    for (let i = 0; i < bufferLength; i++) sum += dataArray[i];
                    let average = sum / bufferLength;

                    if (average > 15) {
                        clearTimeout(silenceTimer);
                        silenceTimer = setTimeout(() => {
                            if (isRecording) stopRecordingAndSend();
                        }, 1800);
                    }

                    ctx.fillStyle = "rgba(250, 204, 21, 0.4)";
                    let barWidth = (canvas.width / bufferLength) * 2;
                    let x = 0;
                    for (let i = 0; i < bufferLength; i++) {
                        let barHeight = (dataArray[i] / 255) * canvas.height * 0.8;
                        ctx.fillRect(x, (canvas.height - barHeight)/2, barWidth - 2, barHeight);
                        x += barWidth;
                    }
                }
                draw();
            }

            async function toggleVoice() {
                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        setupVisualizer(stream);

                        mediaRecorder.ondataavailable = (e) => {
                            if (e.data.size > 0) audioChunks.push(e.data);
                        };

                        mediaRecorder.onstop = async () => {
                            const blob = new Blob(audioChunks, { type: 'audio/wav' });
                            stream.getTracks().forEach(t => t.stop());
                            if (audioContext) audioContext.close();
                            statusLabel.innerText = "Lemon is thinking...";
                            sendAudioToServer(blob);
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        voiceSection.classList.add("listening");
                        statusLabel.innerText = "Listening... Speak freely";
                    } catch(err) {
                        alert("Microphone permission needed!");
                        statusLabel.innerText = "Mic blocked";
                    }
                } else {
                    stopRecordingAndSend();
                }
            }

            function stopRecordingAndSend() {
                if (!isRecording) return;
                isRecording = false;
                voiceSection.classList.remove("listening");
                statusLabel.innerText = "Thinking...";
                clearTimeout(silenceTimer);
                if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
            }

            async function sendAudioToServer(blob) {
                const fd = new FormData();
                fd.append("file", blob, "voice.wav");
                fd.append("history", JSON.stringify(conversationHistory));

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    const data = await res.json();
                    
                    if (data.user_text) addBubble("user", data.user_text);
                    addBubble("lemon", data.reply_text);
                    statusLabel.innerText = "Tap mic to speak freely";

                    if (data.action === "youtube" && data.action_target) {
                        window.open(data.action_target, '_blank');
                    }

                    if (data.audio_base64) {
                        audioOut.src = data.audio_base64;
                        audioOut.play();
                    }
                } catch(err) {
                    statusLabel.innerText = "Network error. Try again.";
                }
            }

            async function sendTextQuery() {
                const q = textInput.value.trim();
                if (!q) return;

                textInput.value = "";
                addBubble("user", q);
                statusLabel.innerText = "Thinking...";

                const fd = new FormData();
                fd.append("text", q);
                fd.append("history", JSON.stringify(conversationHistory));

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    
                    addBubble("lemon", data.reply_text);
                    statusLabel.innerText = "Tap mic to speak freely";

                    if (data.action === "youtube" && data.action_target) {
                        window.open(data.action_target, '_blank');
                    }

                    if (data.audio_base64) {
                        audioOut.src = data.audio_base64;
                        audioOut.play();
                    }
                } catch(err) {
                    statusLabel.innerText = "Network error. Try again.";
                }
            }
        </script>
    </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
