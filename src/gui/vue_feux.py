from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsItemGroup, QGraphicsItem, QGraphicsPixmapItem, QGraphicsEllipseItem
)
from PySide6.QtGui import QPixmap, QColor, QBrush, QPen
from PySide6.QtCore import QTimer

class ElementFeu(QGraphicsItemGroup):
    def __init__(self, numero, position_x, position_y, hauteur=45):
        super().__init__()
        self.numero = numero
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        )

        image = QPixmap("assets/feux.png")
        if image.isNull():
            image = QPixmap("assets/feux.svg")

        image_reduite = image.scaledToHeight(hauteur)
        element_visuel = QGraphicsPixmapItem(image_reduite)
        self.addToGroup(element_visuel)

        facteur = hauteur / 300
        diametre = max(3, int(36 * facteur))
        decalage_x = int(45 * facteur)

        contour_invisible = QPen(QColor("transparent"))
        couleur_rouge = QBrush(QColor(255, 0, 0))
        couleur_orange = QBrush(QColor(255, 165, 0))
        couleur_verte = QBrush(QColor(0, 220, 0))

        self.lampe_rouge = QGraphicsEllipseItem(decalage_x, int(35 * facteur), diametre, diametre)
        self.lampe_rouge.setPen(contour_invisible)
        self.lampe_rouge.setBrush(couleur_rouge)
        self.addToGroup(self.lampe_rouge)

        self.lampe_orange = QGraphicsEllipseItem(decalage_x, int(85 * facteur), diametre, diametre)
        self.lampe_orange.setPen(contour_invisible)
        self.lampe_orange.setBrush(couleur_orange)
        self.addToGroup(self.lampe_orange)

        self.lampe_verte = QGraphicsEllipseItem(decalage_x, int(135 * facteur), diametre, diametre)
        self.lampe_verte.setPen(contour_invisible)
        self.lampe_verte.setBrush(couleur_verte)
        self.addToGroup(self.lampe_verte)

        self.setPos(position_x, position_y)

    def mouseReleaseEvent(self, evenement):
        super().mouseReleaseEvent(evenement)
        print(f"{self.numero}: ElementFeu(self.scene, {int(self.pos().x())}, {int(self.pos().y())}),")

    def actualiser(self, etat):
        self.lampe_rouge.setVisible(etat == "Rouge")
        self.lampe_orange.setVisible(etat == "Orange")
        self.lampe_verte.setVisible(etat == "Vert")

class FenetreCarrefour(QWidget):
    def __init__(self, gestionnaire):
        super().__init__()
        self.gestionnaire = gestionnaire
        self.setWindowTitle("Simulation Carrefour Colmar - Mode Calibrage")
        self.resize(1050, 750)

        self.scene = QGraphicsScene()
        self.vue = QGraphicsView(self.scene)

        disposition = QVBoxLayout()
        disposition.addWidget(self.vue)
        self.setLayout(disposition)

        carte = QPixmap("assets/carrefour.png").scaledToWidth(1000)
        if not carte.isNull():
            self.scene.addPixmap(carte)

        coordonnees_initiales = {
            1: (327, 378),
            5: (495, 546),
            6: (459, 227),
            8: (686, 334),
        }

        self.feux = {}
        for numero, (x, y) in coordonnees_initiales.items():
            feu = ElementFeu(numero, x, y)
            self.scene.addItem(feu)
            self.feux[numero] = feu

        self.actualiser_affichage()

        self.minuteur = QTimer()
        self.minuteur.timeout.connect(self.avancer_cycle)
        self.minuteur.start(self.gestionnaire.duree_actuelle())

    def avancer_cycle(self):
        self.gestionnaire.avancer_phase()
        self.actualiser_affichage()
        self.minuteur.start(self.gestionnaire.duree_actuelle())

    def actualiser_affichage(self):
        for numero, feu in self.feux.items():
            feu.actualiser(self.gestionnaire.etat_feu(numero))