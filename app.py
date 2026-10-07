import os
import tempfile
import urllib.parse
import datetime
import gradio as gr
from groq import Groq
from gtts import gTTS
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse

# 1. API Client Setup
api_key = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=api_key) if api_key else None

MODELS_TO_TRY = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

def execute_intent(query_text):
    """Command & Control logic: Handles YouTube, Google, Maps, Utilities, and LLM Fallback"""
    if not query_text or not query_text.strip():
        return "Please say or type a command!", ""

    query_lower = query_text.lower().strip()
    action_html = ""
    command_detected = False
    response_text = ""

    # --- 1. Device Utilities (Time & Date) ---
    if "time" in query_lower and any(w in query_lower for w in ["kya", "what", "batao", "now", "tell"]):
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        response_text = f"The current time is {current_time}."
        command_detected = True

    elif "date" in query_lower and any(w in query_lower for w in ["kya", "today", "aaj", "what", "tell"]):
        current_date = datetime.datetime.now().strftime("%d %B %Y, %A")
        response_text = f"Today's date is {current_date}."
        command_detected = True

    # --- 2. Music & Media (YouTube) ---
    elif query_lower.startswith("play ") or "play on youtube" in query_lower:
        song_name = query_lower.replace("play on youtube", "").replace("play", "").strip()
        encoded = urllib.parse.quote(song_name)
        yt_url = f"https://www.youtube.com/results?search_query={encoded}"
        response_text = f"Playing {song_name} on YouTube for you."
        action_html = f'<a href="{yt_url}" target="_blank" style="display:inline-block;padding:10px 18px;background-color:#ff0000;color:white;text-decoration:none;border-radius:8px;font-weight:bold;margin-top:8px;">▶️ Open YouTube: {song_name}</a>'
        command_detected = True

    # --- 3. Web Searches (Google) ---
    elif query_lower.startswith("search ") or query_lower.startswith("google "):
        search_query = query_lower.replace("search", "").replace("google", "").strip()
        encoded = urllib.parse.quote(search_query)
        google_url = f"https://www.google.com/search?q={encoded}"
        response_text = f"Searching Google for {search_query}."
        action_html = f'<a href="{google_url}" target="_blank" style="display:inline-block;padding:10px 18px;background-color:#4285F4;color:white;text-decoration:none;border-radius:8px;font-weight:bold;margin-top:8px;">🔍 View Google Results: {search_query}</a>'
        command_detected = True

    # --- 4. Navigation & Maps ---
    elif any(k in query_lower for k in ["open map", "navigate to", "directions to", "rasta", "map of"]):
        place = query_lower
        for trigger in ["open map", "navigate to", "directions to", "rasta", "map of"]:
            place = place.replace(trigger, "")
        place = place.strip()
        encoded = urllib.parse.quote(place)
        maps_url = f"https://www.google.com/maps/search/?api=1&query={encoded}"
        response_text = f"Opening navigation for {place}."
        action_html = f'<a href="{maps_url}" target="_blank" style="display:inline-block;padding:10px 18px;background-color:#34A853;color:white;text-decoration:none;border-radius:8px;font-weight:bold;margin-top:8px;">📍 Open in Maps: {place}</a>'
        command_detected = True

    # --- 5. General Intelligence (Groq LLM Fallback) ---
    if not command_detected:
        if not client:
            return "GROQ_API_KEY environment variable is not configured!", ""

        system_prompt = (
            "You are Lemon, an advanced personal AI operating via earbuds and direct command interface. "
            "Deliver crisp, helpful, and direct answers in 1 to 2 sentences."
        )
        for model_id in MODELS_TO_TRY:
            try:
                completion = client.chat.completions.create(
                    model=model_id,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query_text}
                    ],
                    temperature=0.6,
                    max_tokens=150
                )
                response_text = completion.choices[0].message.content
                break
            except Exception as e:
                if model_id == MODELS_TO_TRY[-1]:
                    response_text = f"Groq Error: {str(e)}"

    return response_text, action_html

def create_tts_audio(text):
    """Generates MP3 voice response using gTTS"""
    try:
        clean_text = text.replace("http://", "").replace("https://", "")
        tts = gTTS(text=clean_text, lang='en', slow=False)
        out_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(out_audio.name)
        return out_audio.name
    except Exception:
        return None

# Gradio / Text Handler
def handle_text_query(user_text):
    reply_text, action_html = execute_intent(user_text)
    audio_path = create_tts_audio(reply_text)
    return reply_text, action_html, audio_path

# Gradio / Audio Handler (Voice input from browser)
def handle_audio_query(audio_file_path):
    if not audio_file_path or not client:
        return "Audio input missing or Groq Key not set.", "", None

    try:
        with open(audio_file_path, "rb") as file:
            transcription = client.audio.transcriptions.create(
                file=(os.path.basename(audio_file_path), file.read()),
                model="whisper-large-v3-turbo",
                language="en",
                response_format="text"
            )
        user_text = str(transcription).strip()
        reply_text, action_html = execute_intent(user_text)
        audio_path = create_tts_audio(reply_text)
        return f"You said: {user_text}\n\nLemon: {reply_text}", action_html, audio_path
    except Exception as e:
        return f"Voice Error: {str(e)}", "", None

# Custom UI
custom_css = """
body { background-color: #0b0f19; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #fff; }
.gradio-container { max-width: 680px !important; margin: auto !important; }
"""

with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🍋 LEMON - Command & Control Voice Core")
    gr.Markdown("⚡ *Voice or text commands: Media, Navigation, Google, Device Time & Intelligence.*")

    with gr.Tab("Text Command"):
        txt_input = gr.Textbox(
            label="Command or Question",
            placeholder="Try: 'play Believer', 'search best AI laptops in India', 'open map nearest hospital', or 'time batao'"
        )
        send_btn = gr.Button("Execute", variant="primary")

    with gr.Tab("Voice Command (Mic / Earbud)"):
        audio_input = gr.Audio(sources=["microphone"], type="filepath", label="Speak Command")

    assistant_reply = gr.Textbox(label="Lemon Response", interactive=False)
    action_display = gr.HTML(label="Action Launcher")
    assistant_voice = gr.Audio(label="Voice Output", autoplay=True)

    send_btn.click(
        fn=handle_text_query,
        inputs=[txt_input],
        outputs=[assistant_reply, action_display, assistant_voice]
    )
    txt_input.submit(
        fn=handle_text_query,
        inputs=[txt_input],
        outputs=[assistant_reply, action_display, assistant_voice]
    )
    audio_input.change(
        fn=handle_audio_query,
        inputs=[audio_input],
        outputs=[assistant_reply, action_display, assistant_voice]
    )

# --- FastAPI REST Endpoint for Phone Earbud Automation (MacroDroid) ---
app = FastAPI()

@app.post("/voice-agent")
async def voice_agent(file: UploadFile = File(...)):
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".m4a")
    content = await file.read()
    temp_in.write(content)
    temp_in.close()

    _, _, reply_audio_path = handle_audio_query(temp_in.name)
    if reply_audio_path and os.path.exists(reply_audio_path):
        return FileResponse(reply_audio_path, media_type="audio/mpeg")
    return {"message": "Audio processed"}

# Mount Gradio
app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
