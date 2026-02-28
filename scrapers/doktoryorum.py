# DoktorYorum Scraper - doktoryorum.net
from scrapers.base import BaseScraper

class DoktorYorumScraper(BaseScraper):
    site_adi = "DoktorYorum"
    base_url = "https://doktoryorum.net"
    
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
            
            # Branş
            brans = soup.select_one('.specialty, .doctor-specialty, .branch')
            if brans:
                sonuc['brans'] = self.clean_text(brans.get_text())
            
            # Hastane bulma
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            else:
                lokasyon = soup.select_one('.location, .hospital, .address')
                if lokasyon:
                    sonuc['hastane'] = self.clean_text(lokasyon.get_text())
            
            if sonuc:
                if self.is_trash(sonuc, doktor):
                    return None
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
