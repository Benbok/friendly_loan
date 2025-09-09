from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import json
import re
import os
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# Настройки для загрузки файлов
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Создаем папку для загрузок если её нет
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Проверяет, разрешен ли тип файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def hash_password(password):
    """Хеширует пароль"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_default_users():
    """Создает пользователей по умолчанию"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Проверяем, есть ли уже пользователи
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        # Создаем кредитодателя
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ('lender', hash_password('lender123'), 'lender'))
        
        # Создаем закредитованного
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ('borrower', hash_password('borrower123'), 'borrower'))
        
        conn.commit()
    
    conn.close()

def login_required(f):
    """Декоратор для проверки авторизации"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Требуется авторизация'}), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def role_required(required_role):
    """Декоратор для проверки роли"""
    def decorator(f):
        def decorated_function(*args, **kwargs):
            if 'user_role' not in session or session['user_role'] != required_role:
                return jsonify({'error': 'Недостаточно прав доступа'}), 403
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function
    return decorator

def get_borrowers():
    """Получить список всех закредитованных пользователей"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, username, full_name FROM users WHERE role = "borrower"')
    borrowers = cursor.fetchall()
    conn.close()
    
    return [{'id': borrower[0], 'username': borrower[1], 'full_name': borrower[2] or borrower[1]} for borrower in borrowers]

def get_borrower_credentials(borrower_id):
    """Получить учетные данные закредитованного пользователя"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, password_hash FROM users WHERE id = ? AND role = "borrower"', (borrower_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        # Для демонстрации возвращаем стандартный пароль
        # В реальном приложении пароли не должны храниться в открытом виде
        return {'username': result[0], 'password': 'password123'}
    return None

def create_borrower(username, password, full_name):
    """Создать нового закредитованного пользователя"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Проверяем, не существует ли уже пользователь с таким именем
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return {'success': False, 'error': 'Пользователь с таким именем уже существует'}
    
    # Создаем нового пользователя
    password_hash = hash_password(password)
    cursor.execute('''
        INSERT INTO users (username, password_hash, role, full_name)
        VALUES (?, ?, 'borrower', ?)
    ''', (username, password_hash, full_name))
    
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {'success': True, 'user_id': user_id, 'username': username, 'full_name': full_name}

def delete_borrower(borrower_id):
    """Удалить закредитованного пользователя с каскадным удалением"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Проверяем, что пользователь существует и является закредитованным
    cursor.execute('SELECT username FROM users WHERE id = ? AND role = "borrower"', (borrower_id,))
    borrower = cursor.fetchone()
    
    if not borrower:
        conn.close()
        return {'success': False, 'error': 'Закредитованный пользователь не найден'}
    
    username = borrower[0]
    
    # Получаем все кредиты этого закредитованного
    cursor.execute('SELECT id FROM loans WHERE borrower_id = ?', (borrower_id,))
    loan_ids = [row[0] for row in cursor.fetchall()]
    
    # Удаляем все платежи по кредитам этого закредитованного
    if loan_ids:
        placeholders = ','.join(['?' for _ in loan_ids])
        cursor.execute(f'DELETE FROM payments WHERE loan_id IN ({placeholders})', loan_ids)
    
    # Удаляем все кредиты этого закредитованного
    cursor.execute('DELETE FROM loans WHERE borrower_id = ?', (borrower_id,))
    
    # Удаляем самого пользователя
    cursor.execute('DELETE FROM users WHERE id = ?', (borrower_id,))
    
    conn.commit()
    conn.close()
    
    return {
        'success': True, 
        'message': f'Закредитованный пользователь "{username}" и все связанные данные удалены',
        'deleted_loans': len(loan_ids)
    }

def clean_amount(amount_str):
    """Очищает отформатированную сумму от пробелов и возвращает int"""
    if isinstance(amount_str, (int, float)):
        return int(round(float(amount_str)))
    
    # Удаляем все нецифровые символы кроме точки и запятой
    cleaned = re.sub(r'[^\d.,]', '', str(amount_str))
    
    # Заменяем запятую на точку для правильного парсинга
    cleaned = cleaned.replace(',', '.')
    
    try:
        return int(round(float(cleaned)))
    except ValueError:
        return 0

def calculate_last_payment_date(start_date_str, term_months):
    """Рассчитывает дату последнего запланированного платежа"""
    # Проверяем тип данных и конвертируем в строку если нужно
    if isinstance(start_date_str, (int, float)):
        # Если это число, возможно это timestamp или неправильный формат
        return "Неизвестно"
    
    try:
        start_date = datetime.strptime(str(start_date_str), '%Y-%m-%d')
        
        # Рассчитываем дату последнего платежа
        last_payment_date = start_date + timedelta(days=30 * term_months)
        
        return last_payment_date.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return "Неизвестно"

def init_db():
    """Инициализация базы данных"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('lender', 'borrower')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lender_id INTEGER NOT NULL,
            borrower_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            interest_rate REAL NOT NULL,
            start_date TEXT NOT NULL,
            term_months INTEGER NOT NULL,
            monthly_payment REAL NOT NULL,
            total_payment REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lender_id) REFERENCES users (id),
            FOREIGN KEY (borrower_id) REFERENCES users (id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            payment_date TEXT NOT NULL,
            document_path TEXT,
            document_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES loans (id)
        )
    ''')
    
    # Миграция: добавляем колонки document_path и document_name если их нет
    try:
        cursor.execute("ALTER TABLE payments ADD COLUMN document_path TEXT")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    try:
        cursor.execute("ALTER TABLE payments ADD COLUMN document_name TEXT")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    # Миграция: добавляем колонки lender_id и borrower_id если их нет
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN lender_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    try:
        cursor.execute("ALTER TABLE loans ADD COLUMN borrower_id INTEGER")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    # Миграция: заполняем lender_id и borrower_id для существующих кредитов
    cursor.execute("SELECT id FROM loans WHERE lender_id IS NULL OR borrower_id IS NULL")
    old_loans = cursor.fetchall()
    
    if old_loans:
        # Получаем ID кредитодателя по умолчанию
        cursor.execute("SELECT id FROM users WHERE role = 'lender' LIMIT 1")
        lender = cursor.fetchone()
        lender_id = lender[0] if lender else 1
        
        # Получаем ID закредитованного по умолчанию
        cursor.execute("SELECT id FROM users WHERE role = 'borrower' LIMIT 1")
        borrower = cursor.fetchone()
        borrower_id = borrower[0] if borrower else 2
        
        # Обновляем старые кредиты
        cursor.execute("UPDATE loans SET lender_id = ?, borrower_id = ? WHERE lender_id IS NULL OR borrower_id IS NULL", 
                      (lender_id, borrower_id))
    
    # Миграция: добавляем поле full_name для пользователей
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
    except sqlite3.OperationalError:
        pass  # Колонка уже существует
    
    # Заполняем full_name для существующих пользователей
    cursor.execute("UPDATE users SET full_name = username WHERE full_name IS NULL")
    
    conn.commit()
    conn.close()
    
    # Создаем пользователей по умолчанию
    create_default_users()

def calculate_loan(amount, interest_rate, term_months):
    """Расчет кредитных выплат"""
    monthly_rate = interest_rate / 100 / 12
    if monthly_rate == 0:
        monthly_payment = amount / term_months
    else:
        monthly_payment = amount * (monthly_rate * (1 + monthly_rate) ** term_months) / ((1 + monthly_rate) ** term_months - 1)
    
    total_payment = monthly_payment * term_months
    
    return {
        'monthly_payment': round(monthly_payment),
        'total_payment': round(total_payment),
        'total_interest': round(total_payment - amount)
    }

def recalculate_loan_after_payment(loan_id):
    """Перерасчет кредита после внесения платежа"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Получаем данные кредита
    cursor.execute('SELECT * FROM loans WHERE id = ?', (loan_id,))
    loan = cursor.fetchone()
    
    if not loan:
        conn.close()
        return None
    
    # Получаем все платежи по кредиту
    cursor.execute('SELECT amount FROM payments WHERE loan_id = ? ORDER BY payment_date', (loan_id,))
    payments = cursor.fetchall()
    
    total_paid = sum(payment[0] for payment in payments)
    remaining_amount = loan[6] - total_paid  # total_payment - total_paid
    
    # Рассчитываем оставшиеся месяцы
    try:
        start_date = datetime.strptime(str(loan[3]), '%Y-%m-%d')
        current_date = datetime.now()
        months_passed = (current_date.year - start_date.year) * 12 + (current_date.month - start_date.month)
        months_remaining = max(0, loan[4] - months_passed)  # term_months - months_passed
    except (ValueError, TypeError):
        # Если не можем распарсить дату, используем весь срок
        months_remaining = loan[4]
    
    # Если кредит полностью погашен
    if remaining_amount <= 0:
        conn.close()
        return {
            'remaining_amount': 0,
            'new_monthly_payment': 0,
            'months_remaining': 0,
            'recalculated': True,
            'payment_breakdown': {
                'principal': 0,
                'interest': 0,
                'total': 0
            }
        }
    
    if months_remaining <= 0:
        conn.close()
        return {
            'remaining_amount': remaining_amount,
            'new_monthly_payment': remaining_amount,
            'months_remaining': 0,
            'recalculated': True,
            'payment_breakdown': {
                'principal': round(remaining_amount),
                'interest': 0,
                'total': round(remaining_amount)
            }
        }
    
    # Пересчитываем ежемесячный платеж на оставшуюся сумму
    monthly_rate = loan[2] / 100 / 12  # interest_rate / 100 / 12
    if monthly_rate == 0:
        new_monthly_payment = remaining_amount / months_remaining
        payment_breakdown = {
            'principal': round(remaining_amount / months_remaining),
            'interest': 0,
            'total': round(remaining_amount / months_remaining)
        }
    else:
        new_monthly_payment = remaining_amount * (monthly_rate * (1 + monthly_rate) ** months_remaining) / ((1 + monthly_rate) ** months_remaining - 1)
        
        # Рассчитываем разбивку первого платежа (приблизительно)
        interest_payment = remaining_amount * monthly_rate
        principal_payment = new_monthly_payment - interest_payment
        
        payment_breakdown = {
            'principal': round(principal_payment),
            'interest': round(interest_payment),
            'total': round(new_monthly_payment)
        }
    
    conn.close()
    
    return {
        'remaining_amount': round(remaining_amount),
        'new_monthly_payment': round(new_monthly_payment),
        'months_remaining': months_remaining,
        'recalculated': True,
        'payment_breakdown': payment_breakdown
    }

@app.route('/')
def index():
    """Главная страница"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_role = session.get('user_role', 'unknown')
    role_display = 'Кредитодатель' if user_role == 'lender' else 'Закредитованный'
    
    return render_template('index.html', user_role=role_display)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        conn = sqlite3.connect('loans.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and user[2] == hash_password(password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['user_role'] = user[3]
            return jsonify({'success': True, 'role': user[3]})
        else:
            return jsonify({'error': 'Неверное имя пользователя или пароль'}), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Выход из системы"""
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/borrowers', methods=['GET'])
@login_required
@role_required('lender')
def get_borrowers_api():
    """Получить список закредитованных пользователей"""
    return jsonify(get_borrowers())

@app.route('/api/borrowers/<int:borrower_id>/credentials', methods=['GET'])
@login_required
@role_required('lender')
def get_borrower_credentials_api(borrower_id):
    """Получить учетные данные закредитованного пользователя"""
    credentials = get_borrower_credentials(borrower_id)
    if credentials:
        return jsonify(credentials)
    else:
        return jsonify({'error': 'Пользователь не найден'}), 404

@app.route('/api/borrowers', methods=['POST'])
@login_required
@role_required('lender')
def create_borrower_api():
    """Создать нового закредитованного пользователя"""
    data = request.get_json()
    
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    full_name = data.get('full_name', '').strip()
    
    if not username or not password or not full_name:
        return jsonify({'error': 'Имя пользователя, пароль и ФИО обязательны'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Имя пользователя должно содержать минимум 3 символа'}), 400
    
    if len(password) < 4:
        return jsonify({'error': 'Пароль должен содержать минимум 4 символа'}), 400
    
    if len(full_name) < 2:
        return jsonify({'error': 'ФИО должно содержать минимум 2 символа'}), 400
    
    result = create_borrower(username, password, full_name)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': f'Закредитованный пользователь "{full_name}" создан успешно',
            'credentials': {
                'username': username,
                'password': password,
                'full_name': full_name
            }
        })
    else:
        return jsonify({'error': result['error']}), 400

@app.route('/api/borrowers/<int:borrower_id>', methods=['DELETE'])
@login_required
@role_required('lender')
def delete_borrower_api(borrower_id):
    """Удалить закредитованного пользователя"""
    result = delete_borrower(borrower_id)
    
    if result['success']:
        return jsonify({
            'success': True,
            'message': result['message'],
            'deleted_loans': result['deleted_loans']
        })
    else:
        return jsonify({'error': result['error']}), 400

def get_loan_progress(loan_id):
    """Получить прогресс погашения кредита"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Получаем данные кредита
    cursor.execute('SELECT * FROM loans WHERE id = ?', (loan_id,))
    loan = cursor.fetchone()
    
    if not loan:
        conn.close()
        return None
    
    # Получаем все платежи по кредиту
    cursor.execute('SELECT amount, payment_date FROM payments WHERE loan_id = ? ORDER BY payment_date', (loan_id,))
    payments = cursor.fetchall()
    
    total_paid = sum(payment[0] for payment in payments)
    remaining_amount = loan[6] - total_paid  # total_payment - total_paid
    progress_percent = (total_paid / loan[6]) * 100 if loan[6] > 0 else 0
    
    # Получаем дату последнего платежа
    last_payment_date = payments[-1][1] if payments else None
    
    # Рассчитываем дату последнего запланированного платежа
    planned_last_payment_date = calculate_last_payment_date(loan[3], loan[4])
    
    conn.close()
    
    return {
        'total_paid': round(total_paid),
        'remaining_amount': round(remaining_amount),
        'progress_percent': round(progress_percent, 1),
        'payments_count': len(payments),
        'last_payment_date': last_payment_date,
        'planned_last_payment_date': planned_last_payment_date
    }

@app.route('/api/loans', methods=['GET'])
@login_required
def get_loans():
    """Получить все кредиты"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Фильтруем кредиты в зависимости от роли пользователя
    user_id = session['user_id']
    user_role = session['user_role']
    
    if user_role == 'lender':
        # Для кредитодателя получаем кредиты с ФИО закредитованных
        cursor.execute('''
            SELECT l.*, COALESCE(u.full_name, u.username) as borrower_name 
            FROM loans l 
            JOIN users u ON l.borrower_id = u.id 
            WHERE l.lender_id = ? 
            ORDER BY l.created_at DESC
        ''', (user_id,))
    else:  # borrower
        # Для закредитованного получаем кредиты с ФИО кредитодателей
        cursor.execute('''
            SELECT l.*, COALESCE(u.full_name, u.username) as lender_name 
            FROM loans l 
            JOIN users u ON l.lender_id = u.id 
            WHERE l.borrower_id = ? 
            ORDER BY l.created_at DESC
        ''', (user_id,))
    
    loans = cursor.fetchall()
    conn.close()
    
    result = []
    for loan in loans:
        progress = get_loan_progress(loan[0])
        
        # Безопасное извлечение данных с проверкой типов
        def safe_int(value):
            try:
                return int(float(value)) if value is not None else 0
            except (ValueError, TypeError):
                return 0
        
        def safe_float(value):
            try:
                return float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                return 0.0
        
        def safe_str(value):
            return str(value) if value is not None else ''
        
        # Определяем имя пользователя в зависимости от роли
        if user_role == 'lender':
            user_name = safe_str(loan[10])  # borrower_name
            user_role_display = 'Закредитованный'
        else:
            user_name = safe_str(loan[10])  # lender_name
            user_role_display = 'Кредитодатель'
        
        result.append({
            'id': safe_int(loan[0]),
            'amount': safe_int(loan[1]),
            'interest_rate': safe_float(loan[2]),
            'start_date': safe_str(loan[3]),
            'term_months': safe_int(loan[4]),
            'monthly_payment': safe_int(loan[5]),
            'total_payment': safe_int(loan[6]),
            'created_at': safe_str(loan[7]),
            'lender_id': safe_int(loan[8]),
            'borrower_id': safe_int(loan[9]),
            'user_name': user_name,
            'user_role_display': user_role_display,
            'total_paid': progress['total_paid'],
            'remaining_amount': progress['remaining_amount'],
            'progress_percent': progress['progress_percent'],
            'payments_count': progress['payments_count'],
            'last_payment_date': progress['last_payment_date'],
            'planned_last_payment_date': progress['planned_last_payment_date']
        })
    
    return jsonify(result)

@app.route('/api/loans', methods=['POST'])
@login_required
@role_required('lender')
def create_loan():
    """Создать новый кредит"""
    data = request.get_json()
    
    amount = clean_amount(data['amount'])
    interest_rate = float(data['interest_rate'])
    start_date = data['start_date']
    term_months = int(data['term_months'])
    
    # Расчет выплат
    calculations = calculate_loan(amount, interest_rate, term_months)
    
    # Получаем ID закредитованного пользователя
    borrower_id = data.get('borrower_id')
    if not borrower_id:
        return jsonify({'error': 'Необходимо выбрать закредитованного пользователя'}), 400
    
    # Проверяем, что закредитованный существует
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE id = ? AND role = "borrower"', (borrower_id,))
    borrower = cursor.fetchone()
    
    if not borrower:
        conn.close()
        return jsonify({'error': 'Закредитованный пользователь не найден'}), 404
    
    # Сохранение в базу данных
    lender_id = session['user_id']
    cursor.execute('''
        INSERT INTO loans (lender_id, borrower_id, amount, interest_rate, start_date, term_months, monthly_payment, total_payment)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (lender_id, borrower_id, amount, interest_rate, start_date, term_months, 
          calculations['monthly_payment'], calculations['total_payment']))
    conn.commit()
    loan_id = cursor.lastrowid
    conn.close()
    
    return jsonify({
        'id': loan_id,
        'amount': amount,
        'interest_rate': interest_rate,
        'start_date': start_date,
        'term_months': term_months,
        'monthly_payment': calculations['monthly_payment'],
        'total_payment': calculations['total_payment'],
        'total_interest': calculations['total_interest']
    })

@app.route('/api/calculate', methods=['POST'])
def calculate():
    """Расчет кредита без сохранения"""
    data = request.get_json()
    
    amount = clean_amount(data['amount'])
    interest_rate = float(data['interest_rate'])
    term_months = int(data['term_months'])
    
    calculations = calculate_loan(amount, interest_rate, term_months)
    
    return jsonify(calculations)

@app.route('/api/loans/<int:loan_id>', methods=['DELETE'])
@login_required
@role_required('lender')
def delete_loan(loan_id):
    """Удалить кредит"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM payments WHERE loan_id = ?', (loan_id,))
    cursor.execute('DELETE FROM loans WHERE id = ?', (loan_id,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/payments', methods=['POST'])
@login_required
@role_required('borrower')
def add_payment():
    """Добавить платеж по кредиту"""
    # Проверяем, есть ли файл в запросе
    if 'file' in request.files:
        # Обработка с файлом
        file = request.files['file']
        loan_id = int(request.form.get('loan_id'))
        amount = clean_amount(request.form.get('amount'))
        payment_date = request.form.get('payment_date')
        
        # Проверяем обязательность файла
        if not file or not file.filename:
            return jsonify({'error': 'Необходимо прикрепить документ (чек) для сохранения платежа'}), 400
        
        # Проверяем тип файла
        if not allowed_file(file.filename):
            return jsonify({'error': 'Неподдерживаемый тип файла. Разрешены: PDF, PNG, JPG, JPEG, GIF, DOC, DOCX'}), 400
        
        # Генерируем уникальное имя файла
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        unique_filename = f"{name}_{timestamp}{ext}"
        
        # Сохраняем файл
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Сохраняем относительный путь для веб-доступа
        document_path = os.path.join('static', 'uploads', unique_filename).replace('\\', '/')
        document_name = filename
    else:
        # Если нет файла, возвращаем ошибку
        return jsonify({'error': 'Необходимо прикрепить документ (чек) для сохранения платежа'}), 400
    
    # Проверяем, существует ли кредит
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM loans WHERE id = ?', (loan_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Кредит не найден'}), 404
    
    # Добавляем платеж
    cursor.execute('''
        INSERT INTO payments (loan_id, amount, payment_date, document_path, document_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (loan_id, amount, payment_date, document_path, document_name))
    conn.commit()
    payment_id = cursor.lastrowid
    conn.close()
    
    # Пересчитываем кредит после внесения платежа
    recalculation = recalculate_loan_after_payment(loan_id)
    
    return jsonify({
        'id': payment_id,
        'loan_id': loan_id,
        'amount': amount,
        'payment_date': payment_date,
        'document_path': document_path,
        'document_name': document_name,
        'recalculation': recalculation
    })

@app.route('/api/loans/<int:loan_id>/payments', methods=['GET'])
def get_loan_payments(loan_id):
    """Получить все платежи по кредиту"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, amount, payment_date, document_path, document_name, created_at 
        FROM payments 
        WHERE loan_id = ? 
        ORDER BY payment_date DESC
    ''', (loan_id,))
    payments = cursor.fetchall()
    conn.close()
    
    result = []
    for payment in payments:
        # Безопасное извлечение данных для платежей
        def safe_int(value):
            try:
                return int(float(value)) if value is not None else 0
            except (ValueError, TypeError):
                return 0
        
        def safe_str(value):
            return str(value) if value is not None else ''
        
        result.append({
            'id': safe_int(payment[0]),
            'amount': safe_int(payment[1]),
            'payment_date': safe_str(payment[2]),
            'document_path': safe_str(payment[3]),
            'document_name': safe_str(payment[4]),
            'created_at': safe_str(payment[5])
        })
    
    return jsonify(result)

@app.route('/api/payments/<int:payment_id>', methods=['DELETE'])
def delete_payment(payment_id):
    """Удалить платеж"""
    conn = sqlite3.connect('loans.db')
    cursor = conn.cursor()
    
    # Получаем loan_id перед удалением
    cursor.execute('SELECT loan_id FROM payments WHERE id = ?', (payment_id,))
    result = cursor.fetchone()
    if not result:
        conn.close()
        return jsonify({'error': 'Платеж не найден'}), 404
    
    loan_id = result[0]
    
    # Удаляем платеж
    cursor.execute('DELETE FROM payments WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    
    # Пересчитываем кредит после удаления платежа
    recalculation = recalculate_loan_after_payment(loan_id)
    
    return jsonify({
        'success': True,
        'recalculation': recalculation
    })

@app.route('/api/loans/<int:loan_id>/recalculate', methods=['GET'])
def get_loan_recalculation(loan_id):
    """Получить перерасчет кредита"""
    recalculation = recalculate_loan_after_payment(loan_id)
    
    if not recalculation:
        return jsonify({'error': 'Кредит не найден'}), 404
    
    return jsonify(recalculation)

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
