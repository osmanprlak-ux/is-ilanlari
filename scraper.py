import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

# Antalya bölgesindeki mutfak ilanlarını arattığımız link
URL = "https://www.isbul.net/is-ilanlari/antalya?aranan=soguk-sef" # Örnek bir site, mantığı anlamak için

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def ilanlari_topla():
    print("İlanlar taranıyor...")
    cevap = requests.get(URL, headers=HEADERS)
    corba = BeautifulSoup(cevap.content, "html.parser")
    
    toplanan_ilanlar = []
    
    # İlan kutularını bul (Sitenin HTML yapısına göre bu sınıflar değişebilir)
    ilan_kutulari = corba.find_all("div", class_="job-card") # Örnek class ismi
    
    # Eğer sitede ilan bulamazsa veya site yapısı farklıysa test için örnek veri ekleyelim
    if not ilan_kutulari:
        print("Siteden veri çekilemedi, test verisi ekleniyor...")
        return [
            {
                "baslik": "Soğuk CDP (Chef de Partie)",
                "sirket": "Örnek 5 Yıldızlı Otel",
                "konum": "Antalya",
                "tarih": datetime.now().strftime("%Y-%m-%d"),
                "link": "#"
            }
        ]

    for kutu in ilan_kutulari:
        try:
            baslik = kutu.find("h2").text.strip()
            sirket = kutu.find("div", class_="company").text.strip()
            konum = kutu.find("span", class_="location").text.strip()
            link = kutu.find("a")["href"]
            
            toplanan_ilanlar.append({
                "baslik": baslik,
                "sirket": sirket,
                "konum": konum,
                "tarih": datetime.now().strftime("%Y-%m-%d"),
                "link": f"https://www.isbul.net{link}"
            })
        except Exception as e:
            continue

    return toplanan_ilanlar

yeni_ilanlar = ilanlari_topla()

with open("ilanlar.json", "w", encoding="utf-8") as dosya:
    json.dump(yeni_ilanlar, dosya, ensure_ascii=False, indent=4)

print("İşlem tamamlandı.")