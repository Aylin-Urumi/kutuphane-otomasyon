"""model paketi: UML sınıf diyagramındaki varlık sınıfları."""
from abc import ABC
from datetime import date


class Kullanici(ABC):
    """Soyut taban sınıf: sisteme giriş yapan herkes."""
    ROL = ""

    def __init__(self, id, ad, soyad, kullanici_adi):
        self.id, self.ad, self.soyad, self.kullanici_adi = id, ad, soyad, kullanici_adi

    @property
    def ad_soyad(self):
        return f"{self.ad} {self.soyad}"

    @property
    def rol(self):
        return self.ROL


class Ogrenci(Kullanici):
    ROL = "ogrenci"

    def __init__(self, id, ad, soyad, kullanici_adi, ogrenci_no, bolum):
        super().__init__(id, ad, soyad, kullanici_adi)
        self.ogrenci_no, self.bolum = ogrenci_no, bolum


class Yonetici(Kullanici):
    ROL = "yonetici"

    def __init__(self, id, ad, soyad, kullanici_adi, sicil_no):
        super().__init__(id, ad, soyad, kullanici_adi)
        self.sicil_no = sicil_no


class Yazar:
    def __init__(self, id, ad_soyad):
        self.id, self.ad_soyad = id, ad_soyad


class Kategori:
    def __init__(self, id, ad):
        self.id, self.ad = id, ad


class Kitap:
    def __init__(self, id, isbn, baslik, toplam_adet, mevcut_adet, kategori=None, yazarlar=None):
        self.id, self.isbn, self.baslik = id, isbn, baslik
        self.toplam_adet, self.mevcut_adet = toplam_adet, mevcut_adet
        self.kategori = kategori          # Kategori (1)
        self.yazarlar = yazarlar or []    # Yazar (1..*)

    @property
    def musait(self):
        return self.mevcut_adet > 0


class OduncKaydi:
    GUNLUK_CEZA = 2.0  # TL / gün

    def __init__(self, id, ogrenci, kitap, odunc_tarihi, son_teslim_tarihi, iade_tarihi=None):
        self.id, self.ogrenci, self.kitap = id, ogrenci, kitap
        self.odunc_tarihi = date.fromisoformat(odunc_tarihi)
        self.son_teslim_tarihi = date.fromisoformat(son_teslim_tarihi)
        self.iade_tarihi = date.fromisoformat(iade_tarihi) if iade_tarihi else None

    def iade_edildi_mi(self):
        return self.iade_tarihi is not None

    def gecikme_gunu(self):
        bitis = self.iade_tarihi or date.today()
        return max(0, (bitis - self.son_teslim_tarihi).days)

    def gecikmis_mi(self):
        return not self.iade_edildi_mi() and self.gecikme_gunu() > 0

    def ceza(self):
        return self.gecikme_gunu() * self.GUNLUK_CEZA
