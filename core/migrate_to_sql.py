import json
import os
import sqlite3
from database import init_db, get_db_connection

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_DB = os.path.join(BASE_DIR, 'database/db.json')

def migrate():
    if not os.path.exists(JSON_DB):
        print("db.json bulunamadı, göç atlanıyor.")
        return

    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    with open(JSON_DB, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Hastaneleri aktar
    for h in data.get('hospitals', []):
        try:
            cursor.execute('INSERT INTO hospitals (name) VALUES (?)', (h,))
        except sqlite3.IntegrityError:
            pass

    # Doktorları aktar
    for d in data.get('doctors', []):
        try:
            cursor.execute('''
            INSERT INTO doctors (id, ad, soyad, unvan, brans, sehir, hastane, tarih, durum, site_sonuclari, site_puanlari)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                d['id'], d.get('ad'), d.get('soyad'), d.get('unvan'), 
                d.get('brans'), d.get('sehir'), d.get('hastane'), 
                d.get('tarih'), d.get('durum'),
                json.dumps(d.get('site_sonuclari', {})),
                json.dumps(d.get('site_puanlari', {}))
            ))
        except sqlite3.IntegrityError:
            pass

    # Talepleri aktar
    for r in data.get('update_requests', []):
        try:
            cursor.execute('''
            INSERT INTO update_requests (id, doctor_id, doctor_name, degisiklikler, tarih, durum)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                r['id'], r.get('doctor_id'), r.get('doctor_name'),
                json.dumps(r.get('degisiklikler', {})),
                r.get('tarih'), r.get('durum')
            ))
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    print("Veriler başarıyla SQLite'a aktarıldı.")

if __name__ == '__main__':
    migrate()
