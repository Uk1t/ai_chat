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

ПРАВИЛА:
1. Используй только каталог. Ничего не придумывай.
2. Учитывай наличие:
   - >0 — есть
   - 0 — нет
3. Если нет — предложи аналоги.
4. Фильтруй по запросу:
   - "кран" → только краны
   - учитывай уточнения (DN, муфтовый и т.д.)
5. Учитывай предыдущие сообщения клиента.
6. Не предлагай товары с приводом.
7. Не задавай лишних вопросов.
8. Пиши коротко.

ФОРМАТ:
В наличии:
1. Название — остаток X, цена Y

Максимум 3 позиции.
Без лишнего текста.
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