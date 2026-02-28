# DoktorAraBul Scraper - doktorarabul.com.tr
from scrapers.base import BaseScraper

class DoktorAraBulScraper(BaseScraper):
    site_adi = "DoktorAraBul"
    base_url = "https://doktorarabul.com.tr"
    
    def build_url(self, doktor):
        unvan = self.slug(doktor.get('unvan', 'dr').replace('.', ''))
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        return f"{self.base_url}/tum-doktorlar/{unvan}-{ad}-{soyad}/"
    
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
                meta = soup.find('meta', {'name': 'description'})
                if meta and meta.get('content') and 'hastane' in meta.get('content').lower():
                    sonuc['hastane'] = meta.get('content')
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
