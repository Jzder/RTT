# AutoTimeTable

Real Time Timetable est un outil automatisé qui permet :
1. de se connecter au portail **PASS** de l’IMT Atlantique,  
2. d’exporter automatiquement l’emploi du temps au format **PDF**,  
3. d’annoter ce PDF (certification de présence, semaine courante, nom/prénom, etc.),  
4. d’y apposer une signature et de générer un fichier prêt à l’usage administratif.

---

## 🚀 Fonctionnalités

- Connexion automatique au portail PASS (via **Playwright**)
- Export de l’agenda en **PDF** (équivalent à `Cmd + P → PDF`)
- Annotation automatique sur la **deuxième page**
- Ajout de la **signature en PNG**, redimensionnée et positionnée automatiquement
- Renommage du PDF selon la convention :  NOM Prénom – FIPA3X – Sxx.pdf (où `xx` est le numéro de la semaine ISO)

---

## 📦 Installation

### 1. Cloner le projet
```bash
git clone git@github.com:Jzder/RTT.git AutoTimeTable
cd AutoTimeTable
```

### 2. Créer un environnement virtuel 
```bash
python3 -m venv .venv
source .venv/bin/activate   # macOS / Linux
.venv\Scripts\activate      # Windows PowerShell
```
 ### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```
### 4. Installer les navigateurs playwright
```bash
playwright install chromium
```
⚠️ Ne pas lancer avec sudo, les navigateurs doivent être installés pour un utilisateur normal.

## ▶️ Utilisation

### Première execution

Lance simplement :
```bash
python main.py
```
👉 Une fenêtre (ou un assistant console si Tkinter n’est pas dispo) s’ouvre et te demande :
	•	ton URL PASS, identifiant, mot de passe,
	•	ton nom, prénom, site (B, R ou N), ville,
	•	ton texte de certification (ex: Certifie sur l’honneur avoir été présent(e) sur les créneaux indiqués dans le planning),
	•	ton image de signature (.png).
 	•	l'endroit où enregistrer le fichier pdf 

Ces informations sont sauvegardées dans conf.yaml et conf_annot.yaml.
Ensuite le programme s’arrête → relance-le pour exécuter le workflow.

## Exécutions suivantes

Un simple :
```bash
python main.py
```
… lancera automatiquement :
	1.	Connexion PASS & export PDF
	2.	Annotation + signature
	3.	Génération du fichier final dans ./sorties/.
👉 Pour réinitialiser la configuration → supprime conf.yaml et conf_annot.yaml, puis relance python main.py.

## 🖼️ Signature
	•	Doit être au format PNG.
	•	La taille (signature_height_pt) et la position (signature_x_offset, signature_y_offset) sont configurables dans conf_annot.yaml.

## 📄 Licence
Projet personnel — usage interne.


 

