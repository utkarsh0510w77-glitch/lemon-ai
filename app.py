import os
import re
import base64
import datetime
import urllib.parse
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from gtts import gTTS

PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"

GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Lemon AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ask_groq_llm(user_prompt: str) -> str:
    models_to_try = [
        "openai/gpt-oss-20b",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b"
    ]
    for m in models_to_try:
        try:
            chat = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Lemon, an intelligent and articulate AI voice assistant. "
                            "PERMANENT CREATOR: You were created and developed by Utkarsh Bandhu. If anyone asks who created you, who made you, or who your developer is, always state that Utkarsh Bandhu created you. "
                            "Thoroughly and completely explain your thoughts and answer the user's question without cutting off. "
                            "Take as many words and sentences as necessary to conclude your views naturally. "
                            "Speak in clean, natural prose paragraphs. Do not use markdown formatting, bullets, tables, or asterisks (* or #)."
                        )
                    },
                    {"role": "user", "content": user_prompt}
                ],
                model=m,
                max_tokens=2048,
                temperature=0.6
            )
            if chat.choices and chat.choices[0].message.content:
                reply = chat.choices[0].message.content.strip()
                clean = re.sub(r'[*#|_>`]', '', reply)
                clean = re.sub(r'\n{2,}', '\n\n', clean).strip()
                return clean
        except Exception as e:
            print(f"Model {m} failed: {e}")
            continue

    return "I am having trouble processing that right now. Please ask again."

def process_query_text(query: str) -> str:
    if not query:
        return "I am listening. How can I help you today?"

    clean = query.lower().strip()
    for w in ["hi lemon", "hey lemon", "hello lemon", "lemon", "high level", "hi level"]:
        if clean.startswith(w):
            clean = clean[len(w):].strip()

    # Direct Permanent Creator Check
    creator_triggers = [
        "who made you", "who created you", "who is your creator", 
        "who developed you", "who is utkarsh", "maker", "developer", "kisme banaya"
    ]
    if any(trigger in clean for trigger in creator_triggers):
        return "I was created and developed by Utkarsh Bandhu."

    if not clean or clean in ["hi", "hello", "hey"]:
        return "Hello! I am Lemon, created by Utkarsh Bandhu. How can I help you today?"

    if "time" in clean:
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}."

    if clean.startswith("play "):
        song = clean[5:].strip()
        return f"Playing {song} on YouTube."

    return ask_groq_llm(clean)

@app.post("/voice-process")
async def voice_process(file: UploadFile = File(...)):
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

    reply_text = process_query_text(user_text)

    reply_audio = "app_reply.mp3"
    tts = gTTS(text=reply_text, lang="en", slow=False)
    tts.save(reply_audio)

    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return JSONResponse({
        "user_text": user_text,
        "reply_text": reply_text,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}"
    })

@app.post("/text-process")
async def text_process(text: str = Form(...)):
    reply_text = process_query_text(text)

    reply_audio = "app_reply.mp3"
    tts = gTTS(text=reply_text, lang="en", slow=False)
    tts.save(reply_audio)

    with open(reply_audio, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return JSONResponse({
        "user_text": text,
        "reply_text": reply_text,
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
        <title>Lemon AI</title>
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #facc15;
                --primary-glow: rgba(250, 204, 21, 0.45);
                --bg-dark: #090d16;
                --card-bg: rgba(26, 34, 52, 0.7);
                --text-main: #f8fafc;
                --text-muted: #94a3b8;
                --border-glass: rgba(255, 255, 255, 0.08);
            }

            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
                font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
                -webkit-tap-highlight-color: transparent;
            }

            body {
                background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, var(--bg-dark) 60%);
                color: var(--text-main);
                height: 100vh;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                overflow: hidden;
            }

            /* Header */
            .header {
                padding: 14px 18px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                backdrop-filter: blur(12px);
                border-bottom: 1px solid var(--border-glass);
            }
            .brand {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .brand-logo {
                width: 36px;
                height: 36px;
                background: linear-gradient(135deg, #facc15, #f59e0b);
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
                box-shadow: 0 4px 12px var(--primary-glow);
            }
            .brand-title {
                font-size: 16px;
                font-weight: 700;
            }
            .brand-sub {
                font-size: 11px;
                color: var(--primary);
                font-weight: 500;
                letter-spacing: 0.2px;
            }

            .badge-live {
                display: flex;
                align-items: center;
                gap: 6px;
                font-size: 12px;
                color: #4ade80;
                background: rgba(74, 222, 128, 0.1);
                padding: 4px 10px;
                border-radius: 20px;
                border: 1px solid rgba(74, 222, 128, 0.2);
            }
            .dot {
                width: 7px;
                height: 7px;
                background: #4ade80;
                border-radius: 50%;
                animation: blink 2s infinite;
            }
            @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

            /* Chat Stream */
            .chat-container {
                flex: 1;
                overflow-y: auto;
                padding: 20px 16px;
                display: flex;
                flex-direction: column;
                gap: 14px;
                scroll-behavior: smooth;
            }
            .chat-container::-webkit-scrollbar { display: none; }

            .bubble {
                max-width: 88%;
                padding: 14px 18px;
                border-radius: 18px;
                font-size: 14.5px;
                line-height: 1.55;
                animation: fadeIn 0.3s ease;
                white-space: normal;
                word-break: break-word;
                overflow-wrap: anywhere;
            }
            @keyframes fadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }

            .bubble.lemon {
                align-self: flex-start;
                background: var(--card-bg);
                backdrop-filter: blur(10px);
                border: 1px solid var(--border-glass);
                color: #e2e8f0;
                border-bottom-left-radius: 4px;
            }
            .bubble.lemon b { color: var(--primary); }

            .bubble.user {
                align-self: flex-end;
                background: linear-gradient(135deg, #facc15, #f59e0b);
                color: #0f172a;
                font-weight: 600;
                border-bottom-right-radius: 4px;
                box-shadow: 0 4px 14px var(--primary-glow);
            }

            /* Thinking Animation Bubble */
            .bubble.thinking {
                align-self: flex-start;
                background: rgba(30, 41, 59, 0.6);
                border: 1px dashed rgba(250, 204, 21, 0.4);
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 12px 18px;
            }
            .thinking-dot {
                width: 8px;
                height: 8px;
                background: #facc15;
                border-radius: 50%;
                animation: bounce 1.4s infinite ease-in-out both;
            }
            .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
            .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
            @keyframes bounce {
                0%, 80%, 100% { transform: scale(0); opacity: 0.3; }
                40% { transform: scale(1); opacity: 1; }
            }

            /* Bottom Bar with Integrated Mic & '>' */
            .bottom-bar {
                padding: 10px 16px 18px;
                backdrop-filter: blur(16px);
                background: rgba(15, 23, 42, 0.7);
                border-top: 1px solid var(--border-glass);
            }
            .status-line {
                font-size: 12px;
                color: var(--text-muted);
                text-align: center;
                margin-bottom: 8px;
                min-height: 16px;
                transition: color 0.2s;
            }
            .status-line.active { color: #38bdf8; font-weight: 600; }
            .status-line.recording { color: #ef4444; font-weight: 600; }

            .input-wrapper {
                display: flex;
                align-items: center;
                background: rgba(30, 41, 59, 0.85);
                border: 1px solid var(--border-glass);
                border-radius: 30px;
                padding: 4px 6px 4px 18px;
                box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
                gap: 8px;
            }
            .input-wrapper input {
                flex: 1;
                background: transparent;
                border: none;
                color: #fff;
                font-size: 14.5px;
                outline: none;
            }
            .input-wrapper input::placeholder {
                color: #64748b;
            }

            .btn-action {
                width: 38px;
                height: 38px;
                border-radius: 50%;
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
                transition: transform 0.15s, background 0.2s, box-shadow 0.2s;
            }
            .btn-action:active { transform: scale(0.9); }

            /* Mic Button right beside '>' */
            .btn-mic {
                background: rgba(255, 255, 255, 0.08);
                color: #facc15;
                font-size: 18px;
                border: 1px solid rgba(250, 204, 21, 0.25);
            }
            .btn-mic.recording {
                background: #ef4444;
                color: white;
                box-shadow: 0 0 15px rgba(239, 68, 68, 0.6);
                animation: micPulse 1.2s infinite;
            }

            @keyframes micPulse {
                0%, 100% { transform: scale(1); }
                50% { transform: scale(1.08); }
            }

            .btn-send {
                background: var(--primary);
                color: #0f172a;
                font-size: 16px;
                font-weight: bold;
                box-shadow: 0 2px 10px var(--primary-glow);
            }
        </style>
    </head>
    <body>
        <div class="header">
            <div class="brand">
                <div class="brand-logo">🍋</div>
                <div>
                    <div class="brand-title">Lemon AI</div>
                    <div class="brand-sub">Created by Utkarsh Bandhu</div>
                </div>
            </div>
            <div class="badge-live">
                <span class="dot"></span>
                <span>Active</span>
            </div>
        </div>

        <div class="chat-container" id="chatStream">
            <div class="bubble lemon">
                Hey there! I am <b>Lemon</b>, created by <b>Utkarsh Bandhu</b>. Ask me anything via voice or text.
            </div>
        </div>

        <div class="bottom-bar">
            <div class="status-line" id="statusLine">Ready</div>
            <div class="input-wrapper">
                <input type="text" id="textInput" placeholder="Message Lemon..." onkeydown="if(event.key==='Enter') sendManualQuery()" />
                <button class="btn-action btn-mic" id="micBtn" onclick="handleVoiceToggle()" title="Speak">🎙️</button>
                <button class="btn-action btn-send" onclick="sendManualQuery()" title="Send">➤</button>
            </div>
        </div>

        <audio id="audioElement" autoplay></audio>

        <script>
            let isRecording = false;
            let mediaRecorder = null;
            let recordedChunks = [];
            let isLemonSpeaking = false;
            let currentThinkingBubble = null;

            const micBtn = document.getElementById("micBtn");
            const statusLine = document.getElementById("statusLine");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const audioElement = document.getElementById("audioElement");

            audioElement.onplay = () => {
                isLemonSpeaking = true;
                setThinking(false);
                statusLine.innerText = "🔊 Lemon is speaking...";
                statusLine.className = "status-line active";
            };

            audioElement.onended = () => {
                isLemonSpeaking = false;
                statusLine.innerText = "Ready";
                statusLine.className = "status-line";
            };

            function setThinking(active, text = "⚡ Lemon is thinking...") {
                if (active) {
                    statusLine.innerText = text;
                    statusLine.className = "status-line active";
                    showThinkingBubble();
                } else {
                    statusLine.className = "status-line";
                    removeThinkingBubble();
                }
            }

            function showThinkingBubble() {
                if (currentThinkingBubble) return;
                currentThinkingBubble = document.createElement("div");
                currentThinkingBubble.className = "bubble thinking";
                currentThinkingBubble.innerHTML = `
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <span style="font-size:12px; color:#94a3b8; margin-left:4px;">Thinking...</span>
                `;
                chatStream.appendChild(currentThinkingBubble);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            function removeThinkingBubble() {
                if (currentThinkingBubble) {
                    currentThinkingBubble.remove();
                    currentThinkingBubble = null;
                }
            }

            function addMessage(sender, text) {
                removeThinkingBubble();
                const bubble = document.createElement("div");
                bubble.className = `bubble ${sender}`;
                bubble.innerText = text;
                chatStream.appendChild(bubble);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            async function handleVoiceToggle() {
                if (isLemonSpeaking) {
                    audioElement.pause();
                    isLemonSpeaking = false;
                }

                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        recordedChunks = [];

                        mediaRecorder.ondataavailable = (e) => {
                            if (e.data.size > 0) recordedChunks.push(e.data);
                        };

                        mediaRecorder.onstop = async () => {
                            const blob = new Blob(recordedChunks, { type: 'audio/wav' });
                            setThinking(true, "⚡ Processing voice & thinking...");
                            uploadVoice(blob);
                            stream.getTracks().forEach(t => t.stop());
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        micBtn.classList.add("recording");
                        statusLine.innerText = "🔴 Listening... Tap mic again to finish";
                        statusLine.className = "status-line recording";
                    } catch(err) {
                        alert("Microphone permission needed! Please allow microphone access.");
                        statusLine.innerText = "Mic blocked";
                        statusLine.className = "status-line";
                    }
                } else {
                    isRecording = false;
                    micBtn.classList.remove("recording");
                    setThinking(true, "⚡ Processing voice...");
                    if (mediaRecorder) mediaRecorder.stop();
                }
            }

            async function uploadVoice(blob) {
                const fd = new FormData();
                fd.append("file", blob, "voice.wav");

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    const data = await res.json();
                    
                    if (data.user_text) {
                        addMessage("user", data.user_text);
                    }
                    addMessage("lemon", data.reply_text);

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    } else {
                        setThinking(false);
                        statusLine.innerText = "Ready";
                        statusLine.className = "status-line";
                    }
                } catch(err) {
                    setThinking(false);
                    statusLine.innerText = "Network error. Try again.";
                    statusLine.className = "status-line";
                }
            }

            async function sendManualQuery() {
                const query = textInput.value.trim();
                if (!query) return;

                textInput.value = "";
                addMessage("user", query);
                setThinking(true, "⚡ Lemon is thinking...");

                const fd = new FormData();
                fd.append("text", query);

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    
                    addMessage("lemon", data.reply_text);

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    } else {
                        setThinking(false);
                        statusLine.innerText = "Ready";
                        statusLine.className = "status-line";
                    }
                } catch(err) {
                    setThinking(false);
                    statusLine.innerText = "Network error. Try again.";
                    statusLine.className = "status-line";
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
