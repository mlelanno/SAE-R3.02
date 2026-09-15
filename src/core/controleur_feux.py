class GestionnaireCarrefour:
    def __init__(self):
        self.phase = 1
        self.durees = {
            1: 5000,
            2: 2000,
            3: 5000,
            4: 2000
        }
        self.etat_axe_principal = "Vert"
        self.etat_axe_secondaire = "Rouge"

    def avancer_phase(self):
        if self.phase == 1:
            self.phase = 2
            self.etat_axe_principal = "Orange"
            self.etat_axe_secondaire = "Rouge"
        elif self.phase == 2:
            self.phase = 3
            self.etat_axe_principal = "Rouge"
            self.etat_axe_secondaire = "Vert"
        elif self.phase == 3:
            self.phase = 4
            self.etat_axe_principal = "Rouge"
            self.etat_axe_secondaire = "Orange"
        elif self.phase == 4:
            self.phase = 1
            self.etat_axe_principal = "Vert"
            self.etat_axe_secondaire = "Rouge"

    def duree_actuelle(self):
        return self.durees[self.phase]

    def etat_feu(self, numero_feu):
        if numero_feu in (1, 8):
            return self.etat_axe_principal
        return self.etat_axe_secondaire