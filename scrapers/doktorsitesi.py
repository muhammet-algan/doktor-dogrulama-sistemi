# DoktorSitesi Scraper - www.doktorsitesi.com
from scrapers.base import BaseScraper

class DoktorSitesiScraper(BaseScraper):
    site_adi = "DoktorSitesi"
    base_url = "https://www.doktorsitesi.com"
    
    def build_url(self, doktor):
        unvan = self.slug(doktor.get('unvan', 'dr').replace('.', ''))
        ad = self.slug(doktor['ad'])
        soyad = self.slug(doktor['soyad'])
        brans = self.slug(doktor.get('brans', ''))
        sehir = self.slug(doktor.get('sehir', ''))
        return f"{self.base_url}/{unvan}-{ad}-{soyad}/{brans}/{sehir}"
    
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
            
            # Branş - og:description'dan al
            og_desc = soup.find('meta', {'property': 'og:description'})
            if og_desc and og_desc.get('content'):
                desc = og_desc.get('content')
                # "Dermatoloji doktoru Prof. Dr. ..."
                if 'doktoru' in desc:
                    brans = desc.split('doktoru')[0].strip()
                    if brans:
                        sonuc['brans'] = brans
            
            # Branş bulunamadıysa linklerden dene
            if 'brans' not in sonuc:
                brans_link = soup.select_one('a[href*="/uzmanlik-alanlari/"]')
                if brans_link:
                    sonuc['brans'] = self.clean_text(brans_link.get_text().replace(',', ''))
            
            # Hastane bulma mantığını merkezi fonksiyona devret
            hastane = self.find_hospital(soup)
            if hastane:
                sonuc['hastane'] = hastane
            # Şehir
            sonuc['sehir'] = doktor.get('sehir', '')
            
            if sonuc:
                sonuc['bulundu'] = True
                return sonuc
        except:
            pass
        return None
