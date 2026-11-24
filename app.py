
import os
import logging
import threading
import uuid
import time
import requests

from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Временное хранилище в памяти сервера
jobs = {}
lock = threading.Lock()

SYSTEM_PROMPT = """
Ты умный голосовой помощник.
Отвечай естественно, содержательно и понятно.
Учитывай контекст разговора, если он передан.
Не задавай ненужных вопросов в конце каждого ответа.
На простые вопросы отвечай кратко, на сложные подробно.
Не выдумывай факты. Если не знаешь — скажи честно.
"""

STOP_WORDS = (
    "стоп",
    "выключи ии",
    "отключи ии",
    "закончить",
    "завершить разговор",
    "выйти из режима",
)

START_WORDS = (
    "включи моего ии",
    "запусти моего ии",
    "начни разговор с ии",
    "включи помощника",
)

CHECK_WORDS = (
    "что ответил",
    "готов ли ответ",
    "покажи ответ",
    "ответил ли ии",
)


def get_session_id(data):
    session = data.get("session", {})
    return session.get("session_id") or "default"


def ask_gemini(text):
    if not API_KEY:
        raise RuntimeError("Не настроен ключ Gemini")

    url = (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{MODEL}:generateContent"
    )

    result = requests.post(
        url,
        headers={
            "x-goog-api-key": API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [{
                "role": "user",
                "parts": [{"text": text}]
            }],
            "generationConfig": {
                "maxOutputTokens": 700,
                "temperature": 0.4,
            },
        },
        timeout=35,
    )

    result.raise_for_status()
    body = result.json()

    return body["candidates"][0]["content"]["parts"][0]["text"]


def process_question(session_id, job_id, question):
    try:
        answer = ask_gemini(question)

        with lock:
            job = jobs.get(session_id)
            if job and job["id"] == job_id:
                job["status"] = "done"
                job["answer"] = answer

    except Exception:
        logging.exception("Gemini processing error")

        with lock:
            job = jobs.get(session_id)
            if job and job["id"] == job_id:
                job["status"] = "error"


def make_response(text, session_state):
    return jsonify({
        "response": {
            "text": str(text)[:1024],
            "end_session": False,
        },
        "session_state": session_state,
        "version": "1.0",
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/", methods=["GET", "POST"])
def alice():
    if request.method == "GET":
        return "Alice AI server is running!"

    data = request.get_json(silent=True) or {}

    command = data.get("request", {}).get("command", "")
    command = command.strip() if isinstance(command, str) else ""
    normalized = command.lower().strip()

    session_id = get_session_id(data)

    # Получаем состояние режима из предыдущего ответа Алисы
    state = data.get("state", {})
    session_state = state.get("session", {})
    active = session_state.get("active", False)

    # Новый запуск навыка
    if data.get("session", {}).get("new"):
        active = True

    if any(word in normalized for word in STOP_WORDS):
        session_state["active"] = False
        with lock:
            jobs.pop(session_id, None)
        return make_response(
            "Хорошо, режим моего ИИ выключен.",
            session_state,
        )

    if any(word in normalized for word in START_WORDS):
        session_state["active"] = True
        return make_response(
            "Мой ИИ включён. Спрашивай, я передам ему вопрос.",
            session_state,
        )

    if any(word in normalized for word in CHECK_WORDS):
        with lock:
            job = jobs.get(session_id)

            if not job:
                answer = "У меня пока нет сохранённого ответа."
            elif job["status"] == "working":
                answer = "Мой ИИ ещё готовит ответ. Спроси немного позже."
            elif job["status"] == "error":
                answer = "Не получилось получить ответ от Gemini. Попробуй задать вопрос ещё раз."
            else:
                answer = job["answer"]
                jobs.pop(session_id, None)

        return make_response(answer, session_state)

    if not active:
        return make_response(
            "Чтобы начать, скажи: включи моего ИИ.",
            session_state,
        )

    if not command:
        return make_response(
            "Я слушаю. Какой у тебя вопрос?",
            session_state,
        )

    if not API_KEY:
        return make_response(
            "Не настроен ключ Gemini на сервере.",
            session_state,
        )

    with lock:
        current = jobs.get(session_id)

        if current and current["status"] == "working":
            return make_response(
                "Я ещё обрабатываю предыдущий вопрос. Спроси, что ответил мой ИИ.",
                session_state,
            )

        job_id = str(uuid.uuid4())
        jobs[session_id] = {
            "id": job_id,
            "status": "working",
            "answer": "",
            "created": time.time(),
        }

    thread = threading.Thread(
        target=process_question,
        args=(session_id, job_id, command),
        daemon=True,
    )
    thread.start()

    return make_response(
        "Передала вопрос моему ИИ. Он готовит ответ. "
        "Когда захочешь проверить, скажи: что ответил мой ИИ?",
        session_state,
    )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", 10000)),
        )
    
