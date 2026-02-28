"""
YARDIMCI ARAÇLAR (core/utils.py)
------------------------------
Metin normalizasyonu ve karşılaştırma gibi genel amaçlı yardımcı fonksiyonlar içerir.
Özellikle farklı sitelerden gelen verileri standart bir formatta karşılaştırmak için kullanılır.
"""
import re

def normalize_text(text):
    """
    Metni karşılaştırmaya uygun hale getirir:
    - Küçük harfe çevirir.
    - Türkçe karakterleri İngilizce karşılıklarıyla değiştirir (ı->i, ş->s vb.).
    - Gereksiz boşlukları temizler.
    """
    if not text:
        return ""
    text = str(text).strip().lower() # str dönüşümü güvenliği için
    
    tr_map = {
        'ı': 'i', 'İ': 'i', 'I': 'i',
        'ğ': 'g', 'Ğ': 'g',
        'ü': 'u', 'Ü': 'u',
        'ş': 's', 'Ş': 's',
        'ö': 'o', 'Ö': 'o',
        'ç': 'c', 'Ç': 'c'
    }
    for k, v in tr_map.items():
        text = text.replace(k, v)
        
    # Boşlukları tekle indir ve temizle
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def compare_text(a, b):
    """İki metni normalize ederek tam eşleşme kontrolü yapar."""
    return normalize_text(a) == normalize_text(b)
