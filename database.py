import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.getenv("DATABASE_URL")

async def setup_db():
    conn = await asyncpg.connect(DB_URL)
    # 1. O'yinlar jadvali (PostgreSQL tilida yozilgan)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS apps (
            id SERIAL PRIMARY KEY,
            name TEXT,
            file_id TEXT,
            caption TEXT
        );
    ''')
    
    # 2. Foydalanuvchilar jadvali
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    await conn.close()

# ================= APP (O'YINLAR) FUNKSIYALARI =================

async def add_app(name, file_id, caption):
    conn = await asyncpg.connect(DB_URL)
    # PostgreSQL da ma'lumot qoshishda (?) emas, ($1, $2) ishlatiladi
    await conn.execute('''
        INSERT INTO apps (name, file_id, caption) VALUES ($1, $2, $3)
    ''', name, file_id, caption)
    await conn.close()

async def search_app(query):
    conn = await asyncpg.connect(DB_URL)
    # ILIKE so'zi katta-kichik harflarni farqlamay qidirish uchun
    rows = await conn.fetch('''
        SELECT file_id, name, caption FROM apps WHERE name ILIKE $1
    ''', f'%{query}%')
    await conn.close()
    return [(row['file_id'], row['name'], row['caption']) for row in rows]
            
async def delete_app(name):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute('DELETE FROM apps WHERE name = $1', name)
    await conn.close()

async def count_apps():
    conn = await asyncpg.connect(DB_URL)
    val = await conn.fetchval('SELECT COUNT(*) FROM apps')
    await conn.close()
    return val if val else 0

# ================= FOYDALANUVCHILAR (STATISTIKA) FUNKSIYALARI =================

async def add_or_update_user(user_id, username, full_name):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute('''
        INSERT INTO users (user_id, username, full_name, last_active) 
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id) DO UPDATE SET 
        username = EXCLUDED.username,
        full_name = EXCLUDED.full_name,
        last_active = CURRENT_TIMESTAMP
    ''', user_id, username, full_name)
    await conn.close()

async def count_users():
    conn = await asyncpg.connect(DB_URL)
    val = await conn.fetchval('SELECT COUNT(*) FROM users')
    await conn.close()
    return val if val else 0

async def count_active_users():
    conn = await asyncpg.connect(DB_URL)
    val = await conn.fetchval("SELECT COUNT(*) FROM users WHERE last_active >= NOW() - INTERVAL '15 minutes'")
    await conn.close()
    return val if val else 0