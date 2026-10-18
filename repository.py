"""repository paketi: SQLite veri erişimi."""
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from werkzeug.security import generate_password_hash
from models import Ogrenci, Yonetici, Yazar, Kategori, Kitap, OduncKaydi

SEMA = """
CREATE TABLE IF NOT EXISTS kategori(id INTEGER PRIMARY KEY, ad TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS yazar(id INTEGER PRIMARY KEY, ad_soyad TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS kitap(id INTEGER PRIMARY KEY, isbn TEXT UNIQUE NOT NULL,
  baslik TEXT NOT NULL,
  toplam_adet INTEGER NOT NULL CHECK(toplam_adet >= 0),
  mevcut_adet INTEGER NOT NULL CHECK(mevcut_adet >= 0),
  kategori_id INTEGER REFERENCES kategori(id));
CREATE TABLE IF NOT EXISTS kitap_yazar(kitap_id INTEGER REFERENCES kitap(id),
  yazar_id INTEGER REFERENCES yazar(id), PRIMARY KEY(kitap_id, yazar_id));
CREATE TABLE IF NOT EXISTS kullanici(id INTEGER PRIMARY KEY, ad TEXT NOT NULL, soyad TEXT NOT NULL,
  kullanici_adi TEXT UNIQUE NOT NULL, sifre_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK(rol IN ('ogrenci','yonetici')),
  ogrenci_no TEXT UNIQUE, bolum TEXT, sicil_no TEXT);
CREATE TABLE IF NOT EXISTS odunc(id INTEGER PRIMARY KEY,
  ogrenci_id INTEGER NOT NULL REFERENCES kullanici(id),
  kitap_id INTEGER NOT NULL REFERENCES kitap(id),
  odunc_tarihi TEXT NOT NULL, son_teslim_tarihi TEXT NOT NULL, iade_tarihi TEXT);
"""


class Veritabani:
    def __init__(self, yol="kutuphane.db", ornek_veri=True):
        self.yol = yol
        with closing(self.baglan()) as c, c:
            c.executescript(SEMA)
        if ornek_veri and not self.sorgula("SELECT 1 FROM kullanici LIMIT 1"):
            self._ornek_veri()

    def baglan(self):
        c = sqlite3.connect(self.yol)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    def sorgula(self, sql, p=()):
        with closing(self.baglan()) as c:
            return c.execute(sql, p).fetchall()

    def _ornek_veri(self):
        """İlk çalıştırmada demo için örnek kullanıcı, kitap ve bir gecikmiş ödünç ekler."""
        kullanicilar = KullaniciRepository(self)
        kullanicilar.yonetici_ekle("Ayşe", "Demir", "admin", "admin123", "K-014")
        kullanicilar.ogrenci_ekle("Ali", "Yılmaz", "ali", "1234", "2023001", "Bilgisayar Müh.")
        kullanicilar.ogrenci_ekle("Zeynep", "Kaya", "zeynep", "1234", "2023002", "Endüstri Müh.")
        kitaplar = KitapRepository(self)
        kitaplar.ekle("9780132350884", "Temiz Kod", 3, "Yazılım", ["Robert C. Martin"])
        kitaplar.ekle("9780201633610", "Tasarım Örüntüleri", 2, "Yazılım", ["Erich Gamma", "Richard Helm"])
        kitaplar.ekle("9789750719387", "Suç ve Ceza", 1, "Roman", ["Fyodor Dostoyevski"])
        kitaplar.ekle("9789754703832", "Kürk Mantolu Madonna", 2, "Roman", ["Sabahattin Ali"])
        # Gecikme raporunu gösterebilmek için 30 gün önce alınmış, teslim edilmemiş bir kayıt
        eski = date.today() - timedelta(days=30)
        with closing(self.baglan()) as c, c:
            c.execute("UPDATE kitap SET mevcut_adet = mevcut_adet - 1 WHERE isbn='9789750719387'")
            c.execute("INSERT INTO odunc(ogrenci_id,kitap_id,odunc_tarihi,son_teslim_tarihi) "
                      "SELECT (SELECT id FROM kullanici WHERE kullanici_adi='zeynep'),"
                      "(SELECT id FROM kitap WHERE isbn='9789750719387'),?,?",
                      (eski.isoformat(), (eski + timedelta(days=14)).isoformat()))


class KullaniciRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _nesne(r):
        if r["rol"] == "yonetici":
            return Yonetici(r["id"], r["ad"], r["soyad"], r["kullanici_adi"], r["sicil_no"])
        return Ogrenci(r["id"], r["ad"], r["soyad"], r["kullanici_adi"], r["ogrenci_no"], r["bolum"])

    def bul(self, id):
        r = self.db.sorgula("SELECT * FROM kullanici WHERE id=?", (id,))
        return self._nesne(r[0]) if r else None

    def sifre_hash(self, kullanici_adi):
        """(Kullanici, hash) döndürür; yoksa (None, None)."""
        r = self.db.sorgula("SELECT * FROM kullanici WHERE kullanici_adi=?", (kullanici_adi,))
        return (self._nesne(r[0]), r[0]["sifre_hash"]) if r else (None, None)

    def ogrenciler(self):
        return [self._nesne(r) for r in
                self.db.sorgula("SELECT * FROM kullanici WHERE rol='ogrenci' ORDER BY ad, soyad")]

    def ogrenci_ekle(self, ad, soyad, kullanici_adi, sifre, ogrenci_no, bolum):
        with closing(self.db.baglan()) as c, c:
            return c.execute(
                "INSERT INTO kullanici(ad,soyad,kullanici_adi,sifre_hash,rol,ogrenci_no,bolum) "
                "VALUES(?,?,?,?, 'ogrenci',?,?)",
                (ad, soyad, kullanici_adi, generate_password_hash(sifre), ogrenci_no, bolum)).lastrowid

    def yonetici_ekle(self, ad, soyad, kullanici_adi, sifre, sicil_no):
        with closing(self.db.baglan()) as c, c:
            return c.execute(
                "INSERT INTO kullanici(ad,soyad,kullanici_adi,sifre_hash,rol,sicil_no) "
                "VALUES(?,?,?,?, 'yonetici',?)",
                (ad, soyad, kullanici_adi, generate_password_hash(sifre), sicil_no)).lastrowid


class KitapRepository:
    SQL = """SELECT k.id, k.isbn, k.baslik, k.toplam_adet, k.mevcut_adet, kt.id kid, kt.ad kad,
             GROUP_CONCAT(y.ad_soyad, ', ') yazarlar FROM kitap k
             LEFT JOIN kategori kt ON kt.id = k.kategori_id
             LEFT JOIN kitap_yazar ky ON ky.kitap_id = k.id
             LEFT JOIN yazar y ON y.id = ky.yazar_id {where} GROUP BY k.id ORDER BY k.baslik"""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _nesne(r):
        yazarlar = [Yazar(None, a) for a in (r["yazarlar"] or "").split(", ") if a]
        kat = Kategori(r["kid"], r["kad"]) if r["kid"] else None
        return Kitap(r["id"], r["isbn"], r["baslik"], r["toplam_adet"], r["mevcut_adet"], kat, yazarlar)

    def hepsi(self):
        return [self._nesne(r) for r in self.db.sorgula(self.SQL.format(where=""))]

    def bul(self, id):
        r = self.db.sorgula(self.SQL.format(where="WHERE k.id = ?"), (id,))
        return self._nesne(r[0]) if r else None

    def ekle(self, isbn, baslik, adet, kategori_ad, yazar_adlari):
        with closing(self.db.baglan()) as c, c:
            c.execute("INSERT OR IGNORE INTO kategori(ad) VALUES(?)", (kategori_ad,))
            kid = c.execute("SELECT id FROM kategori WHERE ad=?", (kategori_ad,)).fetchone()["id"]
            kitap_id = c.execute(
                "INSERT INTO kitap(isbn,baslik,toplam_adet,mevcut_adet,kategori_id) VALUES(?,?,?,?,?)",
                (isbn, baslik, adet, adet, kid)).lastrowid
            for ad in yazar_adlari:
                c.execute("INSERT OR IGNORE INTO yazar(ad_soyad) VALUES(?)", (ad,))
                yid = c.execute("SELECT id FROM yazar WHERE ad_soyad=?", (ad,)).fetchone()["id"]
                c.execute("INSERT OR IGNORE INTO kitap_yazar VALUES(?,?)", (kitap_id, yid))
            return kitap_id

    def adet_ekle(self, kitap_id, adet):
        with closing(self.db.baglan()) as c, c:
            c.execute("UPDATE kitap SET toplam_adet = toplam_adet + ?, mevcut_adet = mevcut_adet + ? WHERE id=?",
                      (adet, adet, kitap_id))


class OduncRepository:
    SQL = """SELECT o.*, u.ad uad, u.soyad usoyad, u.kullanici_adi ukadi, u.ogrenci_no, u.bolum,
             k.isbn, k.baslik, k.toplam_adet, k.mevcut_adet
             FROM odunc o JOIN kullanici u ON u.id=o.ogrenci_id JOIN kitap k ON k.id=o.kitap_id
             {where} ORDER BY o.id DESC"""

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _nesne(r):
        return OduncKaydi(
            r["id"],
            Ogrenci(r["ogrenci_id"], r["uad"], r["usoyad"], r["ukadi"], r["ogrenci_no"], r["bolum"]),
            Kitap(r["kitap_id"], r["isbn"], r["baslik"], r["toplam_adet"], r["mevcut_adet"]),
            r["odunc_tarihi"], r["son_teslim_tarihi"], r["iade_tarihi"])

    def hepsi(self):
        return [self._nesne(r) for r in self.db.sorgula(self.SQL.format(where=""))]

    def ogrencinin(self, ogrenci_id):
        return [self._nesne(r) for r in
                self.db.sorgula(self.SQL.format(where="WHERE o.ogrenci_id=?"), (ogrenci_id,))]

    def bul(self, id):
        r = self.db.sorgula(self.SQL.format(where="WHERE o.id=?"), (id,))
        return self._nesne(r[0]) if r else None

    def aktifler(self):
        return [self._nesne(r) for r in
                self.db.sorgula(self.SQL.format(where="WHERE o.iade_tarihi IS NULL"))]

    def ver(self, ogrenci_id, kitap_id, gun):
        """Stok düşümü ve kayıt tek işlemde; stok yoksa None döner."""
        bugun = date.today()
        with closing(self.db.baglan()) as c, c:
            d = c.execute("UPDATE kitap SET mevcut_adet = mevcut_adet - 1 WHERE id=? AND mevcut_adet > 0",
                          (kitap_id,))
            if d.rowcount == 0:
                return None
            return c.execute(
                "INSERT INTO odunc(ogrenci_id,kitap_id,odunc_tarihi,son_teslim_tarihi) VALUES(?,?,?,?)",
                (ogrenci_id, kitap_id, bugun.isoformat(), (bugun + timedelta(days=gun)).isoformat())).lastrowid

    def iade_al(self, odunc_id):
        with closing(self.db.baglan()) as c, c:
            r = c.execute("SELECT kitap_id FROM odunc WHERE id=? AND iade_tarihi IS NULL", (odunc_id,)).fetchone()
            if not r:
                return False
            c.execute("UPDATE odunc SET iade_tarihi=? WHERE id=?", (date.today().isoformat(), odunc_id))
            c.execute("UPDATE kitap SET mevcut_adet = mevcut_adet + 1 WHERE id=?", (r["kitap_id"],))
            return True
