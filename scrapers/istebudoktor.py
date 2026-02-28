# IsteBuDoktor Scraper - istebudoktor.com.tr
from scrapers.base import BaseScraper

class IsteBuDoktorScraper(BaseScraper):
    site_adi = "IsteBuDoktor"
    base_url = "https://istebudoktor.com.tr"
    
    def build_url(self, doktor):
        unvan = self.slug(doktor.get('unvan', 'dr').replace('.', ''))
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        return f"{self.base_url}/{unvan}-{ad}-{soyad}"
    
    def ara(self, doktor):
        soup = self.get_html(self.build_url(doktor))
        if not soup:
            return None
        
        sonuc = {}
        try:
            # Başlık
            h1 = soup.find('h1')
            if h1:
                baslik = self.clean_doctor_name(h1.get_text())
                sonuc['unvan'] = self.extract_title(baslik)
                for u in ['Prof. Dr.', 'Doç. Dr.', 'Op. Dr.', 'Uzm. Dr.', 'Dr.']:
                    baslik = baslik.replace(u, '').strip()
                parts = baslik.split()
                if len(parts) >= 2:
                    sonuc['ad'] = parts[0]
                    sonuc['soyad'] = ' '.join(parts[1:])
                # print(f"DEBUG: Bulundu {sonuc['ad']} {sonuc['soyad']}")
            
            # Şehir ve ilçe linkleri - BURSA / NİLÜFER formatında
            sehir_link = soup.select_one('a[href*="/search/"]')
            if sehir_link:
                sonuc['sehir'] = self.clean_text(sehir_link.get_text())
            
            # Şehir linkleri (Branş içeren linkleri hariç tut)
            links = soup.select('a[href*="/search/"]')
            for link in links:
                text = self.clean_text(link.get_text())
                # Branş isimlerini içeren linkleri atla
                if text and len(text) < 20 and not any(b.lower() in text.lower() for b in ['Dermatoloji', 'Cildiye', 'Cerrah']):
                    if 'sehir' not in sonuc:
                        sonuc['sehir'] = text
                        break
            
            # Hastane bulma
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            
            if sonuc:
                if self.is_trash(sonuc, doktor):
                    return None
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
