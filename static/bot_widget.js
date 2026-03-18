// bot_widget.js
(function() {
    const BOT_URL = "http://127.0.0.1:8000/ai"; // сюда твой FastAPI сервер

    // Создаём контейнер чата
    const chatBox = document.createElement("div");
    chatBox.id = "ai-bot-widget";
    chatBox.style.position = "fixed";
    chatBox.style.bottom = "20px";
    chatBox.style.right = "20px";
    chatBox.style.width = "300px";
    chatBox.style.height = "400px";
    chatBox.style.border = "1px solid #ccc";
    chatBox.style.background = "#fff";
    chatBox.style.zIndex = 9999;
    chatBox.style.padding = "10px";
    chatBox.style.display = "flex";
    chatBox.style.justifyContent = 'end'
    chatBox.style.flexDirection = "column";

    // Блок сообщений
    const chat = document.createElement("div");
    chat.id = "chat-messages";
    chat.style.flex = "1";
    chat.style.overflowY = "auto";
    chat.style.marginBottom = "10px";

    // Input + кнопка
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Ваш вопрос...";
    input.name = 'input'
    input.style.minWidth = 'max-content'
    input.style.flex = "0";
    input.style.width = "calc(100% - 60px)";

    const btn = document.createElement("button");
    btn.innerText = "Отправить";

    const inputWrapper = document.createElement("div");
    inputWrapper.style.display = "flex";
    inputWrapper.appendChild(input);
    inputWrapper.appendChild(btn);

    chatBox.appendChild(chat);
    chatBox.appendChild(inputWrapper);
    document.body.appendChild(chatBox);

    const USER_ID = "guest_" + Math.floor(Math.random() * 100000);

    function addMessage(who, text) {
        const div = document.createElement("div");
        div.textContent = `${who}: ${text}`;
        div.style.margin = "5px 0";
        div.style.color = who === "Вы" ? "blue" : "green";
        chat.appendChild(div);
        chat.scrollTop = chat.scrollHeight;
    }

    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;
        addMessage("Вы", text);
        input.value = "";

        const res = await fetch(`${BOT_URL}/ask`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: USER_ID, description: text })
        });
        const data = await res.json();
        addMessage("Бот", data.answer);
    }

    btn.onclick = sendMessage;
    input.addEventListener("keypress", e => { if(e.key === "Enter") sendMessage(); });
})();

async function clearChat() {
    await fetch(`/ai/clear?user_id=${USER_ID}`, { method: "POST" });
    document.getElementById("chat").innerHTML = "";
}