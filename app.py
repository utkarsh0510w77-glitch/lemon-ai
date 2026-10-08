import os
import datetime
import urllib.parse
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
from groq import Groq
from gtts import gTTS

# ----------------- Configuration & Clients -----------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("Warning: GROQ_API_KEY is not set in environment variables.")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="Lemon Voice Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_AUDIO_FILE = "lemon_reply.mp3"


# ----------------- Assistant Core Logic -----------------
def generate_speech(text: str, filename: str = OUTPUT_AUDIO_FILE) -> str:
    """Converts response text to an MP3 speech file using gTTS."""
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(filename)
    return filename


def process_query_text(query: str) -> str:
    """Executes query intent (Time, YouTube, Search, Navigation, General LLM)."""
    if not query:
        return "I didn't catch that. Could you please repeat?"

    q_lower = query.lower().strip()

    # 1. Time query
    if "time" in q_lower:
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}."

    # 2. YouTube playback / search command
    if q_lower.startswith("play "):
        song_name = query[5:].strip()
        encoded = urllib.parse.quote_plus(song_name)
        return f"Playing {song_name} on YouTube. https://www.youtube.com/results?search_query={encoded}"

    # 3. Google Search command
    if q_lower.startswith("search ") or q_lower.startswith("google "):
        search_term = query.split(" ", 1)[1].strip()
        encoded = urllib.parse.quote_plus(search_term)
        return f"Here is what I found for {search_term}. https://www.google.com/search?q={encoded}"

    # 4. Navigation / Maps command
    if "navigate to" in q_lower or "directions to" in q_lower:
        destination = (
            q_lower.replace("navigate to", "")
            .replace("directions to", "")
            .strip()
        )
        encoded = urllib.parse.quote_plus(destination)
        return f"Navigating to {destination}. https://www.google.com/maps/dir/?api=1&destination={encoded}"

    # 5. General AI Intelligence via Groq LLM
    if client:
        try:
            chat_completion = client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are Lemon, a friendly, concise, and ultra-smart earbud voice assistant. "
                            "Keep answers very short, spoken-style, and limited to 1-2 clear sentences."
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=100,
                temperature=0.7,
            )
            return chat_completion.choices[0].message.content.strip()
        except Exception as e:
            return f"Sorry, I encountered an issue: {str(e)}"

    return f"You said: {query}."


# ----------------- MacroDroid API Endpoint -----------------
@app.post("/voice-agent")
async def voice_agent_endpoint(file: UploadFile = File(...)):
    """Receives voice recording from MacroDroid, transcribes via Groq Whisper, and replies."""
    input_path = "temp_input_audio.m4a"

    with open(input_path, "wb") as buffer:
        content = await file.read()
        buffer.write(content)

    transcription_text = ""
    if client:
        try:
            with open(input_path, "rb") as audio_file:
                transcription = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=audio_file,
                    response_format="text",
                )
                transcription_text = str(transcription).strip()
        except Exception as e:
            print("STT Error:", e)

    reply_text = process_query_text(transcription_text)
    out_audio = generate_speech(reply_text, OUTPUT_AUDIO_FILE)

    return FileResponse(out_audio, media_type="audio/mpeg")


# ----------------- Gradio UI with Continuous 'Hi Lemon' -----------------
wake_word_script = """
<script>
(function() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("SpeechRecognition not supported in this browser.");
        return;
    }

    const recognizer = new SpeechRecognition();
    recognizer.continuous = true;
    recognizer.interimResults = false;
    recognizer.lang = 'en-US';

    recognizer.onresult = function(event) {
        const lastResult = event.results[event.results.length - 1][0].transcript.trim();
        console.log("Heard:", lastResult);
        const lower = lastResult.toLowerCase();

        if (lower.includes("lemon") || lower.includes("hi lemon") || lower.includes("hey lemon")) {
            // Remove the wake word and extract query
            let cleanCommand = lower.replace(/.*lemon/i, "").trim();
            if (!cleanCommand) {
                cleanCommand = "hello";
            }

            const inputElem = document.querySelector("#lemon_input textarea, #lemon_input input");
            const btnElem = document.querySelector("#lemon_submit_btn");

            if (inputElem && btnElem) {
                inputElem.value = cleanCommand;
                inputElem.dispatchEvent(new Event('input', { bubbles: true }));
                setTimeout(() => { btnElem.click(); }, 150);
            }
        }
    };

    recognizer.onerror = function(err) {
        console.log("Voice Recognition Error:", err);
    };

    recognizer.onend = function() {
        try { recognizer.start(); } catch(e) {}
    };

    try {
        recognizer.start();
        console.log("Listening for wake word 'Hi Lemon'...");
    } catch(err) {
        console.error("Wake word init failed:", err);
    }
})();
</script>
"""


def ui_handler(user_text):
    reply = process_query_text(user_text)
    audio_file = generate_speech(reply, "ui_reply.mp3")
    return reply, audio_file


with gr.Blocks(title="Lemon AI Assistant") as demo:
    gr.HTML(wake_word_script)

    gr.Markdown("# 🍋 Lemon AI Voice Assistant")
    gr.Markdown(
        "Say **'Hi Lemon'** followed by your command (e.g. *'Hi Lemon, what is the time?'* or *'Hi Lemon, play Believer'*). "
        "No screen tap required."
    )

    with gr.Row():
        text_input = gr.Textbox(
            label="Command",
            placeholder="Listening for 'Hi Lemon'...",
            elem_id="lemon_input",
            scale=4,
        )
        submit_btn = gr.Button(
            "Send", elem_id="lemon_submit_btn", variant="primary", scale=1
        )

    response_text = gr.Textbox(label="Lemon's Answer")
    response_audio = gr.Audio(
        label="Voice Response", autoplay=True, type="filepath"
    )

    submit_btn.click(
        fn=ui_handler,
        inputs=[text_input],
        outputs=[response_text, response_audio],
    )
    text_input.submit(
        fn=ui_handler,
        inputs=[text_input],
        outputs=[response_text, response_audio],
    )

# Mount Gradio into FastAPI
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
