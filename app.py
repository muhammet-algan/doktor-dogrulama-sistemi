"""
ANA UYGULAMA SUNUCUSU (app.py) - PRODUCTION READY
--------------------------------------------
Flask tabanlı web sunucusu. SQLite veritabanı ve güvenli oturum yönetimi içerir.
"""
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_bcrypt import Bcrypt
import json, os, uuid, sqlite3
from datetime import datetime
from threading import Thread
from config import UNVAN_LISTESI, BRANSLAR, SITELER, ADMIN_USERNAME, ADMIN_PASSWORD
from core.scoring import site_puani
from scrapers import tum_siteleri_tara
from core.database import get_db_connection

app = Flask(__name__)
app.secret_key = os.urandom(24) # Üretim ortamında sabit bir anahtar kullanılmalı
bcrypt = Bcrypt(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Yardımcı Fonksiyonlar ---

def load_json(path):
    with open(os.path.join(BASE_DIR, path), 'r', encoding='utf-8') as f:
        return json.load(f)

def is_logged_in():
    return session.get('logged_in')

# --- Sayfa Yönlendirmeleri ---

@app.route('/')
def index():
    sehirler = load_json('data/sehirler.json')
    return render_template('index.html', unvanlar=UNVAN_LISTESI, branslar=BRANSLAR, sehirler=sehirler)

@app.route('/login')
def login_page():
    if is_logged_in():
        return redirect(url_for('admin'))
    return render_template('login.html')

@app.route('/admin')
def admin():
    if not is_logged_in():
        return redirect(url_for('login_page'))
    
    conn = get_db_connection()
    doctors = conn.execute('SELECT * FROM doctors').fetchall()
    conn.close()
    
    doctors_list = [dict(row) for row in doctors]
    # JSON stringlerini objeye çevir
    for d in doctors_list:
        d['site_sonuclari'] = json.loads(d['site_sonuclari']) if d['site_sonuclari'] else {}
        d['site_puanlari'] = json.loads(d['site_puanlari']) if d['site_puanlari'] else {}

    return render_template('admin.html', doktorlar=doctors_list, siteler=SITELER)

# --- API Endpointleri ---

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if user and bcrypt.check_password_hash(user['password_hash'], password):
        session['logged_in'] = True
        session['username'] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Hatalı kullanıcı adı veya şifre'}), 401

@app.route('/api/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login_page'))

@app.route('/api/change-password', methods=['POST'])
def change_password():
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    username = session.get('username')
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    
    if not user or not bcrypt.check_password_hash(user['password_hash'], current_password):
        conn.close()
        return jsonify({'error': 'Mevcut şifre yanlış!'}), 400
    
    new_hash = bcrypt.generate_password_hash(new_password).decode('utf-8')
    conn.execute('UPDATE users SET password_hash = ? WHERE username = ?', (new_hash, username))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    doc_id = str(uuid.uuid4())
    tarih = datetime.now().isoformat()
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO doctors (id, ad, soyad, unvan, brans, sehir, hastane, tarih, durum, site_sonuclari, site_puanlari)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (doc_id, data['ad'], data['soyad'], data['unvan'], data['brans'], data['sehir'], 
          data['hastane'], tarih, 'beklemede', '{}', '{}'))
    conn.commit()
    conn.close()
    
    Thread(target=verify_doctor, args=(doc_id,)).start()
    return jsonify({'success': True, 'message': 'DOKTOR BİLDİRİLDİ'})

def verify_doctor(doctor_id):
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
        if not row: return
        
        doctor = dict(row)
        sonuclar = tum_siteleri_tara(doctor)
        
        puanlar = {}
        for site_adi, site_verisi in sonuclar.items():
            try:
                puan, detay = site_puani(doctor, site_verisi or {})
                puanlar[site_adi] = {'puan': puan, 'detay': detay}
            except:
                puanlar[site_adi] = {'puan': 0, 'detay': {}}
        
        conn.execute('''
            UPDATE doctors 
            SET site_sonuclari = ?, site_puanlari = ?, durum = ? 
            WHERE id = ?
        ''', (json.dumps(sonuclar), json.dumps(puanlar), 'tamamlandi', doctor_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error in verify_doctor: {e}")

@app.route('/api/doctors')
def get_doctors():
    if not is_logged_in(): return jsonify([]), 401
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM doctors').fetchall()
    conn.close()
    
    res = []
    for r in rows:
        d = dict(r)
        d['site_sonuclari'] = json.loads(d['site_sonuclari'])
        d['site_puanlari'] = json.loads(d['site_puanlari'])
        res.append(d)
    return jsonify(res)

@app.route('/api/doctor/<doctor_id>', methods=['DELETE'])
def delete_doctor(doctor_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    conn.execute('DELETE FROM doctors WHERE id = ?', (doctor_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/doctor/<doctor_id>', methods=['PUT'])
def update_doctor(doctor_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    conn = get_db_connection()
    conn.execute('''
        UPDATE doctors SET ad=?, soyad=?, unvan=?, brans=?, sehir=?, hastane=?
        WHERE id=?
    ''', (data.get('ad'), data.get('soyad'), data.get('unvan'), 
          data.get('brans'), data.get('sehir'), data.get('hastane'), doctor_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/approve-doctor/<doctor_id>', methods=['POST'])
def approve_doctor(doctor_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    doc = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    if not doc: return jsonify({'error': 'Not found'}), 404
    
    doc = dict(doc)
    doc['site_puanlari'] = json.loads(doc['site_puanlari'])
    doc['site_sonuclari'] = json.loads(doc['site_sonuclari'])
    
    # En iyi hastane ismini bulma mantığı
    kullanici_hastanesi = doc.get('hastane', '').strip()
    kullanici_hastane_puani = 0
    for site, puan_data in doc['site_puanlari'].items():
        detay = puan_data.get('detay', {})
        if detay.get('hastane', 0) > kullanici_hastane_puani:
            kullanici_hastane_puani = detay.get('hastane', 0)
    
    en_iyi_hastane = kullanici_hastanesi
    if kullanici_hastane_puani < 20:
        bulunan_hastaneler = {}
        for site, sonuc in doc['site_sonuclari'].items():
            if sonuc and sonuc.get('bulundu') and sonuc.get('hastane'):
                h = sonuc['hastane'].strip()
                if h and len(h) > 3:
                    bulunan_hastaneler[h] = bulunan_hastaneler.get(h, 0) + 1
        if bulunan_hastaneler:
            en_iyi_hastane = max(bulunan_hastaneler, key=bulunan_hastaneler.get)

    conn.execute('UPDATE doctors SET durum=?, hastane=? WHERE id=?', ('onaylandi', en_iyi_hastane, doctor_id))
    
    # Hastaneyi kalıcı listeye ekle
    if en_iyi_hastane:
        try:
            conn.execute('INSERT OR IGNORE INTO hospitals (name) VALUES (?)', (en_iyi_hastane,))
        except: pass
        
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/update-requests')
def get_update_requests():
    if not is_logged_in(): return jsonify([]), 401
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM update_requests').fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d['degisiklikler'] = json.loads(d['degisiklikler'])
        res.append(d)
    return jsonify(res)

@app.route('/api/approve-update-request/<request_id>', methods=['POST'])
def approve_update_request(request_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    req = conn.execute('SELECT * FROM update_requests WHERE id = ?', (request_id,)).fetchone()
    if not req:
        conn.close()
        return jsonify({'error': 'Talep bulunamadı'}), 404
    
    req = dict(req)
    degisiklikler = json.loads(req['degisiklikler'])
    
    # Doktoru güncelle
    set_clause = ", ".join([f"{k} = ?" for k in degisiklikler.keys()])
    values = list(degisiklikler.values()) + [req['doctor_id']]
    conn.execute(f"UPDATE doctors SET {set_clause}, durum = 'onaylandi' WHERE id = ?", values)
    
    # Talebi sil
    conn.execute('DELETE FROM update_requests WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/reject-update-request/<request_id>', methods=['POST'])
def reject_update_request(request_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    conn.execute('DELETE FROM update_requests WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/add-doctor-direct', methods=['POST'])
def add_doctor_direct():
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    doc_id = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO doctors (id, ad, soyad, unvan, brans, sehir, hastane, tarih, durum, site_sonuclari, site_puanlari)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (doc_id, data.get('ad'), data.get('soyad'), data.get('unvan'), 
          data.get('brans'), data.get('sehir'), data.get('hastane'), 
          datetime.now().isoformat(), 'onaylandi', '{}', '{}'))
    
    # Hastaneyi kalıcı listeye ekle
    hastane = data.get('hastane', '').strip()
    if hastane:
        try:
            conn.execute('INSERT OR IGNORE INTO hospitals (name) VALUES (?)', (hastane,))
        except: pass
        
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/doctor/<doctor_id>')
def get_doctor(doctor_id):
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['site_sonuclari'] = json.loads(d['site_sonuclari'])
        d['site_puanlari'] = json.loads(d['site_puanlari'])
        return jsonify(d)
    return jsonify({'error': 'Bulunamadı'}), 404

@app.route('/api/sehirler')
def get_sehirler(): 
    sehirler = load_json('data/sehirler.json')
    return jsonify(list(sehirler.values()))

@app.route('/api/pending-doctors')
def pending_doctors():
    if not is_logged_in(): return jsonify([]), 401
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM doctors WHERE durum IN ('beklemede', 'tamamlandi')").fetchall()
    conn.close()
    res = []
    for r in rows:
        d = dict(r)
        d['site_sonuclari'] = json.loads(d['site_sonuclari'])
        d['site_puanlari'] = json.loads(d['site_puanlari'])
        res.append(d)
    return jsonify(res)

@app.route('/api/hastaneler')
def get_hastaneler():
    conn = get_db_connection()
    hospitals = conn.execute('SELECT name FROM hospitals ORDER BY name ASC').fetchall()
    conn.close()
    return jsonify([h['name'] for h in hospitals])

@app.route('/api/hospital', methods=['PUT'])
def update_hospital():
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json
    eski_ad = data.get('eski_ad', '').strip()
    yeni_ad = data.get('yeni_ad', '').strip()
    
    conn = get_db_connection()
    conn.execute('UPDATE hospitals SET name = ? WHERE name = ?', (yeni_ad, eski_ad))
    conn.execute('UPDATE doctors SET hastane = ? WHERE hastane = ?', (yeni_ad, eski_ad))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/hospital/<path:hospital_name>', methods=['DELETE'])
def delete_hospital(hospital_name):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    conn.execute('DELETE FROM hospitals WHERE name = ?', (hospital_name,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/branslar')
def get_branslar(): return jsonify(BRANSLAR)

@app.route('/api/unvanlar')
def get_unvanlar(): return jsonify(UNVAN_LISTESI)


if __name__ == '__main__':
    from core.database import init_db, create_default_user
    init_db()
    
    # Varsayılan admin kullanıcısını oluştur (şifre: admin123)
    # Eğer kullanıcı zaten varsa create_default_user işlem yapmaz
    hashed_pw = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
    create_default_user(ADMIN_USERNAME, hashed_pw)
    
    app.run(debug=True, port=5000)
