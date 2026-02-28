# DoktorNumarasi Scraper - www.doktornumarasi.com
from scrapers.base import BaseScraper

class DoktorNumarasiScraper(BaseScraper):
    site_adi = "DoktorNumarasi"
    base_url = "https://www.doktornumarasi.com"
    
    def build_url(self, doktor):
        unvan = self.slug(doktor.get('unvan', 'dr').replace('.', ''))
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        return f"{self.base_url}/{unvan}-{ad}-{soyad}-kimdir-muayenehane-randevu.html"
    
    def ara(self, doktor):
        soup = self.get_html(self.build_url(doktor))
        if not soup:
            return None
        
        sonuc = {}
        try:
            h1 = soup.find('h1')
            if h1:
                baslik = self.clean_doctor_name(h1.get_text())
                sonuc['unvan'] = self.extract_title(baslik)
                for u in ['Prof. Dr.', 'Doç. Dr.', 'Op. Dr.', 'Uzm. Dr.', 'Dr.']:
                    baslik = baslik.replace(u, '').strip()
                parts = [p for p in baslik.split() if p.lower() not in ['kimdir?', 'kimdir', 'muayenehane', 'randevu', '–', '-', '|']]
                if len(parts) >= 2:
                    sonuc['ad'] = parts[0]
                    sonuc['soyad'] = ' '.join(parts[1:])
            
            # Hastane bulma
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
