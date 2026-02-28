# TrDoktor Scraper - www.trdoktor.com
from scrapers.base import BaseScraper

class TrDoktorScraper(BaseScraper):
    site_adi = "TrDoktor"
    base_url = "https://www.trdoktor.com"
    
    def build_url(self, doktor):
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        brans = self.slug(doktor.get('brans', ''))
        sehir = self.slug(doktor.get('sehir', ''))
        return f"{self.base_url}/{ad}-{soyad}-{brans}-{sehir}"
    
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
                parts = baslik.split()
                if len(parts) >= 2:
                    sonuc['ad'] = parts[0]
                    sonuc['soyad'] = ' '.join(parts[1:])
            
            # Hastane
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
