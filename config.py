"""
PROJE SÜRÜCÜ YAPILANDIRMASI (config.py)
-------------------------------------
Bu dosya sistem genelinde kullanılan sabitleri ve yapılandırma ayarlarını içerir.
UI listeleri, unvan eşleştirmeleri ve taranacak site listesi burada tanımlanır.
"""
import os
from dotenv import load_dotenv

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# Unvan eşleştirme (Sitelerden gelen farklı formatları standart forma dönüştürür)
UNVANLAR = {
    'prof. dr.': 'Prof. Dr.', 'prof.dr.': 'Prof. Dr.', 'prof dr': 'Prof. Dr.',
    'prof.': 'Prof. Dr.', 'prof': 'Prof. Dr.',
    'doç. dr.': 'Doç. Dr.', 'doç.dr.': 'Doç. Dr.', 'doç dr': 'Doç. Dr.',
    'doç.': 'Doç. Dr.', 'doç': 'Doç. Dr.',
    'op. dr.': 'Op. Dr.', 'op.dr.': 'Op. Dr.', 'op dr': 'Op. Dr.',
    'op.': 'Op. Dr.', 'op': 'Op. Dr.',
    'uzm. dr.': 'Uzm. Dr.', 'uzm.dr.': 'Uzm. Dr.', 'uzm dr': 'Uzm. Dr.',
    'uzm.': 'Uzm. Dr.', 'uzm': 'Uzm. Dr.',
    'dr.': 'Dr.', 'dr': 'Dr.',
    'cer.': 'Cer.', 'cer': 'Cer.',
    'prat.': 'Prat.', 'prat': 'Prat.'
}

# Yeni doktor ekleme formunda kullanıcıya sunulan unvan seçenekleri
UNVAN_LISTESI = ['Prof. Dr.', 'Doç. Dr.', 'Uzm. Dr.', 'Op. Dr.', 'Dr.', 'Cer.', 'Prat.']

# Desteklenen tıbbi branşlar listesi
BRANSLAR = [
    'Acil Tıp', 'Aile Hekimliği', 'Anestezi ve Reanimasyon',
    'Beyin ve Sinir Cerrahisi', 'Çocuk Cerrahisi',
    'Çocuk Sağlığı ve Hastalıkları', 'Dahiliye', 'Dermatoloji',
    'Diş Hekimi', 'Endokrinoloji', 'Enfeksiyon Hastalıkları',
    'Fizik Tedavi ve Rehabilitasyon', 'Gastroenteroloji',
    'Genel Cerrahi', 'Göğüs Cerrahisi', 'Göğüs Hastalıkları',
    'Göz Hastalıkları', 'Kadın Hastalıkları ve Doğum',
    'Kalp ve Damar Cerrahisi', 'Kardiyoloji', 'Kulak Burun Boğaz',
    'Nöroloji', 'Ortopedi ve Travmatoloji', 'Plastik Cerrahi',
    'Psikiyatri', 'Psikoloji', 'Radyoloji', 'Üroloji'
]

# Taranacak sitelerin listesi ve temel adresleri
SITELER = [
    {'ad': 'DoktorYorum', 'url': 'https://doktoryorum.net'},
    {'ad': 'DoktorAraBul', 'url': 'https://doktorarabul.com.tr'},
    {'ad': 'TrDoktor', 'url': 'https://www.trdoktor.com'},
    {'ad': 'DoktorUzman', 'url': 'https://www.doktoruzman.com'},
    {'ad': 'BulutKlinik', 'url': 'https://bulutklinik.com'},
    {'ad': 'DoktorNumarasi', 'url': 'https://www.doktornumarasi.com'},
    {'ad': 'IsteBuDoktor', 'url': 'https://istebudoktor.com.tr'},
    {'ad': 'DoktorunuBil', 'url': 'http://www.doktorunubil.com'},
    {'ad': 'DoktorTakvimi', 'url': 'https://www.doktortakvimi.com'},
    {'ad': 'DoktorSitesi', 'url': 'https://www.doktorsitesi.com'}
]

# Yönetim paneli giriş bilgileri
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
