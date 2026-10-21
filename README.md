***

# Simulateur de Carrefour V2I / V2V - SAÉ 3.02

Ce projet est un simulateur de trafic routier développé en Python avec **PySide6**. Il modélise le carrefour Poudrière / Riquewihr / Ingersheim (Colmar) et implémente un système de gestion de trafic prioritaire pour les véhicules d'urgence, s'appuyant sur des protocoles de communication **V2I (Vehicle-to-Infrastructure)** et **V2V (Vehicle-to-Vehicle)**.

## Fonctionnalités

*   **Modélisation Vectorielle 2D :** Rendu fluide et adaptatif du carrefour basé sur un plan SVG (`QGraphicsScene`).
*   **Moteur Cinématique & Trajectoires :** 12 itinéraires définis par des courbes de Bézier (`QPainterPath`) avec calcul dynamique des angles de rotation.
*   **Gestion des Feux et Anticollision :** Cycle de feux tricolores (incluant une phase pour les convois) et radar géométrique empêchant les collisions (`deadlocks`).
*   **Communication Réseau UDP (V2I) :** Serveur d'écoute intégré dans un `QThread` avec multiplexage `select`. Il réceptionne les trames `JSON` d'urgence en temps réel sans geler l'interface graphique.
*   **Réaction d'Urgence (V2V) :** 
    *   **Anticipation :** Mise au rouge des axes civils 3 secondes avant l'arrivée de l'ambulance.
    *   **Dégagement latéral :** Décalage physique de 20 pixels sur la droite pour les véhicules précédant l'ambulance, permettant un franchissement sécurisé à haute vitesse (250 px/s).

##  Technique

*   **Langage :** Python 3.12+
*   **Interface Graphique :** PySide6 (Qt for Python)
*   **Réseau :** `socket`, `select`, `json` (Librairies standards)
*   **Concurrence :** `QThread`, `Signal`, `threading.Event`

##  Architecture du Projet

```text
SAE-R3.02/
│
├── simulation.py          # Serveur principal (IHM, Moteur 2D, Serveur UDP V2I)
├── client_urgence.py      # Script client (OBU) pour émettre la trame d'alerte UDP
├── donnees_couleurs.py    # Matrices des coordonnées topologiques des trajectoires
├── carrefour_couleurs.svg # Plan vectoriel du carrefour
├── requirements.txt       # Dépendances du projet
└── images/                # Actifs graphiques (horloges, etc.)
