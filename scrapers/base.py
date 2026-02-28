"""
TEMEL SCRAPER SINIFI (scrapers/base.py)
--------------------------------------
Tüm web tarayıcıları için ortak fonksiyonları ve yapıyı tanımlar.
Her site özelindeki scraper bu sınıftan türetilir.
"""
import requests
from bs4 import BeautifulSoup
import re

class BaseScraper:
    site_adi = "" # Alt sınıfta tanımlanacak (Örn: 'DoktorTakvimi')
    base_url = "" # Alt sınıfta tanımlanacak

    def get_html(self, url):
        """Web sayfasını indirir ve BeautifulSoup nesnesi döner."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en;q=0.8'
            }
            r = requests.get(url, headers=headers, timeout=6)
            if r.status_code == 200:
                return BeautifulSoup(r.text, 'lxml')
        except:
            pass
        return None

    def ara(self, doktor):
        """Doktor arama işlemi - Alt sınıflarda her siteye özel olarak yazılır."""
        return None

    def build_url(self, doktor):
        """Doktor bilgilerine göre profil URL'si oluşturur."""
        return ""

    def clean_text(self, text):
        """Metindeki fazla boşlukları ve satır sonlarını temizler."""
        if not text:
            return ""
        return re.sub(r'\s+', ' ', text).strip()

    def extract_title(self, text):
        """Ham metin içerisinden (Örn: 'Prof. Dr. Ahmet Yılmaz') unvanı ayıklar."""
        text = text.lower()
        titles = {
            'prof. dr.': 'Prof.', 'prof.dr.': 'Prof.', 'prof dr': 'Prof.',
            'doç. dr.': 'Doç.', 'doç.dr.': 'Doç.', 'doç dr': 'Doç.',
            'op. dr.': 'Op.', 'op.dr.': 'Op.', 'op dr': 'Op.',
            'uzm. dr.': 'Uzm.', 'uzm.dr.': 'Uzm.', 'uzm dr': 'Uzm.',
            'dr.': 'Dr.', 'prat.': 'Prat.'
        }
        for key, val in titles.items():
            if key in text:
                return val
        return ""

    def slug(self, text):
        """Metni URL dostu (küçük harf, kısa çizgili) formata çevirir."""
        if not text:
            return ""
        text = text.lower().strip()
        tr_map = {'ı': 'i', 'ğ': 'g', 'ü': 'u', 'ş': 's', 'ö': 'o', 'ç': 'c',
                  'İ': 'i', 'Ğ': 'g', 'Ü': 'u', 'Ş': 's', 'Ö': 'o', 'Ç': 'c',
                  'â': 'a', 'î': 'i', 'û': 'u'}
        for k, v in tr_map.items():
            text = text.replace(k, v)
        text = re.sub(r'[^a-z0-9\s-]', '', text) # Alfabetik olmayanları sil
        text = re.sub(r'\s+', '-', text)        # Boşlukları tire yap
        return text
    def is_trash(self, data, doktor):
        """
        Bulunan verinin gerçekten bir doktor profili olup olmadığını doğrular.
        """
        if not data or not data.get('ad') or not data.get('soyad'):
            return True
            
        full_text = f"{data.get('ad', '')} {data.get('soyad', '')}".lower()
        
        # Eğer girilen soyad bulunan metinde hiç geçmiyorsa (slug olarak) yanlış kişidir
        soyad_norm = self.slug(doktor['soyad'])
        bulunan_norm = self.slug(full_text)
        if soyad_norm not in bulunan_norm:
            return True
        
        # EĞER metin SADECE çöp kelimelerden oluşuyorsa çöptür.
        # Ama "Ahmet Yılmaz Yorumları" gibi bir başlık geçerlidir.
        trash_keywords = ['en iyi', 'doktorları', 'hızlı ve kolay', 'randevu al', 'incele', 'listesi']
        pure_trash = True
        for word in full_text.split():
            if len(word) > 2 and word not in trash_keywords:
                pure_trash = False
                break
        
        return pure_trash

    def clean_doctor_name(self, name_text):
        """İsim içindeki 'Yorumları', 'Randevu' gibi ekleri temizler."""
        if not name_text: return ""
        text = name_text
        junk = ['yorumları', 'randevu', 'kimdir', 'fiyatları', 'iletişim', '–', '-', '|', 'profil', 'hocamız']
        for j in junk:
            # Sadece kelime olarak varsa temizle
            text = re.sub(rf'\b{j}\b', '', text, flags=re.IGNORECASE)
        return self.clean_text(text)

    def find_hospital(self, soup):
        """
        Sayfa içerisinde hastane/kliknik isimlerini anahtar kelimelerle arar.
        Adres bilgilerini (mah, sok vb.) filtreler.
        """
        # Kullanıcının istediği ve genel tıbbi tesis anahtar kelimeleri
        keywords = [
            'hastanesi', 'klinigi', 'muayenehanesi', 'universitesi', 
            'egitim ve arastirma', 'tip merkezi', 'poliklinigi', 
            'saglik merkezi', 'vakfi', 'enstitusu'
        ]
        
        # Sadece bu kelimeleri içeren metinleri ara
        for text in soup.find_all(string=True):
            cleaned = text.strip().lower()
            # En az bir anahtar kelime içermeli ve çok uzun olmamalı (adres bloğu olmaması için)
            if any(k in cleaned for k in keywords) and len(cleaned) < 150:
                # Eğer sadece mahalle/sokak bilgisi ise (örn: "Altındağ Mahallesi") alma
                # Ama hem hastane hem mahalle geçiyorsa (örn: "Özel Umut Hastanesi, Yenimahalle") bu hastanedir.
                is_address_only = ('mah' in cleaned or 'sok' in cleaned) and not any(k in cleaned for k in keywords[:4])
                
                if not is_address_only:
                    return self.clean_text(text)
        return None
