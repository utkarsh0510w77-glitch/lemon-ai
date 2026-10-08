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


def process_query_text(query: str) -> str:
  if not query:
    return "I didn't catch that. Could you please repeat?"

  q_lower = query.lower().strip()

  # Clean wake words
  for wake in ["hi lemon", "hey lemon", "hello lemon", "lemon"]:
    if q_lower.startswith(wake):
      q_lower = q_lower[len(wake) :].strip()

  if not q_lower:
    return "Yes, I am listening. How can I help you?"

  # 1. Time query
  if "time" in q_lower:
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."

  # 2. Play song command
  if q_lower.startswith("play "):
    song = q_lower[5:].strip()
    return f"Playing {song} on YouTube."

  # 3. Groq LLM (llama-3.1-8b-instant)
  if client:
    try:
      res = client.chat.completions.create(
          messages=[
              {
                  "role": "system",
                  "content": (
                      "You are Lemon, a friendly and ultra-fast voice"
                      " assistant. Always respond in only 1 or 2 concise,"
                      " spoken-style sentences."
                  ),
              },
              {"role": "user", "content": q_lower},
          ],
          model="llama-3.1-8b-instant",
          max_tokens=70,
          temperature=0.6,
      )
      return res.choices[0].message.content.strip()
    except Exception as e:
      return f"Sorry, could not process: {str(e)}"

  return f"You said: {q_lower}"


@app.post("/ask")
async def ask_lemon(payload: QueryPayload):
  reply_text = process_query_text(payload.query)

  # Generate Voice MP3
  temp_file = "lemon_voice.mp3"
  tts = gTTS(text=reply_text, lang="en", slow=False)
  tts.save(temp_file)

  with open(temp_file, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")

  return JSONResponse({
      "reply": reply_text,
      "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
  })


@app.get("/", response_class=HTMLResponse)
async def serve_app():
  return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🍋 Lemon AI Assistant</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background: #0b1120; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; text-align: center; padding: 16px; }
            .card { max-width: 460px; width: 100%; background: #1e293b; border-radius: 20px; padding: 24px; box-shadow: 0 12px 32px rgba(0,0,0,0.4); border: 1px solid #334155; }
            h1 { font-size: 26px; color: #facc15; margin-bottom: 4px; }
            p.sub { font-size: 13px; color: #94a3b8; margin-bottom: 20px; }
            
            .orb-wrapper { width: 100px; height: 100px; margin: 0 auto 16px; display: flex; align-items: center; justify-content: center; position: relative; }
            .orb { width: 80px; height: 80px; border-radius: 50%; background: linear-gradient(135deg, #facc15, #f59e0b); display: flex; align-items: center; justify-content: center; font-size: 34px; cursor: pointer; transition: transform 0.2s; box-shadow: 0 0 20px rgba(250, 204, 21, 0.4); }
            .listening .orb { animation: pulse 1.4s infinite; box-shadow: 0 0 35px rgba(250, 204, 21, 0.8); }
            
            @keyframes pulse {
                0% { transform: scale(0.95); }
                50% { transform: scale(1.08); }
                100% { transform: scale(0.95); }
            }
            
            .status { font-size: 14px; font-weight: 600; color: #38bdf8; margin-bottom: 16px; min-height: 20px; }
            
            .chat-box { background: #0f172a; border-radius: 12px; padding: 14px; min-height: 90px; text-align: left; font-size: 14px; border: 1px solid #334155; margin-bottom: 16px; }
            .user-msg { color: #94a3b8; margin-bottom: 8px; }
            .lemon-msg { color: #facc15; font-weight: 500; }
            
            .input-row { display: flex; gap: 8px; }
            .input-row input { flex: 1; padding: 12px; border-radius: 10px; border: 1px solid #334155; background: #0f172a; color: white; outline: none; font-size: 14px; }
            .input-row input:focus { border-color: #facc15; }
            .input-row button { padding: 0 16px; border: none; border-radius: 10px; background: #facc15; color: #0b1120; font-weight: bold; cursor: pointer; }
            .input-row button:hover { background: #eab308; }
            
            .hint { font-size: 11px; color: #64748b; margin-top: 14px; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>🍋 Lemon AI</h1>
            <p class="sub">Speak ("Hi Lemon") or Type below</p>

            <div class="orb-wrapper" id="orbWrapper">
                <div class="orb" onclick="toggleVoice()">🎙️</div>
            </div>

            <div class="status" id="statusText">Tap mic icon once to activate speech</div>

            <div class="chat-box">
                <div class="user-msg" id="userMsg">Say "Hi Lemon" or type a command...</div>
                <div class="lemon-msg" id="lemonMsg"></div>
            </div>

            <div class="input-row">
                <input type="text" id="textInput" placeholder="Type here..." onkeydown="onEnter(event)" />
                <button onclick="handleSendText()">Send</button>
            </div>

            <div class="hint">Tap 🎙️ once. Then simply say: <i>"Hi Lemon, what is the time?"</i></div>
        </div>

        <audio id="player" autoplay></audio>

        <script>
            let recognition = null;
            let active = false;
            let isSpeakingResponse = false;

            const statusText = document.getElementById("statusText");
            const userMsg = document.getElementById("userMsg");
            const lemonMsg = document.getElementById("lemonMsg");
            const orbWrapper = document.getElementById("orbWrapper");
            const player = document.getElementById("player");
            const textInput = document.getElementById("textInput");

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            function setupSpeech() {
                if (!SpeechRecognition) {
                    statusText.innerText = "Speech API not available on this browser. Use typing.";
                    return null;
                }
                const rec = new SpeechRecognition();
                rec.continuous = true;
                rec.interimResults = false;
                rec.lang = 'en-US';

                rec.onresult = async function(event) {
                    if (isSpeakingResponse) return;

                    const text = event.results[event.results.length - 1][0].transcript.trim();
                    userMsg.innerText = `You: "${text}"`;

                    const lower = text.toLowerCase();
                    if (lower.includes("lemon") || lower.includes("hi lemon") || lower.includes("hey lemon")) {
                        statusText.innerText = "⚡ Thinking...";
                        await sendQuery(text);
                    }
                };

                rec.onerror = function(e) {
                    console.log("Rec error:", e.error);
                };

                rec.onend = function() {
                    if (active && !isSpeakingResponse) {
                        try { rec.start(); } catch(err) {}
                    }
                };
                return rec;
            }

            function toggleVoice() {
                if (!recognition) recognition = setupSpeech();
                if (!recognition) return;

                if (!active) {
                    active = true;
                    try { recognition.start(); } catch(e) {}
                    orbWrapper.classList.add("listening");
                    statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                    player.play().catch(() => {});
                } else {
                    active = false;
                    try { recognition.stop(); } catch(e) {}
                    orbWrapper.classList.remove("listening");
                    statusText.innerText = "Mic paused. Tap to resume.";
                }
            }

            async function sendQuery(queryStr) {
                try {
                    const res = await fetch("/ask", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ query: queryStr })
                    });
                    const data = await res.json();
                    lemonMsg.innerText = `Lemon: ${data.reply}`;

                    if (data.audio_base64) {
                        isSpeakingResponse = true;
                        player.src = data.audio_base64;
                        player.onended = () => {
                            isSpeakingResponse = false;
                            if (active) {
                                statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                                try { recognition.start(); } catch(e) {}
                            }
                        };
                        await player.play().catch(() => { isSpeakingResponse = false; });
                    } else {
                        statusText.innerText = active ? "🟢 Listening for 'Hi Lemon'..." : "Ready";
                    }
                } catch(err) {
                    statusText.innerText = "Error contacting Lemon server.";
                    isSpeakingResponse = false;
                }
            }

            function handleSendText() {
                const val = textInput.value.trim();
                if (!val) return;
                userMsg.innerText = `You: "${val}"`;
                textInput.value = "";
                statusText.innerText = "⚡ Thinking...";
                sendQuery(val);
            }

            function onEnter(e) {
                if (e.key === "Enter") handleSendText();
            }
        </script>
    </body>
    </html>
  """


if __name__ == "__main__":
  import uvicorn

  port = int(os.environ.get("PORT", 10000))
  uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
