"""service paketi: iş kuralları."""
import sqlite3
from werkzeug.security import check_password_hash

_KATLA = str.maketrans("ıİöÖüÜşŞçÇğĞ", "iioouussccgg")


def katla(metin):
    """Türkçe karakterlere ve büyük/küçük harfe duyarsız arama için normalleştirir."""
    return (metin or "").translate(_KATLA).lower()


class IsKuraliHatasi(Exception):
    pass


class KutuphaneServisi:
    MAX_AKTIF_ODUNC = 3
    ODUNC_GUN = 14

    def __init__(self, kullanicilar, kitaplar, oduncler):
        self.kullanicilar, self.kitaplar, self.oduncler = kullanicilar, kitaplar, oduncler

    # --- oturum ---
    def giris(self, kullanici_adi, sifre):
        kullanici, hash_ = self.kullanicilar.sifre_hash(kullanici_adi.strip())
        if not kullanici or not check_password_hash(hash_, sifre):
            raise IsKuraliHatasi("Kullanıcı adı veya şifre hatalı.")
        return kullanici

    # --- kitap arama ve stok ---
    def ara(self, sorgu):
        tum = self.kitaplar.hepsi()
        q = katla(sorgu.strip())
        if not q:
            return tum
        return [k for k in tum if q in katla(" ".join(
            [k.baslik, k.isbn, k.kategori.ad if k.kategori else ""] + [y.ad_soyad for y in k.yazarlar]))]

    def kitap_ekle(self, isbn, baslik, adet, kategori, yazarlar_metni):
        yazarlar = [y.strip() for y in yazarlar_metni.split(",") if y.strip()]
        if not (isbn.strip() and baslik.strip() and kategori.strip() and yazarlar):
            raise IsKuraliHatasi("ISBN, başlık, kategori ve en az bir yazar zorunludur.")
        if not adet.isdigit() or int(adet) < 1:
            raise IsKuraliHatasi("Adet en az 1 olan bir sayı olmalıdır.")
        try:
            self.kitaplar.ekle(isbn.strip(), baslik.strip(), int(adet), kategori.strip(), yazarlar)
        except sqlite3.IntegrityError:
            raise IsKuraliHatasi("Bu ISBN ile kayıtlı bir kitap zaten var.")

    def adet_ekle(self, kitap_id, adet):
        if not adet.isdigit() or int(adet) < 1:
            raise IsKuraliHatasi("Eklenecek adet en az 1 olan bir sayı olmalıdır.")
        if not self.kitaplar.bul(kitap_id):
            raise IsKuraliHatasi("Kitap bulunamadı.")
        self.kitaplar.adet_ekle(kitap_id, int(adet))

    def ogrenci_ekle(self, ad, soyad, kullanici_adi, sifre, ogrenci_no, bolum):
        if not all(s.strip() for s in (ad, soyad, kullanici_adi, sifre, ogrenci_no)):
            raise IsKuraliHatasi("Ad, soyad, kullanıcı adı, şifre ve öğrenci numarası zorunludur.")
        try:
            self.kullanicilar.ogrenci_ekle(ad.strip(), soyad.strip(), kullanici_adi.strip(), sifre,
                                           ogrenci_no.strip(), bolum.strip())
        except sqlite3.IntegrityError:
            raise IsKuraliHatasi("Bu kullanıcı adı veya öğrenci numarası zaten kayıtlı.")

    # --- ödünç / iade ---
    def odunc_al(self, ogrenci, kitap_id):
        kitap = self.kitaplar.bul(kitap_id)
        if not kitap:
            raise IsKuraliHatasi("Kitap bulunamadı.")
        kayitlar = [k for k in self.oduncler.ogrencinin(ogrenci.id) if not k.iade_edildi_mi()]
        if any(k.gecikmis_mi() for k in kayitlar):
            raise IsKuraliHatasi("Gecikmiş kitabınız var; önce iade etmeden yeni kitap alamazsınız.")
        if any(k.kitap.id == kitap.id for k in kayitlar):
            raise IsKuraliHatasi("Bu kitap zaten sizde.")
        if len(kayitlar) >= self.MAX_AKTIF_ODUNC:
            raise IsKuraliHatasi(f"En fazla {self.MAX_AKTIF_ODUNC} kitap ödünç alabilirsiniz.")
        if self.oduncler.ver(ogrenci.id, kitap.id, self.ODUNC_GUN) is None:
            raise IsKuraliHatasi(f"'{kitap.baslik}' şu an stokta yok.")
        return kitap

    def iade_al(self, odunc_id, kullanici):
        kayit = self.oduncler.bul(odunc_id)
        if not kayit:
            raise IsKuraliHatasi("Kayıt bulunamadı.")
        if kullanici.rol == "ogrenci" and kayit.ogrenci.id != kullanici.id:
            raise IsKuraliHatasi("Bu kayıt size ait değil.")
        if not self.oduncler.iade_al(odunc_id):
            raise IsKuraliHatasi("Kitap zaten iade edilmiş.")
        return kayit

    # --- raporlar ---
    def gecikme_raporu(self):
        kayitlar = [k for k in self.oduncler.aktifler() if k.gecikmis_mi()]
        return sorted(kayitlar, key=lambda k: k.gecikme_gunu(), reverse=True)

    def stok_ozeti(self):
        kitaplar = self.kitaplar.hepsi()
        return {"baslik_sayisi": len(kitaplar),
                "toplam": sum(k.toplam_adet for k in kitaplar),
                "mevcut": sum(k.mevcut_adet for k in kitaplar),
                "tukenen": [k for k in kitaplar if not k.musait]}
