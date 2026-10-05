import sys
import random
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsRectItem, QMainWindow
from PySide6.QtGui import QPixmap, QColor, QBrush, QPainterPath, QPen
from PySide6.QtCore import QTimer, Qt, QPointF

# On importe les donnees du carrefour extraites par le script
from donnees_couleurs import DONNEES

class Vehicule:
    def __init__(self, scene, trajet, est_urgence=False):
        self.est_urgence = est_urgence

        # Le vehicule est un simple rectangle
        self.rect = QGraphicsRectItem(-10, -5, 20, 10)

        if self.est_urgence:
            self.rect.setBrush(QBrush(QColor("red")))
        else:
            self.rect.setBrush(QBrush(QColor("blue")))

        scene.addItem(self.rect)

        # Creer le chemin a partir des donnees extraites
        self.chemin = QPainterPath()
        for segment in trajet['segments']:
            commande = segment['commande']
            coords = segment['coordonnees']
            if commande == 'M':
                self.chemin.moveTo(coords[0], coords[1])
            elif commande == 'L':
                self.chemin.lineTo(coords[0], coords[1])
            elif commande == 'C':
                self.chemin.cubicTo(coords[0], coords[1], coords[2], coords[3], coords[4], coords[5])

        self.progression = 0.0
        self.vitesse = 0.005 if self.est_urgence else 0.002
        self.fini = False

        # Mettre la voiture au point de depart
        self.mettre_a_jour_position()

    def mettre_a_jour_position(self):
        # On recupere le point sur le chemin selon la progression (0 a 1)
        point = self.chemin.pointAtPercent(self.progression)
        angle = self.chemin.angleAtPercent(self.progression)

        self.rect.setPos(point)
        # On tourne la voiture pour qu'elle suive la route (angle negatif car Qt va a l'envers)
        self.rect.setRotation(-angle)

    def avancer(self, urgence_en_cours):
        if self.fini:
            return

        # Si c'est une voiture normale et qu'il y a une urgence, elle s'arrete !
        if not self.est_urgence and urgence_en_cours:
            return

        # Sinon la voiture avance
        self.progression += self.vitesse
        if self.progression >= 1.0:
            self.progression = 1.0
            self.fini = True

        self.mettre_a_jour_position()

    def supprimer(self, scene):
        scene.removeItem(self.rect)

class Simulation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simulation Carrefour Connecté - Projet 1ère Année")
        self.resize(1000, 700)

        self.scene = QGraphicsScene()

        # Afficher la carte en fond (le plan du carrefour)
        # L'image originale carrefour.png est utilisée, on la redimensionne pour qu'elle corresponde au SVG
        # Le chemin est modifié pour utiliser assets au lieu de ../assets afin d'être exécutable depuis la racine
        image_fond = QPixmap("assets/carrefour.png").scaled(1770, 1120)
        if not image_fond.isNull():
            self.scene.addPixmap(image_fond)

        self.vue = QGraphicsView(self.scene)
        self.vue.setRenderHint(self.vue.renderHints()) # Mode simple
        self.setCentralWidget(self.vue)

        # Ajuster la vue pour voir tout le carrefour
        self.vue.fitInView(0, 0, 1770, 1120, Qt.KeepAspectRatio)

        self.vehicules = []

        # Timer pour animer les voitures
        self.timer_animation = QTimer()
        self.timer_animation.timeout.connect(self.animer)
        self.timer_animation.start(30) # 30 ms

        # Timer pour ajouter de nouvelles voitures
        self.timer_ajout = QTimer()
        self.timer_ajout.timeout.connect(self.ajouter_vehicule)
        self.timer_ajout.start(2000) # Toutes les 2 secondes

    def ajouter_vehicule(self):
        trajets = DONNEES['trajets']
        trajet_choisi = random.choice(trajets)

        # 10% de chance d'avoir un véhicule d'urgence
        est_urgence = (random.random() < 0.1)

        nouveau_vehicule = Vehicule(self.scene, trajet_choisi, est_urgence)
        self.vehicules.append(nouveau_vehicule)

    def animer(self):
        # 1. Verifier s'il y a un vehicule d'urgence dans le carrefour
        urgence_en_cours = False
        for v in self.vehicules:
            if v.est_urgence and not v.fini:
                urgence_en_cours = True
                break

        # 2. Faire avancer toutes les voitures en leur disant s'il y a une urgence
        for v in self.vehicules:
            v.avancer(urgence_en_cours)

        # 3. Supprimer les voitures arrivees
        vehicules_restants = []
        for v in self.vehicules:
            if v.fini:
                v.supprimer(self.scene)
            else:
                vehicules_restants.append(v)
        self.vehicules = vehicules_restants

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = Simulation()
    fenetre.show()
    sys.exit(app.exec())
