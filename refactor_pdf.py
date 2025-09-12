import sys
import pathlib
import datetime as dt
import yaml

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Paris")
except Exception:
    import pytz
    TZ = pytz.timezone("Europe/Paris")

# ---------- utilitaires ----------
def iso_week_now_paris():
    today = dt.datetime.now(TZ).date()
    return today.isocalendar().week

def safe_mkdir(p: pathlib.Path):
    p.mkdir(parents=True, exist_ok=True)

def load_cfg(path="conf_annot.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def output_filename(nom, prenom, site_lettre, week):
    site = (site_lettre or "").strip().upper()
    return f"{nom.strip()} {prenom.strip()} – FIPA3{site} – S{week}.pdf"

def register_font():
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        return "DejaVu"
    except Exception:
        return "Helvetica"

def make_overlay(page_width_pt, page_height_pt, texte_certif, nom_prenom, ville,
                 date_str, margin_bottom_mm, overlay_path,
                 signature_path=None, signature_height_pt=14,
                 sig_x_offset=0, sig_y_offset=0):
    font_name = register_font()
    c = canvas.Canvas(str(overlay_path), pagesize=(page_width_pt, page_height_pt))

    margin = 12 * mm
    y = float(margin_bottom_mm) * mm

    # bloc texte
    c.setFont(font_name, 10)
    c.drawString(margin, y, texte_certif)
    sign = f"Fait à {ville}, le {date_str} — {nom_prenom}"
    c.drawString(margin, y - 12, sign)

    # encadré global
    c.setLineWidth(0.5)
    width_box = page_width_pt - 2*(margin - 3)
    c.rect(margin - 3, y - 20, width_box, 40, stroke=1, fill=0)

    # image signature
    if signature_path and pathlib.Path(signature_path).exists():
        try:
            sig = ImageReader(signature_path)
            sig_h = signature_height_pt
            sig_w = sig_h * sig.getSize()[0] / sig.getSize()[1]
            # position par défaut = à droite de l’encadré
            x_pos = margin + width_box - sig_w - 8 + sig_x_offset
            y_pos = y - 12 + sig_y_offset
            print(f"[INFO] Insertion signature ({sig_w:.1f}x{sig_h:.1f} pt) → x={x_pos:.1f}, y={y_pos:.1f}")
            c.drawImage(sig, x_pos, y_pos, width=sig_w, height=sig_h, mask="auto")
        except Exception as e:
            print(f"[WARN] Impossible d’insérer la signature: {e}")
    else:
        if signature_path:
            print(f"[WARN] Signature non trouvée: {signature_path}")

    c.showPage()
    c.save()

def annotate_pdf(input_pdf, output_pdf, texte_certif, nom_prenom, ville="Brest",
                 margin_bottom_mm=18, signature_path=None,
                 signature_height_pt=14, sig_x_offset=0, sig_y_offset=0):
    reader = PdfReader(input_pdf)
    writer = PdfWriter()
    date_str = dt.datetime.now(TZ).strftime("%d/%m/%Y")

    tmp_overlays = []
    for i, page in enumerate(reader.pages):
        # seulement la 2ᵉ page (i == 1)
        if i == 1:
            pw = float(page.mediabox.width)
            ph = float(page.mediabox.height)
            tmp_path = pathlib.Path(output_pdf).with_suffix(f".overlay.p{i}.pdf")
            make_overlay(pw, ph, texte_certif, nom_prenom, ville, date_str,
                         margin_bottom_mm, tmp_path,
                         signature_path, signature_height_pt,
                         sig_x_offset, sig_y_offset)
            ov_reader = PdfReader(str(tmp_path))
            page.merge_page(ov_reader.pages[0])
            tmp_overlays.append(tmp_path)
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    for p in tmp_overlays:
        try:
            p.unlink()
        except Exception:
            pass

# ---------- main ----------
def main():
    cfg_path = "conf_annot.yaml" if len(sys.argv) < 2 else sys.argv[1]
    cfg = load_cfg(cfg_path)

    input_pdf = pathlib.Path(cfg["input_pdf"]).resolve()
    if not input_pdf.exists():
        print(f"❌ PDF introuvable: {input_pdf}")
        sys.exit(1)

    out_dir = pathlib.Path(cfg.get("output_dir", "./sorties")).resolve()
    safe_mkdir(out_dir)

    nom = cfg["nom"]
    prenom = cfg["prenom"]
    site_lettre = cfg.get("site_lettre", "B")
    week = iso_week_now_paris()
    out_name = output_filename(nom, prenom, site_lettre, week)
    out_pdf = out_dir / out_name

    texte = cfg.get("texte_certif", "Certifie sur l’honneur avoir été présent(e) sur les créneaux indiqués dans le planning")
    ville = cfg.get("ville", "Brest")
    marge_mm = int(cfg.get("marge_bas_mm", 18))
    signature_path = cfg.get("signature_image")
    sig_h_pt = int(cfg.get("signature_height_pt", 14))
    sig_x_offset = int(cfg.get("signature_x_offset", 0))
    sig_y_offset = int(cfg.get("signature_y_offset", 0))

    print(f"[INFO] Semaine ISO courante (Europe/Paris): S{week}")
    print(f"[INFO] Entrée : {input_pdf}")
    print(f"[INFO] Sortie : {out_pdf}")
    print(f"[DEBUG] Signature path: {signature_path}, hauteur: {sig_h_pt}pt, x_offset: {sig_x_offset}, y_offset: {sig_y_offset}")

    annotate_pdf(
        input_pdf=str(input_pdf),
        output_pdf=str(out_pdf),
        texte_certif=texte,
        nom_prenom=f"{prenom} {nom}",
        ville=ville,
        margin_bottom_mm=marge_mm,
        signature_path=signature_path,
        signature_height_pt=sig_h_pt,
        sig_x_offset=sig_x_offset,
        sig_y_offset=sig_y_offset,
    )

    print("✅ Terminé.")

if __name__ == "__main__":
    main()