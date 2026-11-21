import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

BASE_URL = os.getenv(
    "STARIMG_BASE_URL",
    "https://ai.starimg.ru/v1"
).rstrip("/")

API_KEY = os.getenv("STARIMG_API_KEY")
MODEL = os.getenv("STARIMG_MODEL")


@app.route("/", methods=["GET", "POST"])
def alice():
    if request.method == "GET":
        return "Alice AI server is running!"

    data = request.get_json(silent=True) or {}
    command = data.get("request", {}).get("command", "").strip()

    answer = "Привет! Спроси меня о чём-нибудь."

    if command:
        if not API_KEY or not MODEL:
            answer = "ИИ пока не настроен. Попробуй позже."
        else:
            try:
                result = requests.post(
                    BASE_URL + "/chat/completions",
                    headers={
                        "Authorization": f"Bearer {API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": MODEL,
                        "messages": [
                            {
                                "role": "system",
                                "content": "Ты голосовой помощник. Отвечай по-русски, кратко и понятно."
                            },
                            {
                                "role": "user",
                                "content": command
                            }
                        ]
                    },
                    timeout=20
                )

                result.raise_for_status()
                answer = result.json()["choices"][0]["message"]["content"]

            except Exception:
                answer = "Не получилось получить ответ от ИИ. Попробуй ещё раз."

    return jsonify({
        "response": {
            "text": str(answer)[:1024],
            "end_session": False
        },
        "version": "1.0"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
