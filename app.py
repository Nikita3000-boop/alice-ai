import os
import logging
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

@app.route("/", methods=["GET", "POST"])
def alice():
    if request.method == "GET":
        return "Alice AI server is running!"

    data = request.get_json(silent=True) or {}
    command = data.get("request", {}).get("command", "")
    command = command.strip() if isinstance(command, str) else ""

    answer = "Привет! Спроси меня о чём-нибудь."

    if command:
        if not API_KEY:
            answer = "Не настроен ключ Gemini."
        else:
            try:
                url = (
                    "https://generativelanguage.googleapis.com/"
                    f"v1beta/models/{MODEL}:generateContent"
                )

                result = requests.post(
                    url,
                    headers={
                        "x-goog-api-key": API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={
                        "systemInstruction": {
                            "parts": [{
                                "text": "Ты голосовой помощник. "
                                        "Отвечай по-русски, кратко и понятно."
                            }]
                        },
                        "contents": [{
                            "parts": [{"text": command}]
                        }],
                        "generationConfig": {
                            "maxOutputTokens": 40,
                            "temperature": 0.2
                        }
                    },
                    timeout=4
                )

                result.raise_for_status()
                answer = result.json()["candidates"][0]["content"]["parts"][0]["text"]

            except requests.exceptions.Timeout:
                logging.exception("Gemini timeout")
                answer = "Gemini не успел ответить."
            except requests.exceptions.HTTPError:
                logging.error(
                    "Gemini HTTP %s: %s",
                    result.status_code,
                    result.text[:1000]
                )
                answer = "Ошибка обращения к Gemini."
            except Exception:
                logging.exception("Gemini error")
                answer = "Ошибка обработки ответа Gemini."

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
    
