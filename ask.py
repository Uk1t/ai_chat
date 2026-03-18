import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from typing import List
from dotenv import load_dotenv

from services.main_data import ProductCatalogLoader

from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings

from langchain_community.vectorstores import FAISS

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
load_dotenv()
API = os.getenv("OPENAI_API_KEY")
SYSTEM_PROMPT = """
Ты — профессиональный менеджер по продажам трубопроводной арматуры.

Правила:
1. Отвечай только по товарам из каталога.
2. НЕ придумывай товары.
3. Если товара нет — предложи похожие.
4. Проверяй наличие stock.
5. Отвечай кратко как менеджер.
"""


print("📦 Загружаем каталог...")

loader = ProductCatalogLoader("test.json")
documents = loader.create_documents()

print(f"✅ Загружено товаров: {len(documents)}")


# =========================
# EMBEDDINGS
# =========================

print("🧠 Создаем embeddings...")

embeddings = OpenAIEmbeddings(
    openai_api_key=API
)

# =========================
# VECTOR DB
# =========================

if os.path.exists("catalog_index"):

    print("📂 Загружаем готовый индекс")

    vectorstore = FAISS.load_local(
        "catalog_index",
        embeddings,
        allow_dangerous_deserialization=True
    )

else:

    print("⚙ Создаем новый индекс")

    vectorstore = FAISS.from_documents(
        documents,
        embeddings
    )

    vectorstore.save_local("catalog_index")

print("✅ Векторная БД готова")


# =========================
# LLM
# =========================

llm = ChatOpenAI(
    model="gpt-5-mini",
    temperature=0.2,
    openai_api_key=API,
)


chat_history: List = []


# =========================
# SEARCH
# =========================

def search_products(question: str):

    results = vectorstore.similarity_search(
        question,
        k=20
    )

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


# =========================
# ASSISTANT
# =========================

def ask_assistant(question: str):

    product_context = search_products(question)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        SystemMessage(content=f"Найденные товары:\n{product_context}")
    ]

    messages.extend(chat_history[-6:])

    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)

    chat_history.append(HumanMessage(content=question))
    chat_history.append(AIMessage(content=response.content))

    return response.content


# =========================
# CLI
# =========================

if __name__ == "__main__":

    print("🤖 AI менеджер готов")

    while True:

        q = input("\n❓ Вопрос: ")

        if q.lower() in ["exit", "quit"]:
            break

        try:

            answer = ask_assistant(q)

            print("\n🤖", answer)

        except Exception as e:

            print("⚠ Ошибка:", e)