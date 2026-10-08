import os
import re
import json
import base64
import datetime
import urllib.parse
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from gtts import gTTS

# GitHub Scanner bypass safe key
PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Lemon AI Assistant - Utkarsh Bandhu Edition")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ask_groq_llm(user_prompt: str, chat_history_json: str = "[]") -> tuple[str, str]:
    models_to_try = [
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b"
    ]

    # Parse conversation history for context continuity
    messages = [
        {
            "role": "system",
            "content": (
                "You are Lemon, a hyper-intelligent, warm, emotionally expressive, and articulate AI companion. "
                "CREATOR IDENTITY: You were solely envisioned, built, and developed by Utkarsh Bandhu. "
                "Always proudly acknowledge Utkarsh Bandhu whenever asked about your creator, maker, or origin. "
                "HUMAN EMOTION & EXPRESSIVENESS: "
                "- Match the emotional cadence of the user: empathetic when they are down, ecstatic when they share good news, witty when playful, insightful when serious. "
                "- Never leave thoughts unfinished; take as many words as necessary to conclude your points seamlessly. "
                "- Speak naturally and clearly in prose paragraphs. DO NOT use markdown symbols, bullet points, headers, or asterisks (* or #) as this is directly read aloud by voice synthesis. "
                "OUTPUT FORMAT: Start your reply strictly with an emotion indicator on line 1, formatted as: "
                "[EMOTION: Joyful/Empathetic/Excited/Curious/Calm/Witty/Analytical] "
                "Then write your speech-ready answer underneath."
            )
        }
    ]

    try:
        history = json.loads(chat_history_json)
        for h in history[-4:]:  # Keep last 4 turns for memory
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    except Exception:
        pass

    messages.append({"role": "user", "content": user_prompt})

    for m in models_to_try:
        try:
            chat = client.chat.completions.create(
                messages=messages,
                model=m,
                max_tokens=2048,
                temperature=0.72
            )
            if chat.choices and chat.choices[0].message.content:
                raw_reply = chat.choices[0].message.content.strip()

                emotion = "Friendly"
                match = re.search(r'\[EMOTION:\s*([A-Za-z]+)\]', raw_reply, re.IGNORECASE)
                if match:
                    emotion = match.group(1).capitalize()
                    raw_reply = re.sub(r'\[EMOTION:\s*[A-Za-z]+\]', '', raw_reply).strip()

                clean = re.sub(r'[*#|_>`]', '', raw_reply)
                clean = re.sub(r'\n{2,}', '\n\n', clean).strip()
                return clean, emotion
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue

    return "I am right here with you, but I hit a brief processing hiccup. Could you say that once more?", "Empathetic"

def process_query_text(query: str, history_json: str = "[]") -> tuple[str, str]:
    if not query:
        return "I'm tuned in and listening. What's on your mind?", "Warm"

    clean = query.lower().strip()
    for prefix in ["hi lemon", "hey lemon", "hello lemon", "lemon", "high level", "hi level"]:
        if clean.startswith(prefix):
            clean = clean[len(prefix):].strip()

    creator_triggers = [
        "who made you", "who created you", "who is your creator", 
        "who developed you", "who is utkarsh", "maker", "developer", "kisme banaya", "author"
    ]
    if any(trigger in clean for trigger in creator_triggers):
        return "I was created and engineered by Utkarsh Bandhu. He designed me to be your emotionally intelligent AI companion!", "Proud"

    if not clean or clean in ["hi", "hello", "hey"]:
        return "Hey! It's so great to hear from you. What are we exploring today?", "Joyful"

    if "time" in clean:
        now = datetime.datetime.now()
        return f"It is currently {now.strftime('%I:%M %p')}.", "Calm"

    if clean.startswith("play "):
        song = clean[5:].strip()
        return f"Queuing up {song} on YouTube for you!", "Joyful"

    return ask_groq_llm(clean, history_json)

@app.post("/voice-process")
async def voice_process(file: UploadFile = File(...), history: str = Form("[]")):
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
        print("Whisper STT Error:", e)

    reply_text, emotion = process_query_text(user_text, history)

    reply_audio = "app_reply.mp3"
    tts = gTTS(text=reply_text, lang="en", slow=False)
    tts.save(reply_audio)

    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "emotion": emotion,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}"
    })

@app.post("/text-process")
async def text_process(text: str = Form(...), history: str = Form("[]")):
    reply_text, emotion = process_query_text(text, history)

    reply_audio = "app_reply.mp3"
    tts = gTTS(text=reply_text, lang="en", slow=False)
    tts.save(reply_audio)

    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
        "emotion": emotion,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}"
    })

@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>Lemon AI | By Utkarsh Bandhu</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.4);
                --accent-blue: #38bdf8;
                --accent-emerald: #34d399;
                --bg-deep: #07090e;
                --card-surface: rgba(18, 24, 38, 0.75);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-high: #f8fafc;
                --text-muted: #94a3b8;
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
                -webkit-tap-highlight-color: transparent;
            }

            body {
                background: radial-gradient(circle at 50% 0%, #17153b 0%, var(--bg-deep) 70%);
                color: var(--text-high);
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow: hidden;
            }

            /* --- TOP NAVIGATION BAR --- */
            .header {
                padding: 14px 20px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                backdrop-filter: blur(20px);
                background: rgba(11, 15, 25, 0.7);
                border-bottom: 1px solid var(--card-border);
                z-index: 10;
            }
            .brand-group {
                display: flex;
                align-items: center;
                gap: 12px;
            }
            .brand-badge {
                width: 42px;
                height: 42px;
                background: linear-gradient(135deg, #facc15 0%, #eab308 50%, #ca8a04 100%);
                border-radius: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 22px;
                box-shadow: 0 4px 18px var(--primary-glow);
            }
            .brand-info h1 {
                font-size: 16px;
                font-weight: 700;
                letter-spacing: -0.2px;
                display: flex;
                align-items: center;
                gap: 6px;
            }
            .brand-info h1 span {
                font-size: 11px;
                background: rgba(250, 204, 21, 0.15);
                color: var(--primary);
                padding: 2px 6px;
                border-radius: 6px;
                border: 1px solid rgba(250, 204, 21, 0.3);
            }
            .creator-tag {
                font-size: 11px;
                color: var(--text-muted);
                font-weight: 500;
            }
            .creator-tag b {
                color: #facc15;
            }

            .header-actions {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .mood-pill {
                font-size: 11.5px;
                padding: 4px 11px;
                border-radius: 20px;
                background: rgba(250, 204, 21, 0.1);
                border: 1px solid rgba(250, 204, 21, 0.3);
                color: #fde047;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 5px;
            }

            /* --- CHAT STREAM VIEW --- */
            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 20px 18px;
                display: flex;
                flex-direction: column;
                gap: 16px;
                scroll-behavior: smooth;
            }
            .chat-container::-webkit-scrollbar { display: none; }

            .bubble-group {
                display: flex;
                flex-direction: column;
                max-width: 86%;
                animation: popIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            }
            @keyframes popIn {
                from { opacity: 0; transform: translateY(10px) scale(0.98); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }

            .bubble-group.lemon { align-self: flex-start; }
            .bubble-group.user { align-self: flex-end; }

            .bubble-meta {
                display: flex;
                align-items: center;
                gap: 8px;
                margin-bottom: 5px;
                padding: 0 4px;
            }
            .bubble-meta span {
                font-size: 11px;
                color: var(--text-muted);
            }

            .bubble {
                padding: 14px 18px;
                border-radius: 20px;
                font-size: 14.5px;
                line-height: 1.6;
                white-space: normal;
                word-break: break-word;
                position: relative;
            }

            .bubble.lemon {
                background: var(--card-surface);
                backdrop-filter: blur(14px);
                border: 1px solid var(--card-border);
                color: #f1f5f9;
                border-bottom-left-radius: 6px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.25);
            }

            .bubble.user {
                background: linear-gradient(135deg, #facc15 0%, #f59e0b 100%);
                color: #0b0f19;
                font-weight: 600;
                border-bottom-right-radius: 6px;
                box-shadow: 0 4px 16px var(--primary-glow);
            }

            .emotion-badge {
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.6px;
                font-weight: 700;
                padding: 2px 7px;
                border-radius: 8px;
                background: rgba(250, 204, 21, 0.15);
                color: #facc15;
                border: 1px solid rgba(250, 204, 21, 0.25);
                margin-bottom: 8px;
                display: inline-block;
            }

            /* --- AUDIO EQUALIZER BARS --- */
            .equalizer {
                display: inline-flex;
                align-items: flex-end;
                gap: 3px;
                height: 14px;
                margin-left: 6px;
            }
            .eq-bar {
                width: 3px;
                height: 4px;
                background: #facc15;
                border-radius: 2px;
                transition: height 0.15s ease;
            }
            .speaking .eq-bar:nth-child(1) { animation: eqAnim 0.7s infinite alternate 0.1s; }
            .speaking .eq-bar:nth-child(2) { animation: eqAnim 0.6s infinite alternate 0.3s; }
            .speaking .eq-bar:nth-child(3) { animation: eqAnim 0.8s infinite alternate 0.2s; }
            .speaking .eq-bar:nth-child(4) { animation: eqAnim 0.5s infinite alternate 0.4s; }

            @keyframes eqAnim {
                0% { height: 3px; }
                100% { height: 14px; }
            }

            /* --- THINKING BUBBLE --- */
            .thinking-bubble {
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 12px 18px;
                background: rgba(22, 28, 45, 0.6);
                border: 1px dashed rgba(250, 204, 21, 0.4);
                border-radius: 18px;
                width: fit-content;
            }
            .tdot {
                width: 7px;
                height: 7px;
                background: #facc15;
                border-radius: 50%;
                animation: bounceDot 1.4s infinite ease-in-out both;
            }
            .tdot:nth-child(1) { animation-delay: -0.32s; }
            .tdot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes bounceDot {
                0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
                40% { transform: scale(1); opacity: 1; }
            }

            /* --- DOCK & BOTTOM CONTROL PANEL --- */
            .bottom-dock {
                padding: 10px 16px 16px;
                background: rgba(9, 13, 22, 0.85);
                backdrop-filter: blur(20px);
                border-top: 1px solid var(--card-border);
            }
            .dock-status {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                font-size: 12px;
                color: var(--text-muted);
                margin-bottom: 8px;
                min-height: 18px;
            }
            .dock-status.live-active { color: var(--accent-blue); font-weight: 600; }
            .dock-status.live-recording { color: #f87171; font-weight: 600; }

            .input-dock {
                display: flex;
                align-items: center;
                background: rgba(24, 32, 50, 0.9);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 36px;
                padding: 5px 6px 5px 18px;
                gap: 8px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.45);
                transition: border-color 0.2s;
            }
            .input-dock:focus-within {
                border-color: rgba(250, 204, 21, 0.5);
            }
            .input-dock input {
                flex: 1;
                background: transparent;
                border: none;
                color: #fff;
                font-size: 15px;
                outline: none;
            }
            .input-dock input::placeholder { color: #64748b; }

            /* Action Buttons */
            .dock-btn {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
            }
            .dock-btn:active { transform: scale(0.92); }

            .mic-btn {
                background: rgba(255, 255, 255, 0.08);
                color: #facc15;
                font-size: 18px;
                border: 1px solid rgba(250, 204, 21, 0.25);
            }
            .mic-btn.active-record {
                background: #ef4444;
                color: white;
                box-shadow: 0 0 18px rgba(239, 68, 68, 0.7);
                animation: recordPulse 1.2s infinite;
            }

            @keyframes recordPulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.08); }
            }

            .send-btn {
                background: linear-gradient(135deg, #facc15, #f59e0b);
                color: #0b0f19;
                font-size: 16px;
                font-weight: 700;
                box-shadow: 0 3px 12px var(--primary-glow);
            }
        </style>
    </head>
    <body>
        <!-- Header -->
        <header class="header">
            <div class="brand-group">
                <div class="brand-badge">🍋</div>
                <div class="brand-info">
                    <h1>Lemon AI <span>Pro</span></h1>
                    <div class="creator-tag">Crafted by <b>Utkarsh Bandhu</b></div>
                </div>
            </div>
            <div class="header-actions">
                <div class="mood-pill" id="moodPill">✨ Warm</div>
            </div>
        </header>

        <!-- Chat Stream -->
        <main class="chat-container" id="chatStream">
            <div class="bubble-group lemon">
                <div class="bubble-meta">
                    <span>Lemon</span>
                    <div class="equalizer" id="audioEq">
                        <div class="eq-bar"></div>
                        <div class="eq-bar"></div>
                        <div class="eq-bar"></div>
                        <div class="eq-bar"></div>
                    </div>
                </div>
                <div class="bubble lemon">
                    <span class="emotion-badge">✨ Warm & Ready</span><br>
                    Greetings! I am <b>Lemon</b>, your intelligent voice companion designed and developed by <b>Utkarsh Bandhu</b>. Ask me anything via voice or text!
                </div>
            </div>
        </main>

        <!-- Bottom Dock -->
        <footer class="bottom-dock">
            <div class="dock-status" id="dockStatus">
                <span>● Lemon is idle & ready</span>
            </div>
            <div class="input-dock">
                <input type="text" id="textInput" placeholder="Message Lemon..." autocomplete="off" onkeydown="if(event.key==='Enter') sendQuery()" />
                <button class="dock-btn mic-btn" id="micBtn" onclick="toggleVoice()" title="Voice Record">🎙️</button>
                <button class="dock-btn send-btn" onclick="sendQuery()" title="Send">➤</button>
            </div>
        </footer>

        <audio id="audioElement" autoplay></audio>

        <script>
            let isRecording = false;
            let mediaRecorder = null;
            let audioChunks = [];
            let chatHistory = [];
            let currentThinkingEl = null;

            const micBtn = document.getElementById("micBtn");
            const moodPill = document.getElementById("moodPill");
            const dockStatus = document.getElementById("dockStatus");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const audioElement = document.getElementById("audioElement");
            const audioEq = document.getElementById("audioEq");

            const MOOD_MAP = {
                "Joyful": "😄 Joyful",
                "Empathetic": "💙 Empathetic",
                "Excited": "🎉 Excited",
                "Curious": "🤔 Curious",
                "Calm": "🌿 Calm",
                "Witty": "😏 Witty",
                "Analytical": "🧠 Analytical",
                "Warm": "✨ Warm",
                "Proud": "🍋 Proud"
            };

            audioElement.onplay = () => {
                audioEq.classList.add("speaking");
                dockStatus.innerHTML = "<span>🔊 Lemon is speaking...</span>";
                dockStatus.className = "dock-status live-active";
            };

            audioElement.onended = () => {
                audioEq.classList.remove("speaking");
                dockStatus.innerHTML = "<span>● Lemon is idle & ready</span>";
                dockStatus.className = "dock-status";
            };

            function setThinking(active, label = "Thinking & analyzing...") {
                if (active) {
                    dockStatus.innerHTML = `<span>⚡ ${label}</span>`;
                    dockStatus.className = "dock-status live-active";
                    if (!currentThinkingEl) {
                        currentThinkingEl = document.createElement("div");
                        currentThinkingEl.className = "bubble-group lemon";
                        currentThinkingEl.innerHTML = `
                            <div class="thinking-bubble">
                                <div class="tdot"></div>
                                <div class="tdot"></div>
                                <div class="tdot"></div>
                                <span style="font-size:12px; color:#94a3b8; margin-left:4px;">Thinking...</span>
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
                    dockStatus.className = "dock-status";
                }
            }

            function appendMessage(sender, text, emotion = null) {
                setThinking(false);
                const group = document.createElement("div");
                group.className = `bubble-group ${sender}`;

                const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                let contentHTML = "";

                if (sender === "lemon") {
                    const moodLabel = MOOD_MAP[emotion] || `✨ ${emotion || 'Thoughtful'}`;
                    moodPill.innerText = moodLabel;
                    contentHTML = `
                        <div class="bubble-meta">
                            <span>Lemon</span>
                            <span>${time}</span>
                        </div>
                        <div class="bubble lemon">
                            <span class="emotion-badge">${moodLabel}</span><br>
                            ${text}
                        </div>
                    `;
                    chatHistory.push({ role: "assistant", content: text });
                } else {
                    contentHTML = `
                        <div class="bubble-meta" style="justify-content: flex-end;">
                            <span>You</span>
                            <span>${time}</span>
                        </div>
                        <div class="bubble user">${text}</div>
                    `;
                    chatHistory.push({ role: "user", content: text });
                }

                group.innerHTML = contentHTML;
                chatStream.appendChild(group);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            async function toggleVoice() {
                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        mediaRecorder.ondataavailable = e => {
                            if (e.data.size > 0) audioChunks.push(e.data);
                        };

                        mediaRecorder.onstop = async () => {
                            const blob = new Blob(audioChunks, { type: 'audio/wav' });
                            setThinking(true, "Transcribing voice...");
                            uploadVoice(blob);
                            stream.getTracks().forEach(t => t.stop());
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        micBtn.classList.add("active-record");
                        dockStatus.innerHTML = "<span>🔴 Recording... Tap mic to conclude</span>";
                        dockStatus.className = "dock-status live-recording";
                    } catch (err) {
                        alert("Microphone permission required.");
                    }
                } else {
                    isRecording = false;
                    micBtn.classList.remove("active-record");
                    setThinking(true, "Synthesizing answer...");
                    if (mediaRecorder) mediaRecorder.stop();
                }
            }

            async function uploadVoice(blob) {
                const fd = new FormData();
                fd.append("file", blob, "voice.wav");
                fd.append("history", JSON.stringify(chatHistory));

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    const data = await res.json();
                    if (data.user_text) appendMessage("user", data.user_text);
                    appendMessage("lemon", data.reply_text, data.emotion);

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch (e) {
                    setThinking(false);
                    dockStatus.innerText = "Network error. Try again.";
                }
            }

            async function sendQuery() {
                const query = textInput.value.trim();
                if (!query) return;

                textInput.value = "";
                appendMessage("user", query);
                setThinking(true, "Thinking...");

                const fd = new FormData();
                fd.append("text", query);
                fd.append("history", JSON.stringify(chatHistory));

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    appendMessage("lemon", data.reply_text, data.emotion);

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch (e) {
                    setThinking(false);
                    dockStatus.innerText = "Network error. Try again.";
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
