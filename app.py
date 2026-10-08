import base64
import datetime
import os
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from groq import Groq
from gtts import gTTS
from pydantic import BaseModel

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


class QueryPayload(BaseModel):
  query: str


def clean_query(text: str) -> str:
  # Filter common misheard wake-words like 'high level', 'hi lemon', 'lemon'
  t = text.lower().strip()
  for w in [
      "hi lemon",
      "hey lemon",
      "hello lemon",
      "lemon",
      "high level",
      "hi level",
  ]:
    if t.startswith(w):
      t = t[len(w) :].strip()
  return t


def process_query_text(query: str) -> str:
  clean = clean_query(query)
  if not clean:
    return "Yes! I am Lemon. How can I help you?"

  # 1. Time query
  if "time" in clean:
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."

  # 2. YouTube play query
  if clean.startswith("play "):
    song = clean[5:].strip()
    return f"Playing {song} on YouTube."

  # 3. Groq LLM with safety fallback
  if client:
    for model_name in ["llama-3.1-8b-instant", "llama3-8b-8192"]:
      try:
        res = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Lemon, a witty and quick voice assistant."
                        " Answer in 1 short spoken sentence."
                    ),
                },
                {"role": "user", "content": clean},
            ],
            model=model_name,
            max_tokens=60,
            temperature=0.7,
        )
        return res.choices[0].message.content.strip()
      except Exception:
        continue

  return f"I heard: {clean}."


@app.post("/ask")
async def ask_lemon(payload: QueryPayload):
  reply_text = process_query_text(payload.query)
  return JSONResponse({"reply": reply_text})


@app.get("/", response_class=HTMLResponse)
async def serve_app():
  return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🍋 Lemon Voice AI</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background: #0b1120; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; text-align: center; padding: 16px; }
            .card { max-width: 450px; width: 100%; background: #1e293b; border-radius: 20px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #334155; }
            h1 { font-size: 26px; color: #facc15; margin-bottom: 6px; }
            p.sub { font-size: 13px; color: #94a3b8; margin-bottom: 20px; }
            
            .orb-box { width: 100px; height: 100px; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; }
            .orb { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #facc15, #f59e0b); display: flex; align-items: center; justify-content: center; font-size: 34px; cursor: pointer; transition: transform 0.2s; box-shadow: 0 0 20px rgba(250, 204, 21, 0.4); }
            .listening .orb { animation: pulse 1.4s infinite; box-shadow: 0 0 35px rgba(250, 204, 21, 0.9); }
            
            @keyframes pulse {
                0% { transform: scale(0.95); }
                50% { transform: scale(1.08); }
                100% { transform: scale(0.95); }
            }
            
            .status { font-size: 14px; font-weight: 600; color: #38bdf8; margin-bottom: 14px; min-height: 20px; }
            
            .display-box { background: #0f172a; border-radius: 12px; padding: 14px; min-height: 85px; text-align: left; font-size: 14px; border: 1px solid #334155; margin-bottom: 14px; }
            .user-line { color: #94a3b8; margin-bottom: 6px; }
            .lemon-line { color: #facc15; font-weight: 500; }
            
            .input-box { display: flex; gap: 8px; }
            .input-box input { flex: 1; padding: 12px; border-radius: 10px; border: 1px solid #334155; background: #0f172a; color: white; outline: none; font-size: 14px; }
            .input-box input:focus { border-color: #facc15; }
            .input-box button { padding: 0 16px; border: none; border-radius: 10px; background: #facc15; color: #0b1120; font-weight: bold; cursor: pointer; }
            .hint { font-size: 11px; color: #64748b; margin-top: 14px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🍋 Lemon AI</h1>
            <p class="sub">Hands-Free Built-in Voice Assistant</p>

            <div class="orb-box" id="orbBox">
                <div class="orb" onclick="toggleMic()">🎙️</div>
            </div>

            <div class="status" id="statusText">Tap mic once to enable voice</div>

            <div class="display-box">
                <div class="user-line" id="userMsg">Say "Hi Lemon" or type below...</div>
                <div class="lemon-line" id="lemonMsg"></div>
            </div>

            <div class="input-box">
                <input type="text" id="textInput" placeholder="Type query and press Enter..." onkeydown="handleKey(event)" />
                <button onclick="submitText()">Send</button>
            </div>

            <div class="hint">Tap 🎙️ once. Then simply say: <i>"Hi Lemon, what is the time?"</i></div>
        </div>

        <script>
            let recognition = null;
            let active = false;
            let speaking = false;

            const statusText = document.getElementById("statusText");
            const userMsg = document.getElementById("userMsg");
            const lemonMsg = document.getElementById("lemonMsg");
            const orbBox = document.getElementById("orbBox");
            const textInput = document.getElementById("textInput");

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            function speakOut(text, callback) {
                if (!window.speechSynthesis) {
                    if (callback) callback();
                    return;
                }
                window.speechSynthesis.cancel();
                const utter = new SpeechSynthesisUtterance(text);
                utter.rate = 1.0;
                utter.pitch = 1.0;
                utter.onend = () => {
                    speaking = false;
                    if (callback) callback();
                };
                utter.onerror = () => {
                    speaking = false;
                    if (callback) callback();
                };
                speaking = true;
                window.speechSynthesis.speak(utter);
            }

            function setupSpeech() {
                if (!SpeechRecognition) {
                    statusText.innerText = "Speech Recognition not supported on this browser";
                    return null;
                }
                const rec = new SpeechRecognition();
                rec.continuous = true;
                rec.interimResults = false;
                rec.lang = 'en-US';

                rec.onresult = async function(event) {
                    if (speaking) return;

                    const spoken = event.results[event.results.length - 1][0].transcript.trim();
                    userMsg.innerText = `You: "${spoken}"`;

                    const low = spoken.toLowerCase();
                    // Catch flexible triggers so accent never fails
                    if (low.includes("lemon") || low.includes("level") || low.includes("hi") || low.includes("hey")) {
                        statusText.innerText = "⚡ Thinking...";
                        await sendCommand(spoken);
                    }
                };

                rec.onerror = function(err) {
                    console.log("Rec Error:", err);
                };

                rec.onend = function() {
                    if (active && !speaking) {
                        try { rec.start(); } catch(e) {}
                    }
                };
                return rec;
            }

            function toggleMic() {
                if (!recognition) recognition = setupSpeech();
                if (!recognition) return;

                if (!active) {
                    active = true;
                    try { recognition.start(); } catch(e) {}
                    orbBox.classList.add("listening");
                    statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                    speakOut("Lemon is ready.", () => {});
                } else {
                    active = false;
                    try { recognition.stop(); } catch(e) {}
                    orbBox.classList.remove("listening");
                    statusText.innerText = "Mic stopped. Tap to resume.";
                }
            }

            async function sendCommand(query) {
                try {
                    const res = await fetch("/ask", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ query: query })
                    });
                    const data = await res.json();
                    lemonMsg.innerText = `Lemon: ${data.reply}`;

                    speakOut(data.reply, () => {
                        if (active) {
                            statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                            try { recognition.start(); } catch(e) {}
                        }
                    });
                } catch(e) {
                    lemonMsg.innerText = "Lemon: Could not connect to server.";
                    statusText.innerText = active ? "🟢 Listening for 'Hi Lemon'..." : "Ready";
                }
            }

            function submitText() {
                const val = textInput.value.trim();
                if (!val) return;
                userMsg.innerText = `You typed: "${val}"`;
                textInput.value = "";
                statusText.innerText = "⚡ Thinking...";
                sendCommand(val);
            }

            function handleKey(e) {
                if (e.key === "Enter") submitText();
            }
        </script>
    </body>
    </html>
  """


if __name__ == "__main__":
  import uvicorn

  port = int(os.environ.get("PORT", 10000))
  uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
