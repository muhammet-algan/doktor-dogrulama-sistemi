# Puanlama algoritması
import re
from core.utils import compare_text, normalize_text

PUANLAR = {
    'ad': 10,
    'soyad': 10,
    'unvan': 20,
    'brans': 20,
    'sehir': 20,
    'hastane': 20
}

def compare_brans(girilen, bulunan_dict):
    """Branş karşılaştır"""
    if not girilen:
        return False
    ng = normalize_text(girilen)
    ng_words = [w for w in ng.split() if len(w) >= 3]
    
    if isinstance(bulunan_dict, dict):
        for val in bulunan_dict.values():
            if val and isinstance(val, str):
                nv = normalize_text(val)
                if ng in nv or nv in ng:
                    return True
                for kw in ng_words:
                    if kw in nv:
                        return True
    return False

def hesapla_puan(girilen, bulunan):
    """Puanı hesapla"""
    puan = 0
    detay = {}
    
    # Ad/Soyad için esnek eşleşme (Kelimelerin varlığını kontrol et)
    g_ad = normalize_text(girilen.get('ad', ""))
    g_soyad = normalize_text(girilen.get('soyad', ""))
    b_ad = normalize_text(bulunan.get('ad', ""))
    b_soyad = normalize_text(bulunan.get('soyad', ""))
    
    # Harf harf karşılaştırma yerine kelime seti olarak kontrol
    g_full = set(re.findall(r'\w+', g_ad + " " + g_soyad))
    b_full = set(re.findall(r'\w+', b_ad + " " + b_soyad))
    
    isim_eslesti = False
    if g_full and b_full:
        # En az bir isim ve soyisim kelimesi eşleşmeli
        if g_full & b_full:
            common = len(g_full & b_full)
            if common >= min(len(g_full), len(b_full)):
                isim_eslesti = True
            
    for alan, max_puan in PUANLAR.items():
        g = normalize_text(girilen.get(alan, ""))
        b = normalize_text(bulunan.get(alan, ""))
        
        # Ad/Soyad için ortak sonuç kullan
        if alan in ('ad', 'soyad'):
            if isim_eslesti:
                puan += max_puan
                detay[alan] = max_puan
            else:
                detay[alan] = 0
        # Branş için özel
        elif alan == 'brans':
            if compare_brans(girilen.get(alan, ""), bulunan):
                puan += max_puan
                detay[alan] = max_puan
            else:
                detay[alan] = 0
        # Hastane için kelime eşleşmesi (%60 yeterli)
        elif alan == 'hastane':
            if g and b:
                g_words = set(w for w in g.split() if len(w) >= 2)
                b_words = set(w for w in b.split() if len(w) >= 2)
                if g in b or b in g:
                    puan += max_puan
                    detay[alan] = max_puan
                elif g_words and b_words:
                    common = len(g_words & b_words)
                    if common >= 1 and (common / len(g_words) >= 0.5 or common / len(b_words) >= 0.5):
                        puan += max_puan
                        detay[alan] = max_puan
                    else:
                        detay[alan] = 0
                else:
                    detay[alan] = 0
            else:
                detay[alan] = 0
        # Diğer alanlar için kısmi eşleşme kabul
        elif g and b and (g == b or g in b or b in g):
            puan += max_puan
            detay[alan] = max_puan
        else:
            detay[alan] = 0
    
    return puan, detay

def site_puani(girilen, site_verileri):
    """Tek site için puan hesapla"""
    if not site_verileri:
        return 0, {}
    return hesapla_puan(girilen, site_verileri)
