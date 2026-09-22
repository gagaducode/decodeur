"""
Petit serveur local qui se connecte à Pronote via pronotepy
et expose tes notes en JSON pour que Turbowarp puisse les récupérer.

Installation (une seule fois) :
    pip3 install pronotepy flask flask-cors

Lancement :
    python3 serveur_pronote.py

Ensuite dans Turbowarp :
1) Envoie une requête POST à http://localhost:5000/connexion
   avec un corps JSON : {"url": "...", "username": "...", "password": "..."}
2) Une fois connecté, appelle http://localhost:5000/notes pour récupérer les notes
"""

import pronotepy
from flask import Flask, jsonify, request
from flask_cors import CORS
import subprocess
import platform
import os
import sys

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------------
# Application externe à lancer au démarrage (optionnel)
# ------------------------------------------------------------------

def dossier_ressources():
    """
    Renvoie le dossier où chercher l'application à lancer.
    - Si le script tourne en .app packagé : Contents/Resources
    - Sinon (script Python normal) : le dossier du script
    """
    if getattr(sys, "frozen", False):
        # Packagé (py2app / PyInstaller) : on remonte depuis l'exécutable
        # jusqu'à Contents/, puis on va dans Resources/
        dossier_macos = os.path.dirname(sys.executable)          # .../Contents/MacOS
        dossier_contents = os.path.dirname(dossier_macos)         # .../Contents
        return os.path.join(dossier_contents, "Resources")
    else:
        # Script Python classique
        return os.path.dirname(os.path.abspath(__file__))


def trouver_application(dossier):
    """Cherche automatiquement un .app (Mac) ou .exe (Windows) dans le dossier donné."""
    extension = ".app" if platform.system() == "Darwin" else ".exe"

    if not os.path.isdir(dossier):
        return None

    for nom in os.listdir(dossier):
        if nom.lower().endswith(extension):
            return os.path.join(dossier, nom)

    return None


def lancer_application(chemin):
    """Lance une application externe (.app sur Mac, .exe sur Windows)."""
    if not chemin:
        return

    if not os.path.exists(chemin):
        print(f"⚠️  Application introuvable : {chemin}")
        return

    systeme = platform.system()
    try:
        if systeme == "Darwin":  # macOS
            subprocess.Popen(["open", chemin])
        elif systeme == "Windows":
            subprocess.Popen([chemin], shell=True)
        else:  # Linux, au cas où
            subprocess.Popen([chemin])
        print(f"✅ Application lancée : {chemin}")
    except Exception as e:
        print(f"⚠️  Impossible de lancer l'application : {e}")


# Le client Pronote sera stocké ici une fois la connexion réussie
client = None


def nombre_propre(valeur):
    """Convertit une note Pronote (ex: '19,5') en vrai nombre (19.5)."""
    if valeur is None:
        return 0.0
    return float(str(valeur).replace(",", "."))


@app.route("/connexion", methods=["POST"])
def connexion():
    global client

    data = request.get_json(force=True)
    if not data:
        return jsonify({"erreur": "corps JSON manquant"}), 400

    url = data.get("url")
    username = data.get("username")
    password = data.get("password")

    if not url or not username or not password:
        return jsonify({"erreur": "url, username et password sont requis"}), 400

    try:
        client = pronotepy.Client(url, username=username, password=password)
    except Exception as e:
        client = None
        return jsonify({"erreur": f"connexion impossible : {str(e)}"}), 500

    if not client.logged_in:
        client = None
        return jsonify({"erreur": "identifiants incorrects ou URL invalide"}), 401

    return jsonify({"succes": True, "nom": client.info.name})


@app.route("/notes")
def get_notes():
    if client is None or not client.logged_in:
        return jsonify({"erreur": "non connecté, appelle /connexion d'abord"}), 401

    periode = client.current_period
    notes = periode.grades

    resultat = []
    for note in notes:
        resultat.append({
            "matiere": note.subject.name,
            "note": nombre_propre(note.grade),
            "note_sur": nombre_propre(note.out_of),
            "coefficient": nombre_propre(note.coefficient),
            "date": str(note.date),
        })

    return jsonify(resultat)


@app.route("/emploi_du_temps")
def get_emploi_du_temps():
    if client is None or not client.logged_in:
        return jsonify({"erreur": "non connecté, appelle /connexion d'abord"}), 401

    from datetime import date
    cours = client.lessons(date.today())

    resultat = []
    for c in cours:
        resultat.append({
            "matiere": c.subject.name if c.subject else "?",
            "debut": str(c.start),
            "fin": str(c.end),
            "salle": c.classroom,
        })

    return jsonify(resultat)


if __name__ == "__main__":
    chemin_app = trouver_application(dossier_ressources())
    if chemin_app:
        lancer_application(chemin_app)
    else:
        print("ℹ️  Aucune application (.app/.exe) trouvée dans le dossier de ressources.")

    # En local : port 5000 par défaut. Sur Render : port fourni via la variable PORT.
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
