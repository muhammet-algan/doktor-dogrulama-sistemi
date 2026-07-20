"""
YAPAY ZEKA MOTORU (core/ai_engine.py)
------------------------------------
Bulanık metin eşleştirme (Fuzzy Matching), TF-IDF tabanlı metin benzerliği,
Bayesian güven skoru, anomali tespiti ve otomatik karar önerisi metotları.

NOT: Tüm algoritmalar saf Python ile yazılmıştır. numpy, sklearn gibi
     ağır kütüphanelere bağımlılık yoktur.
"""
import re
import math
from difflib import SequenceMatcher
from collections import Counter
from datetime import datetime, timedelta
from core.utils import normalize_text
from core.database import get_db_connection


# =============================================
# 1. FUZZY MATCHING (Bulanık Metin Eşleştirme)
# =============================================
class FuzzyMatcher:
    """
    difflib.SequenceMatcher tabanlı bulanık metin eşleştirme.

    Geleneksel birebir eşleştirme yerine, yazım hatalarına ve
    farklı formatlara toleranslı benzerlik oranı hesaplar.

    Örnek:
        FuzzyMatcher.similarity("Ahmet Yılmaz", "Ahmet Yilmaz") → 0.92
        FuzzyMatcher.similarity("Özel Yıldız Hastanesi", "Yıldız Özel Hastanesi") → 0.85
    """

    @staticmethod
    def similarity(text1, text2):
        """
        İki metin arasındaki benzerlik oranını hesaplar.

        Dönüş: 0.0 (tamamen farklı) - 1.0 (birebir aynı)

        Algoritma:
        1. Karakter dizisi benzerliği (SequenceMatcher) - %40 ağırlık
        2. Kelime seti benzerliği (Jaccard) - %60 ağırlık
        """
        if not text1 or not text2:
            return 0.0

        t1 = normalize_text(text1)
        t2 = normalize_text(text2)

        if t1 == t2:
            return 1.0

        if not t1 or not t2:
            return 0.0

        # Karakter dizisi benzerliği
        char_ratio = SequenceMatcher(None, t1, t2).ratio()

        # Kelime bazlı Jaccard benzerliği
        words1 = set(t1.split())
        words2 = set(t2.split())

        if words1 and words2:
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            word_ratio = intersection / union if union > 0 else 0.0
            # Ağırlıklı ortalama
            combined = (char_ratio * 0.4) + (word_ratio * 0.6)
        else:
            combined = char_ratio

        return round(combined, 4)

    @staticmethod
    def partial_match(query, text, threshold=0.6):
        """
        Sorgu metninin hedef metin içinde kısmi eşleşip eşleşmediğini kontrol eder.
        Alt-dizi eşleşmesine benzer ama toleranslı.
        """
        if not query or not text:
            return False

        q = normalize_text(query)
        t = normalize_text(text)

        # Tam içerme kontrolü
        if q in t or t in q:
            return True

        return FuzzyMatcher.similarity(q, t) >= threshold

    @staticmethod
    def best_match(query, candidates, threshold=0.5):
        """
        Verilen aday listesinden sorguya en benzer olanı bulur.

        Dönüş: (en_iyi_aday, benzerlik_skoru) veya (None, 0)
        """
        best_score = 0
        best_candidate = None

        for candidate in candidates:
            score = FuzzyMatcher.similarity(query, candidate)
            if score > best_score and score >= threshold:
                best_score = score
                best_candidate = candidate

        return best_candidate, best_score


# =============================================
# 2. TF-IDF METİN BENZERLİĞİ (Cosine Similarity)
# =============================================
class TFIDFSimilarity:
    """
    Saf Python ile TF-IDF (Term Frequency - Inverse Document Frequency)
    tabanlı metin benzerliği hesaplama.

    Metinleri vektörlere dönüştürüp Cosine Similarity ile karşılaştırır.
    Özellikle hastane ve branş isimlerinin karşılaştırılmasında kullanılır.

    Örnek:
        TFIDFSimilarity.compare(
            "Ankara Üniversitesi Tıp Fakültesi Hastanesi",
            "Ankara Üniversitesi Hastanesi Tıp Fakültesi"
        ) → 0.95
    """

    @staticmethod
    def tokenize(text):
        """Metni normalize edip kelimelere ayırır (2+ karakter)."""
        if not text:
            return []
        t = normalize_text(text)
        return [w for w in t.split() if len(w) >= 2]

    @staticmethod
    def tf(tokens):
        """Term Frequency: Her kelimenin dokümandaki frekansı."""
        counter = Counter(tokens)
        total = len(tokens)
        if total == 0:
            return {}
        return {word: count / total for word, count in counter.items()}

    @staticmethod
    def idf(documents):
        """Inverse Document Frequency: Nadir kelimelere daha yüksek ağırlık."""
        n = len(documents)
        idf_dict = {}
        all_tokens = set()

        for doc in documents:
            all_tokens.update(set(doc))

        for token in all_tokens:
            containing = sum(1 for doc in documents if token in doc)
            # Smoothed IDF
            idf_dict[token] = math.log((n + 1) / (containing + 1)) + 1

        return idf_dict

    @staticmethod
    def cosine_similarity(vec1, vec2):
        """İki TF-IDF vektörü arasındaki Cosine Similarity."""
        all_keys = set(vec1.keys()) | set(vec2.keys())

        dot_product = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
        magnitude1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        magnitude2 = math.sqrt(sum(v ** 2 for v in vec2.values()))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return round(dot_product / (magnitude1 * magnitude2), 4)

    @classmethod
    def compare(cls, text1, text2):
        """
        İki metin arasındaki TF-IDF Cosine Similarity'yi hesaplar.

        Dönüş: 0.0 (tamamen farklı) - 1.0 (birebir aynı)
        """
        tokens1 = cls.tokenize(text1)
        tokens2 = cls.tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        # IDF hesapla (iki doküman üzerinden)
        idf_dict = cls.idf([tokens1, tokens2])

        # TF-IDF vektörleri
        tf1 = cls.tf(tokens1)
        tf2 = cls.tf(tokens2)

        tfidf1 = {word: tf_val * idf_dict.get(word, 1) for word, tf_val in tf1.items()}
        tfidf2 = {word: tf_val * idf_dict.get(word, 1) for word, tf_val in tf2.items()}

        return cls.cosine_similarity(tfidf1, tfidf2)


# =============================================
# 3. BAYESIAN GÜVEN SKORU
# =============================================
class BayesianScorer:
    """
    Bayesian istatistik yaklaşımıyla güven skoru hesaplama.

    Her sitenin geçmiş doğruluk oranına (prior) göre ağırlık verir ve
    doktorun kaç sitede, ne kalitede bulunduğunu değerlendirerek
    posterior güven skoru üretir.

    Formül:
        P(Gerçek | Veriler) ∝ Σ (site_ağırlığı × eşleşme_puanı) / Σ site_ağırlığı
        × güven_çarpanı (bulunma oranına bağlı)
    """

    # Varsayılan site güvenilirlik ağırlıkları (prior probability)
    DEFAULT_WEIGHTS = {
        'DoktorTakvimi': 0.90,
        'DoktorSitesi': 0.85,
        'DoktorYorum': 0.80,
        'IsteBuDoktor': 0.80,
        'DoktorAraBul': 0.75,
        'BulutKlinik': 0.75,
        'DoktorUzman': 0.70,
        'DoktorNumarasi': 0.70,
        'DoktorunuBil': 0.65,
        'TrDoktor': 0.65
    }

    @classmethod
    def get_site_weight(cls, site_name):
        """
        Bir sitenin güvenilirlik ağırlığını döndürür.
        Veritabanında öğrenilmiş değer varsa onu, yoksa varsayılanı kullanır.
        """
        try:
            conn = get_db_connection()
            row = conn.execute(
                'SELECT success_rate FROM site_reliability WHERE site_name = ?',
                (site_name,)
            ).fetchone()
            conn.close()
            if row and row['success_rate'] is not None:
                return row['success_rate']
        except Exception:
            pass

        return cls.DEFAULT_WEIGHTS.get(site_name, 0.5)

    @classmethod
    def calculate(cls, site_puanlari):
        """
        Bayesian güven skoru hesaplar.

        Parametre:
            site_puanlari: {'SiteAdi': {'puan': 80, 'detay': {...}}, ...}

        Dönüş: 0-100 arası güven skoru (float)
        """
        if not site_puanlari:
            return 0.0

        toplam_agirlik = 0.0
        agirlikli_puan = 0.0
        bulunma_sayisi = 0
        toplam_site = 0

        for site_adi, puan_data in site_puanlari.items():
            puan = puan_data.get('puan', 0) if isinstance(puan_data, dict) else 0
            agirlik = cls.get_site_weight(site_adi)
            toplam_site += 1

            if puan > 0:
                bulunma_sayisi += 1
                agirlikli_puan += puan * agirlik
                toplam_agirlik += agirlik

        if toplam_agirlik == 0:
            return 0.0

        # Temel skor = Ağırlıklı ortalama puan
        temel_skor = agirlikli_puan / toplam_agirlik

        # Bulunma oranına göre güven çarpanı
        if bulunma_sayisi <= 1:
            guven_carpani = 0.50  # Tek sitede bulunmak düşük güven
        elif bulunma_sayisi <= 3:
            guven_carpani = 0.75  # 2-3 site orta güven
        elif bulunma_sayisi <= 5:
            guven_carpani = 0.90  # 4-5 site yüksek güven
        else:
            guven_carpani = 1.00  # 6+ site tam güven

        # Bayesian posterior
        bayesian_skor = temel_skor * guven_carpani

        return round(min(bayesian_skor, 100), 1)

    @classmethod
    def update_site_reliability(cls, site_name, was_correct, conn=None):
        """
        Bir sitenin güvenilirlik oranını günceller (öğrenme mekanizması).
        Admin onay/red kararlarına göre site ağırlıkları zamanla iyileşir.
        """
        should_close = False
        try:
            if conn is None:
                conn = get_db_connection()
                should_close = True
                
            row = conn.execute(
                'SELECT * FROM site_reliability WHERE site_name = ?',
                (site_name,)
            ).fetchone()

            if row:
                total = row['total_checks'] + 1
                successes = row['successful_checks'] + (1 if was_correct else 0)
                rate = round(successes / total, 4) if total > 0 else 0.5

                conn.execute(
                    'UPDATE site_reliability SET total_checks=?, successful_checks=?, success_rate=? WHERE site_name=?',
                    (total, successes, rate, site_name)
                )
            else:
                conn.execute(
                    'INSERT INTO site_reliability (site_name, total_checks, successful_checks, success_rate) VALUES (?, 1, ?, ?)',
                    (site_name, 1 if was_correct else 0, 1.0 if was_correct else 0.0)
                )

            if should_close:
                conn.commit()
                conn.close()
        except Exception as e:
            print(f"Error in update_site_reliability: {e}")
            if should_close:
                try: conn.close()
                except: pass



# =============================================
# 4. ANOMALİ TESPİTİ (Sahte Profil Algılama)
# =============================================
class AnomalyDetector:
    """
    Kural tabanlı anomali tespit sistemi.
    Gönderilen doktor bilgilerindeki şüpheli desenleri yakalar
    ve her gönderime 0-100 arası risk skoru atar.

    Kurallar:
    - Eksik alan sayısı kontrolü
    - İsim format kontrolü (uzunluk, rakam, özel karakter)
    - Aynı IP'den yoğun gönderi tespiti
    - Branş-unvan tutarsızlığı
    """

    @staticmethod
    def calculate_risk_score(doctor_data, client_ip=None):
        """
        Gönderime risk skoru atar.

        Dönüş: (risk_skoru: int [0-100], risk_faktorleri: list[str])
        """
        risk = 0
        risk_factors = []

        ad = doctor_data.get('ad', '').strip()
        soyad = doctor_data.get('soyad', '').strip()

        # --- KURAL 1: Eksik alan kontrolü ---
        optional_fields = ['unvan', 'brans', 'sehir', 'hastane']
        missing = sum(1 for f in optional_fields if not doctor_data.get(f, '').strip())
        if missing >= 3:
            risk += 15
            risk_factors.append(f"Cok fazla eksik alan ({missing}/4)")

        # --- KURAL 2: İsim uzunluk kontrolü ---
        if len(ad) < 2 or len(soyad) < 2:
            risk += 20
            risk_factors.append("Isim veya soyisim cok kisa")

        if len(ad) > 30 or len(soyad) > 30:
            risk += 15
            risk_factors.append("Isim veya soyisim anormal derecede uzun")

        # --- KURAL 3: İsimde rakam kontrolü ---
        if re.search(r'[0-9]', ad + soyad):
            risk += 25
            risk_factors.append("Isimde rakam tespit edildi")

        # --- KURAL 4: İsimde özel karakter kontrolü ---
        if re.search(r'[!@#$%^&*()+=\[\]{}|\\/<>]', ad + soyad):
            risk += 30
            risk_factors.append("Isimde ozel karakter tespit edildi")

        # --- KURAL 5: Aynı IP'den yoğun gönderi kontrolü ---
        if client_ip:
            try:
                conn = get_db_connection()
                one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
                result = conn.execute(
                    "SELECT COUNT(*) as cnt FROM security_events "
                    "WHERE ip=? AND event_type='FORM_SUBMIT' AND timestamp > ?",
                    (client_ip, one_hour_ago)
                ).fetchone()
                conn.close()

                if result and result['cnt'] > 10:
                    risk += 25
                    risk_factors.append(f"Ayni IP'den cok fazla gonderi ({result['cnt']}/saat)")
                elif result and result['cnt'] > 5:
                    risk += 10
                    risk_factors.append(f"Ayni IP'den sik gonderi ({result['cnt']}/saat)")
            except Exception:
                pass

        # --- KURAL 6: Branş-unvan tutarsızlık kontrolü ---
        brans = normalize_text(doctor_data.get('brans', ''))
        unvan = normalize_text(doctor_data.get('unvan', ''))

        if brans and unvan:
            # Diş hekimi branşı ama Dr. unvanı (Dt. olmalı)
            if 'dis' in brans and 'dt' not in unvan and 'dis' not in unvan:
                risk += 10
                risk_factors.append("Brans ve unvan tutarsizligi (Dis Hekimi - Dr.)")

        return min(risk, 100), risk_factors


# =============================================
# 5. OTOMATİK KARAR ÖNERİSİ MOTORU
# =============================================
class AIDecisionEngine:
    """
    Tüm AI metriklerini birleştirerek admin'e karar önerisi sunar.

    Karar Çıktıları:
        🟢 'onayla'  — Yüksek güven, otomatik onay önerisi
        🟡 'incele'  — Orta güven, manuel inceleme önerilir
        🔴 'reddet'  — Düşük güven, red önerisi
    """

    @classmethod
    def get_recommendation(cls, site_puanlari, doctor_data=None, client_ip=None):
        """
        AI karar önerisi üretir.

        Parametreler:
            site_puanlari: Site bazlı puan verileri
            doctor_data: Doktor bilgileri (anomali tespiti için)
            client_ip: İstemci IP adresi (risk analizi için)

        Dönüş: {
            'karar': 'onayla' | 'incele' | 'reddet',
            'guven': float (0-100),
            'bayesian_skor': float,
            'risk_skoru': int,
            'risk_faktorleri': list[str],
            'bulunma': str ("3/10")
        }
        """
        # 1. Bayesian güven skoru hesapla
        bayesian_skor = BayesianScorer.calculate(site_puanlari)

        # 2. Anomali/Risk skoru hesapla
        risk_skoru = 0
        risk_faktorleri = []
        if doctor_data:
            risk_skoru, risk_faktorleri = AnomalyDetector.calculate_risk_score(
                doctor_data, client_ip
            )

        # 3. Kaç sitede bulundu
        bulunma = sum(
            1 for v in (site_puanlari or {}).values()
            if isinstance(v, dict) and v.get('puan', 0) > 0
        )
        toplam = len(site_puanlari) if site_puanlari else 1

        # 4. Nihai güven skoru = Bayesian skor - (risk × 0.3)
        guven = max(0, bayesian_skor - (risk_skoru * 0.3))

        # 5. Karar verme
        if guven >= 60 and bulunma >= 3 and risk_skoru < 30:
            karar = 'onayla'
        elif guven < 25 or risk_skoru >= 60 or bulunma == 0:
            karar = 'reddet'
        else:
            karar = 'incele'

        return {
            'karar': karar,
            'guven': round(guven, 1),
            'bayesian_skor': bayesian_skor,
            'risk_skoru': risk_skoru,
            'risk_faktorleri': risk_faktorleri,
            'bulunma': f"{bulunma}/{toplam}"
        }
