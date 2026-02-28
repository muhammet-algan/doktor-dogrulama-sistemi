# DoktorunuBil Scraper - www.doktorunubil.com
from scrapers.base import BaseScraper

class DoktorunuBilScraper(BaseScraper):
    site_adi = "DoktorunuBil"
    base_url = "http://www.doktorunubil.com"
    
    def build_url(self, doktor):
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        return f"{self.base_url}/doktor/{ad}-{soyad}"
    
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
            
            # Hastane bulma
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            else:
                info = soup.select_one('.doctor-info, .profile-info, .info')
                if info:
                    text = self.clean_text(info.get_text())
                    sonuc['hastane'] = text[:100] if len(text) > 100 else text
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
