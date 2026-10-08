import base64
import datetime
import os
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from groq import Groq
from gtts import gTTS

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="Lemon AI In-App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def process_query_text(query: str) -> str:
  if not query:
    return "I am listening. How can I help you?"

  clean = query.lower().strip()
  for w in [
      "hi lemon",
      "hey lemon",
      "lemon",
      "hello lemon",
      "high level",
      "hi level",
  ]:
    if clean.startswith(w):
      clean = clean[len(w) :].strip()

  if not clean:
    return "Yes! I am Lemon. Tell me what you need."

  if "time" in clean:
    return (
        f"The current time is {datetime.datetime.now().strftime('%I:%M %p')}."
    )

  if clean.startswith("play "):
    song = clean[5:].strip()
    return f"Playing {song} on YouTube."

  if client:
    for model in ["llama-3.1-8b-instant", "llama3-8b-8192"]:
      try:
        res = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Lemon, a friendly mobile app voice assistant."
                        " Keep responses strictly in 1 to 2 spoken sentences."
                    ),
                },
                {"role": "user", "content": clean},
            ],
            model=model,
            max_tokens=60,
            temperature=0.7,
        )
        return res.choices[0].message.content.strip()
      except Exception:
        continue

  return f"I heard: {clean}"


@app.post("/voice-process")
async def voice_process(file: UploadFile = File(...)):
  temp_audio = "app_input.wav"
  with open(temp_audio, "wb") as f:
    f.write(await file.read())

  user_text = ""
  if client:
    try:
      with open(temp_audio, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model="whisper-large-v3", file=f, response_format="text"
        )
        user_text = str(transcription).strip()
    except Exception as e:
      print("STT Error:", e)

  reply_text = process_query_text(user_text)

  # Audio response
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
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>Lemon AI</title>
        <style>
            * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
            body { background: #0f172a; color: white; display: flex; flex-direction: column; height: 100vh; justify-content: space-between; padding: 20px; text-align: center; }
            .header h1 { font-size: 26px; color: #facc15; margin-top: 10px; }
            .header p { font-size: 13px; color: #94a3b8; }

            .orb-container { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; }
            .orb { width: 110px; height: 110px; border-radius: 50%; background: linear-gradient(135deg, #facc15, #f59e0b); display: flex; align-items: center; justify-content: center; font-size: 46px; cursor: pointer; box-shadow: 0 0 25px rgba(250, 204, 21, 0.4); transition: transform 0.2s; -webkit-tap-highlight-color: transparent; }
            .orb:active { transform: scale(0.92); }
            .recording { animation: pulse 1.2s infinite; box-shadow: 0 0 45px rgba(250, 204, 21, 0.9); }

            @keyframes pulse {
                0% { transform: scale(0.95); }
                50% { transform: scale(1.1); }
                100% { transform: scale(0.95); }
            }

            .status-text { font-size: 15px; font-weight: 600; color: #38bdf8; margin-top: 20px; }

            .dialog-box { background: #1e293b; border-radius: 16px; padding: 16px; min-height: 90px; text-align: left; font-size: 14px; border: 1px solid #334155; margin-bottom: 16px; }
            .user-msg { color: #94a3b8; margin-bottom: 6px; }
            .lemon-msg { color: #facc15; font-weight: 500; font-size: 15px; }

            .input-bar { display: flex; gap: 8px; margin-bottom: 10px; }
            .input-bar input { flex: 1; padding: 14px; border-radius: 12px; border: 1px solid #334155; background: #1e293b; color: white; outline: none; font-size: 15px; }
            .input-bar button { padding: 0 20px; border-radius: 12px; border: none; background: #facc15; color: #0f172a; font-weight: bold; font-size: 15px; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🍋 Lemon AI</h1>
            <p>Your Voice & Text Companion</p>
        </div>

        <div class="orb-container">
            <div class="orb" id="micBtn" onclick="toggleRecord()">🎙️</div>
            <div class="status-text" id="status">Tap 🎙️ to Speak</div>
        </div>

        <div>
            <div class="dialog-box">
                <div class="user-msg" id="userDisplay">Tap mic or type a message...</div>
                <div class="lemon-msg" id="lemonDisplay"></div>
            </div>

            <div class="input-bar">
                <input type="text" id="typeInput" placeholder="Type here..." onkeydown="if(event.key==='Enter') sendText()" />
                <button onclick="sendText()">Send</button>
            </div>
        </div>

        <audio id="audioOut" autoplay></audio>

        <script>
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;

            const micBtn = document.getElementById("micBtn");
            const statusLabel = document.getElementById("status");
            const userDisplay = document.getElementById("userDisplay");
            const lemonDisplay = document.getElementById("lemonDisplay");
            const audioOut = document.getElementById("audioOut");
            const typeInput = document.getElementById("typeInput");

            async function toggleRecord() {
                if (!isRecording) {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        mediaRecorder = new MediaRecorder(stream);
                        audioChunks = [];

                        mediaRecorder.ondataavailable = (e) => {
                            if (e.data.size > 0) audioChunks.push(e.data);
                        };

                        mediaRecorder.onstop = async () => {
                            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                            statusLabel.innerText = "⚡ Lemon is thinking...";
                            uploadAudio(audioBlob);
                            stream.getTracks().forEach(t => t.stop());
                        };

                        mediaRecorder.start();
                        isRecording = true;
                        micBtn.classList.add("recording");
                        statusLabel.innerText = "🔴 Listening... Tap again to send";
                    } catch(err) {
                        alert("Microphone permission required! Please enable microphone in your app permissions.");
                        statusLabel.innerText = "Mic access blocked";
                    }
                } else {
                    isRecording = false;
                    micBtn.classList.remove("recording");
                    if (mediaRecorder) mediaRecorder.stop();
                }
            }

            async function uploadAudio(blob) {
                const fd = new FormData();
                fd.append("file", blob, "voice.wav");

                try {
                    const res = await fetch("/voice-process", { method: "POST", body: fd });
                    const data = await res.json();
                    userDisplay.innerText = `You: "${data.user_text || 'Voice command'}"`;
                    lemonDisplay.innerText = `Lemon: ${data.reply_text}`;
                    statusLabel.innerText = "Tap 🎙️ to Speak";

                    if (data.audio_base64) {
                        audioOut.src = data.audio_base64;
                        audioOut.play();
                    }
                } catch(e) {
                    statusLabel.innerText = "Server error. Try again.";
                }
            }

            async function sendText() {
                const val = typeInput.value.trim();
                if (!val) return;
                typeInput.value = "";
                userDisplay.innerText = `You: "${val}"`;
                statusLabel.innerText = "⚡ Lemon is thinking...";

                const fd = new FormData();
                fd.append("text", val);

                try {
                    const res = await fetch("/text-process", { method: "POST", body: fd });
                    const data = await res.json();
                    lemonDisplay.innerText = `Lemon: ${data.reply_text}`;
                    statusLabel.innerText = "Tap 🎙️ to Speak";

                    if (data.audio_base64) {
                        audioOut.src = data.audio_base64;
                        audioOut.play();
                    }
                } catch(e) {
                    statusLabel.innerText = "Server error. Try again.";
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
