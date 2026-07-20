"""
ANA UYGULAMA SUNUCUSU (app.py) - PRODUCTION READY
--------------------------------------------
Flask tabanlı web sunucusu. SQLite veritabanı ve güvenli oturum yönetimi içerir.
Siber güvenlik ve yapay zeka metotları entegre edilmiştir.
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

# --- SİBER GÜVENLİK: Import ---
from core.security import (
    rate_limiter,
    brute_force,
    generate_csrf_token,
    validate_csrf_token,
    sanitize_input,
    sanitize_dict,
    check_honeypot,
    add_security_headers,
    log_security_event,
    log_audit,
    get_client_ip
)

# --- YAPAY ZEKA: Import ---
from core.ai_engine import (
    AIDecisionEngine,
    BayesianScorer,
    AnomalyDetector
)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Üretim ortamında sabit bir anahtar kullanılmalı
bcrypt = Bcrypt(app)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================
# SİBER GÜVENLİK: After-request middleware
# =============================================
@app.after_request
def apply_security_headers(response):
    """Her yanıta güvenlik başlıklarını otomatik ekler."""
    return add_security_headers(response)


# =============================================
# SİBER GÜVENLİK: CSRF token'ı template context'ine ekle
# =============================================
@app.context_processor
def inject_csrf_token():
    """Tüm template'lere csrf_token fonksiyonunu enjekte eder."""
    return dict(csrf_token=generate_csrf_token)


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
    ip = get_client_ip()

    # --- SİBER GÜVENLİK: Rate Limiting ---
    if rate_limiter.is_rate_limited(ip, '/api/login', max_requests=10, window_seconds=60):
        log_security_event(ip, 'RATE_LIMITED', 'Login endpoint rate limit asildi')
        return jsonify({'success': False, 'message': 'Çok fazla istek gönderdiniz. Lütfen bekleyin.'}), 429

    # --- SİBER GÜVENLİK: Brute Force Koruması ---
    allowed, error_msg = brute_force.check_and_record(ip)
    if not allowed:
        return jsonify({'success': False, 'message': error_msg}), 403

    # --- SİBER GÜVENLİK: Input Sanitization ---
    username = sanitize_input(username)
    
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    
    if user and bcrypt.check_password_hash(user['password_hash'], password):
        # Başarılı giriş
        brute_force.record_success(ip)
        session['logged_in'] = True
        session['username'] = username
        log_security_event(ip, 'LOGIN_SUCCESS', f'Kullanici: {username}')
        return jsonify({'success': True})
    
    # Başarısız giriş
    locked = brute_force.record_failure(ip)
    log_security_event(ip, 'LOGIN_FAILURE', f'Basarisiz giris denemesi. Kullanici: {username}')
    
    if locked:
        return jsonify({'success': False, 'message': f'Çok fazla başarısız deneme. {brute_force.LOCKOUT_MINUTES} dakika sonra tekrar deneyin.'}), 403
    
    return jsonify({'success': False, 'message': 'Hatalı kullanıcı adı veya şifre'}), 401

@app.route('/api/logout')
def logout():
    username = session.get('username', '')
    ip = get_client_ip()
    log_security_event(ip, 'LOGOUT', f'Kullanici: {username}')
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

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(username, 'PASSWORD_CHANGE', username, 'Sifre degistirildi')
    
    return jsonify({'success': True})

@app.route('/api/submit', methods=['POST'])
def submit():
    data = request.json
    ip = get_client_ip()

    # --- SİBER GÜVENLİK: Rate Limiting ---
    if rate_limiter.is_rate_limited(ip, '/api/submit', max_requests=5, window_seconds=60):
        log_security_event(ip, 'RATE_LIMITED', 'Form submit rate limit asildi')
        return jsonify({'success': False, 'message': 'Çok fazla istek gönderdiniz. Lütfen bekleyin.'}), 429

    # --- SİBER GÜVENLİK: Honeypot Bot Tuzağı ---
    if check_honeypot(data):
        return jsonify({'success': False, 'message': 'İşlem reddedildi.'}), 400

    # --- SİBER GÜVENLİK: Input Sanitization ---
    data = sanitize_dict(data)

    doc_id = str(uuid.uuid4())
    tarih = datetime.now().isoformat()

    # --- YAPAY ZEKA: Anomali Tespiti (Risk Skoru) ---
    risk_skoru, risk_faktorleri = AnomalyDetector.calculate_risk_score(data, ip)

    # Güvenlik olayı: Form gönderimi kaydet
    log_security_event(ip, 'FORM_SUBMIT', f'Doktor: {data.get("ad", "")} {data.get("soyad", "")} | Risk: {risk_skoru}')
    
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO doctors (id, ad, soyad, unvan, brans, sehir, hastane, tarih, durum, site_sonuclari, site_puanlari)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (doc_id, data.get('ad', ''), data.get('soyad', ''), data.get('unvan', ''),
          data.get('brans', ''), data.get('sehir', ''),
          data.get('hastane', ''), tarih, 'beklemede', '{}', '{}'))
    conn.commit()
    conn.close()
    
    Thread(target=verify_doctor, args=(doc_id, data, ip)).start()
    return jsonify({'success': True, 'message': 'DOKTOR BİLDİRİLDİ'})

def verify_doctor(doctor_id, doctor_data=None, client_ip=None):
    try:
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
        if not row: return
        
        doctor = dict(row)
        sonuclar = tum_siteleri_tara(doctor)
        
        puanlar = {}
        for site_adi, site_verisi in sonuclar.items():
            try:
                puan, detay, ai_detay = site_puani(doctor, site_verisi or {})
                puanlar[site_adi] = {'puan': puan, 'detay': detay, 'ai_detay': ai_detay}
            except:
                puanlar[site_adi] = {'puan': 0, 'detay': {}, 'ai_detay': {}}

        # --- YAPAY ZEKA: AI Karar Önerisi ---
        ai_recommendation = AIDecisionEngine.get_recommendation(
            puanlar,
            doctor_data or doctor,
            client_ip
        )

        # Puanlar JSON'ına AI önerisini ekle
        ai_data = {
            '_ai_recommendation': ai_recommendation
        }
        puanlar['_ai'] = ai_data
        
        # Check current status to prevent overwriting approved doctor
        status_row = conn.execute('SELECT durum FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
        new_durum = 'tamamlandi'
        if status_row and status_row['durum'] == 'onaylandi':
            new_durum = 'onaylandi'

        conn.execute('''
            UPDATE doctors 
            SET site_sonuclari = ?, site_puanlari = ?, durum = ? 
            WHERE id = ?
        ''', (json.dumps(sonuclar), json.dumps(puanlar), new_durum, doctor_id))
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

    # --- SİBER GÜVENLİK: Audit Log ---
    conn = get_db_connection()
    doc = conn.execute('SELECT ad, soyad FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    doc_name = f"{doc['ad']} {doc['soyad']}" if doc else doctor_id
    
    conn.execute('DELETE FROM doctors WHERE id = ?', (doctor_id,))
    conn.commit()
    conn.close()

    log_audit(session.get('username'), 'DELETE_DOCTOR', doc_name, f'Doktor kaydı silindi: {doctor_id}')
    return jsonify({'success': True})

@app.route('/api/doctor/<doctor_id>', methods=['PUT'])
def update_doctor(doctor_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json

    # --- SİBER GÜVENLİK: Input Sanitization ---
    data = sanitize_dict(data)

    conn = get_db_connection()
    conn.execute('''
        UPDATE doctors SET ad=?, soyad=?, unvan=?, brans=?, sehir=?, hastane=?
        WHERE id=?
    ''', (data.get('ad'), data.get('soyad'), data.get('unvan'), 
          data.get('brans'), data.get('sehir'), data.get('hastane'), doctor_id))
    conn.commit()
    conn.close()

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'EDIT_DOCTOR', f"{data.get('ad')} {data.get('soyad')}", f'Doktor bilgileri güncellendi: {doctor_id}')
    return jsonify({'success': True})

@app.route('/api/approve-doctor/<doctor_id>', methods=['POST'])
def approve_doctor(doctor_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    doc = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    if not doc: 
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    
    doc = dict(doc)
    
    # Safe JSON parsing
    site_puanlari = {}
    if doc.get('site_puanlari'):
        try:
            site_puanlari = json.loads(doc['site_puanlari'])
        except Exception:
            pass
    if not isinstance(site_puanlari, dict):
        site_puanlari = {}

    site_sonuclari = {}
    if doc.get('site_sonuclari'):
        try:
            site_sonuclari = json.loads(doc['site_sonuclari'])
        except Exception:
            pass
    if not isinstance(site_sonuclari, dict):
        site_sonuclari = {}
    
    # En iyi hastane ismini bulma mantığı
    kullanici_hastanesi = doc.get('hastane', '').strip() if doc.get('hastane') else ''
    kullanici_hastane_puani = 0
    for site, puan_data in site_puanlari.items():
        if site == '_ai':
            continue  # AI meta verisini atla
        if isinstance(puan_data, dict):
            detay = puan_data.get('detay', {})
            if isinstance(detay, dict):
                hastane_puan = detay.get('hastane', 0)
                if isinstance(hastane_puan, (int, float)) and hastane_puan > kullanici_hastane_puani:
                    kullanici_hastane_puani = hastane_puan
    
    en_iyi_hastane = kullanici_hastanesi
    if kullanici_hastane_puani < 20:
        bulunan_hastaneler = {}
        for site, sonuc in site_sonuclari.items():
            if isinstance(sonuc, dict) and sonuc.get('bulundu') and sonuc.get('hastane'):
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

    # --- YAPAY ZEKA: Site güvenilirlik güncelleme ---
    # pass conn to avoid database locking issues
    try:
        for site_adi, puan_data in site_puanlari.items():
            if site_adi == '_ai':
                continue
            
            puan = 0
            if isinstance(puan_data, dict):
                puan = puan_data.get('puan', 0)
            elif isinstance(puan_data, (int, float)):
                puan = puan_data
                
            was_correct = puan > 40
            BayesianScorer.update_site_reliability(site_adi, was_correct, conn=conn)
    except Exception as e:
        print(f"Error updating site reliability: {e}")
        
    conn.commit()
    conn.close()

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'APPROVE_DOCTOR', f"{doc.get('ad', '')} {doc.get('soyad', '')}", f'Doktor onaylandi: {doctor_id}')
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

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'APPROVE_UPDATE', req.get('doctor_name', ''), f'Guncelleme onaylandi: {request_id}')
    return jsonify({'success': True})

@app.route('/api/reject-update-request/<request_id>', methods=['POST'])
def reject_update_request(request_id):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()

    req = conn.execute('SELECT doctor_name FROM update_requests WHERE id = ?', (request_id,)).fetchone()
    doc_name = req['doctor_name'] if req else request_id

    conn.execute('DELETE FROM update_requests WHERE id = ?', (request_id,))
    conn.commit()
    conn.close()

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'REJECT_UPDATE', doc_name, f'Guncelleme reddedildi: {request_id}')
    return jsonify({'success': True})

@app.route('/api/add-doctor-direct', methods=['POST'])
def add_doctor_direct():
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    data = request.json

    # --- SİBER GÜVENLİK: Input Sanitization ---
    data = sanitize_dict(data)

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

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'ADD_DOCTOR_DIRECT', f"{data.get('ad')} {data.get('soyad')}", 'Admin tarafindan dogrudan eklendi')
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

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'EDIT_HOSPITAL', yeni_ad, f'Hastane adi degistirildi: {eski_ad} -> {yeni_ad}')
    return jsonify({'success': True})

@app.route('/api/hospital/<path:hospital_name>', methods=['DELETE'])
def delete_hospital(hospital_name):
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    conn = get_db_connection()
    conn.execute('DELETE FROM hospitals WHERE name = ?', (hospital_name,))
    conn.commit()
    conn.close()

    # --- SİBER GÜVENLİK: Audit Log ---
    log_audit(session.get('username'), 'DELETE_HOSPITAL', hospital_name, 'Hastane silindi')
    return jsonify({'success': True})

@app.route('/api/branslar')
def get_branslar(): return jsonify(BRANSLAR)

@app.route('/api/unvanlar')
def get_unvanlar(): return jsonify(UNVAN_LISTESI)


# =============================================
# YAPAY ZEKA: AI Karar Önerisi API
# =============================================
@app.route('/api/ai-recommendation/<doctor_id>')
def get_ai_recommendation(doctor_id):
    """Belirli bir doktor için AI karar önerisini döndürür."""
    if not is_logged_in(): return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    row = conn.execute('SELECT * FROM doctors WHERE id = ?', (doctor_id,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Doktor bulunamadı'}), 404
    
    doctor = dict(row)
    site_puanlari = json.loads(doctor['site_puanlari']) if doctor['site_puanlari'] else {}
    
    # Eğer daha önce hesaplanmışsa, cache'den döndür
    if '_ai' in site_puanlari and '_ai_recommendation' in site_puanlari['_ai']:
        return jsonify(site_puanlari['_ai']['_ai_recommendation'])
    
    # Yoksa yeniden hesapla
    ai_puanlar = {k: v for k, v in site_puanlari.items() if k != '_ai'}
    recommendation = AIDecisionEngine.get_recommendation(ai_puanlar, doctor)
    
    return jsonify(recommendation)


# =============================================
# SİBER GÜVENLİK: Güvenlik Olayları API
# =============================================
@app.route('/api/security-events')
def get_security_events():
    """Son güvenlik olaylarını döndürür (Admin paneli için)."""
    if not is_logged_in(): return jsonify([]), 401
    
    conn = get_db_connection()
    events = conn.execute(
        'SELECT * FROM security_events ORDER BY timestamp DESC LIMIT 100'
    ).fetchall()
    conn.close()
    
    return jsonify([dict(e) for e in events])


@app.route('/api/audit-logs')
def get_audit_logs():
    """Son denetim kayıtlarını döndürür (Admin paneli için)."""
    if not is_logged_in(): return jsonify([]), 401
    
    conn = get_db_connection()
    logs = conn.execute(
        'SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100'
    ).fetchall()
    conn.close()
    
    return jsonify([dict(l) for l in logs])


@app.route('/api/security-stats')
def get_security_stats():
    """Güvenlik istatistiklerini döndürür (Dashboard kartı için)."""
    if not is_logged_in(): return jsonify({}), 401
    
    conn = get_db_connection()
    
    # Son 24 saat güvenlik olayları
    today = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    
    total_events = conn.execute(
        'SELECT COUNT(*) as cnt FROM security_events WHERE timestamp > ?', (today,)
    ).fetchone()['cnt']
    
    failed_logins = conn.execute(
        "SELECT COUNT(*) as cnt FROM security_events WHERE event_type='LOGIN_FAILURE' AND timestamp > ?", (today,)
    ).fetchone()['cnt']
    
    blocked_ips = conn.execute(
        "SELECT COUNT(*) as cnt FROM security_events WHERE event_type='BRUTE_FORCE_LOCK' AND timestamp > ?", (today,)
    ).fetchone()['cnt']
    
    bots_detected = conn.execute(
        "SELECT COUNT(*) as cnt FROM security_events WHERE event_type='HONEYPOT_TRIGGERED' AND timestamp > ?", (today,)
    ).fetchone()['cnt']
    
    conn.close()
    
    return jsonify({
        'total_events': total_events,
        'failed_logins': failed_logins,
        'blocked_ips': blocked_ips,
        'bots_detected': bots_detected
    })


# =============================================
# SİBER GÜVENLİK: CSRF Token API
# =============================================
@app.route('/api/csrf-token')
def get_csrf_token():
    """CSRF token döndürür (AJAX istekleri için)."""
    return jsonify({'csrf_token': generate_csrf_token()})


# =============================================
# Güncelleme Talebi (Kullanıcı tarafı)
# =============================================
@app.route('/api/update-request', methods=['POST'])
def submit_update_request():
    data = request.json
    ip = get_client_ip()

    # --- SİBER GÜVENLİK: Rate Limiting ---
    if rate_limiter.is_rate_limited(ip, '/api/update-request', max_requests=5, window_seconds=60):
        log_security_event(ip, 'RATE_LIMITED', 'Update request rate limit asildi')
        return jsonify({'success': False, 'message': 'Çok fazla istek gönderdiniz.'}), 429

    # --- SİBER GÜVENLİK: Honeypot ---
    if check_honeypot(data):
        return jsonify({'success': False, 'message': 'İşlem reddedildi.'}), 400

    req_id = str(uuid.uuid4())
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO update_requests (id, doctor_id, doctor_name, degisiklikler, tarih, durum)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (req_id, data.get('doctor_id'), data.get('doctor_name'),
          json.dumps(data.get('degisiklikler', {})),
          datetime.now().isoformat(), 'beklemede'))
    conn.commit()
    conn.close()

    log_security_event(ip, 'UPDATE_REQUEST', f'Guncelleme talebi: {data.get("doctor_name", "")}')
    return jsonify({'success': True})


if __name__ == '__main__':
    from core.database import init_db, create_default_user
    init_db()
    
    # Varsayılan admin kullanıcısını oluştur (şifre: admin123)
    # Eğer kullanıcı zaten varsa create_default_user işlem yapmaz
    hashed_pw = bcrypt.generate_password_hash(ADMIN_PASSWORD).decode('utf-8')
    create_default_user(ADMIN_USERNAME, hashed_pw)
    
    app.run(debug=True, port=5000)
