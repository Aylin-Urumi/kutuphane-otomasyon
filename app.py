"""api paketi: Flask rotaları (controller)."""
import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, abort
from repository import Veritabani, KullaniciRepository, KitapRepository, OduncRepository
from service import KutuphaneServisi, IsKuraliHatasi


def uygulama_olustur(db_yolu="kutuphane.db", ornek_veri=True):
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "yerel-gelistirme-anahtari")
    db = Veritabani(db_yolu, ornek_veri)
    kullanicilar, kitaplar, oduncler = KullaniciRepository(db), KitapRepository(db), OduncRepository(db)
    servis = KutuphaneServisi(kullanicilar, kitaplar, oduncler)

    @app.before_request
    def oturumu_yukle():
        g.kullanici = kullanicilar.bul(session["uid"]) if "uid" in session else None

    def giris_gerekli(rol=None):
        def dekor(f):
            @wraps(f)
            def sarmal(*a, **k):
                if g.kullanici is None:
                    return redirect(url_for("giris"))
                if rol and g.kullanici.rol != rol:
                    abort(403)
                return f(*a, **k)
            return sarmal
        return dekor

    def calistir(islem, basari, hedef, **hedef_arg):
        try:
            sonuc = islem()
            flash(basari(sonuc) if callable(basari) else basari, "ok")
        except IsKuraliHatasi as e:
            flash(str(e), "err")
        return redirect(url_for(hedef, **hedef_arg))

    # --- oturum ---
    @app.route("/giris", methods=["GET", "POST"])
    def giris():
        if request.method == "POST":
            try:
                session["uid"] = servis.giris(request.form["kullanici_adi"], request.form["sifre"]).id
                return redirect(url_for("kitaplar_sayfasi"))
            except IsKuraliHatasi as e:
                flash(str(e), "err")
        return render_template("giris.html")

    @app.post("/cikis")
    def cikis():
        session.clear()
        return redirect(url_for("giris"))

    # --- öğrenci + yönetici: arama ---
    @app.get("/")
    @giris_gerekli()
    def kitaplar_sayfasi():
        q = request.args.get("q", "")
        aktif = {k.kitap.id for k in oduncler.ogrencinin(g.kullanici.id) if not k.iade_edildi_mi()} \
            if g.kullanici.rol == "ogrenci" else set()
        return render_template("kitaplar.html", kitaplar=servis.ara(q), q=q, bende=aktif)

    # --- öğrenci ---
    @app.post("/odunc-al/<int:kitap_id>")
    @giris_gerekli("ogrenci")
    def odunc_al(kitap_id):
        return calistir(lambda: servis.odunc_al(g.kullanici, kitap_id),
                        lambda k: f"'{k.baslik}' ödünç alındı. Son teslim: {servis.ODUNC_GUN} gün içinde.",
                        "kitaplar_sayfasi", q=request.form.get("q", ""))

    @app.get("/oduncler")
    @giris_gerekli("ogrenci")
    def oduncler_sayfasi():
        return render_template("oduncler.html", kayitlar=oduncler.ogrencinin(g.kullanici.id))

    @app.post("/iade/<int:odunc_id>")
    @giris_gerekli()
    def iade(odunc_id):
        hedef = "oduncler_sayfasi" if g.kullanici.rol == "ogrenci" else "gecikmeler_sayfasi"
        return calistir(lambda: servis.iade_al(odunc_id, g.kullanici),
                        lambda k: f"'{k.kitap.baslik}' iade alındı."
                        + (f" Gecikme cezası: {k.ceza():.2f} TL." if k.gecikme_gunu() else ""),
                        hedef)

    # --- yönetici ---
    @app.get("/yonetim/kitaplar")
    @giris_gerekli("yonetici")
    def yonetim_kitaplar():
        return render_template("yonetim_kitaplar.html", kitaplar=kitaplar.hepsi(), ozet=servis.stok_ozeti())

    @app.post("/yonetim/kitap")
    @giris_gerekli("yonetici")
    def kitap_ekle():
        f = request.form
        return calistir(lambda: servis.kitap_ekle(f["isbn"], f["baslik"], f["adet"], f["kategori"], f["yazarlar"]),
                        "Kitap eklendi.", "yonetim_kitaplar")

    @app.post("/yonetim/kitap/<int:kitap_id>/adet")
    @giris_gerekli("yonetici")
    def adet_ekle(kitap_id):
        return calistir(lambda: servis.adet_ekle(kitap_id, request.form["adet"]),
                        "Stok güncellendi.", "yonetim_kitaplar")

    @app.get("/yonetim/gecikmeler")
    @giris_gerekli("yonetici")
    def gecikmeler_sayfasi():
        rapor = servis.gecikme_raporu()
        return render_template("gecikmeler.html", rapor=rapor, toplam_ceza=sum(k.ceza() for k in rapor))

    @app.get("/yonetim/ogrenciler")
    @giris_gerekli("yonetici")
    def yonetim_ogrenciler():
        return render_template("yonetim_ogrenciler.html", ogrenciler=kullanicilar.ogrenciler())

    @app.post("/yonetim/ogrenci")
    @giris_gerekli("yonetici")
    def ogrenci_ekle():
        f = request.form
        return calistir(lambda: servis.ogrenci_ekle(f["ad"], f["soyad"], f["kullanici_adi"], f["sifre"],
                                                    f["ogrenci_no"], f["bolum"]),
                        "Öğrenci eklendi.", "yonetim_ogrenciler")

    return app


if __name__ == "__main__":
    uygulama_olustur().run(debug=True, port=5001)


   
