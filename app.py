import gradio as gr
from groq import Groq
from gtts import gTTS
import os
import re
from datetime import datetime
from duckduckgo_search import DDGS

# API key Render environment variables se aayegi
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
client = Groq(api_key=GROQ_API_KEY)

def get_web_info(query):
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=1))
            if results:
                return results[0]['body'][:250]
    except Exception:
        return ""
    return ""

def chat_with_lemon(user_message, client_name, assistant_custom_name):
    if not user_message.strip():
        return "", None

    user_name = client_name.strip() if client_name.strip() else "Sir/Ma'am"
    bot_name = assistant_custom_name.strip() if assistant_custom_name.strip() else "Lemon"

    now = datetime.now()
    current_time_str = now.strftime("%A, %d %B %Y, %I:%M %p")

    search_keywords = ["today", "aaj", "current", "news", "weather", "score", "latest", "date", "tarikh"]
    extra_context = ""
    if any(k in user_message.lower() for k in search_keywords):
        data = get_web_info(user_message)
        if data:
            extra_context = f"\nLive Internet Data: {data}"

    system_prompt = (
        f"Your name is {bot_name}, created by Utkarsh Bandhu. "
        f"You are dedicated, deeply loyal, and helpful to your client, {user_name}. "
        f"Address the client politely as {user_name}. "
        f"If asked who made you, proudly say you were created by Utkarsh Bandhu. "
        f"Today's date and time is: {current_time_str}. {extra_context}\n"
        f"Give factual, direct answers in 1 to 2 sharp sentences only. No roleplay or filler words."
    )

    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        model="llama-3.1-8b-instant",
        temperature=0.3,
        max_tokens=60
    )

    response = chat_completion.choices[0].message.content.strip()

    for delimiter in ["\nYou:", "You:", "\nUser:", "User:", f"\n{bot_name}:", "<|user|>", "\n\n"]:
        if delimiter in response:
            response = response.split(delimiter)[0].strip()

    response = re.sub(r'\(.*?\)', '', response)
    response = re.sub(rf'(?i)^{bot_name}:\s*', '', response).strip()

    sentences = re.split(r'(?<=[.!?]) +', response)
    if len(sentences) > 2:
        response = " ".join(sentences[:2])

    if not response:
        response = f"Ji {user_name}, main aapki seva me hazir hoon."

    audio_path = "lemon_reply.mp3"
    try:
        tts = gTTS(text=response, lang='hi')
        tts.save(audio_path)
    except Exception:
        tts = gTTS(text=response, lang='en', tld='co.in')
        tts.save(audio_path)

    return response, audio_path

def start_app(c_name, a_name):
    final_user = c_name.strip() if c_name.strip() else "Client"
    final_bot = a_name.strip() if a_name.strip() else "Lemon"
    welcome_text = f"### Welcome {final_user}! {final_bot} is ready to assist you.\n*Created with precision by Utkarsh Bandhu*"
    return (
        gr.update(visible=False),
        gr.update(visible=True),
        welcome_text,
        final_user,
        final_bot
    )

with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🍋 LEMON - Personal AI")
    
    with gr.Column(visible=True) as onboarding_box:
        gr.Markdown("### 👋 Welcome! Let's get to know each other.")
        c_input = gr.Textbox(label="Aapka Naam (Your Name)", placeholder="Enter your name...", value="Utkarsh")
        a_input = gr.Textbox(label="Assistant ka Naam", placeholder="What would you like to call me?", value="Lemon")
        start_btn = gr.Button("Save & Start Talking 🚀", variant="primary")

    with gr.Column(visible=False) as chat_box:
        header_text = gr.Markdown("")
        with gr.Accordion("⚙️ Settings (Change Names)", open=False):
            sett_c_name = gr.Textbox(label="Client Name", value="Utkarsh")
            sett_a_name = gr.Textbox(label="Assistant Name", value="Lemon")
        
        user_input = gr.Textbox(lines=1, placeholder="Apne assistant se sawal poochein...", label="Aapka Sawal")
        send_btn = gr.Button("Send", variant="primary")
        
        with gr.Row():
            lemon_output = gr.Textbox(label="Assistant Response")
            lemon_audio = gr.Audio(label="Voice Reply", autoplay=True)

    start_btn.click(
        start_app,
        inputs=[c_input, a_input],
        outputs=[onboarding_box, chat_box, header_text, sett_c_name, sett_a_name]
    )

    send_btn.click(
        chat_with_lemon,
        inputs=[user_input, sett_c_name, sett_a_name],
        outputs=[lemon_output, lemon_audio]
    )

port = int(os.environ.get("PORT", 7860))
demo.launch(server_name="0.0.0.0", server_port=port)
