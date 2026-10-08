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

  # Remove wake words if present
  for wake in ["hi lemon", "hey lemon", "lemon"]:
    if q_lower.startswith(wake):
      q_lower = q_lower[len(wake) :].strip()

  if not q_lower:
    return "Yes? I'm listening!"

  # 1. Time query
  if "time" in q_lower:
    now = datetime.datetime.now()
    return f"The current time is {now.strftime('%I:%M %p')}."

  # 2. YouTube play query
  if q_lower.startswith("play "):
    song = q_lower[5:].strip()
    return f"Playing {song} on YouTube."

  # 3. Groq LLM (Updated to active working model)
  if client:
    try:
      res = client.chat.completions.create(
          messages=[
              {
                  "role": "system",
                  "content": (
                      "You are Lemon, a friendly and smart voice assistant."
                      " Answer directly in 1 to 2 spoken sentences."
                  ),
              },
              {"role": "user", "content": q_lower},
          ],
          model="llama-3.1-8b-instant",
          max_tokens=80,
          temperature=0.7,
      )
      return res.choices[0].message.content.strip()
    except Exception as e:
      return f"Sorry, error: {str(e)}"

  return f"You said: {q_lower}"


@app.post("/ask")
async def ask_lemon(payload: QueryPayload):
  reply_text = process_query_text(payload.query)

  # Convert response to speech
  temp_file = "lemon_reply.mp3"
  tts = gTTS(text=reply_text, lang="en", slow=False)
  tts.save(temp_file)

  with open(temp_file, "rb") as f:
    audio_b64 = base64.b64encode(f.read()).decode("utf-8")

  return JSONResponse({
      "reply": reply_text,
      "audio_base64": f"data:audio/mp3;base64,{audio_b64}",
  })


# Complete In-App UI (Dono: Likhne wala + Hands-free Bolne wala)
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
            body { background: #0f172a; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; text-align: center; padding: 15px; }
            .container { max-width: 480px; width: 100%; background: #1e293b; border-radius: 24px; padding: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h1 { font-size: 26px; margin-bottom: 6px; color: #facc15; }
            p.sub { font-size: 13px; color: #94a3b8; margin-bottom: 20px; }
            
            /* Hands-Free Voice Orb */
            .orb-container { position: relative; width: 110px; height: 110px; margin: 0 auto 15px; display: flex; align-items: center; justify-content: center; }
            .orb { width: 85px; height: 85px; border-radius: 50%; background: linear-gradient(135deg, #facc15, #f59e0b); display: flex; align-items: center; justify-content: center; font-size: 36px; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 0 20px rgba(250, 204, 21, 0.4); }
            .listening .orb { animation: pulse 1.5s infinite; box-shadow: 0 0 35px rgba(250, 204, 21, 0.9); }
            
            @keyframes pulse {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250, 204, 21, 0.7); }
                70% { transform: scale(1.08); box-shadow: 0 0 0 20px rgba(250, 204, 21, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250, 204, 21, 0); }
            }
            
            .status { font-size: 14px; font-weight: 600; margin-bottom: 15px; color: #38bdf8; }
            
            /* Type / Likhne Wala Box */
            .input-group { display: flex; gap: 8px; margin-bottom: 15px; }
            .text-box { flex: 1; padding: 12px 16px; border-radius: 12px; border: 1px solid #334155; background: #0f172a; color: white; font-size: 15px; outline: none; }
            .text-box:focus { border-color: #facc15; }
            .send-btn { background: #facc15; color: #0f172a; border: none; border-radius: 12px; padding: 0 18px; font-weight: bold; cursor: pointer; font-size: 14px; transition: background 0.2s; }
            .send-btn:hover { background: #eab308; }

            .transcript-box { background: #0f172a; border-radius: 12px; padding: 14px; min-height: 80px; font-size: 14px; color: #e2e8f0; border: 1px solid #334155; text-align: left; }
            .reply-box { margin-top: 10px; color: #facc15; font-size: 15px; font-weight: 500; }
            .hint { font-size: 11px; color: #64748b; margin-top: 15px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍋 Lemon AI</h1>
            <p class="sub">Speak ("Hi Lemon") or Type your question</p>

            <!-- Voice Orb (Hands-Free) -->
            <div class="orb-container" id="orbWrapper">
                <div class="orb" id="startBtn" onclick="toggleAssistant()">🎙️</div>
            </div>

            <div class="status" id="statusText">Tap Lemon once to enable Voice</div>

            <!-- Likhne wala Section -->
            <div class="input-group">
                <input type="text" id="manualInput" class="text-box" placeholder="Type here or talk above..." onkeydown="handleKey(event)" />
                <button class="send-btn" onclick="sendManualText()">Send</button>
            </div>

            <!-- Responses Box -->
            <div class="transcript-box">
                <div id="heardText" style="color: #94a3b8;">Conversation will show here...</div>
                <div id="replyText" class="reply-box"></div>
            </div>

            <div class="hint">Say <b>"Hi Lemon, what is the time?"</b> or just type and press Send.</div>
        </div>

        <audio id="audioPlayer" autoplay></audio>

        <script>
            let isListening = false;
            let recognition = null;
            const statusText = document.getElementById("statusText");
            const heardText = document.getElementById("heardText");
            const replyText = document.getElementById("replyText");
            const orbWrapper = document.getElementById("orbWrapper");
            const audioPlayer = document.getElementById("audioPlayer");
            const manualInput = document.getElementById("manualInput");

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            function initRecognition() {
                if (!SpeechRecognition) {
                    statusText.innerText = "Speech API not supported in this browser. Use typing below.";
                    return null;
                }
                const rec = new SpeechRecognition();
                rec.continuous = true;
                rec.interimResults = false;
                rec.lang = "en-US";

                rec.onresult = async function(event) {
                    const lastResult = event.results[event.results.length - 1][0].transcript.trim();
                    heardText.innerText = `You said: "${lastResult}"`;
                    
                    const lower = lastResult.toLowerCase();
                    if (lower.includes("lemon") || lower.includes("hi lemon")) {
                        statusText.innerText = "⚡ Thinking...";
                        await sendCommand(lastResult);
                    }
                };

                rec.onerror = function(err) {
                    console.warn("Recognition error:", err);
                };

                rec.onend = function() {
                    if (isListening) {
                        try { rec.start(); } catch(e) {}
                    }
                };
                return rec;
            }

            function toggleAssistant() {
                if (!recognition) {
                    recognition = initRecognition();
                }

                if (!isListening && recognition) {
                    isListening = true;
                    try { recognition.start(); } catch(e) {}
                    orbWrapper.classList.add("listening");
                    statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                    audioPlayer.play().catch(() => {});
                } else if (recognition) {
                    isListening = false;
                    recognition.stop();
                    orbWrapper.classList.remove("listening");
                    statusText.innerText = "Voice Paused. Tap 🎙️ to resume.";
                }
            }

            async function sendCommand(queryText) {
                try {
                    const res = await fetch("/ask", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ query: queryText })
                    });
                    const data = await res.json();
                    
                    replyText.innerText = `Lemon: ${data.reply}`;
                    if (isListening) {
                        statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                    }

                    if (data.audio_base64) {
                        audioPlayer.src = data.audio_base64;
                        audioPlayer.play();
                    }
                } catch(e) {
                    statusText.innerText = "Error getting response.";
                }
            }

            function sendManualText() {
                const text = manualInput.value.trim();
                if (!text) return;
                heardText.innerText = `You typed: "${text}"`;
                manualInput.value = "";
                statusText.innerText = "⚡ Thinking...";
                sendCommand(text);
            }

            function handleKey(e) {
                if (e.key === "Enter") {
                    sendManualText();
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
