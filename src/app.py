import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib

app = Flask(__name__)
CORS(app)

# Конфигурация
DATABASE = '/tmp/poll.db'
ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

# ==================== РАБОТА С БАЗОЙ ДАННЫХ ====================

def get_db():
    """Создаёт соединение с базой данных"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Инициализация базы данных — таблицы и начальные данные"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Таблица с ответами
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
    
    # Таблица с настройками
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    ''')
    
    # Добавляем настройку allow_custom_answers, если её нет
    cursor.execute("SELECT value FROM settings WHERE key = 'allow_custom_answers'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO settings (key, value) VALUES ('allow_custom_answers', '1')")
    
    # Проверяем и добавляем начальные ответы, если таблица пуста
    cursor.execute("SELECT COUNT(*) FROM poll_data")
    count = cursor.fetchone()[0]
    
    if count == 0:
        default_answers = ["Любовь", "Поддержка", "Забота", "Уважение", "Опора", "Уют", "Понимание", "Тепло"]
        for answer in default_answers:
            cursor.execute("INSERT INTO poll_data (question, answer, votes) VALUES (?, ?, 1)",
                          ("Что для вас семья?", answer))
    
    conn.commit()
    conn.close()

def get_settings():
    """Получить настройки опроса"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    conn.close()
    settings = {row['key']: row['value'] for row in rows}
    # Значение по умолчанию, если вдруг чего-то нет
    settings.setdefault('allow_custom_answers', '1')
    return settings

def update_settings(settings_dict):
    """Обновить настройки опроса"""
    conn = get_db()
    cursor = conn.cursor()
    for key, value in settings_dict.items():
        cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (str(value), key))
        if cursor.rowcount == 0:
            cursor.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# ==================== API ЭНДПОИНТЫ ====================

@app.route('/api/init', methods=['GET'])
def init_poll():
    """Инициализация опроса (при первом запуске)"""
    init_db()
    return jsonify({"status": "ok"})

@app.route('/api/data', methods=['GET'])
def get_data():
    """Получить все данные опроса"""
    init_db()
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

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    """Получить или обновить настройки опроса"""
    if request.method == 'GET':
        return jsonify(get_settings())
    
    # POST — обновление настроек (требует пароль)
    data = request.json
        
    # Обновляем настройки
    new_settings = {}
    if 'allow_custom_answers' in data:
        new_settings['allow_custom_answers'] = '1' if data['allow_custom_answers'] else '0'
    
    if new_settings:
        update_settings(new_settings)
    
    return jsonify({"status": "ok", "settings": get_settings()})

@app.route('/api/vote', methods=['POST'])
def vote():
    """Проголосовать за ответ"""
    init_db()
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
        # Проверяем, разрешены ли свои варианты
        settings = get_settings()
        if settings.get('allow_custom_answers') != '1':
            conn.close()
            return jsonify({"error": "Добавление своих вариантов запрещено администратором"}), 403
        cursor.execute("INSERT INTO poll_data (question, answer, votes) VALUES (?, ?, 1)",
                      ("Что для вас семья?", answer))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/add_answer', methods=['POST'])
def add_answer():
    """Добавить новый вариант ответа (только для админа)"""
    init_db()
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

@app.route('/api/remove_answer', methods=['POST'])
def remove_answer():
    """Удалить вариант ответа (только для админа)"""
    data = request.json
    answer = data.get('answer', '').strip()
    
    # Защита: нельзя удалить ответ, если он среди начальных
    default_answers = ["Любовь", "Поддержка", "Забота", "Уважение", "Опора", "Уют", "Понимание", "Тепло"]
    if answer in default_answers:
        return jsonify({"error": "Нельзя удалить стандартный вариант ответа"}), 403
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM poll_data WHERE answer = ?", (answer,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/reset_rating', methods=['POST'])
def reset_rating():
    """Сбросить все голоса к 1 (только для админа)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE poll_data SET votes = 1")
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route('/api/set_question', methods=['POST'])
def set_question():
    """Изменить вопрос (только для админа)"""
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

# ==================== СТАТИЧЕСКИЕ СТРАНИЦЫ ====================

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

@app.route('/')
def index():
    return results_page()

# ==================== ЗАПУСК ====================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
