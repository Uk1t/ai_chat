import os

from fastapi import APIRouter, Request, HTTPException
from langchain_core.messages import HumanMessage
from fastapi.responses import Response
from slowapi import Limiter
from slowapi.util import get_remote_address
import time
import secrets

from schemas import Question, Answer
from services.bot_service import ask_assistant, chat_histories

router = APIRouter(prefix="/ai", tags=["AI bot"])

# =========================
# 🔒 CONFIG
# =========================
BASE_URL = "http://72.56.23.114"
SECRET_TOKEN = os.getenv("SECRET_TOKEN")
ALLOWED_ORIGINS = ["http://72.56.23.114"]

limiter = Limiter(key_func=get_remote_address)

# лимиты пользователей
user_limits = {}

# =========================
# 🧠 WIDGET JS
# =========================
@router.get("/widget.js")
def widget_js():
    token = secrets.token_hex(16)

    return Response(
        content=f"""
(function() {{
    const BASE_URL = "{BASE_URL}";
    const TOKEN = "{token}";

    const iframe = document.createElement('iframe');
    iframe.src = BASE_URL + '/widget?token=' + TOKEN;
    iframe.style.display = 'none';
    iframe.style.position = 'fixed';
    iframe.style.bottom = '20px';
    iframe.style.right = '20px';
    iframe.style.width = '400px';
    iframe.style.height = '600px';
    iframe.style.border = 'none';
    iframe.style.zIndex = '99999';
    iframe.id = 'ai-bot-iframe';
    document.body.appendChild(iframe);

    function createButton(parent) {{
        if (document.getElementById('ai-widget-toggle')) return;

        const toggleButton = document.createElement('div');
        toggleButton.id = 'ai-widget-toggle';

        toggleButton.style.width = '60px';
        toggleButton.style.height = '60px';
        toggleButton.style.borderRadius = '50%';
        toggleButton.style.backgroundColor = '#004225';
        toggleButton.style.cursor = 'pointer';
        toggleButton.style.display = 'flex';
        toggleButton.style.justifyContent = 'center';
        toggleButton.style.alignItems = 'center';
        toggleButton.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
        toggleButton.style.margin = '5px';

        toggleButton.innerHTML = '<img src="{BASE_URL}/static/icons/ai.png" width="30px" style="filter: brightness(0) invert(1);">';

        toggleButton.addEventListener('click', () => {{
            iframe.style.display = iframe.style.display === 'none' ? 'block' : 'none';
        }});

        parent.appendChild(toggleButton);
    }}

    function waitForB24() {{
        const target = document.querySelector('.b24-widget-button-social');
        if (target) {{
            createButton(target);
        }} else {{
            setTimeout(waitForB24, 500);
        }}
    }}

    window.addEventListener("message", (event) => {{
        if (event.data?.action === "close-ai-widget") {{
            iframe.style.display = "none";
        }}
    }});

    window.AI_WIDGET_TOKEN = TOKEN;

    waitForB24();
}})();
        """,
        media_type="application/javascript"
    )

# =========================
# 🔒 ПРОВЕРКИ
# =========================
def check_origin(request: Request):
    origin = request.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Forbidden origin")

def check_token(request: Request):
    token = request.headers.get("X-Widget-Token")
    if not token:
        raise HTTPException(status_code=403, detail="No token")

def check_user_limit(user_id: str):
    user_limits.setdefault(user_id, [])
    now = time.time()

    # оставляем только последние 60 секунд
    user_limits[user_id] = [t for t in user_limits[user_id] if now - t < 60]

    if len(user_limits[user_id]) > 10:
        raise HTTPException(status_code=429, detail="Too many requests")

    user_limits[user_id].append(now)

# =========================
# 🤖 ASK
# =========================
@router.post("/ask", response_model=Answer)
@limiter.limit("10/minute")
def ask_bot(question: Question, request: Request):

    check_origin(request)
    check_token(request)
    check_user_limit(question.user_id)

    # анти-спам
    if len(question.description) > 500:
        raise HTTPException(400, "Message too long")

    answer_text = ask_assistant(
        user_id=question.user_id,
        question=question.description
    )

    return {"answer": answer_text}

# =========================
# 📜 HISTORY
# =========================
@router.get("/history")
def get_history(user_id: str):
    history = chat_histories.get(user_id, [])

    return {
        "history": [
            {
                "role": "user" if isinstance(m, HumanMessage) else "bot",
                "content": m.content
            }
            for m in history
        ]
    }

# =========================
# 🧹 CLEAR
# =========================
@router.post("/clear")
def clear_history(user_id: str):
    chat_histories[user_id] = []
    return {"status": "ok"}