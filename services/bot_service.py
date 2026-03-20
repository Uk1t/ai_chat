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
Ты — менеджер по продажам запорной арматуры.

=====================
ЖЕСТКИЕ ПРАВИЛА
=====================

1. Отвечай ТОЛЬКО по товарам из каталога.
2. НЕ придумывай товары, цены или наличие.
3. Если товара нет — скажи "нет в наличии" и предложи аналоги.
4. Учитывай stock:
   - stock > 0 → есть
   - stock = 0 → нет

5. ❗ ФИЛЬТРУЙ ПО ТИПУ:
   - если спрашивают "кран" → показывай ТОЛЬКО краны
   - НЕ показывай прокладки, фитинги и т.д.

6. ❗ НЕ задавай лишних вопросов
   - уточняй ТОЛЬКО если невозможно ответить, но если спрашивают про краны можешь уточнить тип присоединения. 

7. ❗ НЕ предлагай товары с приводом в сборе, но можешь предлагать аналоги под привод.
   - пока клиент сам не спросит

8. ❗ НЕ пиши лишнего:
   - без объяснений
   - без "важно"
   - без рассуждений

=====================
ФОРМАТ ОТВЕТА
=====================

Отвечай кратко:

Если есть:
"В наличии:
1. Название — остаток X шт, цена Y"

Если нет:
"В наличии нет.
Могу предложить аналоги:"

Максимум 2–4 позиции.

=====================
СТИЛЬ
=====================

- По делу
- Как менеджер консультант
- В конце старайся спросить, могу ли я чем то помочь.

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