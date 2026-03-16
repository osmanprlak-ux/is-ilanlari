import requests
from bs4 import BeautifulSoup
import json
import os
import sys
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

KONFIG_DOSYASI = "config.json"


def konfig_oku():
    """config.json dosyasını oku ve ayarları döndür."""
    if not os.path.exists(KONFIG_DOSYASI):
        print(f"HATA: {KONFIG_DOSYASI} bulunamadı!")
        sys.exit(1)

    with open(KONFIG_DOSYASI, "r", encoding="utf-8") as f:
        try:
            konfig = json.load(f)
        except json.JSONDecodeError as e:
            print(f"HATA: config.json okunamadı: {e}")
            sys.exit(1)

    # Zorunlu alanları kontrol et
    gerekli_alanlar = ["pozisyonlar", "sehirler", "kaynaklar", "secili_pozisyon", "secili_sehir"]
    for alan in gerekli_alanlar:
        if alan not in konfig:
            print(f"HATA: config.json içinde '{alan}' alanı eksik!")
            sys.exit(1)

    return konfig


def kaynak_tara(kaynak, pozisyon, sehir):
    """Tek bir kaynaktan ilanları topla."""
    if not kaynak.get("aktif", False):
        return []

    url = kaynak["url_sablonu"].format(pozisyon=pozisyon, sehir=sehir)
    seciciler = kaynak.get("seciciler", {})
    kaynak_adi = kaynak.get("ad", "Bilinmeyen")

    print(f"  -> {kaynak_adi} taranıyor: {url}")

    try:
        cevap = requests.get(url, headers=HEADERS, timeout=15)
        cevap.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"  [!] {kaynak_adi}: Bağlantı zaman aşımına uğradı.")
        return []
    except requests.exceptions.ConnectionError:
        print(f"  [!] {kaynak_adi}: Bağlantı kurulamadı.")
        return []
    except requests.exceptions.HTTPError as e:
        print(f"  [!] {kaynak_adi}: HTTP hatası - {e.response.status_code}")
        return []
    except requests.exceptions.RequestException as e:
        print(f"  [!] {kaynak_adi}: İstek hatası - {e}")
        return []

    corba = BeautifulSoup(cevap.content, "html.parser")

    ilan_secici = seciciler.get("ilan_kutusu", "div.job-card")
    # CSS seçicisini ayır (tag.class formatı)
    parcalar = ilan_secici.split(".", 1)
    etiket = parcalar[0] if parcalar[0] else "div"
    sinif = parcalar[1] if len(parcalar) > 1 else None

    if sinif:
        ilan_kutulari = corba.find_all(etiket, class_=sinif)
    else:
        ilan_kutulari = corba.find_all(etiket)

    if not ilan_kutulari:
        print(f"  [!] {kaynak_adi}: İlan bulunamadı.")
        return []

    toplanan = []
    for kutu in ilan_kutulari:
        try:
            baslik_el = kutu.select_one(seciciler.get("baslik", "h2"))
            sirket_el = kutu.select_one(seciciler.get("sirket", "div.company"))
            konum_el = kutu.select_one(seciciler.get("konum", "span.location"))
            link_el = kutu.select_one(seciciler.get("link", "a"))

            if not baslik_el:
                continue

            baslik = baslik_el.text.strip()
            sirket = sirket_el.text.strip() if sirket_el else "Belirtilmemiş"
            konum = konum_el.text.strip() if konum_el else sehir.capitalize()
            link = link_el.get("href", "#") if link_el else "#"

            # Göreceli linkleri düzelt
            if link and link.startswith("/"):
                # Kaynak URL'den domain al
                from urllib.parse import urlparse
                parsed = urlparse(kaynak["url_sablonu"])
                link = f"{parsed.scheme}://{parsed.netloc}{link}"

            toplanan.append({
                "baslik": baslik,
                "sirket": sirket,
                "konum": konum,
                "kaynak": kaynak_adi,
                "tarih": datetime.now().strftime("%Y-%m-%d"),
                "link": link
            })
        except Exception as e:
            print(f"  [!] {kaynak_adi}: Bir ilan işlenirken hata: {e}")
            continue

    print(f"  [+] {kaynak_adi}: {len(toplanan)} ilan bulundu.")
    return toplanan


def ilanlari_topla():
    """Tüm aktif kaynaklardan ilanları topla."""
    konfig = konfig_oku()

    pozisyon = konfig["secili_pozisyon"]
    sehir = konfig["secili_sehir"]
    kaynaklar = konfig["kaynaklar"]

    # Seçili pozisyon ve şehir geçerli mi kontrol et
    if pozisyon not in konfig["pozisyonlar"]:
        print(f"UYARI: '{pozisyon}' tanımlı pozisyonlar listesinde yok. Yine de aranacak.")
    if sehir not in konfig["sehirler"]:
        print(f"UYARI: '{sehir}' tanımlı şehirler listesinde yok. Yine de aranacak.")

    aktif_kaynaklar = [k for k in kaynaklar if k.get("aktif", False)]
    if not aktif_kaynaklar:
        print("HATA: Hiçbir aktif kaynak bulunamadı!")
        return []

    print(f"Arama: pozisyon='{pozisyon}', şehir='{sehir}', kaynak sayısı={len(aktif_kaynaklar)}")

    tum_ilanlar = []
    for kaynak in aktif_kaynaklar:
        ilanlar = kaynak_tara(kaynak, pozisyon, sehir)
        tum_ilanlar.extend(ilanlar)

    # Hiç ilan bulunamazsa bilgi ver
    if not tum_ilanlar:
        print("Hiçbir kaynaktan ilan bulunamadı. Test verisi ekleniyor...")
        tum_ilanlar = [
            {
                "baslik": f"{pozisyon.replace('-', ' ').title()} - Örnek İlan",
                "sirket": "Örnek 5 Yıldızlı Otel",
                "konum": sehir.capitalize(),
                "kaynak": "test-verisi",
                "tarih": datetime.now().strftime("%Y-%m-%d"),
                "link": "#"
            }
        ]

    return tum_ilanlar


# Ana çalıştırma
if __name__ == "__main__":
    print("=" * 50)
    print("İş İlanı Tarayıcı Başlatılıyor...")
    print("=" * 50)

    yeni_ilanlar = ilanlari_topla()

    with open("ilanlar.json", "w", encoding="utf-8") as dosya:
        json.dump(yeni_ilanlar, dosya, ensure_ascii=False, indent=4)

    print(f"\nToplam {len(yeni_ilanlar)} ilan ilanlar.json dosyasına kaydedildi.")
    print("İşlem tamamlandı.")
