import os
import datetime
import urllib.parse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq
from gtts import gTTS
import base64

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="Lemon AI In-App Voice Assistant")

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

    # Remove wake word
    for wake in ["hi lemon", "hey lemon", "lemon"]:
        if q_lower.startswith(wake):
            q_lower = q_lower[len(wake):].strip()

    if not q_lower:
        return "Yes? I'm listening!"

    # 1. Time
    if "time" in q_lower:
        now = datetime.datetime.now()
        return f"The time is {now.strftime('%I:%M %p')}."

    # 2. YouTube
    if q_lower.startswith("play "):
        song = q_lower[5:].strip()
        return f"Playing {song} on YouTube."

    # 3. Groq LLM
    if client:
        try:
            res = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are Lemon, an ultra-fast, friendly in-app voice assistant. Answer in 1 short spoken sentence."
                    },
                    {"role": "user", "content": q_lower}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=60,
                temperature=0.7
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    return f"You asked: {q_lower}"

@app.post("/ask")
async def ask_lemon(payload: QueryPayload):
    reply_text = process_query_text(payload.query)
    
    # Generate TTS audio as base64 so browser plays it instantly
    tts = gTTS(text=reply_text, lang="en", slow=False)
    temp_file = "reply.mp3"
    tts.save(temp_file)
    
    with open(temp_file, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    return JSONResponse({
        "reply": reply_text,
        "audio_base64": f"data:audio/mp3;base64,{audio_b64}"
    })

# In-App Pure Hands-Free UI
@app.get("/", response_class=HTMLResponse)
async def serve_app():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>🍋 Lemon Voice Assistant</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background: #0f172a; color: white; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; text-align: center; padding: 20px; }
            .container { max-width: 480px; width: 100%; background: #1e293b; border-radius: 24px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
            h1 { font-size: 28px; margin-bottom: 8px; color: #facc15; }
            p.sub { font-size: 14px; color: #94a3b8; margin-bottom: 24px; }
            
            .orb-container { position: relative; width: 140px; height: 140px; margin: 0 auto 24px; display: flex; align-items: center; justify-content: center; }
            .orb { width: 100px; height: 100px; border-radius: 50%; background: linear-gradient(135deg, #facc15, #f59e0b); display: flex; align-items: center; justify-content: center; font-size: 40px; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 0 20px rgba(250, 204, 21, 0.4); }
            .listening .orb { animation: pulse 1.5s infinite; box-shadow: 0 0 40px rgba(250, 204, 21, 0.8); }
            
            @keyframes pulse {
                0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250, 204, 21, 0.7); }
                70% { transform: scale(1.1); box-shadow: 0 0 0 25px rgba(250, 204, 21, 0); }
                100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(250, 204, 21, 0); }
            }
            
            .status { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: #38bdf8; }
            .transcript-box { background: #0f172a; border-radius: 12px; padding: 15px; min-height: 80px; margin-top: 16px; font-size: 15px; color: #e2e8f0; border: 1px solid #334155; }
            .reply-box { margin-top: 14px; color: #facc15; font-size: 16px; font-weight: 500; }
            .hint { font-size: 12px; color: #64748b; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container" id="mainContainer">
            <h1>🍋 Lemon AI</h1>
            <p class="sub">Hands-Free Built-in Voice Assistant</p>

            <div class="orb-container" id="orbWrapper">
                <div class="orb" id="startBtn" onclick="toggleAssistant()">🎙️</div>
            </div>

            <div class="status" id="statusText">Tap Lemon once to activate</div>

            <div class="transcript-box">
                <div id="heardText" style="color: #94a3b8;">Listening output will appear here...</div>
                <div id="replyText" class="reply-box"></div>
            </div>

            <div class="hint">Just say: <b>"Hi Lemon, what is the time?"</b> or <b>"Lemon, tell me a joke"</b></div>
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

            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

            function initRecognition() {
                if (!SpeechRecognition) {
                    statusText.innerText = "Speech API not supported in this browser";
                    return null;
                }
                const rec = new SpeechRecognition();
                rec.continuous = true;
                rec.interimResults = false;
                rec.lang = "en-US";

                rec.onresult = async function(event) {
                    const lastResult = event.results[event.results.length - 1][0].transcript.trim();
                    heardText.innerText = `You: "${lastResult}"`;
                    
                    const lower = lastResult.toLowerCase();
                    // Wake-word detection: "hi lemon", "hey lemon", or "lemon"
                    if (lower.includes("lemon")) {
                        statusText.innerText = "⚡ Processing...";
                        await sendCommand(lastResult);
                    }
                };

                rec.onerror = function(err) {
                    console.warn("Recognition error:", err);
                };

                rec.onend = function() {
                    // Continuous loop - restart immediately if still enabled
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

                if (!isListening) {
                    isListening = true;
                    try { recognition.start(); } catch(e) {}
                    orbWrapper.classList.add("listening");
                    statusText.innerText = "🟢 Listening for 'Hi Lemon'...";
                    // Unlock browser audio
                    audioPlayer.play().catch(() => {});
                } else {
                    isListening = false;
                    recognition.stop();
                    orbWrapper.classList.remove("listening");
                    statusText.innerText = "Paused. Tap to wake.";
                }
            }

            async function sendCommand(spokenText) {
                try {
                    const res = await fetch("/ask", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ query: spokenText })
                    });
                    const data = await res.json();
                    
                    replyText.innerText = `Lemon: ${data.reply}`;
                    statusText.innerText = "🟢 Listening for 'Hi Lemon'...";

                    if (data.audio_base64) {
                        audioPlayer.src = data.audio_base64;
                        audioPlayer.play();
                    }
                } catch(e) {
                    statusText.innerText = "Error getting response";
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
