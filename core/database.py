import sqlite3
import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database/dr.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Veritabanı tablolarını oluşturur."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Hastaneler tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hospitals (
        name TEXT PRIMARY KEY
    )
    ''')
    
    # Doktorlar tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS doctors (
        id TEXT PRIMARY KEY,
        ad TEXT,
        soyad TEXT,
        unvan TEXT,
        brans TEXT,
        sehir TEXT,
        hastane TEXT,
        tarih TEXT,
        durum TEXT,
        site_sonuclari TEXT, -- JSON string
        site_puanlari TEXT   -- JSON string
    )
    ''')
    
    # Güncelleme talepleri tablosu
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS update_requests (
        id TEXT PRIMARY KEY,
        doctor_id TEXT,
        doctor_name TEXT,
        degisiklikler TEXT, -- JSON string
        tarih TEXT,
        durum TEXT
    )
    ''')
    
    # Admin kullanıcı tablosu (Gelecek planı için)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT
    )
    ''')
    
    conn.commit()
    conn.close()

def create_default_user(username, password_hash):
    """Varsayılan kullanıcıyı oluşturur."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Veritabanı başarıyla oluşturuldu.")
