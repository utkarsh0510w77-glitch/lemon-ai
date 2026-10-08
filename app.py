import os
import datetime
import urllib.parse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import gradio as gr
from groq import Groq
from gtts import gTTS

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

app = FastAPI(title="Lemon AI Voice Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_speech(text: str, filename: str = "lemon_reply.mp3") -> str:
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(filename)
    return filename

def process_query_text(query: str) -> str:
    if not query:
        return "I didn't hear anything. How can I help you?"

    q_lower = query.lower().strip()

    # Wake word strip
    if "lemon" in q_lower:
        q_lower = q_lower.replace("hi lemon", "").replace("hey lemon", "").replace("lemon", "").strip()

    if not q_lower:
        return "Hi there! I am Lemon. What can I do for you?"

    if "time" in q_lower:
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%I:%M %p')}."

    if q_lower.startswith("play "):
        song = q_lower.replace("play", "").strip()
        return f"Playing {song} on YouTube. https://www.youtube.com/results?search_query={urllib.parse.quote_plus(song)}"

    if client:
        try:
            res = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are Lemon, a friendly and quick voice assistant. Respond strictly in 1 to 2 spoken sentences."},
                    {"role": "user", "content": q_lower}
                ],
                model="llama-3.3-70b-versatile",
                max_tokens=80,
                temperature=0.7,
            )
            return res.choices[0].message.content.strip()
        except Exception as e:
            return f"Error: {str(e)}"

    return f"You said: {query}"

def lemon_voice_chat(user_text):
    reply = process_query_text(user_text)
    audio_path = generate_speech(reply)
    return reply, audio_path

# Gradio Web Interface
with gr.Blocks(title="Lemon AI Voice Assistant", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🍋 Lemon AI Voice Assistant
    ### Speak to Lemon directly from your browser!
    """)

    with gr.Row():
        user_input = gr.Textbox(
            label="You can type or speak",
            placeholder="Click 'Start Speaking' or type here...",
            elem_id="user_input_box",
            scale=4
        )
        send_btn = gr.Button("Send", variant="primary", scale=1)

    with gr.Row():
        audio_mic = gr.Audio(
            sources=["microphone"], 
            type="filepath", 
            label="🎙️ Speak using Mic (Say anything or 'Hi Lemon')",
            interactive=True
        )

    lemon_text = gr.Textbox(label="Lemon's Answer", interactive=False)
    lemon_audio = gr.Audio(label="Lemon's Voice", autoplay=True, type="filepath")

    # Send text
    send_btn.click(fn=lemon_voice_chat, inputs=[user_input], outputs=[lemon_text, lemon_audio])
    user_input.submit(fn=lemon_voice_chat, inputs=[user_input], outputs=[lemon_text, lemon_audio])

    # Audio speech recognition automatically via Whisper on audio upload
    def handle_audio_stream(audio_path):
        if not audio_path:
            return "No audio recorded", None
        if client:
            try:
                with open(audio_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-large-v3",
                        file=f,
                        response_format="text"
                    )
                reply = process_query_text(str(transcript))
                audio_reply = generate_speech(reply)
                return f"You: {transcript}\n\nLemon: {reply}", audio_reply
            except Exception as e:
                return f"Error: {e}", None
        return "Groq client not ready", None

    audio_mic.change(fn=handle_audio_stream, inputs=[audio_mic], outputs=[lemon_text, lemon_audio])

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
