(function () {
    const BASE_URL = "http://72.56.23.114";

    async function init() {

        // 🔥 1. загружаем HTML с сервера
        const res = await fetch(`${BASE_URL}/widget`);
        const html = await res.text();

        const wrapper = document.createElement("div");
        wrapper.innerHTML = html;
        document.body.appendChild(wrapper);

        // 🔥 2. находим элементы из шаблона
        const chat = document.getElementById("chat-messages");
        const input = document.getElementById("chat-input");
        const btn = document.getElementById("chat-send");

        let USER_ID = localStorage.getItem("chat_user_id");

        if (!USER_ID) {
            USER_ID = "guest_" + Math.random().toString(36).substring(2, 10);
            localStorage.setItem("chat_user_id", USER_ID);
        }

        async function loadHistory() {
            const res = await fetch(`${BASE_URL}/ai/history?user_id=${USER_ID}`);
            const data = await res.json();

            const history = data.history || [];

            history.forEach(msg => {
                addMessage(msg.role === "user" ? "Вы" : "Бот", msg.content);
            });
        }

        function addMessage(who, text) {
            const div = document.createElement("div");
            div.textContent = `${who}: ${text}`;
            div.style.color = "white";
            div.style.maxWidth = '85%'
            div.style.marginLeft = who === "Вы" ? "auto" : "0"
            div.style.marginBottom = '5px'
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            addMessage("Вы", text);
            input.value = "";

            const res = await fetch(`${BASE_URL}/ai/ask`, {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({
                    user_id: USER_ID,
                    description: text
                })
            });

            const data = await res.json();
            addMessage("Бот", data.answer);
        }

        btn.onclick = sendMessage;
        input.addEventListener("keypress", e => {
            if (e.key === "Enter") sendMessage();
        });
        await loadHistory();
    }

    init();
})();