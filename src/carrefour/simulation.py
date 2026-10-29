from math import isfinite
import socket
import json
import select
import sqlite3
from datetime import datetime
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, QMainWindow,
                               QWidget, QHBoxLayout, QPushButton, QButtonGroup)
from PySide6.QtGui import QColor, QBrush, QPainterPath, QPen, QTransform, QPainter, QPixmap, QFont
from PySide6.QtCore import QTimer, Qt, QThread, Signal, Slot, QFileInfo, QDir, QUrl
from PySide6.QtSvgWidgets import QGraphicsSvgItem

TRAFIC = "dense"
FREQUENCES = {"faible": 8, "moyen": 4, "dense": 2}
PAS = 0.03
VITESSE = 100  # Unités du dessin par seconde pour les voitures civiles.
FACTEUR_URGENCE = 1.67
DELAI_URGENCE = 20  # Secondes de simulation avant l’apparition.
ANTICIPATION = 10  # Préparer les feux quand il reste 10 secondes avant l'arrivée.
DISTANCE_REACTION = 55  # Une voiture réagit seulement juste devant l'ambulance.
DECALAGE_DROITE = 20
DUREE_DECALAGE_SANS_OPTI = 3  # Attente avant de se ranger, sans optimisation.
LONGUEUR = 30
LARGEUR = 15
ESPACE = 12
MAX_VIRAGES = 3
ORDRE = [1, 1, 1, 0, 0, 0, 1, 1, 1, 2]
PHASES = [
    (2, "VERT", 20),
    (2, "ORANGE", 2),
    (0, "ROUGE", 2),
    (1, "VERT", 20),
    (1, "ORANGE", 2),
    (0, "ROUGE", 2),
]
APPROCHES = [2, 2, 2, 3, 3, 3, 3, 3, 3, 2, 2, 2]
CENTRES = [3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4]
RONDS = [
    ["circle167", "circle168", "circle169"],
    ["circle195", "circle196", "circle197"],
    ["circle187", "circle188", "circle189"],
    ["circle183", "circle184", "circle185"],
]


def fichier_projet(nom):
    return QDir(QFileInfo(__file__).absolutePath()).filePath(nom)


def lire_base(fichier, requete):
    information = QFileInfo(str(fichier))
    if not information.isFile():
        raise FileNotFoundError("Remettre carrefour.db fournie avec cette version.")
    adresse = bytes(QUrl.fromLocalFile(information.absoluteFilePath()).toEncoded()).decode("ascii")
    try:
        connexion = sqlite3.connect(adresse + "?mode=ro", uri=True, timeout=1)
        try:
            return connexion.execute(requete).fetchall()
        finally:
            connexion.close()
    except sqlite3.Error as erreur:
        raise ValueError("Base du carrefour illisible : " + str(erreur)) from erreur


def charger_trajets(fichier):
    lignes = lire_base(fichier, """
        SELECT o.numero, o.couleur, s.ordre, s.commande,
               s.x1, s.y1, s.x2, s.y2, s.x3, s.y3
        FROM objets AS o LEFT JOIN segments AS s
          ON s.categorie = o.categorie AND s.numero = o.numero
        WHERE o.categorie = 'trajets' ORDER BY o.numero, s.ordre
    """)
    trajets = {}
    for numero, couleur, ordre, commande, *valeurs in lignes:
        trajet = trajets.setdefault(numero, {"numero": numero, "couleur": couleur, "segments": []})
        segments = trajet["segments"]
        if commande not in ("M", "L", "C") or ordre != len(segments) + 1:
            raise ValueError(f"Segments absents ou incorrects pour le trajet {numero}.")
        if (commande == "M") != (ordre == 1):
            raise ValueError(f"Départ incorrect pour le trajet {numero}.")
        coordonnees = valeurs[:6 if commande == "C" else 2]
        if any(not isinstance(v, (int, float)) or not isfinite(v) for v in coordonnees):
            raise ValueError(f"Coordonnées incorrectes pour le trajet {numero}.")
        segments.append({"commande": commande, "coordonnees": coordonnees})
    if set(trajets) != set(range(1, 13)):
        raise ValueError("La base doit contenir les trajets numérotés de 1 à 12.")
    for numero, trajet in trajets.items():
        if len(trajet["segments"]) < CENTRES[numero - 1]:
            raise ValueError(f"Trajet {numero} incomplet.")
    return [trajets[numero] for numero in range(1, 13)]


def creer_chemin(segments):
    chemin = QPainterPath()
    chemin.setCachingEnabled(True)
    for segment in segments:
        commande = segment["commande"]
        valeurs = segment["coordonnees"]
        if commande == "M":
            chemin.moveTo(valeurs[0], valeurs[1])
        elif commande == "L":
            chemin.lineTo(valeurs[0], valeurs[1])
        elif commande == "C":
            chemin.cubicTo(valeurs[0], valeurs[1], valeurs[2], valeurs[3], valeurs[4], valeurs[5])
        else:
            raise ValueError("Commande SVG inconnue : " + commande)
    return chemin


def forme_sur_chemin(chemin, distance, marge=0, decalage=0):
    proportion = chemin.percentAtLength(distance)
    point = chemin.pointAtPercent(proportion)
    forme = QPainterPath()
    forme.addRect(-LONGUEUR / 2 - marge, -LARGEUR / 2 - 2 + decalage,
                  LONGUEUR + 2 * marge, LARGEUR + 4)
    placement = QTransform()
    placement.translate(point.x(), point.y())
    placement.rotate(-chemin.angleAtPercent(proportion))
    return placement.map(forme)


class FeuTricolore:
    def __init__(self, scene, plan, identifiants, axe):
        self.axe = axe
        self.ronds = []
        lecteur = plan.renderer()
        for identifiant in identifiants:
            cadre = lecteur.boundsOnElement(identifiant)
            cadre = lecteur.transformForElement(identifiant).mapRect(cadre)
            rond = scene.addEllipse(cadre)
            rond.setPen(QPen(Qt.PenStyle.NoPen))
            rond.setZValue(2)
            self.ronds.append(rond)

    def afficher(self, etat):
        self.etat = etat
        couleurs = {"ROUGE": "#ff3030", "ORANGE": "#ffb000", "VERT": "#00df60"}
        for indice, nom in enumerate(["ROUGE", "ORANGE", "VERT"]):
            couleur = "#78858a"
            if nom == etat:
                couleur = couleurs[nom]
            self.ronds[indice].setBrush(QBrush(QColor(couleur)))


class Vehicule:
    def __init__(self, scene, trajet, numero=0, urgence=False):
        self.numero = numero
        self.trajet = trajet
        self.distance = 0.0
        self.engage = False
        self.urgence = urgence
        self.vitesse = VITESSE * FACTEUR_URGENCE if urgence else VITESSE
        self.decalage = 0.0
        self.attente_decalage = 0.0
        self.rect = scene.addRect(-LONGUEUR / 2, -LARGEUR / 2, LONGUEUR, LARGEUR)
        couleur = "#ff1111" if urgence else "#247bc0"
        self.rect.setBrush(QBrush(QColor(couleur)))
        self.rect.setPen(QPen(QColor("white"), 2) if urgence else QPen(Qt.PenStyle.NoPen))
        self.rect.setZValue(3 if urgence else 1)
        self.mettre_a_jour_position()

    def mettre_a_jour_position(self):
        chemin = self.trajet["chemin"]
        proportion = chemin.percentAtLength(self.distance)
        self.rect.setRect(-LONGUEUR / 2, -LARGEUR / 2 + self.decalage, LONGUEUR, LARGEUR)
        self.rect.setPos(chemin.pointAtPercent(proportion))
        self.rect.setRotation(-chemin.angleAtPercent(proportion))
        self.forme = forme_sur_chemin(chemin, self.distance, decalage=self.decalage)

    def supprimer(self, scene):
        scene.removeItem(self.rect)


class BaseResultats:
    """Conserver les essais terminés dans une base SQLite locale."""

    def __init__(self, fichier):
        self.fichier = str(fichier)
        connexion = sqlite3.connect(self.fichier, timeout=1)
        try:
            with connexion:
                connexion.execute("""
                    CREATE TABLE IF NOT EXISTS essais (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date_heure TEXT NOT NULL,
                        trafic_initial TEXT NOT NULL,
                        trafic_final TEXT NOT NULL,
                        optimisation INTEGER NOT NULL CHECK (optimisation IN (0, 1)),
                        duree_s REAL NOT NULL CHECK (duree_s >= 0),
                        scenario_modifie INTEGER NOT NULL CHECK (scenario_modifie IN (0, 1)),
                        parametres_json TEXT NOT NULL
                    )
                """)
        finally:
            connexion.close()

    def enregistrer(self, trafic_initial, trafic_final, optimisation,
                    duree_s, scenario_modifie, parametres):
        # Une connexion courte par enregistrement : aucun objet SQLite partagé
        # avec le thread réseau ou avec l'autre fenêtre de simulation.
        connexion = sqlite3.connect(self.fichier, timeout=1)
        try:
            with connexion:
                curseur = connexion.execute("""
                    INSERT INTO essais
                    (date_heure, trafic_initial, trafic_final, optimisation,
                     duree_s, scenario_modifie, parametres_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                    trafic_initial, trafic_final, int(optimisation), duree_s,
                    int(scenario_modifie), json.dumps(parametres, ensure_ascii=False)
                ))
                numero = curseur.lastrowid
            return numero
        finally:
            connexion.close()


class ReceptionReseau(QThread):
    """Recevoir les messages en parallèle et les transmettre par signaux Qt."""

    message_recu = Signal(object, object)
    erreur_recue = Signal(str)

    def __init__(self, connexion, parent=None):
        super().__init__(parent)
        self.connexion = connexion

    def run(self):
        while not self.isInterruptionRequested():
            try:
                # L'attente courte permet de vérifier régulièrement l'arrêt.
                disponibles, _, _ = select.select([self.connexion], [], [], 0.1)
                if not disponibles:
                    continue
                donnees, adresse = self.connexion.recvfrom(1024)
                message = json.loads(donnees.decode("utf-8"))
            except BlockingIOError:
                continue
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            except (OSError, ValueError) as erreur:
                if not self.isInterruptionRequested():
                    self.erreur_recue.emit(str(erreur))
                break
            if isinstance(message, dict):
                # Aucune modification de l'interface depuis ce thread.
                self.message_recu.emit(message, adresse)


class Simulation(QMainWindow):
    def __init__(self, optimisation=True, port=9999, reseau=True,
                 fichier_resultats=None, adresse_ecoute="0.0.0.0"):
        super().__init__()
        base_geometrie = fichier_projet("carrefour.db")
        donnees_trajets = charger_trajets(base_geometrie)
        self.optimisation = optimisation
        self.port = port
        self.resultats = {}
        self.trafic = TRAFIC
        self.fermeture_en_cours = False
        self.erreur_reseau = ""
        self.erreur_stockage = ""
        self.base_resultats = None
        if fichier_resultats is None:
            fichier_resultats = fichier_projet("resultats.db")
        try:
            self.base_resultats = BaseResultats(fichier_resultats)
        except (sqlite3.Error, OSError) as erreur:
            self.erreur_stockage = str(erreur)
            print("Base des résultats indisponible :", erreur)
        self.setWindowTitle("Simulation du carrefour — véhicule d’urgence")
        self.resize(1100, 740)
        self.scene = QGraphicsScene()
        fichier = fichier_projet("carrefour_couleurs.svg")
        self.plan = QGraphicsSvgItem(fichier)
        if not self.plan.renderer().isValid():
            raise ValueError("Le plan SVG est absent ou invalide.")
        self.scene.addItem(self.plan)
        self.scene.setSceneRect(self.plan.boundingRect())
        self.vue = QGraphicsView(self.scene)
        self.vue.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.vue.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.vue.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(self.vue)

        self.horloge = self.scene.addPixmap(QPixmap())
        self.horloge.setPos(1190, 60)
        self.horloge.setZValue(5)
        self.afficher_heure()

        contenu = QWidget()
        contenu.setObjectName("choix_trafic")
        contenu.setStyleSheet("QWidget#choix_trafic { background: transparent; }")
        contenu.setFixedWidth(540)
        ligne = QHBoxLayout(contenu)
        ligne.setContentsMargins(0, 0, 0, 0)

        self.boutons = QButtonGroup(self)
        self.boutons.setExclusive(True)
        for nom, niveau in [("Dense", "dense"), ("Moyen", "moyen"), ("Faible", "faible")]:
            bouton = QPushButton(nom)
            bouton.setMinimumHeight(40)
            bouton.setStyleSheet("QPushButton {font-size: 20px; color: black; background: #eeeeee;} QPushButton:checked {background: #b7d8ed;}")
            bouton.setCheckable(True)
            bouton.setChecked(niveau == self.trafic)
            self.boutons.addButton(bouton)
            ligne.addWidget(bouton)

        self.boutons.buttonClicked.connect(self.changer_trafic)
        self.panneau_boutons = self.scene.addWidget(contenu)
        self.panneau_boutons.setPos(1190, 305)
        self.panneau_boutons.setZValue(5)

        self.vehicules = []
        self.nombre_crees = 0

        self.creer_commandes()

        self.trajets = {}
        for donnee in donnees_trajets:
            trajet = donnee.copy()
            numero = trajet["numero"]
            segments = trajet["segments"]
            debut = APPROCHES[numero - 1]
            fin = CENTRES[numero - 1]
            approche = creer_chemin(segments[:debut])
            centre = creer_chemin(segments[:fin])
            trajet["chemin"] = creer_chemin(segments)
            trajet["longueur"] = trajet["chemin"].length()
            trajet["arret"] = approche.length() - LONGUEUR / 2 - 4
            trajet["fin_centre"] = centre.length() + LONGUEUR / 2 + 4
            trajet["gauche"] = numero in [1, 4, 7, 10]
            trajet["axe"] = 2
            if numero <= 6:
                trajet["axe"] = 1
            self.trajets[numero] = trajet

        self.feux = []
        for indice, identifiants in enumerate(RONDS):
            axe = 2
            if indice < 2:
                axe = 1
            self.feux.append(FeuTricolore(self.scene, self.plan, identifiants, axe))

        self.recommencer()
        self.socket_reseau = None
        self.thread_reseau = None
        if reseau:
            self.socket_reseau = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                self.socket_reseau.bind((adresse_ecoute, port))
                self.socket_reseau.setblocking(False)
            except OSError:
                self.socket_reseau.close()
                raise
            self.thread_reseau = ReceptionReseau(self.socket_reseau, self)
            self.thread_reseau.message_recu.connect(
                self.recevoir_message, Qt.ConnectionType.QueuedConnection)
            self.thread_reseau.erreur_recue.connect(
                self.signaler_erreur_reseau, Qt.ConnectionType.QueuedConnection)
            self.thread_reseau.start()
        self.timer_animation = QTimer(self)
        self.timer_animation.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer_animation.timeout.connect(self.animer)
        self.timer_animation.start(round(PAS * 1000))
        self.actualiser_feux()

    def creer_commandes(self):
        contenu = QWidget()
        contenu.setFixedWidth(540)
        ligne = QHBoxLayout(contenu)
        ligne.setContentsMargins(0, 0, 0, 0)
        self.modes = QButtonGroup(self)
        for texte, actif in [("Sans optimisation", False), ("Avec optimisation", True)]:
            bouton = QPushButton(texte)
            bouton.setCheckable(True)
            bouton.setChecked(actif == self.optimisation)
            bouton.setMinimumHeight(40)
            bouton.setStyleSheet("QPushButton {font-size: 18px; color: black; background: #eeeeee;} QPushButton:checked {background: #b7d8ed;}")
            self.modes.addButton(bouton)
            ligne.addWidget(bouton)
        self.modes.buttonClicked.connect(self.changer_mode)
        proxy = self.scene.addWidget(contenu)
        proxy.setPos(1190, 355)
        proxy.setZValue(5)
        self.texte_etat = self.scene.addText("")
        self.texte_etat.setFont(QFont("Arial", 18))
        self.texte_etat.setDefaultTextColor(QColor("black"))
        self.texte_etat.setTextWidth(540)
        self.texte_etat.setPos(1190, 405)
        self.texte_etat.setZValue(5)

    def changer_mode(self, bouton):
        self.optimisation = bouton.text() == "Avec optimisation"
        self.recommencer()

    def recommencer(self):
        for voiture in self.vehicules:
            voiture.supprimer(self.scene)
        self.vehicules = []
        self.nombre_crees = 0
        self.temps = 0.0
        self.phase = 3  # Départ identique : axe horizontal au vert.
        self.fin_phase = PHASES[3][2]
        self.prochaines = {1: 0, 4: 0, 7: 0, 10: 0}
        self.directions = {1: 0, 4: 0, 7: 0, 10: 0}
        # Une urgence ne peut être programmée que par le client UDP.
        self.urgence_en_attente = False
        self.temps_spawn_urgence = None
        self.ambulance = None
        self.voiture_devant = None
        self.urgence_franchie = False
        self.debut_urgence = None
        self.temps_resultat = None
        self.trafic_initial = self.trafic
        self.dernier_resultat_id = None
        if self.base_resultats is not None:
            self.erreur_stockage = ""
        self.scenario_modifie = False
        self.preparer_convois()
        self.actualiser_feux()
        self.afficher_etat()

    def priorite_active(self):
        if not self.optimisation:
            return False
        if self.urgence_en_attente and self.temps + 0.000001 >= self.temps_spawn_urgence - ANTICIPATION:
            return True
        return self.ambulance is not None and not self.urgence_franchie

    def urgence_prioritaire(self):
        # Les virages cèdent le passage dans les DEUX modes.
        # Seul le mode optimisé prépare les feux avant l'apparition.
        return self.priorite_active() or (self.ambulance is not None and not self.urgence_franchie)

    def afficher_etat(self):
        if self.urgence_en_attente:
            reste = max(0, self.temps_spawn_urgence - self.temps)
            texte = f"Véhicule d'urgence dans {reste:.1f} s"
            if reste == 0:
                texte = "En attente d'une place à l'entrée"
            elif self.priorite_active():
                texte += "\nPréparation des feux en cours"
        elif self.ambulance is not None:
            texte = f"Temps A → B : {self.temps - self.debut_urgence:.1f} s"
        elif self.temps_resultat is not None:
            texte = f"Arrivé en {self.temps_resultat:.1f} s"
        else:
            texte = "En attente d’une demande de la VM Véhicule"
        if self.scenario_modifie:
            texte += "\nEssai modifié : relancer pour comparer."
        for nom, actif in [("Sans optimisation", False), ("Avec optimisation", True)]:
            resultat = self.resultats.get((self.trafic, actif))
            if resultat is not None:
                texte += f"\n{nom} : {resultat:.1f} s"
        if self.dernier_resultat_id is not None:
            texte += f"\nRésultat enregistré (essai n° {self.dernier_resultat_id})."
        if self.erreur_stockage:
            texte += "\nSauvegarde impossible : " + self.erreur_stockage
        if self.erreur_reseau:
            texte += "\nErreur réseau : " + self.erreur_reseau
        self.texte_etat.setPlainText(texte)

    @Slot(object, object)
    def recevoir_message(self, message, adresse):
        # Ce slot est exécuté dans le fil principal de l'interface.
        if self.fermeture_en_cours or self.socket_reseau is None:
            return
        if message.get("action") == "URGENCE":
            acceptee = self.declencher_urgence()
            statut = "programmee" if acceptee else "deja_en_cours"
            reponse = json.dumps({"statut": statut, "delai": DELAI_URGENCE})
            try:
                self.socket_reseau.sendto(reponse.encode("utf-8"), adresse)
            except OSError as erreur:
                self.signaler_erreur_reseau(str(erreur))

    @Slot(str)
    def signaler_erreur_reseau(self, erreur):
        if not self.fermeture_en_cours:
            self.erreur_reseau = erreur
            print("Erreur réseau :", erreur)
            self.afficher_etat()

    def sauvegarder_resultat(self):
        if self.base_resultats is None:
            return
        parametres = {
            "pas_s": PAS, "vitesse_civils": VITESSE,
            "facteur_urgence": FACTEUR_URGENCE,
            "delai_urgence_s": DELAI_URGENCE, "anticipation_s": ANTICIPATION,
            "reaction_sans_optimisation_s": DUREE_DECALAGE_SANS_OPTI,
            "frequences_trafic": FREQUENCES,
            "phases": PHASES, "trajet_urgence": 11
        }
        try:
            self.dernier_resultat_id = self.base_resultats.enregistrer(
                self.trafic_initial, self.trafic, self.optimisation,
                self.temps_resultat, self.scenario_modifie, parametres)
            self.erreur_stockage = ""
        except (sqlite3.Error, OSError) as erreur:
            self.erreur_stockage = str(erreur)
            print("Impossible de sauvegarder le résultat :", erreur)

    def resizeEvent(self, evenement):
        super().resizeEvent(evenement)
        QTimer.singleShot(0, self.ajuster_vue)

    def ajuster_vue(self):
        self.vue.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def changer_trafic(self, bouton):
        niveaux = {"Dense": "dense", "Moyen": "moyen", "Faible": "faible"}
        if niveaux[bouton.text()] == self.trafic:
            return
        self.trafic = niveaux[bouton.text()]
        self.scenario_modifie = True
        self.afficher_heure()
        for base in self.prochaines:
            self.prochaines[base] = self.temps + FREQUENCES[self.trafic]

    def declencher_urgence(self):
        # Une seule demande à la fois, même si plusieurs messages sont reçus.
        if self.urgence_en_attente or self.ambulance is not None:
            return False
        self.urgence_en_attente = True
        self.temps_spawn_urgence = self.temps + DELAI_URGENCE
        self.temps_resultat = None
        self.dernier_resultat_id = None
        if self.base_resultats is not None:
            self.erreur_stockage = ""
        self.scenario_modifie = True  # Une nouvelle demande manuelle ne rejoue pas le même début.
        return True

    def spawn_ambulance_physique(self):
        trajet = self.trajets[11]  # Sud vers Nord.
        forme = forme_sur_chemin(trajet["chemin"], 0, ESPACE)
        if self.espace_occupe(forme):
            return  # Attendre une place, sans transformer ni déplacer un civil.
        self.nombre_crees += 1
        self.ambulance = Vehicule(self.scene, trajet, self.nombre_crees, urgence=True)
        self.vehicules.append(self.ambulance)
        self.debut_urgence = self.temps
        self.urgence_franchie = False
        self.urgence_en_attente = False

    def afficher_heure(self):
        fichiers = {"dense": "heure_08.png", "moyen": "heure_12.png", "faible": "heure_23.png"}
        fichier = fichier_projet("images/" + fichiers[self.trafic])
        image = QPixmap(str(fichier))
        if image.isNull():
            raise ValueError("Image de l'heure absente : " + str(fichier))
        self.horloge.setPixmap(image.scaledToWidth(540, Qt.TransformationMode.SmoothTransformation))

    def actualiser_feux(self):
        axe, etat, duree = PHASES[self.phase]
        for feu in self.feux:
            couleur = "ROUGE"
            if feu.axe == axe:
                couleur = etat
            feu.afficher(couleur)

    def preparer_convois(self):
        self.etape = "CONVOIS"
        self.convoi = []
        axe = PHASES[self.phase][0]
        for voiture in self.vehicules:
            trajet = voiture.trajet
            proche = voiture.distance >= trajet["arret"] - MAX_VIRAGES * (LONGUEUR + ESPACE)
            if trajet["axe"] == axe and trajet["gauche"] and not voiture.engage and proche:
                self.convoi.append(voiture)

    def gerer_feux(self):
        axe, etat, duree = PHASES[self.phase]
        priorite = self.priorite_active()
        if priorite and axe == 1 and etat == "VERT":
            # Interrompre le vert horizontal en passant d'abord par l'orange.
            self.phase = 4
            self.fin_phase = self.temps + PHASES[4][2]
            return
        if priorite and axe == 2 and etat == "VERT":
            self.etape = "FLUX"
            return  # Garder le vert pour vider la file et laisser passer l'urgence.
        if etat == "VERT" and self.etape == "CONVOIS":
            for voiture in self.convoi:
                if self.urgence_prioritaire() and not voiture.engage:
                    continue  # Reporter les virages qui n'ont pas encore démarré.
                if voiture.distance < voiture.trajet["fin_centre"]:
                    return
            self.etape = "FLUX"
            if not self.urgence_prioritaire():
                self.fin_phase = self.temps + duree
        if self.temps < self.fin_phase:
            return
        if etat == "ROUGE":
            for voiture in self.vehicules:
                if voiture.engage and voiture.distance < voiture.trajet["fin_centre"]:
                    return  # Les voitures engagées doivent terminer leur passage.
            if priorite:
                self.phase = 0
                self.fin_phase = self.temps + PHASES[0][2]
                self.etape = "FLUX"
                self.convoi = []
                return
        self.phase = (self.phase + 1) % len(PHASES)
        self.fin_phase = self.temps + PHASES[self.phase][2]
        if PHASES[self.phase][1] == "VERT":
            self.preparer_convois()

    def espace_occupe(self, forme, voiture_ignoree=None):
        cadre = forme.boundingRect()
        for autre in self.vehicules:
            if autre is not voiture_ignoree and cadre.intersects(autre.forme.boundingRect()):
                if forme.intersects(autre.forme):
                    return True
        return False

    def ajouter_vehicule(self):
        for base in self.prochaines:
            if base == 10 and self.urgence_en_attente and self.temps >= self.temps_spawn_urgence - 2:
                continue
            if self.temps < self.prochaines[base]:
                continue
            numero = base + ORDRE[self.directions[base]]
            if self.urgence_en_attente and numero in [11, 12]:
                # Garder une place au sud pour l'arrivée prévue, dans les deux modes.
                attente = sum(v.trajet["numero"] in [11, 12] and not v.engage
                              for v in self.vehicules)
                if attente >= 2:
                    self.directions[base] = (self.directions[base] + 1) % len(ORDRE)
                    self.prochaines[base] = self.temps + FREQUENCES[self.trafic]
                    continue
            if numero == base:
                nombre = 0
                for autre in self.vehicules:
                    if autre.trajet["numero"] == base:
                        nombre += 1
                if nombre >= MAX_VIRAGES:
                    self.directions[base] = (self.directions[base] + 1) % len(ORDRE)
                    continue
            trajet = self.trajets[numero]
            if self.espace_occupe(forme_sur_chemin(trajet["chemin"], 0, ESPACE)):
                continue
            self.nombre_crees += 1
            voiture = Vehicule(self.scene, trajet, self.nombre_crees)
            self.vehicules.append(voiture)
            self.directions[base] = (self.directions[base] + 1) % len(ORDRE)
            self.prochaines[base] = self.temps + FREQUENCES[self.trafic]

    def passage_libre(self, voiture):
        if self.urgence_prioritaire():
            # Ne pas libérer le flux si un virage engagé coupe encore sa route.
            for autre in self.vehicules:
                if autre.engage and autre.trajet["gauche"] and autre.distance < autre.trajet["fin_centre"]:
                    return False
            return not voiture.trajet["gauche"]
        if self.etape == "CONVOIS":
            return voiture in self.convoi
        return not voiture.trajet["gauche"]

    def voiture_juste_devant(self):
        if self.ambulance is None:
            return None
        devant = None
        distance_min = DISTANCE_REACTION + 1
        for voiture in self.vehicules:
            if voiture.urgence or voiture.decalage >= DECALAGE_DROITE:
                continue
            # Dans le repère de l'ambulance, x positif est devant, y est le côté.
            position = self.ambulance.rect.mapFromScene(voiture.rect.pos())
            angle = abs((voiture.rect.rotation() - self.ambulance.rect.rotation() + 180) % 360 - 180)
            if LONGUEUR <= position.x() <= DISTANCE_REACTION and abs(position.y()) <= 10 and angle < 15:
                if position.x() < distance_min:
                    devant = voiture
                    distance_min = position.x()
        return devant

    def decalage_souhaite(self, voiture):
        if voiture.urgence:
            return 0
        if voiture is self.voiture_devant:
            return DECALAGE_DROITE
        if voiture.decalage > 0 and self.ambulance is not None:
            position = voiture.rect.mapFromScene(self.ambulance.rect.pos())
            proche = (voiture.rect.pos() - self.ambulance.rect.pos()).manhattanLength() < 120
            if proche and position.x() < LONGUEUR + ESPACE:
                return DECALAGE_DROITE  # Rester rangé jusqu'à ce que l'ambulance soit passée.
        return 0

    def avancer(self, voiture):
        trajet = voiture.trajet
        objectif = self.decalage_souhaite(voiture)
        # Se déplacer directement sur le côté, ou revenir dans sa voie.
        decalage = objectif

        # Sans optimisation, attendre 3 secondes avant de se ranger.
        if objectif > voiture.decalage and not self.optimisation:
            voiture.attente_decalage = round(voiture.attente_decalage + PAS, 2)
            if voiture.attente_decalage < DUREE_DECALAGE_SANS_OPTI:
                decalage = voiture.decalage
        else:
            voiture.attente_decalage = 0.0
        distance = min(voiture.distance + voiture.vitesse * PAS, trajet["longueur"])
        if objectif > 0:
            distance = voiture.distance  # Patienter sur le côté pendant le dépassement.
        engagement = False
        if not voiture.engage and distance > trajet["arret"]:
            axe, etat, duree = PHASES[self.phase]
            if axe == trajet["axe"] and etat == "VERT" and self.passage_libre(voiture):
                engagement = True
            else:
                distance = trajet["arret"]
        # Le décalage est aussi inclus dans le contrôle des collisions.
        forme = forme_sur_chemin(trajet["chemin"], distance, ESPACE, decalage)
        if self.espace_occupe(forme, voiture):
            # Même bloquée devant, une voiture peut encore se ranger latéralement.
            distance = voiture.distance
            forme = forme_sur_chemin(trajet["chemin"], distance, ESPACE, decalage)
            if self.espace_occupe(forme, voiture):
                return
        voiture.decalage = decalage
        voiture.distance = distance
        if engagement and distance > trajet["arret"]:
            voiture.engage = True
        voiture.mettre_a_jour_position()

    def animer(self):
        self.temps += PAS
        self.gerer_feux()
        if self.urgence_en_attente and self.temps + 0.000001 >= self.temps_spawn_urgence:
            self.spawn_ambulance_physique()
        self.voiture_devant = self.voiture_juste_devant()
        for voiture in self.vehicules:
            self.avancer(voiture)
        if self.ambulance is not None and not self.urgence_franchie:
            if self.ambulance.distance >= self.ambulance.trajet["fin_centre"]:
                self.urgence_franchie = True
                if self.optimisation:
                    self.fin_phase = self.temps + PHASES[self.phase][2]
        restants = []
        for voiture in self.vehicules:
            if voiture.distance >= voiture.trajet["longueur"]:
                if voiture.urgence:
                    self.temps_resultat = self.temps - self.debut_urgence
                    if not self.scenario_modifie:
                        self.resultats[(self.trafic, self.optimisation)] = self.temps_resultat
                    self.sauvegarder_resultat()
                    self.ambulance = None
                voiture.supprimer(self.scene)
            else:
                restants.append(voiture)
        self.vehicules = restants
        self.ajouter_vehicule()
        self.actualiser_feux()
        self.afficher_etat()

    def closeEvent(self, evenement):
        self.fermeture_en_cours = True
        self.timer_animation.stop()
        if self.thread_reseau is not None:
            self.thread_reseau.requestInterruption()
            self.thread_reseau.wait()
        if self.socket_reseau is not None:
            self.socket_reseau.close()
        super().closeEvent(evenement)


def lancer(optimisation=True, port=9999):
    app = QApplication([])
    fenetre = Simulation(optimisation, port)
    print(f"Serveur Carrefour en écoute sur toutes les cartes IPv4, port UDP {port}.")
    fenetre.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(lancer())
