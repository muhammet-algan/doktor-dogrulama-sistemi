from concurrent.futures import ThreadPoolExecutor, as_completed
from scrapers.doktoryorum import DoktorYorumScraper
from scrapers.doktorarabul import DoktorAraBulScraper
from scrapers.trdoktor import TrDoktorScraper
from scrapers.doktoruzman import DoktorUzmanScraper
from scrapers.bulutklinik import BulutKlinikScraper
from scrapers.doktornumarasi import DoktorNumarasiScraper
from scrapers.istebudoktor import IsteBuDoktorScraper
from scrapers.doktorunubil import DoktorunuBilScraper
from scrapers.doktortakvimi import DoktorTakvimiScraper
from scrapers.doktorsitesi import DoktorSitesiScraper

# Aktif scraper örneklerinin listesi
SCRAPERS = [
    DoktorYorumScraper(),
    DoktorAraBulScraper(),
    TrDoktorScraper(),
    DoktorUzmanScraper(),
    BulutKlinikScraper(),
    DoktorNumarasiScraper(),
    IsteBuDoktorScraper(),
    DoktorunuBilScraper(),
    DoktorTakvimiScraper(),
    DoktorSitesiScraper()
]

def tum_siteleri_tara(doktor):
    """
    Parametre olarak gelen doktor bilgilerini listedeki tüm sitelerde PARALEL olarak tarar.
    ThreadPoolExecutor kullanarak performansı artırır.
    """
    sonuclar = {}
    
    # max_workers, aktif scraper sayısı kadar belirlenir
    with ThreadPoolExecutor(max_workers=len(SCRAPERS)) as executor:
        # Her scraper için bir thread başlatılır
        future_to_site = {executor.submit(scraper.ara, doktor): scraper.site_adi for scraper in SCRAPERS}
        
        for future in as_completed(future_to_site):
            site_adi = future_to_site[future]
            try:
                # Her site için maksimum bekleme süresi 10 saniyedir (Daha hızlı sonuç için düşürüldü)
                data = future.result(timeout=10)
                sonuclar[site_adi] = data
            except Exception as e:
                # Hata durumunda log basılır ve site sonucu None kaydedilir
                print(f"Hata ({site_adi}): {str(e)}")
                sonuclar[site_adi] = None
                
    return sonuclar
