import os
import gradio as gr
from groq import Groq
from gtts import gTTS
import tempfile

# 1. API Client Setup
api_key = os.environ.get("GROQ_API_KEY", "").strip()
client = Groq(api_key=api_key) if api_key else None

# Active models on Groq
MODELS_TO_TRY = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]

def ask_lemon(user_query):
    if not user_query or not user_query.strip():
        return "Kripya koi sawal likhiye!", None

    if not client:
        return "Error: GROQ_API_KEY environment variable Render par set nahi hai!", None

    # Clean default system prompt bina kisi extra input ke
    system_prompt = (
        "You are Lemon, a friendly, intelligent, and helpful AI assistant. "
        "Keep your answers concise, conversational, and direct."
    )

    response_text = ""
    # Try active models
    for model_id in MODELS_TO_TRY:
        try:
            completion = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                temperature=0.7,
                max_tokens=500
            )
            response_text = completion.choices[0].message.content
            break
        except Exception as e:
            if model_id == MODELS_TO_TRY[-1]:
                response_text = f"Groq Error: {str(e)}"

    # Audio generation using gTTS
    audio_path = None
    try:
        if response_text and not response_text.startswith("Groq Error"):
            tts = gTTS(text=response_text, lang='en', slow=False)
            temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tts.save(temp_audio.name)
            audio_path = temp_audio.name
    except Exception:
        audio_path = None

    return response_text, audio_path

# Custom UI
custom_css = """
body { background-color: #0b0f19; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
.gradio-container { max-width: 650px !important; margin: auto !important; }
"""

with gr.Blocks(css=custom_css, theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🍋 LEMON - Personal AI")
    gr.Markdown("### Lemon is ready to assist you.")

    user_msg = gr.Textbox(
        label="Aapka Sawal", 
        placeholder="Type your message here...", 
        lines=2
    )
    send_btn = gr.Button("Send", variant="primary")

    assistant_reply = gr.Textbox(label="Assistant Response", interactive=False)
    assistant_voice = gr.Audio(label="Lemon Voice", autoplay=True)

    send_btn.click(
        fn=ask_lemon,
        inputs=[user_msg],
        outputs=[assistant_reply, assistant_voice]
    )
    user_msg.submit(
        fn=ask_lemon,
        inputs=[user_msg],
        outputs=[assistant_reply, assistant_voice]
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    demo.launch(server_name="0.0.0.0", server_port=port)
