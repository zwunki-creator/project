import sys
import os

# === ПЕРЕХВАТ ОШИБОК В ФАЙЛ ===
error_log = open('error.log', 'a')
sys.stderr = error_log
sys.stdout = error_log

print("=== ПРИЛОЖЕНИЕ ЗАПУЩЕНО ===", flush=True)

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import sqlite3
import traceback

app = Flask(__name__)
CORS(app)

DATABASE = 'poll.db'

def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS poll_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                votes INTEGER DEFAULT 1
            )
        ''')
        cursor.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS idx_answer ON poll_data(answer)
        ''')
        conn.commit()
        conn.close()
        print("DB: инициализация успешна", flush=True)
    except Exception as e:
        print(f"DB: ОШИБКА инициализации: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/init', methods=['GET'])
def init_poll():
    try:
        print("API: /api/init вызван", flush=True)
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM poll_data")
        count = cursor.fetchone()[0]
        if count == 0:
            default_answers = ["Любовь", "Поддержка", "Забота", "Уважение", "Опора", "Уют", "Понимание", "Тепло"]
            for answer in default_answers:
                cursor.execute("INSERT INTO poll_data (question, answer, votes) VALUES (?, ?, 1)", 
                              ("Что для вас семья?", answer))
            conn.commit()
            print("DB: добавлены начальные ответы", flush=True)
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/init: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/data', methods=['GET'])
def get_data():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT question, answer, votes FROM poll_data")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return jsonify({"question": "Что для вас семья?", "answers": {}})
        question = rows[0]['question']
        answers = {row['answer']: row['votes'] for row in rows}
        return jsonify({"question": question, "answers": answers})
    except Exception as e:
        print(f"API: ОШИБКА в /api/data: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/vote', methods=['POST'])
def vote():
    try:
        data = request.json
        answer = data.get('answer', '').strip()
        if not answer:
            return jsonify({"error": "Ответ не может быть пустым"}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT votes FROM poll_data WHERE answer = ?", (answer,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE poll_data SET votes = votes + 1 WHERE answer = ?", (answer,))
        else:
            cursor.execute("INSERT INTO poll_data (question, answer, votes) VALUES (?, ?, 1)",
                          ("Что для вас семья?", answer))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/vote: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/add_answer', methods=['POST'])
def add_answer():
    try:
        data = request.json
        answer = data.get('answer', '').strip()
        if not answer:
            return jsonify({"error": "Ответ не может быть пустым"}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM poll_data WHERE answer = ?", (answer,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "Такой ответ уже существует"}), 400
        cursor.execute("INSERT INTO poll_data (question, answer, votes) VALUES (?, ?, 1)",
                      ("Что для вас семья?", answer))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/add_answer: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/remove_answer', methods=['POST'])
def remove_answer():
    try:
        data = request.json
        answer = data.get('answer', '').strip()
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM poll_data WHERE answer = ?", (answer,))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/remove_answer: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/reset_rating', methods=['POST'])
def reset_rating():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE poll_data SET votes = 1")
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/reset_rating: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/api/set_question', methods=['POST'])
def set_question():
    try:
        data = request.json
        new_question = data.get('question', '').strip()
        if not new_question:
            return jsonify({"error": "Вопрос не может быть пустым"}), 400
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE poll_data SET question = ?", (new_question,))
        conn.commit()
        conn.close()
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"API: ОШИБКА в /api/set_question: {e}", flush=True)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return redirect('/results.html')

@app.route('/results.html')
def results_page():
    with open('results.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/poll.html')
def poll_page():
    with open('poll.html', 'r', encoding='utf-8') as f:
        return f.read()

@app.route('/admin.html')
def admin_page():
    with open('admin.html', 'r', encoding='utf-8') as f:
        return f.read()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
