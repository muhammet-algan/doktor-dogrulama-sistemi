"""
YARDIMCI ARAÇLAR (core/utils.py)
------------------------------
Metin normalizasyonu ve karşılaştırma gibi genel amaçlı yardımcı fonksiyonlar içerir.
Özellikle farklı sitelerden gelen verileri standart bir formatta karşılaştırmak için kullanılır.
"""
import re

def normalize_text(text):
    if not text:
        return ""
    text = str(text).strip().lower() 
    
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
        
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def compare_text(a, b):
        return normalize_text(a) == normalize_text(b)


