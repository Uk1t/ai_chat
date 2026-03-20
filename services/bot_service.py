import os
from typing import List, Dict
from dotenv import load_dotenv


from services.main_data import ProductCatalogLoader
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Не задан OPENAI_API_KEY в окружении!")


SYSTEM_PROMPT = """
Ты — профессиональный менеджер по продажам запорной арматуры.

Твоя задача — помогать клиенту подобрать товар ТОЛЬКО из доступного каталога.

=====================
ОСНОВНЫЕ ПРАВИЛА
=====================

1. ❗ Используй ТОЛЬКО товары, которые есть в переданном каталоге (context).
2. ❗ НИКОГДА не придумывай товары, характеристики, цены или наличие.
3. ❗ Если товара нет в каталоге — прямо скажи об этом и предложи похожие из найденных.
4. ❗ Всегда учитывай наличие (stock):
   - если stock = 0 → товара нет в наличии
   - предлагай аналоги, если они есть

5. ❗ НЕ предлагай товары с приводом:
   - пока пользователь явно не подтвердил, что нужен привод
   - если есть сомнение — задай уточняющий вопрос

6. ❗ НЕ придумывай цены:
   - используй только те, что есть в данных
   - если цены нет → не указывай её

7. ❗ НЕ предлагай:
   - резервирование
   - выставление счета
   - оформление заказа

8. ❗ Если информации недостаточно:
   - задай уточняющий вопрос
   - ИЛИ предложи связаться с менеджером

9. ❗ Если не уверен в ответе:
   - честно скажи, что нужно уточнение
   - предложи помощь менеджера

=====================
ЛОГИКА ОТВЕТА
=====================

1. Отвечай КРАТКО и по делу (как живой менеджер).
2. Если найдено несколько товаров — предложи 2–5 лучших вариантов.
3. Всегда указывай:
   - название
   - DN (если есть)
   - остаток
   - цену (если есть)

4. Если есть аналоги:
   - используй их как альтернативу

5. Если запрос общий:
   - уточни параметры (DN, тип, среда, давление и т.д.)

=====================
СТИЛЬ ОБЩЕНИЯ
=====================

- Пиши кратко, без лишней воды
- По-деловому, но дружелюбно
- Без "я как ИИ"
- Без длинных объяснений
- Форматируй списками, если предлагаешь варианты

=====================
ПРИМЕРЫ ПОВЕДЕНИЯ
=====================

❌ ПЛОХО:
"Есть отличный кран DN15, стоит примерно 1000 руб"

✅ ХОРОШО:
"Есть в наличии:
1. Кран шаровой DN15 — остаток 12 шт, цена 980 руб

Также могу предложить аналоги."

❌ ПЛОХО:
(придумал товар)

✅ ХОРОШО:
"Такого товара в наличии нет. Могу предложить похожие варианты:"

=====================
ГЛАВНОЕ
=====================

Ты не консультант в общем — ты менеджер по КОНКРЕТНОМУ каталогу.

Любая информация вне каталога — запрещена.
"""

# =========================
# Загрузка каталога и FAISS
# =========================
loader = ProductCatalogLoader("products_ai.json")
documents = loader.create_documents()

embeddings = OpenAIEmbeddings(openai_api_key=os.getenv("OPENAI_API_KEY"))

if os.path.exists("catalog_index"):
    vectorstore = FAISS.load_local("catalog_index", embeddings, allow_dangerous_deserialization=True)
else:
    vectorstore = FAISS.from_documents(documents, embeddings)
    vectorstore.save_local("catalog_index")

# =========================
# LLM
# =========================
llm = ChatOpenAI(model="gpt-5-mini", temperature=0.2, openai_api_key=os.getenv("OPENAI_API_KEY"))

# =========================
# История чата по пользователям
# =========================
# Ключ — user_id (str), значение — список сообщений
chat_histories: Dict[str, List] = {}

MAX_HISTORY = 6  # сколько последних сообщений хранить для контекста

# =========================
# Функции
# =========================
def search_products(question: str) -> str:
    results = vectorstore.similarity_search(question, k=20)
    context = []
    for r in results:
        p = r.metadata
        line = (
            f"{p.get('name')} | "
            f"Тип: {p.get('product_type')} | "
            f"DN: {p.get('dn')} | "
            f"Цена: {p.get('price')} | "
            f"Остаток: {p.get('stock')}"
        )
        context.append(line)
    return "\n".join(context)

def ask_assistant(user_id: str, question: str) -> str:
    """
    user_id: уникальный идентификатор пользователя (например, telegram_id или session_id)
    question: вопрос пользователя
    """
    product_context = search_products(question)

    # Получаем историю пользователя или создаем новую
    history = chat_histories.get(user_id, [])

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Найденные товары:\n{product_context}")
    ]

    # Добавляем последние сообщения пользователя в контекст
    messages.extend(history[-MAX_HISTORY:])
    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)

    # Обновляем историю пользователя
    history.append(HumanMessage(content=question))
    history.append(AIMessage(content=response.content))
    chat_histories[user_id] = history

    return response.content