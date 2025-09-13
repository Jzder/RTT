import subprocess
import sys
import pathlib
import yaml
import tkinter as tk
from tkinter import simpledialog, filedialog, messagebox

BASE_DIR = pathlib.Path(__file__).resolve().parent
CONF_PASS = BASE_DIR / "conf.yaml"
CONF_ANNOT = BASE_DIR / "conf_annot.yaml"

def ask_user_inputs():
    """Ouvre des boîtes de dialogue Tkinter pour remplir les configs YAML."""
    root = tk.Tk()
    root.withdraw()  # on cache la fenêtre principale

    messagebox.showinfo(
        "Configuration requise",
        "Bienvenue ! Première utilisation.\nVeuillez renseigner les informations pour configurer l'application."
    )

    # Champs pour conf.yaml (export PASS)
    pass_url = simpledialog.askstring(
        "PASS",
        "URL du portail PASS :",
        initialvalue="https://pass.imt-atlantique.fr/OpDotNet/Noyau/Login.aspx?"
    )
    username = simpledialog.askstring("PASS", "Identifiant :", parent=root)
    password = simpledialog.askstring("PASS", "Mot de passe :", show="*", parent=root)

    # Champs pour conf_annot.yaml (annotation/signature)
    nom = simpledialog.askstring("Annotation", "Nom :", parent=root)
    prenom = simpledialog.askstring("Annotation", "Prénom :", parent=root)
    site_lettre = simpledialog.askstring("Annotation", "Site (B/R/N) :", initialvalue="B", parent=root)
    ville = simpledialog.askstring("Annotation", "Ville :", initialvalue="Brest", parent=root)
    texte_certif = simpledialog.askstring(
        "Annotation",
        "Texte de certification :",
        initialvalue="Certifie sur l’honneur avoir été présent(e) sur les créneaux indiqués dans le planning"
    )

    signature_path = filedialog.askopenfilename(
        title="Choisissez votre image de signature (PNG)",
        filetypes=[("Images PNG", "*.png")]
    )
    sig_height = simpledialog.askinteger("Annotation", "Taille de la signature (pt)", initialvalue=60)
    sig_x_offset = simpledialog.askinteger("Annotation", "Décalage horizontal (pt)", initialvalue=-370)
    sig_y_offset = simpledialog.askinteger("Annotation", "Décalage vertical (pt)", initialvalue=0)

    # Sauvegarde YAML conf.yaml (⚠️ clé correcte: pass_url)
    conf_pass = {
        "pass_url": pass_url,
        "username": username,
        "password": password,
        "pdf_out": "agenda.pdf"
    }
    with open(CONF_PASS, "w", encoding="utf-8") as f:
        yaml.safe_dump(conf_pass, f, allow_unicode=True)

    # Sauvegarde YAML conf_annot.yaml
    conf_annot = {
        "input_pdf": "agenda.pdf",
        "output_dir": "./sorties",
        "nom": nom,
        "prenom": prenom,
        "site_lettre": site_lettre,
        "ville": ville,
        "texte_certif": texte_certif,
        "marge_bas_mm": 18,
        "signature_image": signature_path,
        "signature_height_pt": sig_height,
        "signature_x_offset": sig_x_offset,
        "signature_y_offset": sig_y_offset
    }
    with open(CONF_ANNOT, "w", encoding="utf-8") as f:
        yaml.safe_dump(conf_annot, f, allow_unicode=True)

    messagebox.showinfo(
        "Configuration enregistrée",
        "Vos paramètres ont été sauvegardés.\nRelancez l'application pour exécuter le workflow."
    )

def run_script(script, args=None):
    """Exécute un script Python séparé avec subprocess"""
    cmd = [sys.executable, str(script)]
    if args:
        cmd.extend(args)
    print(f"[INFO] Lancement: {' '.join(map(str, cmd))}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ Erreur à l'exécution de {script}")
        sys.exit(result.returncode)

def main():
    # Première utilisation : créer les configs puis STOP
    if not CONF_PASS.exists() or not CONF_ANNOT.exists():
        ask_user_inputs()
        # Arrêt immédiat après création des fichiers de config
        sys.exit(0)

    # Exécutions suivantes : lancer les deux scripts
    export_script = BASE_DIR / "Dev-PDF_EDT.py"
    annot_script = BASE_DIR / "refactor_pdf.py"  # adapte si ton fichier a un autre nom

    run_script(export_script, [str(CONF_PASS)])
    run_script(annot_script, [str(CONF_ANNOT)])

    print("✅ Workflow terminé : export + annotation OK")

if __name__ == "__main__":
    main()