import os
from typing import Dict, List
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from openai import OpenAI

load_dotenv()

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — профессиональный менеджер по продажам трубопроводной арматуры.

Ты отвечаешь ТОЛЬКО на основе данных с сайта newkey.ru

ПРАВИЛА:
1. Если товар найден — дай четкий ответ (наличие, цена, характеристики)
2. Если несколько товаров — перечисли кратко и задай уточнение
3. Если нет в наличии — предложи аналог
4. НЕ придумывай товары
5. Если информации мало — предложи связаться с менеджером
6. Отвечай как менеджер, кратко и по делу
7. Если информация не касается запорной арматуры, ты предлагаешь по этому вопросу связаться с менеджером.
8. Ты консультант, не предлагай резервировать товар или оставлять заявки.
"""

# =====================================================
# 🤖 LLM
# =====================================================
llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =====================================================
# 🔎 ПОИСК ПО САЙТУ (УЛУЧШЕННЫЙ)
# =====================================================
def search_site(question: str) -> str:
    try:
        query = f"site:newkey.ru {question} (товар OR купить OR артикул)"

        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=query
        )

        result = ""
        for item in response.output:
            if item.type == "message":
                for c in item.content:
                    if c.type == "output_text":
                        result += c.text

        return result.strip()

    except Exception:
        return ""

# =====================================================
# 🧠 ГЕНЕРАЦИЯ ОТВЕТА
# =====================================================
def generate_answer(question: str, site_text: str, history: List) -> str:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"📄 ДАННЫЕ С САЙТА newkey.ru:\n{site_text[:5000]}")
    ]

    messages.extend(history[-6:])
    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)
    return response.content

# =====================================================
# 💬 ИСТОРИЯ
# =====================================================
chat_histories: Dict[str, List] = {}
MAX_HISTORY = 6

# =====================================================
# 🚀 ОСНОВНАЯ ЛОГИКА (ПРОСТАЯ И СТАБИЛЬНАЯ)
# =====================================================
def ask_assistant(user_id: str, question: str) -> str:
    history = chat_histories.get(user_id, [])

    # 🔎 ВСЕГДА ИЩЕМ НА САЙТЕ
    site_text = search_site(question)

    if site_text and len(site_text) > 80:
        answer = generate_answer(question, site_text, history)
    else:
        answer = "Не удалось найти информацию на сайте. Могу передать вас менеджеру."

    # сохраняем историю
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=answer))
    chat_histories[user_id] = history[-MAX_HISTORY * 2:]

    return answer

# =====================================================
# 🖥️ CLI
# =====================================================
if __name__ == "__main__":
    print("🤖 Бот (поиск по сайту newkey.ru) готов")

    user_id = "test_user"

    while True:
        q = input("\n❓ ")
        if q.lower() in ("exit", "quit"):
            break

        print("\n🤖", ask_assistant(user_id, q))