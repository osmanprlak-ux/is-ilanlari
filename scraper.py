import json
import os
import sys
import requests
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from ddgs import DDGS

KONFIG_DOSYASI = "config.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


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
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return "bilinmeyen"


def modhotel_tara():
    """modhotel.net sitesinden personel arayan ilanlari topla."""
    url = "https://modhotel.net/tr/personel-arayanlar"
    print(f"\n  [modhotel.net] Taraniyor: {url}")

    try:
        cevap = requests.get(url, headers=HEADERS, timeout=20)
        cevap.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"  [!] modhotel.net: Baglanti hatasi - {e}")
        return []

    corba = BeautifulSoup(cevap.content, "html.parser")
    ilanlar = []

    # Sayfa icerigindeki tum linkleri tara, ilan olabilecekleri bul
    # Once bilinen job card yapilari dene
    secici_listesi = [
        {"kutu": "div.job-card", "baslik": "h2", "sirket": ".company", "konum": ".location"},
        {"kutu": "div.listing-item", "baslik": "h2", "sirket": ".company-name", "konum": ".location"},
        {"kutu": "div.card", "baslik": "h5", "sirket": ".card-text", "konum": ".text-muted"},
        {"kutu": "article", "baslik": "h2", "sirket": ".company", "konum": ".location"},
        {"kutu": "tr", "baslik": "td a", "sirket": "td:nth-of-type(2)", "konum": "td:nth-of-type(3)"},
    ]

    for secici in secici_listesi:
        kutular = corba.select(secici["kutu"])
        if kutular and len(kutular) > 1:
            for kutu in kutular:
                baslik_el = kutu.select_one(secici["baslik"])
                if not baslik_el or not baslik_el.text.strip():
                    continue
                sirket_el = kutu.select_one(secici["sirket"])
                konum_el = kutu.select_one(secici["konum"])
                link_el = kutu.select_one("a[href]")

                baslik = baslik_el.text.strip()
                sirket = sirket_el.text.strip() if sirket_el else ""
                konum = konum_el.text.strip() if konum_el else ""
                link = link_el["href"] if link_el else url

                if link.startswith("/"):
                    link = "https://modhotel.net" + link

                ilanlar.append({
                    "baslik": baslik,
                    "aciklama": sirket,
                    "konum": konum if konum else "Turkiye",
                    "kaynak": "modhotel.net",
                    "tarih": datetime.now().strftime("%Y-%m-%d"),
                    "link": link,
                })
            if ilanlar:
                break

    # Seciciler uyusmadiysa, sayfadaki anlamli linkleri topla
    if not ilanlar:
        linkler = corba.select("a[href]")
        for a in linkler:
            href = a.get("href", "")
            metin = a.text.strip()
            # Ilan linklerini filtrele (cok kisa veya navigasyon linkleri atla)
            if len(metin) < 10:
                continue
            if href.startswith("/tr/ilan") or href.startswith("/tr/personel") or "/job" in href or "/ilan" in href:
                if href.startswith("/"):
                    href = "https://modhotel.net" + href
                ilanlar.append({
                    "baslik": metin,
                    "aciklama": "",
                    "konum": "Turkiye",
                    "kaynak": "modhotel.net",
                    "tarih": datetime.now().strftime("%Y-%m-%d"),
                    "link": href,
                })

    print(f"  [+] modhotel.net: {len(ilanlar)} ilan bulundu.")
    return ilanlar


def web_ara(pozisyon, sehir, maks_sonuc=30):
    """DuckDuckGo ile gercek web aramasi yap."""
    pozisyon_metin = pozisyon.replace("-", " ")

    # Farkli arama sorgulari
    sorgular = [
        f"{pozisyon_metin} is ilani {sehir}",
        f"{pozisyon_metin} {sehir} is ilanlari",
        f"{pozisyon_metin} {sehir} eleman araniyor",
        f"site:modhotel.net {pozisyon_metin} {sehir}",
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

    print(f"\nDuckDuckGo toplam benzersiz sonuc: {len(tum_sonuclar)}")
    return tum_sonuclar


def tekrarlari_kaldir(ilanlar):
    """Ayni link veya cok benzer basliklari kaldir."""
    gorulen = set()
    temiz = []
    for ilan in ilanlar:
        anahtar = ilan["link"]
        if anahtar in gorulen:
            continue
        gorulen.add(anahtar)
        temiz.append(ilan)
    return temiz


def ilanlari_topla():
    """Tum kaynaklardan ilanlari topla."""
    konfig = konfig_oku()

    pozisyon = konfig["secili_pozisyon"]
    sehir = konfig["secili_sehir"]

    print(f"Arama: pozisyon='{pozisyon}', sehir='{sehir}'")
    print("=" * 50)

    # 1. DuckDuckGo ile genel arama
    print("\n[1/2] DuckDuckGo web aramasi...")
    ddg_ilanlar = web_ara(pozisyon, sehir)

    # 2. modhotel.net direkt tarama
    print("\n[2/2] modhotel.net direkt tarama...")
    modhotel_ilanlar = modhotel_tara()

    # Birlestir ve tekrarlari kaldir
    tum_ilanlar = ddg_ilanlar + modhotel_ilanlar
    tum_ilanlar = tekrarlari_kaldir(tum_ilanlar)

    if not tum_ilanlar:
        print("\nHicbir sonuc bulunamadi.")
    else:
        print(f"\nToplam benzersiz ilan: {len(tum_ilanlar)}")

    return tum_ilanlar


if __name__ == "__main__":
    print("=" * 50)
    print("Is Ilani Tarayici Baslatiliyor...")
    print("=" * 50)

    yeni_ilanlar = ilanlari_topla()

    with open("ilanlar.json", "w", encoding="utf-8") as dosya:
        json.dump(yeni_ilanlar, dosya, ensure_ascii=False, indent=4)

    print(f"\nToplam {len(yeni_ilanlar)} ilan ilanlar.json dosyasina kaydedildi.")
    print("Islem tamamlandi.")
