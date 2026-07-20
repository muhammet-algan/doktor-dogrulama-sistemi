# Puanlama algoritması - AI Güçlendirilmiş
# Fuzzy Matching, TF-IDF Benzerliği ve Bayesian Ağırlıklı Puanlama
import re
from core.utils import compare_text, normalize_text
from core.ai_engine import FuzzyMatcher, TFIDFSimilarity

PUANLAR = {
    'ad': 10,
    'soyad': 10,
    'unvan': 20,
    'brans': 20,
    'sehir': 20,
    'hastane': 20
}

# Fuzzy eşleşme eşik değerleri
FUZZY_THRESHOLDS = {
    'ad': 0.75,
    'soyad': 0.75,
    'unvan': 0.80,
    'brans': 0.60,
    'sehir': 0.85,
    'hastane': 0.55
}


def compare_brans(girilen, bulunan_dict):
    """Branş karşılaştır - AI destekli fuzzy matching ile"""
    if not girilen:
        return False, 0.0
    ng = normalize_text(girilen)
    ng_words = [w for w in ng.split() if len(w) >= 3]

    best_similarity = 0.0

    if isinstance(bulunan_dict, dict):
        for val in bulunan_dict.values():
            if val and isinstance(val, str):
                nv = normalize_text(val)
                if not nv:
                    continue

                # 1. Birebir eşleşme
                if ng in nv or nv in ng:
                    return True, 1.0

                # 2. Kelime bazlı eşleşme
                for kw in ng_words:
                    if kw in nv:
                        return True, 0.9

                # 3. AI: Fuzzy benzerlik
                fuzzy_score = FuzzyMatcher.similarity(ng, nv)
                if fuzzy_score > best_similarity:
                    best_similarity = fuzzy_score

                # 4. AI: TF-IDF Cosine Similarity
                tfidf_score = TFIDFSimilarity.compare(ng, nv)
                combined = max(fuzzy_score, tfidf_score)
                if combined > best_similarity:
                    best_similarity = combined

    threshold = FUZZY_THRESHOLDS.get('brans', 0.60)
    return best_similarity >= threshold, round(best_similarity, 4)


def fuzzy_field_match(girilen_val, bulunan_val, field_name):
    """
    Tek bir alan için fuzzy eşleşme hesaplar.
    Dönüş: (eşleşti: bool, benzerlik: float)
    """
    g = normalize_text(girilen_val)
    b = normalize_text(bulunan_val)

    if not g or not b:
        return False, 0.0

    # 1. Birebir eşleşme
    if g == b:
        return True, 1.0

    # 2. İçerme kontrolü
    if g in b or b in g:
        return True, 0.95

    # 3. Fuzzy similarity
    fuzzy_score = FuzzyMatcher.similarity(g, b)

    # 4. TF-IDF (özellikle hastane ve branş için etkili)
    if field_name in ('hastane', 'brans'):
        tfidf_score = TFIDFSimilarity.compare(g, b)
        combined = max(fuzzy_score, tfidf_score)
    else:
        combined = fuzzy_score

    threshold = FUZZY_THRESHOLDS.get(field_name, 0.70)
    return combined >= threshold, round(combined, 4)


def hesapla_puan(girilen, bulunan):
    """Puanı hesapla - AI destekli fuzzy matching ile"""
    puan = 0
    detay = {}
    ai_detay = {}  # AI benzerlik skorları

    # Ad/Soyad için esnek eşleşme (Kelimelerin varlığını kontrol et)
    g_ad = normalize_text(girilen.get('ad', ""))
    g_soyad = normalize_text(girilen.get('soyad', ""))
    b_ad = normalize_text(bulunan.get('ad', ""))
    b_soyad = normalize_text(bulunan.get('soyad', ""))

    # Harf harf karşılaştırma yerine kelime seti olarak kontrol
    g_full = set(re.findall(r'\w+', g_ad + " " + g_soyad))
    b_full = set(re.findall(r'\w+', b_ad + " " + b_soyad))

    isim_eslesti = False
    isim_similarity = 0.0

    if g_full and b_full:
        # Klasik kelime seti eşleşmesi
        if g_full & b_full:
            common = len(g_full & b_full)
            if common >= min(len(g_full), len(b_full)):
                isim_eslesti = True
                isim_similarity = 1.0

        # AI: Fuzzy eşleşme (klasik eşleşme başarısız olursa)
        if not isim_eslesti:
            ad_match, ad_sim = fuzzy_field_match(g_ad, b_ad, 'ad')
            soyad_match, soyad_sim = fuzzy_field_match(g_soyad, b_soyad, 'soyad')
            isim_similarity = (ad_sim + soyad_sim) / 2

            if ad_match and soyad_match:
                isim_eslesti = True
            elif isim_similarity >= 0.70:
                isim_eslesti = True

    ai_detay['isim_benzerlik'] = isim_similarity

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

        # Branş için özel AI destekli karşılaştırma
        elif alan == 'brans':
            eslesti, benzerlik = compare_brans(girilen.get(alan, ""), bulunan)
            ai_detay['brans_benzerlik'] = benzerlik
            if eslesti:
                puan += max_puan
                detay[alan] = max_puan
            else:
                detay[alan] = 0

        # Hastane için AI destekli fuzzy eşleşme
        elif alan == 'hastane':
            if g and b:
                eslesti, benzerlik = fuzzy_field_match(g, b, 'hastane')
                ai_detay['hastane_benzerlik'] = benzerlik

                if eslesti:
                    puan += max_puan
                    detay[alan] = max_puan
                else:
                    # Kelime bazlı fallback
                    g_words = set(w for w in g.split() if len(w) >= 2)
                    b_words = set(w for w in b.split() if len(w) >= 2)
                    if g_words and b_words:
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

        # Diğer alanlar (şehir, unvan) için fuzzy eşleşme
        else:
            if g and b:
                eslesti, benzerlik = fuzzy_field_match(g, b, alan)
                ai_detay[f'{alan}_benzerlik'] = benzerlik
                if eslesti:
                    puan += max_puan
                    detay[alan] = max_puan
                else:
                    detay[alan] = 0
            else:
                detay[alan] = 0

    return puan, detay, ai_detay


def site_puani(girilen, site_verileri):
    """Tek site için puan hesapla"""
    if not site_verileri:
        return 0, {}, {}
    return hesapla_puan(girilen, site_verileri)
