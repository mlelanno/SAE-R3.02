import sys
from PySide6.QtWidgets import QApplication
from core.controleur_feux import GestionnaireCarrefour
from gui.vue_feux import FenetreCarrefour

application = QApplication(sys.argv)

gestionnaire = GestionnaireCarrefour()
fenetre = FenetreCarrefour(gestionnaire)
fenetre.show()

sys.exit(application.exec())