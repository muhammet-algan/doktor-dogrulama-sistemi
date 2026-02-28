# BulutKlinik Scraper - bulutklinik.com
from scrapers.base import BaseScraper

class BulutKlinikScraper(BaseScraper):
    site_adi = "BulutKlinik"
    base_url = "https://bulutklinik.com"
    
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
                for u in ['PROF. DR.', 'DOÇ. DR.', 'OP. DR.', 'UZM. DR.', 'DR.', 
                          'Prof. Dr.', 'Doç. Dr.', 'Op. Dr.', 'Uzm. Dr.', 'Dr.']:
                    baslik = baslik.replace(u, '').strip()
                parts = baslik.split()
                if len(parts) >= 2:
                    sonuc['ad'] = parts[0]
                    sonuc['soyad'] = ' '.join(parts[1:])
            
            # Hastane
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            else:
                brans_el = soup.find(text=lambda t: t and any(b in t for b in ['Diğer', 'Ortopedi', 'Kardiyoloji']))
                if brans_el:
                    sonuc['brans'] = self.clean_text(brans_el)
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
