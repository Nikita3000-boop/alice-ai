
import os
import logging
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
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
    command = data.get("request", {}).get("command", "")
    command = command.strip() if isinstance(command, str) else ""

    answer = "Привет! Спроси меня о чём-нибудь."

    if command:
        if not API_KEY or not MODEL:
            answer = "ИИ пока не настроен."
            logging.error("Missing API_KEY or MODEL")
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
                                "content": "Отвечай по-русски, кратко и понятно."
                            },
                            {
                                "role": "user",
                                "content": command
                            }
                        ],
                        "max_tokens": 80
                    },
                    timeout=3
                )

                result.raise_for_status()
                answer = result.json()["choices"][0]["message"]["content"]

            except requests.exceptions.Timeout:
                logging.exception("Starimg request timed out")
                answer = "ИИ не успел ответить. Попробуй ещё раз."

            except requests.exceptions.HTTPError:
                logging.error(
                    "Starimg HTTP error %s: %s",
                    result.status_code,
                    result.text[:1000]
                )
                answer = "Ошибка обращения к ИИ."

            except Exception:
                logging.exception("Unexpected Starimg error")
                answer = "Ошибка обработки ответа ИИ."

    return jsonify({
        "response": {
            "text": str(answer)[:1024],
            "end_session": False
        },
        "version": "1.0"
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000))
    )
    
