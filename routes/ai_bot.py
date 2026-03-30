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
    // Создаем iframe
    const iframe = document.createElement('iframe');
    iframe.src = 'http://72.56.23.114/widget';
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

    // Создаем круг для открытия/закрытия iframe
    const toggleButton = document.createElement('div');
    toggleButton.style.position = 'fixed';
    toggleButton.style.bottom = '20px';
    toggleButton.style.right = '20px';
    toggleButton.style.width = '60px';
    toggleButton.style.height = '60px';
    toggleButton.style.borderRadius = '50%';
    toggleButton.style.backgroundColor = '#004225';
    toggleButton.style.cursor = 'pointer';
    toggleButton.style.zIndex = '100000';
    toggleButton.style.display = 'flex';
    toggleButton.style.justifyContent = 'center';
    toggleButton.style.alignItems = 'center';
    toggleButton.style.boxShadow = '0 2px 8px rgba(0,0,0,0.3)';
    toggleButton.title = 'Открыть/Закрыть чат';
    toggleButton.innerHTML = '<span style="color:white;font-size:24px;">💬</span>';
    document.body.appendChild(toggleButton);

    // Переключение отображения iframe при клике
    toggleButton.addEventListener('click', function() {
        if (iframe.style.display === 'none') {
            iframe.style.display = 'block';
        } else {
            iframe.style.display = 'none';
        }
    });
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