from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from fastapi.responses import Response

from schemas import Question, Answer
from services.bot_service import ask_assistant, chat_histories

router = APIRouter(prefix="/ai", tags=["AI bot"])


@router.get("/widget.js")
def widget_js():
    return Response(
        content="""
(function() {
    const BASE_URL = "http://192.168.0.1:8000"; // твой сервер

    // Создаем iframe
    const iframe = document.createElement('iframe');
    iframe.src = BASE_URL + '/widget';
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

    // Функция для создания кнопки
    function createButton(parent) {
        if (document.getElementById('ai-widget-toggle')) return; // уже есть

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
        toggleButton.innerHTML = '<img src="http://72.56.23.114/static/icons/ai.png" alt="logo_ai" width="30px" style="filter: brightness(0) invert(1);">';

        // Переключение iframe
        toggleButton.addEventListener('click', () => {
            iframe.style.display = iframe.style.display === 'none' ? 'block' : 'none';
            document.querySelector('html').classList.remove('crm-widget-button-mobile')
        });

        parent.appendChild(toggleButton);
    }

    // Ждем появления блока b24-widget-button-social
    function waitForB24() {
        const target = document.querySelector('.b24-widget-button-social');
        if (target) {
            createButton(target);
        } else {
            // проверяем каждые 500мс
            setTimeout(waitForB24, 500);
        }
    }
    window.addEventListener("message", (event) => {
    if (event.data?.action === "close-ai-widget") {
        const iframe = document.getElementById("ai-bot-iframe");
        if (iframe) iframe.style.display = "none";
    }
});

    waitForB24();
})();
        """,
        media_type="application/javascript"
    )

@router.post("/ask", response_model=Answer)
def ask_bot(question: Question):
    answer_text = ask_assistant(user_id=question.user_id, question=question.description)
    return {"answer": answer_text}

@router.get("/history")
def get_history(user_id: str):
    """
    Возвращает историю чата для конкретного пользователя
    """
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

@router.post("/clear")
def clear_history(user_id: str):
    chat_histories[user_id] = []
    return {"status": "ok"}