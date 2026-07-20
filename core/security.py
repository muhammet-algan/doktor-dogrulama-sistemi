"""
SİBER GÜVENLİK MODÜLÜ (core/security.py)
-----------------------------------------
Rate Limiting, Brute Force Koruması, CSRF Token, Input Sanitization,
Honeypot Bot Tuzağı, HTTP Güvenlik Başlıkları ve Denetim Kaydı (Audit Log).
"""
import re
import time
import secrets
import html
from datetime import datetime, timedelta
from flask import request, session
from core.database import get_db_connection


# =============================================
# 1. RATE LIMITING (İstek Hız Sınırlama)
# =============================================
class RateLimiter:
    """
    IP bazlı in-memory istek hız sınırlayıcı.
    Belirli bir süre içinde aynı IP'den gelen istek sayısını kontrol eder.
    """

    def __init__(self):
        self._requests = {}  # {ip:endpoint -> [timestamp, ...]}

    def is_rate_limited(self, ip, endpoint, max_requests=10, window_seconds=60):
        """
        IP+endpoint kombinasyonu için istek limitini kontrol eder.
        True dönerse istek reddedilmelidir.
        """
        key = f"{ip}:{endpoint}"
        now = time.time()

        if key not in self._requests:
            self._requests[key] = []

        # Pencere dışındaki eski istekleri temizle
        self._requests[key] = [
            t for t in self._requests[key] if now - t < window_seconds
        ]

        if len(self._requests[key]) >= max_requests:
            return True

        self._requests[key].append(now)
        return False

    def clear_old_entries(self):
        """Bellekteki eski kayıtları temizler (periyodik bakım)."""
        now = time.time()
        for key in list(self._requests.keys()):
            self._requests[key] = [
                t for t in self._requests[key] if now - t < 300
            ]
            if not self._requests[key]:
                del self._requests[key]


# Global rate limiter instance
rate_limiter = RateLimiter()


# =============================================
# 2. BRUTE FORCE KORUMASI (Giriş Deneme Kilidi)
# =============================================
class BruteForceProtection:
    """
    Login brute force koruması.
    Belirli sayıda başarısız denemeden sonra IP'yi geçici olarak kilitler.
    """
    MAX_ATTEMPTS = 5
    LOCKOUT_MINUTES = 15

    def __init__(self):
        self._attempts = {}  # {ip: {'count': int, 'locked_until': float}}

    def check_and_record(self, ip):
        """
        IP'nin giriş yapmasına izin verilip verilmediğini kontrol eder.
        Dönüş: (izin_var: bool, hata_mesaji: str)
        """
        now = time.time()

        if ip in self._attempts:
            entry = self._attempts[ip]

            # Kilit süresi hala aktif mi?
            if entry.get('locked_until', 0) > now:
                remaining = int((entry['locked_until'] - now) / 60) + 1
                return False, f"Çok fazla başarısız deneme. {remaining} dakika sonra tekrar deneyin."

            # Kilit süresi dolduysa sıfırla
            if entry.get('locked_until', 0) > 0:
                del self._attempts[ip]
                return True, ""

        return True, ""

    def record_failure(self, ip):
        """Başarısız giriş denemesini kaydeder. Kilit oluştuysa True döner."""
        now = time.time()

        if ip not in self._attempts:
            self._attempts[ip] = {'count': 0, 'first_attempt': now}

        self._attempts[ip]['count'] += 1

        if self._attempts[ip]['count'] >= self.MAX_ATTEMPTS:
            self._attempts[ip]['locked_until'] = now + (self.LOCKOUT_MINUTES * 60)
            log_security_event(
                ip, 'BRUTE_FORCE_LOCK',
                f'IP kilitlendi: {self.MAX_ATTEMPTS} basarisiz deneme'
            )
            return True  # Kilitlendi

        return False

    def record_success(self, ip):
        """Başarılı giriş sonrası deneme sayacını sıfırlar."""
        if ip in self._attempts:
            del self._attempts[ip]


# Global brute force instance
brute_force = BruteForceProtection()


# =============================================
# 3. CSRF KORUMASI (Cross-Site Request Forgery)
# =============================================
def generate_csrf_token():
    """Oturum için benzersiz CSRF token oluşturur veya mevcut olanı döner."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(32)
    return session['_csrf_token']


def validate_csrf_token():
    """
    İstek içindeki CSRF token'ı oturumdaki ile karşılaştırır.
    Token geçerliyse True döner.
    """
    token = (
        request.headers.get('X-CSRF-Token')
        or (request.json or {}).get('csrf_token', '')
        or request.form.get('csrf_token', '')
    )
    expected = session.get('_csrf_token', '')
    if not token or not expected or token != expected:
        return False
    return True


# =============================================
# 4. INPUT SANITIZATION (Girdi Temizleme)
# =============================================
# Tehlikeli SQL kalıpları
_SQL_PATTERNS = [
    '--', ';--', '/*', '*/', 'xp_',
    'UNION SELECT', 'DROP TABLE', 'INSERT INTO',
    'DELETE FROM', 'UPDATE SET', 'EXEC('
]


def sanitize_input(text):
    """
    Kullanıcı girdisini XSS ve SQL Injection saldırılarına karşı temizler.
    """
    if not text or not isinstance(text, str):
        return text

    # 1. Script taglarını özellikle temizle
    text = re.sub(
        r'<script[^>]*>.*?</script>', '', text,
        flags=re.IGNORECASE | re.DOTALL
    )

    # 2. Tüm HTML etiketlerini temizle
    text = re.sub(r'<[^>]+>', '', text)

    # 3. HTML entity encode (XSS koruması)
    text = html.escape(text, quote=True)

    # 4. SQL Injection kalıplarını temizle (büyük/küçük harf duyarsız)
    text_upper = text.upper()
    for pattern in _SQL_PATTERNS:
        if pattern.upper() in text_upper:
            text = re.sub(re.escape(pattern), '', text, flags=re.IGNORECASE)

    # 5. Aşırı uzun girdileri kes (DoS koruması)
    text = text[:500]

    return text.strip()


def sanitize_dict(data):
    """Bir sözlük içindeki tüm string değerleri temizler."""
    if not isinstance(data, dict):
        return data
    return {
        k: sanitize_input(v) if isinstance(v, str) else v
        for k, v in data.items()
    }


# =============================================
# 5. HONEYPOT BOT TUZAĞI
# =============================================
def check_honeypot(data):
    """
    Formda gizlenmiş tuzak alanı kontrol eder.
    Botlar bu alanı doldurur, gerçek kullanıcılar göremez.
    True = bot tespit edildi, False = gerçek kullanıcı.
    """
    honeypot_value = data.get('website', '') or data.get('_hp_field', '')
    if honeypot_value:
        ip = get_client_ip()
        log_security_event(ip, 'HONEYPOT_TRIGGERED', f'Bot tespit edildi. Alan değeri: {honeypot_value[:50]}')
        return True
    return False


# =============================================
# 6. HTTP GÜVENLİK BAŞLIKLARI
# =============================================
def add_security_headers(response):
    """
    HTTP yanıtına güvenlik başlıkları ekler.
    OWASP önerilerine uygun standart başlıklar.
    """
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
    )
    return response


# =============================================
# 7. DENETİM KAYDI (Audit Log)
# =============================================
def log_security_event(ip, event_type, detail=''):
    """Güvenlik olayını veritabanına kaydeder."""
    try:
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO security_events (ip, event_type, detail, timestamp) VALUES (?, ?, ?, ?)',
            (ip or '', event_type, detail[:500] if detail else '', datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Güvenlik logu yazılamasa bile ana işlemi engelleme


def log_audit(username, action, target='', detail=''):
    """Admin işlemini denetim kaydına yazar."""
    try:
        ip = get_client_ip()
        conn = get_db_connection()
        conn.execute(
            'INSERT INTO audit_logs (username, action, target, detail, ip, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
            (username or '', action, target, detail[:500] if detail else '', ip, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_client_ip():
    """Gerçek istemci IP adresini döndürür (proxy arkasında bile)."""
    try:
        if request.headers.get('X-Forwarded-For'):
            return request.headers.get('X-Forwarded-For').split(',')[0].strip()
        return request.remote_addr or '0.0.0.0'
    except RuntimeError:
        return '0.0.0.0'
