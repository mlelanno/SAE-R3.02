# Ce programme lit les repères de couleur du SVG et les enregistre dans SQLite.
# Il fonctionne seul : il n'importe pas le fichier donnees_couleurs.py.
# Placer carrefour_couleurs.svg dans le même dossier, puis lancer ce programme.

import xml.etree.ElementTree as ET
import sqlite3
from pathlib import Path

FICHIER_SVG = Path(__file__).with_name("carrefour_couleurs.svg")
FICHIER_BASE = Path(__file__).with_name("carrefour.db")

COULEURS = {
    "#ffff00": "trajets",  # Jaune : chemins suivis par les voitures.
    "#ff0000": "arrets",   # Rouge : lignes d'arrêt.
    "#00ff00": "entrees",  # Vert : points d'entrée.
    "#ff00ff": "sorties",  # Rose : points de sortie.
}


def lire_trace(texte):
    # Dans ce plan, M donne le départ, L une ligne et C une courbe.
    # Ce petit lecteur accepte ces trois commandes en majuscules.
    texte = texte.replace(",", " ")
    for commande in ["M", "L", "C"]:
        texte = texte.replace(commande, " " + commande + " ")

    mots = texte.split()
    segments = []
    position = 0

    while position < len(mots):
        commande = mots[position]
        if commande not in ["M", "L", "C"]:
            raise ValueError("Commande non gérée dans ce plan : " + commande)

        nombre = 2
        if commande == "C":
            nombre = 6

        valeurs = mots[position + 1:position + 1 + nombre]
        if len(valeurs) != nombre:
            raise ValueError("Il manque des coordonnées dans un tracé.")

        coordonnees = []
        for valeur in valeurs:
            coordonnees.append(float(valeur))

        segments.append({"commande": commande, "coordonnees": coordonnees})
        position = position + 1 + nombre

    if len(segments) < 2 or segments[0]["commande"] != "M":
        raise ValueError("Un tracé doit avoir un départ et au moins un segment.")
    for segment in segments[1:]:
        if segment["commande"] == "M":
            raise ValueError("Chaque repère doit former un seul tracé continu.")
    return segments


def lire_couleur(objet, propriete):
    # La couleur peut être dans l'attribut stroke/fill ou dans l'attribut style.
    couleur = objet.get(propriete, "")
    for declaration in objet.get("style", "").split(";"):
        if ":" in declaration:
            nom, valeur = declaration.split(":", 1)
            if nom.strip() == propriete:
                couleur = valeur.strip()
    return couleur.strip().lower()


def lire_decalage(objet, parents):
    # Un groupe peut décaler ses objets avec translate(x, y).
    x = 0.0
    y = 0.0
    while objet is not None:
        texte = objet.get("transform", "").strip()
        if texte:
            if not texte.startswith("translate(") or not texte.endswith(")"):
                raise ValueError("Transformation non gérée sur un repère : " + texte)
            valeurs = texte[10:-1].replace(",", " ").split()
            if len(valeurs) not in [1, 2]:
                raise ValueError("Déplacement SVG incorrect.")
            x = x + float(valeurs[0])
            if len(valeurs) == 2:
                y = y + float(valeurs[1])
        objet = parents.get(objet)
    return x, y


def lire_svg(fichier):
    racine = ET.parse(fichier).getroot()
    groupe = None
    parents = {}
    for objet in racine.iter():
        if objet.get("id") == "reperes_simulation_couleurs":
            groupe = objet
        for enfant in objet:
            parents[enfant] = objet

    if groupe is None:
        raise ValueError("Le groupe reperes_simulation_couleurs est absent du SVG.")

    donnees = {"trajets": [], "arrets": [], "entrees": [], "sorties": []}
    for objet in groupe.iter():
        type_objet = objet.tag.split("}")[-1]
        if type_objet == "path":
            couleur = lire_couleur(objet, "stroke")
        elif type_objet == "circle":
            couleur = lire_couleur(objet, "fill")
        else:
            continue

        categorie = COULEURS.get(couleur)
        if categorie is None:
            continue

        numero = int(objet.get("id", "").split("_")[-1])
        decalage_x, decalage_y = lire_decalage(objet, parents)
        information = {"numero": numero, "couleur": couleur}

        if categorie in ["trajets", "arrets"]:
            if type_objet != "path":
                raise ValueError("Un trajet ou un arrêt doit être un tracé.")
            segments = lire_trace(objet.get("d", ""))
            for segment in segments:
                coordonnees = segment["coordonnees"]
                for indice in range(0, len(coordonnees), 2):
                    coordonnees[indice] = coordonnees[indice] + decalage_x
                    coordonnees[indice + 1] = coordonnees[indice + 1] + decalage_y
            information["segments"] = segments
        else:
            if type_objet != "circle":
                raise ValueError("Une entrée ou une sortie doit être un cercle.")
            information["x"] = float(objet.get("cx")) + decalage_x
            information["y"] = float(objet.get("cy")) + decalage_y
            information["rayon"] = float(objet.get("r"))

        donnees[categorie].append(information)

    # Contrôle adapté à ce carrefour : refuser un plan incomplet ou des doublons.
    nombres_attendus = {"trajets": 12, "arrets": 4, "entrees": 6, "sorties": 4}
    for categorie, objets in donnees.items():
        numeros = [objet["numero"] for objet in objets]
        if sorted(numeros) != list(range(1, nombres_attendus[categorie] + 1)):
            raise ValueError("Repères manquants ou numéros incorrects : " + categorie)
    return donnees


def enregistrer_donnees(donnees, fichier):
    connexion = sqlite3.connect(fichier)
    try:
        connexion.execute("PRAGMA foreign_keys = ON")
        with connexion:
            curseur = connexion.cursor()
            curseur.execute("""
                CREATE TABLE IF NOT EXISTS objets (
                    categorie TEXT NOT NULL,
                    numero INTEGER NOT NULL,
                    couleur TEXT NOT NULL,
                    x REAL, y REAL, rayon REAL,
                    PRIMARY KEY (categorie, numero)
                )
            """)
            curseur.execute("""
                CREATE TABLE IF NOT EXISTS segments (
                    categorie TEXT NOT NULL,
                    numero INTEGER NOT NULL,
                    ordre INTEGER NOT NULL,
                    commande TEXT NOT NULL,
                    x1 REAL NOT NULL, y1 REAL NOT NULL,
                    x2 REAL, y2 REAL, x3 REAL, y3 REAL,
                    PRIMARY KEY (categorie, numero, ordre),
                    FOREIGN KEY (categorie, numero)
                        REFERENCES objets (categorie, numero)
                )
            """)

            for categorie, objets in donnees.items():
                for objet in objets:
                    numero = objet["numero"]
                    # Ajouter l'objet ou actualiser celui qui existe déjà.
                    curseur.execute("""
                        INSERT INTO objets (categorie, numero, couleur, x, y, rayon)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT (categorie, numero) DO UPDATE SET
                            couleur = excluded.couleur,
                            x = excluded.x, y = excluded.y, rayon = excluded.rayon
                    """, (categorie, numero, objet["couleur"],
                          objet.get("x"), objet.get("y"), objet.get("rayon")))

                    # Remplacer uniquement les segments de l'objet relu dans le SVG.
                    curseur.execute("""
                        DELETE FROM segments WHERE categorie = ? AND numero = ?
                    """, (categorie, numero))

                    for ordre, segment in enumerate(objet.get("segments", []), start=1):
                        coordonnees = segment["coordonnees"].copy()
                        # Une ligne n'utilise qu'un point ; une courbe en utilise trois.
                        # None laisse les autres colonnes vides dans la base.
                        while len(coordonnees) < 6:
                            coordonnees.append(None)
                        valeurs = [categorie, numero, ordre, segment["commande"]] + coordonnees
                        curseur.execute("""
                            INSERT INTO segments
                            (categorie, numero, ordre, commande, x1, y1, x2, y2, x3, y3)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, valeurs)
    finally:
        connexion.close()


if __name__ == "__main__":
    print("Lecture du fichier :", FICHIER_SVG)
    donnees = lire_svg(FICHIER_SVG)

    for categorie, objets in donnees.items():
        print(categorie, ":", len(objets), "objets extraits")

    print("Enregistrement dans la base SQL...")
    enregistrer_donnees(donnees, FICHIER_BASE)
    print("Terminé. Base créée ou mise à jour :", FICHIER_BASE)
