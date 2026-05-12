import asyncpg
import os
import random
from dotenv import load_dotenv
 
load_dotenv()
DB_URL = os.getenv("DATABASE_URL")
 
async def setup_db():
    conn = await asyncpg.connect(DB_URL)
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS apps (
            id SERIAL PRIMARY KEY,
            name TEXT,
            file_id TEXT,
            caption TEXT,
            code INTEGER UNIQUE
        );
    ''')
    await conn.execute('''
        ALTER TABLE apps ADD COLUMN IF NOT EXISTS code INTEGER UNIQUE;
    ''')
    await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    await conn.close()
 
async def generate_unique_code():
    conn = await asyncpg.connect(DB_URL)
    existing = await conn.fetch('SELECT code FROM apps WHERE code IS NOT NULL')
    used_codes = {row['code'] for row in existing}
    await conn.close()
    available = set(range(100, 1000)) - used_codes
    if not available:
        raise Exception("Barcha kodlar ishlatilgan!")
    return random.choice(list(available))
 
async def add_app(name, file_id, caption, code=None):
    conn = await asyncpg.connect(DB_URL)
    if code is None:
        code = await generate_unique_code()
    await conn.execute('''
        INSERT INTO apps (name, file_id, caption, code) VALUES ($1, $2, $3, $4)
    ''', name, file_id, caption, code)
    await conn.close()
    return code
 
async def search_app(query):
    conn = await asyncpg.connect(DB_URL)
    rows = await conn.fetch('''
        SELECT file_id, name, caption, code FROM apps WHERE name ILIKE $1
    ''', f'%{query}%')
    await conn.close()
    return [(row['file_id'], row['name'], row['caption'], row['code']) for row in rows]
 
async def search_by_code(code):
    conn = await asyncpg.connect(DB_URL)
    row = await conn.fetchrow('SELECT file_id, name, caption, code FROM apps WHERE code = $1', int(code))
    await conn.close()
    if row:
        return (row['file_id'], row['name'], row['caption'], row['code'])
    return None
 
async def delete_app(name):
    conn = await asyncpg.connect(DB_URL)
    await conn.execute('DELETE FROM apps WHERE name = $1', name)
    await conn.close()
 
async def count_apps():
    conn = await asyncpg.connect(DB_URL)
    val = await conn.fetchval('SELECT COUNT(*) FROM apps')
    await conn.close()
    return val if val else 0
 
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
