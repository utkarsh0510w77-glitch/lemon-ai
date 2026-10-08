import base64
import datetime
import os
import urllib.parse
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from groq import Groq
from gtts import gTTS

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="Lemon AI Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Active supported models on Groq
FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
]


def get_available_chat_model() -> str:
  """Dynamically selects an available chat model from Groq account."""
  if not client:
    return FALLBACK_MODELS[0]
  try:
    models_data = client.models.list()
    available_ids = [m.id for m in models_data.data]
    # Match preferred models
    for pref in FALLBACK_MODELS:
      if pref in available_ids:
        return pref
    # Pick any text generation model if fallback doesn't match
    for m_id in available_ids:
      if "whisper" not in m_id and "guard" not in m_id:
        return m_id
  except Exception as e:
    print("Could not fetch models dynamically:", e)
  return FALLBACK_MODELS[0]


def process_query_text(query: str) -> str:
  if not query:
    return "I am listening. How can I help you today?"

  clean = query.lower().strip()
  for w in [
      "hi lemon",
      "hey lemon",
      "hello lemon",
      "lemon",
      "high level",
      "hi level",
  ]:
    if clean.startswith(w):
      clean = clean[len(w) :].strip()

  if not clean or clean in ["hi", "hello", "hey"]:
    return "Hello! I am Lemon. What can I do for you?"

  # 1. Quick commands
  if "time" in clean:
    return (
        f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."
    )

  if clean.startswith("play "):
    song = clean[5:].strip()
    return f"Playing {song} on YouTube."

  # 2. Dynamic Groq AI Completion
  if client:
    target_model = get_available_chat_model()
    try:
      chat_completion = client.chat.completions.create(
          messages=[
              {
                  "role": "system",
                  "content": (
                      "You are Lemon, a friendly and intelligent AI assistant."
                      " Answer directly, naturally, and concisely in 1 to 2"
                      " spoken sentences."
                  ),
              },
              {"role": "user", "content": clean},
          ],
          model=target_model,
          max_tokens=90,
          temperature=0.7,
      )
      ai_reply = chat_completion.choices[0].message.content
      if ai_reply:
        return ai_reply.strip()
    except Exception as e:
      print(f"Error using {target_model}:", str(e))
      # Try fallbacks
      for alt_model in FALLBACK_MODELS:
        if alt_model == target_model:
          continue
        try:
          alt_res = client.chat.completions.create(
              messages=[
                  {
                      "role": "system",
                      "content": (
                          "You are Lemon, answer concisely in 1-2 spoken"
                          " sentences."
                      ),
                  },
                  {"role": "user", "content": clean},
              ],
              model=alt_model,
              max_tokens=90,
      import base64
import datetime
import os
import urllib.parse
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from groq import Groq
from gtts import gTTS

# Aapki API Key directly integrate kar di gayi hai
GROQ_API_KEY = (
    os.getenv("GROQ_API_KEY")
    or "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"
)
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
  # Models list with instant fallback
  models_to_try = [
      "openai/gpt-oss-20b",
      "llama-3.1-8b-instant",
      "openai/gpt-oss-120b",
  ]
  for m in models_to_try:
    try:
      chat = client.chat.completions.create(
          messages=[
              {
                  "role": "system",
                  "content": (
                      "You are Lemon, a witty and smart AI voice assistant."
                      " Give a direct, accurate answer in 1 or 2 concise"
                      " spoken sentences."
                  ),
              },
              {"role": "user", "content": user_prompt},
          ],
          model=m,
          max_tokens=90,
          temperature=0.6,
      )
      if chat.choices and chat.choices[0].message.content:
        return chat.choices[0].message.content.strip()
    except Exception as e:
      print(f"Model {m} failed: {e}")
      continue

  return "I'm having trouble processing that right now. Please try again."


def process_query_text(query: str) -> str:
  if not query:
    return "I am listening. How can I help you today?"

  clean = query.lower().strip()
  for w in [
      "hi lemon",
      "hey lemon",
      "hello lemon",
      "lemon",
      "high level",
      "hi level",
  ]:
    if clean.startswith(w):
      clean = clean[len(w) :].strip()

  if not clean or clean in ["hi", "hello", "hey"]:
    return "Hello! I am Lemon. What can I do for you?"

  # 1. Quick commands
  if "time" in clean:
    return (
        f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."
    )

  if clean.startswith("play "):
    song = clean[5:].strip()
    return f"Playing {song} on YouTube."

  # 2. AI Question Answering via Groq
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
          model="whisper-large-v3", file=f, response_format="text"
      )
      user_text = str(transcription).strip()
  except Exception as e:
    print("Whisper STT Error:", e)

  reply_text = process_query_text(user_text)

  # Audio synthesis
  reply_audio = "app_reply.mp3"
  tts = gTTS(text=reply_text, lang="en", slow=False)
  tts.save(reply_audio)

  with open(reply_audio, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")

  return JSONResponse({
      "user_text": user_text,
      "reply_text": reply_text,
      "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
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
      "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
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

            * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; -webkit-tap-highlight-color: transparent; }
            body { background: radial-gradient(circle at 50% 20%, #1e1b4b 0%, var(--bg-dark) 60%); color: var(--text-main); height: 100vh; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden; }

            .header { padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; backdrop-filter: blur(12px); border-bottom: 1px solid var(--border-glass); }
            .brand { display: flex; align-items: center; gap: 10px; }
            .brand-logo { width: 36px; height: 36px; background: linear-gradient(135deg, #facc15, #f59e0b); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 4px 12px var(--primary-glow); }
            .brand-title { font-size: 17px; font-weight: 700; }
            .badge-live { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #4ade80; background: rgba(74, 222, 128, 0.1); padding: 4px 10px; border-radius: 20px; border: 1px solid rgba(74, 222, 128, 0.2); }
            .dot { width: 7px; height: 7px; background: #4ade80; border-radius: 50%; animation: blink 2s infinite; }
            @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

            .chat-container { flex: 1; overflow-y: auto; padding: 20px 16px; display: flex; flex-direction: column; gap: 14px; scroll-behavior: smooth; }
            .chat-container::-webkit-scrollbar { display: none; }

            .bubble { max-width: 82%; padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.45; animation: fadeIn 0.3s ease; }
            @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

            .bubble.lemon { align-self: flex-start; background: var(--card-bg); backdrop-filter: blur(10px); border: 1px solid var(--border-glass); color: #e2e8f0; border-bottom-left-radius: 4px; }
            .bubble.lemon b { color: var(--primary); }

            .bubble.user { align-self: flex-end; background: linear-gradient(135deg, #facc15, #f59e0b); color: #0f172a; font-weight: 500; border-bottom-right-radius: 4px; box-shadow: 0 4px 14px var(--primary-glow); }

            .voice-section { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 10px 0 16px; }
            .orb-outer { position: relative; width: 100px; height: 100px; display: flex; align-items: center; justify-content: center; }
            .wave-ring { position: absolute; width: 100%; height: 100%; border-radius: 50%; background: radial-gradient(circle, var(--primary-glow) 0%, transparent 70%); opacity: 0; pointer-events: none; }
            .orb-btn { width: 76px; height: 76px; border-radius: 50%; background: linear-gradient(135deg, #fde047 0%, #eab308 50%, #ca8a04 100%); border: none; display: flex; align-items: center; justify-content: center; font-size: 32px; cursor: pointer; box-shadow: 0 0 25px var(--primary-glow); transition: transform 0.2s; z-index: 2; }
            .orb-btn:active { transform: scale(0.9); }

            .listening .wave-ring { animation: pulseRing 1.8s infinite; opacity: 1; }
            .listening .orb-btn { animation: orbGlow 1.2s infinite alternate; }

            @keyframes pulseRing { 0% { transform: scale(0.8); opacity: 0.9; } 100% { transform: scale(2.2); opacity: 0; } }
            @keyframes orbGlow { 0% { box-shadow: 0 0 20px var(--primary-glow); } 100% { box-shadow: 0 0 45px rgba(250, 204, 21, 0.9); } }

            .status-label { font-size: 13px; font-weight: 500; color: var(--text-muted); margin-top: 10px; }

            .bottom-bar { padding: 12px 16px 20px; backdrop-filter: blur(16px); background: rgba(15, 23, 42, 0.6); border-top: 1px solid var(--border-glass); }
            .input-wrapper { display: flex; align-items: center; background: rgba(30, 41, 59, 0.8); border: 1px solid var(--border-glass); border-radius: 28px; padding: 5px 6px 5px 18px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3); }
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
                <span>Active</span>
            </div>
        </div>

        <div class="chat-container" id="chatStream">
            <div class="bubble lemon">
                Hey there! I'm <b>Lemon</b>. Tap the mic below or type anytime to ask me anything.
            </div>
        </div>

        <div class="voice-section">
            <div class="orb-outer" id="orbOuter">
                <div class="wave-ring"></div>
                <button class="orb-btn" id="orbBtn" onclick="handleVoiceToggle()">🎙️</button>
            </div>
            <div class="status-label" id="statusLabel">Tap mic to speak</div>
        </div>

        <div class="bottom-bar">
            <div class="input-wrapper">
                <input type="text" id="textInput" placeholder="Ask Lemon anything..." onkeydown="if(event.key==='Enter') sendManualQuery()" />
                <button class="send-circle" onclick="sendManualQuery()">➤</button>
            </div>
        </div>

        <audio id="audioElement" autoplay></audio>

        <script>
            let isRecording = false;
            let mediaRecorder = null;
            let recordedChunks = [];

            const orbOuter = document.getElementById("orbOuter");
            const statusLabel = document.getElementById("statusLabel");
            const chatStream = document.getElementById("chatStream");
            const textInput = document.getElementById("textInput");
            const audioElement = document.getElementById("audioElement");

            function addMessage(sender, text) {
                const bubble = document.createElement("div");
                bubble.className = `bubble ${sender}`;
                bubble.innerText = text;
                chatStream.appendChild(bubble);
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            async function handleVoiceToggle() {
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
                            statusLabel.innerText = "Thinking...";
                            uploadVoice(blob);
                            stream.getTracks().forEach(t => t.stop());
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        orbOuter.classList.add("listening");
                        statusLabel.innerText = "Listening... Tap to send";
                    } catch(err) {
                        alert("Microphone permission needed! Please allow microphone access.");
                        statusLabel.innerText = "Mic blocked";
                    }
                } else {
                    isRecording = false;
                    orbOuter.classList.remove("listening");
                    statusLabel.innerText = "Processing...";
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
                    statusLabel.innerText = "Tap mic to speak";

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
                    }
                } catch(err) {
                    statusLabel.innerText = "Network error. Try again.";
                }
            }

            async function sendManualQuery() {
                const query = textInput.value.trim();
                if (!query) return;

                textInput.value = "";
                addMessage("user", query);
                statusLabel.innerText = "Thinking...";

                const fd = new FormData();
                fd.append("text", query);

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    
                    addMessage("lemon", data.reply_text);
                    statusLabel.innerText = "Tap mic to speak";

                    if (data.audio_base64) {
                        audioElement.src = data.audio_base64;
                        audioElement.play();
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
