import os
import json
from datetime import datetime
from typing import List, Dict
from dotenv import load_dotenv
import openai

# =====================================================
# 🔐 ENV
# =====================================================
load_dotenv()

YANDEX_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_CLOUD_FOLDER_ID")

if not YANDEX_API_KEY:
    raise ValueError("YANDEX_CLOUD_API_KEY не найден")

if not YANDEX_FOLDER_ID:
    raise ValueError("YANDEX_CLOUD_FOLDER_ID не найден")

# =====================================================
# 🤖 CLIENT
# =====================================================
client = openai.OpenAI(
    api_key=YANDEX_API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1"
)

# =====================================================
# 🧠 SYSTEM PROMPT
# =====================================================
SYSTEM_PROMPT = """
Ты — менеджер по продажам трубопроводной арматуры компании Newkey.

Ты ОБЯЗАН использовать инструмент web_search для поиска на сайте newkey.ru перед ответом.
Без использования web_search отвечать запрещено.

ВАЖНО:
Ты работаешь ТОЛЬКО с данными сайта newkey.ru
Любая информация вне этих данных запрещена.

Если пользователь указывает артикул — найди точную страницу товара.

Строго:
- Не придумывать товары, цены, наличие, артикулы
- Не делать предположения
- Если нет цены → "цена по согласованию с менеджером"
- Кратко

Формат:

Название товара: ...
Характеристики: ...
Цена: ...

Если несколько товаров — не более 5
"""

# =====================================================
# ❓ QUESTIONS
# =====================================================
QUESTIONS: List[str] = [
    "Меня интересует затвор или дисковый кран под давление 70 бар",
    "В чем отличие Привод пневматический двухсторонний AT105D Привод пневматический двухсторонний AT 83D?",
    "Интересует длина NK-NM15/4",
    "Есть ли межфланцевый одностворчатый обратные клапана с пружиной?",
    "Чем отличается пневмопривод ат52d от at63d?",
    "Нужна вентильная задвижка диам 150 мм на 15 атм",
    "Здравствуйте необходимы краны 1/4 муфтовые на газ,какой артикул подходит?"
]

# =====================================================
# 🧠 MODELS
# =====================================================
MODELS: Dict[str, str] = {
    "deepseek": "deepseek-v32",
    "yandex_pro_5_1": "yandexgpt/rc",
    "yandex_pro_5": "yandexgpt/latest",
    "yandex_lite": "yandexgpt-lite",
    "qwen_235b": "qwen3-235b-a22b-fp8/latest",
    "qwen_35b": "qwen3.5-35b-a3b-fp8",
    "gemma_27b": "gemma-3-27b-it/latest"
}

# =====================================================
# 🧠 GENERATE ANSWER
# =====================================================
def generate_answer(question: str, model_path: str) -> str:
    prompt = f"""
{SYSTEM_PROMPT}

Вопрос:
Подумай и ответь: {question} на сайте newkey.ru
"""

    try:
        response = client.responses.create(
            model=f"gpt://{YANDEX_FOLDER_ID}/{model_path}",
            input=prompt,
            tools=[
                {
                    "type": "web_search",
                    "filters": {
                        "allowed_domains": ["newkey.ru"]
                    }
                }
            ],
            temperature=0.2,
            max_output_tokens=800
        )

        return response.output_text.strip()

    except Exception as e:
        return f"❌ Ошибка: {e}"

# =====================================================
# 🚀 TEST + SAVE
# =====================================================
def test_and_save():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    txt_filename = f"results_{timestamp}.txt"
    json_filename = f"results_{timestamp}.json"

    results = []

    with open(txt_filename, "w", encoding="utf-8") as txt_file:
        for question in QUESTIONS:
            header = f"\n{'='*100}\n❓ ВОПРОС:\n{question}\n{'='*100}\n"
            print(header)
            txt_file.write(header)

            for model_name, model_path in MODELS.items():
                print(f"\n🔹 МОДЕЛЬ: {model_name}")
                txt_file.write(f"\n🔹 МОДЕЛЬ: {model_name}\n")

                answer = generate_answer(question, model_path)

                print("📌 ОТВЕТ:")
                print(answer)
                print("-" * 80)

                txt_file.write("📌 ОТВЕТ:\n")
                txt_file.write(answer + "\n")
                txt_file.write("-" * 80 + "\n")

                results.append({
                    "question": question,
                    "model": model_name,
                    "answer": answer
                })

    # сохраняем JSON
    with open(json_filename, "w", encoding="utf-8") as json_file:
        json.dump(results, json_file, ensure_ascii=False, indent=2)

    print(f"\n✅ Сохранено:")
    print(f"TXT: {txt_filename}")
    print(f"JSON: {json_filename}")

# =====================================================
# ▶️ RUN
# =====================================================
if __name__ == "__main__":
    print("🚀 Запуск теста моделей...\n")
    test_and_save()