import json
import os
import sys
from datetime import datetime
from urllib.parse import urlparse

from ddgs import DDGS

KONFIG_DOSYASI = "config.json"


def konfig_oku():
    """config.json dosyasini oku."""
    if not os.path.exists(KONFIG_DOSYASI):
        print(f"HATA: {KONFIG_DOSYASI} bulunamadi!")
        sys.exit(1)

    with open(KONFIG_DOSYASI, "r", encoding="utf-8") as f:
        try:
            konfig = json.load(f)
        except json.JSONDecodeError as e:
            print(f"HATA: config.json okunamadi: {e}")
            sys.exit(1)

    if "secili_pozisyon" not in konfig or "secili_sehir" not in konfig:
        print("HATA: config.json icinde 'secili_pozisyon' veya 'secili_sehir' eksik!")
        sys.exit(1)

    return konfig


def kaynak_cikar(url):
    """URL'den kaynak site adini cikar."""
    try:
        domain = urlparse(url).netloc
        # www. kaldir
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return "bilinmeyen"


def web_ara(pozisyon, sehir, maks_sonuc=30):
    """DuckDuckGo ile gercek web aramasi yap."""
    # Pozisyondaki tireleri bosluklarla degistir
    pozisyon_metin = pozisyon.replace("-", " ")

    # Farkli arama sorgulari ile genis sonuc bul
    sorgular = [
        f"{pozisyon_metin} is ilani {sehir}",
        f"{pozisyon_metin} {sehir} is ilanlari",
        f"{pozisyon_metin} {sehir} eleman araniyor",
    ]

    tum_sonuclar = []
    gorulen_linkler = set()

    with DDGS() as ddgs:
        for sorgu in sorgular:
            print(f"  Araniyor: \"{sorgu}\"")
            try:
                sonuclar = ddgs.text(
                    sorgu,
                    region="tr-tr",
                    max_results=maks_sonuc,
                )
            except Exception as e:
                print(f"  [!] Arama hatasi: {e}")
                continue

            if not sonuclar:
                print(f"  [!] Sonuc bulunamadi.")
                continue

            for sonuc in sonuclar:
                link = sonuc.get("href", "")

                # Ayni linki tekrar ekleme
                if link in gorulen_linkler:
                    continue
                gorulen_linkler.add(link)

                baslik = sonuc.get("title", "").strip()
                aciklama = sonuc.get("body", "").strip()
                kaynak = kaynak_cikar(link)

                if not baslik or not link:
                    continue

                tum_sonuclar.append({
                    "baslik": baslik,
                    "aciklama": aciklama,
                    "konum": sehir.capitalize(),
                    "kaynak": kaynak,
                    "tarih": datetime.now().strftime("%Y-%m-%d"),
                    "link": link,
                })

            print(f"  [+] {len(sonuclar)} sonuc bulundu.")

    print(f"\nToplam benzersiz sonuc: {len(tum_sonuclar)}")
    return tum_sonuclar


def ilanlari_topla():
    """Config'e gore arama yap ve ilanlari topla."""
    konfig = konfig_oku()

    pozisyon = konfig["secili_pozisyon"]
    sehir = konfig["secili_sehir"]

    print(f"Arama: pozisyon='{pozisyon}', sehir='{sehir}'")
    print("-" * 50)

    ilanlar = web_ara(pozisyon, sehir)

    if not ilanlar:
        print("\nHicbir sonuc bulunamadi.")

    return ilanlar


# Ana calistirma
if __name__ == "__main__":
    print("=" * 50)
    print("Is Ilani Tarayici Baslatiliyor...")
    print("=" * 50)

    yeni_ilanlar = ilanlari_topla()

    with open("ilanlar.json", "w", encoding="utf-8") as dosya:
        json.dump(yeni_ilanlar, dosya, ensure_ascii=False, indent=4)

    print(f"\nToplam {len(yeni_ilanlar)} ilan ilanlar.json dosyasina kaydedildi.")
    print("Islem tamamlandi.")
