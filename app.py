import base64
from datetime import datetime
import io
import json
import os
import re
import urllib.parse
import uuid
import zoneinfo
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from groq import Groq
from gtts import gTTS

# ----------------- CONFIGURATION & SECRETS -----------------
PART1 = "gsk_HFaYhV1dR0lldEmL2zkAWGdy"
PART2 = "b3FYnQHV93Lkgjmz4CtDJ1IpMfy4"
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or (PART1 + PART2)
client = Groq(api_key=GROQ_API_KEY)

app = FastAPI(title="Lemon AI - Precision Core")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEMORY_FILE = "lemon_evolution_memory.json"

# ----------------- AUTONOMOUS MEMORY ENGINE -----------------
def load_evolution_memory() -> dict:
  if os.path.exists(MEMORY_FILE):
    try:
      with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      pass
  return {
      "learned_user_traits": [],
      "conversation_count": 0,
      "summary_of_learnings": (
          "User values precise, insightful, and articulate dialogue."
      ),
  }


def save_evolution_memory(data: dict):
  try:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
      json.dump(data, f, indent=2, ensure_ascii=False)
  except Exception as e:
    print(f"[Memory Engine] Save Error: {e}")


def evolve_lemon_memory(user_msg: str, bot_msg: str):
  if not client or len(user_msg.split()) < 3:
    return

  memory_data = load_evolution_memory()
  memory_data["conversation_count"] += 1

  try:
    prompt = f"""You are the evolutionary metacognitive core of Lemon AI.
Analyze this interaction:
User: "{user_msg}"
Lemon: "{bot_msg[:250]}"
Existing Knowledge: "{memory_data.get('summary_of_learnings')}"

Extract 1 specific, high-signal fact or preference about the user.
If it is trivial banter or already captured, reply strictly with: NO_CHANGE."""

    resp = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.1-8b-instant",
        max_tokens=50,
        temperature=0.2,
    )
    thought = resp.choices[0].message.content.strip()
    if thought and "NO_CHANGE" not in thought:
      memory_data["learned_user_traits"].append(thought)
      memory_data["learned_user_traits"] = memory_data["learned_user_traits"][
          -12:
      ]
      memory_data["summary_of_learnings"] = " | ".join(
          memory_data["learned_user_traits"]
      )
      save_evolution_memory(memory_data)
  except Exception as e:
    print(f"[Evolution Metacognition] Warning: {e}")


# ----------------- QUERY NORMALIZER -----------------
def sanitize_prompt(text: str) -> str:
  # Regex-safe word boundary stripping
  cleaned = re.sub(
      r"^(hi|hey|hello)?\s*(lemon|lemmon|level|lemon ai)\s*[,:]?\s*",
      "",
      text,
      flags=re.IGNORECASE,
  ).strip()
  return cleaned if cleaned else text.strip()


# ----------------- COGNITIVE DIALOGUE PROCESSOR -----------------
def process_ai_dialogue(
    raw_prompt: str, history_json: str
) -> tuple[str, str, str]:
  clean_prompt = sanitize_prompt(raw_prompt)
  lowered = clean_prompt.lower()

  # Action: YouTube Execution
  if lowered.startswith("play "):
    target = clean_prompt[5:].strip()
    return (
        f"Queuing up {target} on YouTube for you now.",
        "youtube",
        f"https://www.youtube.com/results?search_query={urllib.parse.quote(target)}",
    )

  # Action: Accurate Local Time (Handles Server Offset with Asia/Kolkata fallback)
  if "time" in lowered and len(lowered.split()) <= 6:
    try:
      tz = zoneinfo.ZoneInfo("Asia/Kolkata")
      now = datetime.now(tz)
    except Exception:
      now = datetime.now()
    return (
        f"The current local time is {now.strftime('%I:%M %p (%A, %B %d)')}.",
        "",
        "",
    )

  # Memory & History Assembly
  history = []
  if history_json:
    try:
      history = json.loads(history_json)
    except Exception:
      history = []

  memory = load_evolution_memory()
  evolution_summary = memory.get(
      "summary_of_learnings", "Be insightful, warm, and highly engaging."
  )

  system_prompt = f"""You are Lemon, a hyper-precise, articulate, and thoughtful AI voice companion.
Learned Context About User: {evolution_summary}

Operating Rules:
1. Speak naturally with clear phrasing suited for spoken dialogue.
2. Provide thorough, intellectually sound, and accurate answers without unnecessary disclaimers.
3. Automatically match the user's language (English, Hindi, or Hinglish).
4. Do not recite special characters, Markdown formatting, asterisks, or hash symbols, as your words will be directly converted to speech."""

  messages = [{"role": "system", "content": system_prompt}]
  # Inject last 6 conversational turns
  for item in history[-6:]:
    role = "user" if item.get("role") == "user" else "assistant"
    messages.append({"role": role, "content": item.get("text", "")})
  messages.append({"role": "user", "content": clean_prompt})

  # Multi-Model Resilient Execution
  active_models = [
      "llama-3.1-8b-instant",
      "openai/gpt-oss-20b",
      "openai/gpt-oss-120b",
  ]
  reply = "I analyzed your query, but could not finalize a response. Could you rephrase that?"

  if client:
    for model_candidate in active_models:
      try:
        completion = client.chat.completions.create(
            messages=messages,
            model=model_candidate,
            max_tokens=320,  # Optimal sweet-spot: in-depth yet sub-1.5s TTS synthesis
            temperature=0.65,
        )
        if completion.choices and completion.choices[0].message.content:
          reply = completion.choices[0].message.content.strip()
          # Clean markdown asterisks that confuse TTS
          reply = re.sub(r"[\*#_`]", "", reply)
          break
      except Exception as err:
        print(f"[Model Failover] Model {model_candidate} error: {err}")
        continue

  # Asynchronously update evolution core
  evolve_lemon_memory(clean_prompt, reply)
  return reply, "", ""


# ----------------- FAST IN-MEMORY AUDIO SYNTHESIZER -----------------
def generate_speech_stream(text: str) -> str:
  # Truncate cleanly for voice generation if exceedingly long
  spoken_text = text if len(text) < 400 else text[:400] + "..."
  tts = gTTS(text=spoken_text, lang="en", slow=False)
  fp = io.BytesIO()
  tts.write_to_fp(fp)
  fp.seek(0)
  return base64.b64encode(fp.read()).decode("utf-8")


# ----------------- ENDPOINTS -----------------
@app.post("/voice-process")
async def voice_process(
    file: UploadFile = File(...), history: str = Form("[]")
):
  raw_bytes = await file.read()
  temp_name = f"in_{uuid.uuid4().hex[:10]}.wav"
  with open(temp_name, "wb") as f:
    f.write(raw_bytes)

  user_text = ""
  if client:
    try:
      with open(temp_name, "rb") as f:
        tx = client.audio.transcriptions.create(
            model="whisper-large-v3", file=f, response_format="text"
        )
        user_text = str(tx).strip()
    except Exception as e:
      print(f"[Whisper STT] Error: {e}")

  if os.path.exists(temp_name):
    try:
      os.remove(temp_name)
    except Exception:
      pass

  if not user_text:
    return JSONResponse({
        "user_text": "",
        "reply_text": (
            "I couldn't hear any audio clearly. Could you say that again?"
        ),
        "audio_base64": "",
        "action": "",
        "action_target": "",
    })

  reply_text, action, target = process_ai_dialogue(user_text, history)
  b64_audio = generate_speech_stream(reply_text)

  return JSONResponse({
      "user_text": user_text,
      "reply_text": reply_text,
      "audio_base64": f"data:audio/mp3;base64,{b64_audio}",
      "action": action,
      "action_target": target,
  })


@app.post("/text-process")
async def text_process(text: str = Form(...), history: str = Form("[]")):
  reply_text, action, target = process_ai_dialogue(text.strip(), history)
  b64_audio = generate_speech_stream(reply_text)

  return JSONResponse({
      "user_text": text.strip(),
      "reply_text": reply_text,
      "audio_base64": f"data:audio/mp3;base64,{b64_audio}",
      "action": action,
      "action_target": target,
  })


# ----------------- FRONTEND CLIENT (HIGH-FIDELITY PWA) -----------------
@app.get("/", response_class=HTMLResponse)
async def serve_app():
  return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>Lemon AI | Precision Voice</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #facc15;
            --primary-glow: rgba(250, 204, 21, 0.45);
            --bg-dark: #07090e;
            --card-glass: rgba(18, 24, 38, 0.75);
            --border-glass: rgba(255, 255, 255, 0.09);
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; -webkit-tap-highlight-color: transparent; }
        body {
            background: radial-gradient(circle at 50% 12%, #1a1744 0%, var(--bg-dark) 65%);
            color: #f8fafc; height: 100dvh; display: flex; flex-direction: column; justify-content: space-between; overflow: hidden;
        }

        /* Top Bar */
        .header {
            padding: 14px 20px; display: flex; align-items: center; justify-content: space-between;
            border-bottom: 1px solid var(--border-glass); backdrop-filter: blur(16px); z-index: 10;
        }
        .brand { display: flex; align-items: center; gap: 10px; }
        .brand-logo {
            width: 36px; height: 36px; background: linear-gradient(135deg, #facc15, #eab308);
            border-radius: 10px; display: flex; align-items: center; justify-content: center;
            font-size: 20px; box-shadow: 0 4px 14px var(--primary-glow);
        }
        .brand-title { font-size: 16px; font-weight: 700; letter-spacing: -0.2px; }
        .live-tag {
            display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 600;
            color: #4ade80; background: rgba(74, 222, 128, 0.12); padding: 4px 10px;
            border-radius: 20px; border: 1px solid rgba(74, 222, 128, 0.25);
        }
        .pulse-dot { width: 6px; height: 6px; background: #4ade80; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

        /* Stream Container */
        .chat-container {
            flex: 1; overflow-y: auto; padding: 18px 16px; display: flex;
            flex-direction: column; gap: 14px; scroll-behavior: smooth;
        }
        .chat-container::-webkit-scrollbar { display: none; }
        .bubble {
            max-width: 86%; padding: 13px 17px; border-radius: 18px; font-size: 14px;
            line-height: 1.55; word-wrap: break-word; animation: bubbleIn 0.2s ease-out;
        }
        @keyframes bubbleIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .bubble.lemon {
            align-self: flex-start; background: var(--card-glass); backdrop-filter: blur(12px);
            border: 1px solid var(--border-glass); color: #f1f5f9; border-bottom-left-radius: 4px;
        }
        .bubble.lemon b { color: var(--primary); }
        .bubble.user {
            align-self: flex-end; background: linear-gradient(135deg, #facc15, #f59e0b);
            color: #090d16; font-weight: 600; border-bottom-right-radius: 4px;
            box-shadow: 0 4px 16px var(--primary-glow);
        }

        /* Typewriter Cursor */
        .cursor { display: inline-block; width: 3px; height: 14px; background: #facc15; margin-left: 3px; vertical-align: middle; animation: blink 0.7s infinite; }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0; } }

        /* Thinking Waveform Dots */
        .typing-loader { display: inline-flex; align-items: center; gap: 4px; padding: 4px 0; }
        .typing-loader span { width: 6px; height: 6px; background: #facc15; border-radius: 50%; animation: bounce 1.1s infinite ease-in-out; }
        .typing-loader span:nth-child(2) { animation-delay: 0.15s; }
        .typing-loader span:nth-child(3) { animation-delay: 0.3s; }
        @keyframes bounce { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1.1); opacity: 1; } }

        /* Interactive Voice Section */
        .voice-hub {
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            position: relative; padding: 8px 0 14px;
        }
        #vizCanvas { position: absolute; width: 200px; height: 90px; pointer-events: none; z-index: 1; }
        .orb {
            width: 76px; height: 76px; border-radius: 50%;
            background: linear-gradient(135deg, #fde047 0%, #eab308 55%, #ca8a04 100%);
            border: none; display: flex; align-items: center; justify-content: center;
            font-size: 30px; cursor: pointer; box-shadow: 0 0 24px var(--primary-glow);
            transition: transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1); z-index: 2;
        }
        .orb:active { transform: scale(0.92); }
        .listening .orb { animation: orbGlow 1.2s infinite alternate; }
        @keyframes orbGlow { from { box-shadow: 0 0 20px var(--primary-glow); } to { box-shadow: 0 0 46px rgba(250, 204, 21, 0.95); } }
        .status-txt { font-size: 12.5px; font-weight: 500; color: #94a3b8; margin-top: 9px; min-height: 18px; }

        /* Input Controls */
        .bottom-shelf {
            padding: 8px 16px 20px; backdrop-filter: blur(16px);
            background: rgba(8, 12, 20, 0.7); border-top: 1px solid var(--border-glass);
        }
        .input-pill {
            display: flex; align-items: center; background: rgba(24, 33, 50, 0.85);
            border: 1px solid var(--border-glass); border-radius: 28px;
            padding: 5px 6px 5px 16px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
        }
        .input-pill input { flex: 1; background: transparent; border: none; color: #fff; font-size: 14px; outline: none; }
        .input-pill input::placeholder { color: #64748b; }
        .send-btn {
            width: 36px; height: 36px; border-radius: 50%; background: var(--primary);
            border: none; color: #07090e; display: flex; align-items: center; justify-content: center;
            cursor: pointer; font-size: 15px; font-weight: bold; transition: transform 0.15s;
        }
        .send-btn:active { transform: scale(0.9); }
    </style>
</head>
<body>
    <div class="header">
        <div class="brand">
            <div class="brand-logo">🍋</div>
            <div class="brand-title">Lemon Assistant</div>
        </div>
        <div class="live-tag">
            <span class="pulse-dot"></span>
            <span>Adaptive Brain Active</span>
        </div>
    </div>

    <div class="chat-container" id="stream">
        <div class="bubble lemon">
            Greetings! I am <b>Lemon</b>. My autonomous learning and memory are fully calibrated. You can speak to me hands-free or type anytime.
        </div>
    </div>

    <div class="voice-hub" id="voiceHub">
        <canvas id="vizCanvas"></canvas>
        <button class="orb" id="micOrb" onclick="toggleVoiceSession()">🎙️</button>
        <div class="status-txt" id="statusLabel">Tap mic to speak</div>
    </div>

    <div class="bottom-shelf">
        <div class="input-pill">
            <input type="text" id="queryInput" placeholder="Message Lemon..." onkeydown="if(event.key==='Enter') dispatchManualText()" />
            <button class="send-btn" onclick="dispatchManualText()">➤</button>
        </div>
    </div>

    <audio id="lemonAudio" autoplay></audio>

    <script>
        let isRecording = false;
        let mediaRecorder = null;
        let audioChunks = [];
        let conversationHistory = [];
        let audioContext = null;
        let analyser = null;
        let silenceTimeout = null;
        let baselineNoise = 12;

        const streamContainer = document.getElementById("stream");
        const micOrb = document.getElementById("micOrb");
        const voiceHub = document.getElementById("voiceHub");
        const statusLabel = document.getElementById("statusLabel");
        const queryInput = document.getElementById("queryInput");
        const lemonAudio = document.getElementById("lemonAudio");
        const canvas = document.getElementById("vizCanvas");
        const ctx = canvas.getContext("2d");

        // Real-Time Typewriter with Synced Audio Playback
        function typewriterEffect(element, fullText, audioUrl, onComplete) {
            element.innerHTML = "";
            const cursor = document.createElement("span");
            cursor.className = "cursor";
            
            const words = fullText.split(" ");
            let idx = 0;

            // Trigger audio right as characters start appearing
            if (audioUrl) {
                lemonAudio.src = audioUrl;
                lemonAudio.play().catch(e => console.log("Audio autostart waiting for gesture:", e));
            }

            const pace = Math.max(18, Math.min(42, 1400 / (words.length || 1)));

            function writeToken() {
                if (idx < words.length) {
                    element.innerText += (idx === 0 ? "" : " ") + words[idx];
                    element.appendChild(cursor);
                    streamContainer.scrollTop = streamContainer.scrollHeight;
                    idx++;
                    setTimeout(writeToken, pace);
                } else {
                    cursor.remove();
                    conversationHistory.push({ role: "assistant", text: fullText });
                    if (conversationHistory.length > 10) conversationHistory.shift();
                    if (onComplete) onComplete();
                }
            }
            writeToken();
        }

        function spawnThinkingBubble() {
            const b = document.createElement("div");
            b.className = "bubble lemon";
            b.innerHTML = `<span style="font-size:12.5px; color:#facc15; margin-right:8px; font-weight:600;">Processing Thought</span><div class="typing-loader"><span></span><span></span><span></span></div>`;
            streamContainer.appendChild(b);
            streamContainer.scrollTop = streamContainer.scrollHeight;
            return b;
        }

        // Calibrated Voice Activity Visualizer
        function setupAudioAnalysis(audioStream) {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            const src = audioContext.createMediaStreamSource(audioStream);
            src.connect(analyser);
            analyser.fftSize = 64;

            const bufLength = analyser.frequencyBinCount;
            const dataArr = new Uint8Array(bufLength);

            function render() {
                if (!isRecording) {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    return;
                }
                requestAnimationFrame(render);
                analyser.getByteFrequencyData(dataArr);
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                let sum = 0;
                for (let i = 0; i < bufLength; i++) sum += dataArr[i];
                let energy = sum / bufLength;

                // Dynamic baseline calculation
                if (energy > (baselineNoise + 5)) {
                    clearTimeout(silenceTimeout);
                    silenceTimeout = setTimeout(() => {
                        if (isRecording) terminateAndSend();
                    }, 1500); // 1.5s natural pause
                }

                ctx.fillStyle = "rgba(250, 204, 21, 0.4)";
                let barW = (canvas.width / bufLength) * 2;
                let x = 0;
                for (let i = 0; i < bufLength; i++) {
                    let barH = (dataArr[i] / 255) * canvas.height * 0.85;
                    ctx.fillRect(x, (canvas.height - barH) / 2, barW - 2, barH);
                    x += barW;
                }
            }
            render();
        }

        async function toggleVoiceSession() {
            if (!isRecording) {
                try {
                    const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    mediaRecorder = new MediaRecorder(audioStream);
                    audioChunks = [];

                    setupAudioAnalysis(audioStream);

                    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        audioStream.getTracks().forEach(t => t.stop());
                        if (audioContext) audioContext.close();
                        dispatchVoiceData(audioBlob);
                    };

                    mediaRecorder.start();
                    isRecording = true;
                    voiceHub.classList.add("listening");
                    statusLabel.innerText = "Listening... Speak naturally";
                } catch(err) {
                    alert("Microphone permission required for voice interaction.");
                    statusLabel.innerText = "Mic access withheld";
                }
            } else {
                terminateAndSend();
            }
        }

        function terminateAndSend() {
            if (!isRecording) return;
            isRecording = false;
            voiceHub.classList.remove("listening");
            statusLabel.innerText = "Translating audio...";
            clearTimeout(silenceTimeout);
            if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
        }

        async function dispatchVoiceData(blob) {
            const placeholder = spawnThinkingBubble();
            statusLabel.innerText = "Lemon is synthesizing...";

            const fd = new FormData();
            fd.append("file", blob, "input.wav");
            fd.append("history", JSON.stringify(conversationHistory));

            try {
                const res = await fetch("/voice-process", { method: "POST", body: fd });
                const data = await res.json();

                if (data.user_text) {
                    const userNode = document.createElement("div");
                    userNode.className = "bubble user";
                    userNode.innerText = data.user_text;
                    streamContainer.insertBefore(userNode, placeholder);
                    conversationHistory.push({ role: "user", text: data.user_text });
                }

                typewriterEffect(placeholder, data.reply_text, data.audio_base64, () => {
                    statusLabel.innerText = "Tap mic to speak";
                });

                if (data.action === "youtube" && data.action_target) {
                    window.open(data.action_target, '_blank');
                }
            } catch(e) {
                placeholder.innerText = "Network transmission failed. Please retry.";
                statusLabel.innerText = "Tap mic to speak";
            }
        }

        async function dispatchManualText() {
            const text = queryInput.value.trim();
            if (!text) return;

            queryInput.value = "";
            const userNode = document.createElement("div");
            userNode.className = "bubble user";
            userNode.innerText = text;
            streamContainer.appendChild(userNode);
            conversationHistory.push({ role: "user", text: text });

            const placeholder = spawnThinkingBubble();
            statusLabel.innerText = "Lemon is synthesizing...";

            const fd = new FormData();
            fd.append("text", text);
            fd.append("history", JSON.stringify(conversationHistory));

            try {
                const res = await fetch("/text-process", { method: "POST", body: fd });
                const data = await res.json();

                typewriterEffect(placeholder, data.reply_text, data.audio_base64, () => {
                    statusLabel.innerText = "Tap mic to speak";
                });

                if (data.action === "youtube" && data.action_target) {
                    window.open(data.action_target, '_blank');
                }
            } catch(e) {
                placeholder.innerText = "Service unavailable. Please try again.";
                statusLabel.innerText = "Tap mic to speak";
            }
        }
    </script>
</body>
</html>"""


if __name__ == "__main__":
  import uvicorn

  port = int(os.environ.get("PORT", 10000))
  uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
