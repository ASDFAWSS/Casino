import sqlite3

def init_db():
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 1000,
        referrer_id INTEGER DEFAULT NULL,
        registration_date TEXT DEFAULT CURRENT_TIMESTAMP,
        total_games INTEGER DEFAULT 0,
        total_winnings INTEGER DEFAULT 0,
        biggest_win INTEGER DEFAULT 0,
        favorite_game TEXT DEFAULT '',
        favorite_game_count INTEGER DEFAULT 0
    )''')
    
    # Добавляем новые столбцы к существующим пользователям
    try:
        c.execute('ALTER TABLE users ADD COLUMN referrer_id INTEGER DEFAULT NULL')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN registration_date TEXT DEFAULT CURRENT_TIMESTAMP')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN total_games INTEGER DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN total_winnings INTEGER DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN biggest_win INTEGER DEFAULT 0')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN favorite_game TEXT DEFAULT ""')
    except:
        pass
    try:
        c.execute('ALTER TABLE users ADD COLUMN favorite_game_count INTEGER DEFAULT 0')
    except:
        pass
    
    # Создаем таблицу для подсчета игр
    c.execute('''CREATE TABLE IF NOT EXISTS game_stats (
        user_id INTEGER,
        game_name TEXT,
        games_count INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, game_name)
    )''')
    
    conn.commit()
    conn.close()

def create_user(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_balance(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def update_balance(user_id, amount):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def create_user_with_referrer(user_id, referrer_id=None):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, referrer_id, registration_date) VALUES (?, ?, datetime('now'))", (user_id, referrer_id))
    conn.commit()
    conn.close()

def get_user_stats(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    try:
        c.execute("""SELECT total_games, total_winnings, biggest_win, favorite_game, 
                            favorite_game_count, registration_date, referrer_id 
                     FROM users WHERE user_id = ?""", (user_id,))
        row = c.fetchone()
        if row:
            return {
                'total_games': row[0] or 0,
                'total_winnings': row[1] or 0,
                'biggest_win': row[2] or 0,
                'favorite_game': row[3] or 'Триада',
                'favorite_game_count': row[4] or 74,
                'registration_date': row[5] or '2024-10-20',
                'referrer_id': row[6]
            }
    except sqlite3.OperationalError:
        # Если столбец registration_date не существует, используем старый запрос
        c.execute("""SELECT total_games, total_winnings, biggest_win, favorite_game, 
                            favorite_game_count, referrer_id 
                     FROM users WHERE user_id = ?""", (user_id,))
        row = c.fetchone()
        if row:
            return {
                'total_games': row[0] or 0,
                'total_winnings': row[1] or 0,
                'biggest_win': row[2] or 0,
                'favorite_game': row[3] or 'Триада',
                'favorite_game_count': row[4] or 74,
                'registration_date': '2024-10-20',
                'referrer_id': row[5]
            }
    finally:
        conn.close()
    return None

def update_game_stats(user_id, game_name, win_amount=0):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    
    # Обновляем общую статистику
    c.execute("UPDATE users SET total_games = total_games + 1 WHERE user_id = ?", (user_id,))
    
    if win_amount > 0:
        c.execute("UPDATE users SET total_winnings = total_winnings + ? WHERE user_id = ?", (win_amount, user_id))
        # Проверяем и обновляем самый большой выигрыш
        c.execute("UPDATE users SET biggest_win = ? WHERE user_id = ? AND ? > biggest_win", (win_amount, user_id, win_amount))
    
    # Обновляем статистику по играм
    c.execute("INSERT OR REPLACE INTO game_stats (user_id, game_name, games_count) VALUES (?, ?, COALESCE((SELECT games_count FROM game_stats WHERE user_id = ? AND game_name = ?), 0) + 1)", (user_id, game_name, user_id, game_name))
    
    # Обновляем любимую игру
    c.execute("""UPDATE users SET favorite_game = ?, favorite_game_count = ? 
                 WHERE user_id = ? AND ? IN (
                     SELECT MAX(games_count) FROM game_stats WHERE user_id = ?
                 )""", (game_name, c.lastrowid, user_id, c.lastrowid, user_id))
    
    # Получаем самую играемую игру
    c.execute("SELECT game_name, games_count FROM game_stats WHERE user_id = ? ORDER BY games_count DESC LIMIT 1", (user_id,))
    fav_game = c.fetchone()
    if fav_game:
        c.execute("UPDATE users SET favorite_game = ?, favorite_game_count = ? WHERE user_id = ?", (fav_game[0], fav_game[1], user_id))
    
    conn.commit()
    conn.close()

def get_referral_info(user_id):
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    # Считаем количество рефералов
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    referrals_count = c.fetchone()[0]
    conn.close()
    return referrals_count

def add_referral_bonus(referrer_id, bonus_amount):
    """Добавляет бонус рефереру (5% от выигрыша реферала)"""
    update_balance(referrer_id, bonus_amount)

def delete_user(user_id):
    """Удаляет пользователя из базы данных"""
    conn = sqlite3.connect("casino.db")
    c = conn.cursor()
    
    # Удаляем из основной таблицы
    c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    
    # Удаляем статистику игр
    c.execute("DELETE FROM game_stats WHERE user_id = ?", (user_id,))
    
    # Обнуляем реферера у тех, кто был приглашен этим пользователем
    c.execute("UPDATE users SET referrer_id = NULL WHERE referrer_id = ?", (user_id,))
    
    conn.commit()
    conn.close()
    
    return True
