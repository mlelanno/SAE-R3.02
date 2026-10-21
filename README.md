# Simulateur de carrefour V2I / V2V SAÉ 3.02

**Un carrefour connecté, deux VM et une ambulance déclenchée à distance.**

Ce projet simule le trafic au carrefour Poudrière / Riquewihr / Ingersheim, à Colmar. Développé en Python avec PySide6, il permet d'observer le passage d'un véhicule d'urgence avec ou sans optimisation des feux et d'enregistrer ses temps de trajet dans SQLite.

La **VM Carrefour** affiche la simulation et reçoit les alertes. La **VM Véhicule** envoie une demande d'urgence par UDP. La communication **V2I** (*Vehicle-to-Infrastructure*) fonctionne entre les deux VM ; la réaction des voitures civiles, inspirée du **V2V** (*Vehicle-to-Vehicle*), est calculée localement dans la simulation.

## Fonctionnalités

| Fonction | Comportement dans le projet |
| --- | --- |
| Carrefour en 2D | Plan SVG affiché dans une `QGraphicsScene`, avec adaptation de la vue à la fenêtre. |
| Trafic routier | 12 trajectoires construites avec `QPainterPath`, comprenant des courbes de Bézier et une rotation des véhicules selon leur direction. |
| Feux tricolores | Gestion de deux axes, de transitions orange / rouge et de phases de convois pour les virages. |
| Espacement des véhicules | Vérification géométrique des formes et des marges avant les déplacements et les apparitions. |
| Trois niveaux de trafic | Dense, moyen et faible, sélectionnables dans l'interface. |
| Alerte à distance | Envoi d'une trame JSON par le client de la VM Véhicule vers la VM Carrefour. |
| Réception en parallèle | Écoute UDP dans un `QThread` ; transmission des messages à l'interface par signaux Qt. |
| Gestion de l'urgence | Programmation d'une ambulance, anticipation des feux en mode optimisé et dégagement latéral des voitures qui la précèdent. |
| Sauvegarde des essais | Un enregistrement SQLite à la fin de chaque trajet complet de l'ambulance. |

**L'ambulance apparaît uniquement après une demande du client.** Ouvrir la simulation ou choisir « Avec optimisation » / « Sans optimisation » ne déclenche pas d'urgence. Un changement de mode réinitialise la scène et annule une éventuelle urgence en attente ou en circulation.

## Architecture sur deux VM

![Déploiement du projet sur les deux VM](docs/uml/deploiement.png)

| | VM Carrefour | VM Véhicule |
| --- | --- | --- |
| Système prévu | Debian 13 avec bureau graphique | Debian 13 |
| Rôle | Interface, moteur de simulation, serveur UDP et SQLite | Client d'alerte UDP |
| Adresse sur le réseau interne | `192.168.50.10/24` | `192.168.50.20/24` |
| Mémoire conseillée | **4 Go de RAM** | **4 Go de RAM** |
| Carte réseau 1 | NAT, adresse obtenue par DHCP | NAT, adresse obtenue par DHCP |
| Carte réseau 2 | Réseau interne VirtualBox `SAE302`, adresse fixe | Réseau interne VirtualBox `SAE302`, adresse fixe |
| Fichiers nécessaires | Simulation, données, SVG, images et dépendances | `client_urgence.py` uniquement |

Les deux cartes internes doivent appartenir au même réseau `SAE302`. Le NAT sert aux téléchargements ; les échanges entre les VM utilisent la seconde carte. Le serveur écoute par défaut sur **`192.168.50.10:9999` en UDP**.

## Technologies

| Élément | Utilisation |
| --- | --- |
| Python | Cible d'installation : Debian 13 et son [Python 3.13](https://packages.debian.org/trixie/python3). |
| PySide6 `6.11.2` | Interface Qt, scène graphique, SVG, temporisateur et signaux. Version fixée dans `requirements.txt`. |
| `socket`, `select`, `json` | Échange UDP et traitement des messages JSON. |
| `QThread`, `Signal`, `Slot` | Réception réseau en parallèle et transmission au fil principal. |
| `sqlite3` | Conservation locale des résultats, sans serveur de base de données. |
| VirtualBox | Déploiement des deux VM de démonstration. |

Le client utilise uniquement la bibliothèque standard de Python. PySide6 est nécessaire sur la VM Carrefour.

## Installation et lancement

Le [guide d'installation Debian 13 / VirtualBox](GUIDE_DEBIAN13_VIRTUALBOX.md) détaille la préparation des VM, les deux cartes réseau, le fichier `/etc/network/interfaces` et les dépendances système. Les commandes ci-dessous s'exécutent **dans le dossier contenant les fichiers du projet**, avec l'utilisateur habituel.

### 1. Préparer Python sur Carrefour - une seule fois

Après installation de `python3-venv` et des dépendances système indiquées dans le guide :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Démarrer Carrefour

Après chaque redémarrage, ouvrir un terminal dans le dossier du projet :

```bash
source .venv/bin/activate
python simulation.py
```

La fenêtre démarre en mode optimisé. Choisir le niveau de trafic et le mode souhaités **avant** d'envoyer la demande.

### 3. Envoyer l'urgence depuis Véhicule

Ouvrir un terminal dans le dossier contenant `client_urgence.py` :

```bash
python3 client_urgence.py
```

Le client affiche la réponse reçue puis se termine. Il peut être relancé pour un autre essai lorsque le trajet précédent est terminé.

### Autres lancements disponibles

| Commande sur Carrefour | Mode initial | Port UDP |
| --- | --- | --- |
| `python simulation.py` | Avec optimisation | `9999` |
| `python simulation_opti.py` | Avec optimisation | `9999` |
| `python simulation_sans_opti.py` | Sans optimisation | `9998` |

Pour joindre l'instance sur le port `9998`, lancer sur Véhicule :

```bash
python3 client_urgence.py 9998
```

Les boutons de mode changent le comportement de l'instance ouverte, **sans changer son port**. L'adresse et le port peuvent aussi être renseignés explicitement :

```bash
python simulation.py --ecoute 192.168.50.10 --port 9999
```

```bash
python3 client_urgence.py --serveur 192.168.50.10 --port 9999
```

Pour un essai sur une seule machine, utiliser `127.0.0.1` dans les deux commandes à la place de `192.168.50.10`.

## Déroulement d'un essai

1. Lancer la simulation, choisir le trafic et le mode d'optimisation.
2. Lancer le client sur la VM Véhicule : il envoie une demande d'urgence.
3. Carrefour programme l'apparition de l'ambulance **20 secondes de simulation** plus tard. Si son point d'entrée est occupé, elle attend qu'une place se libère.
4. En mode optimisé, la préparation des feux commence **10 secondes avant l'apparition prévue**. Les transitions et le dégagement du carrefour restent pris en compte.
5. L'ambulance suit le **trajet 11, du sud vers le nord**. Les voitures juste devant elle se rangent à droite lorsque l'espace le permet.
6. À la fin du trajet complet A → B, la durée est affichée et enregistrée dans `resultats.db`.

| Paramètre du code | Valeur actuelle | Signification |
| --- | --- | --- |
| `PAS` | `0.03` s | Temps de simulation ajouté à chaque mise à jour ; temporisateur demandé à 30 ms. |
| `DELAI_URGENCE` | `20` s | Délai simulé entre la demande acceptée et l'apparition prévue. |
| `ANTICIPATION` | `10` s | Préparation des feux avant cette apparition, en mode optimisé. |
| `VITESSE` | `100` unités/s | Vitesse nominale des voitures civiles. |
| `FACTEUR_URGENCE` | `1.67` | Vitesse nominale de l'ambulance : **167 unités/s**. |
| `DECALAGE_DROITE` | `20` unités | Dégagement latéral des voitures concernées. |
| `DUREE_DECALAGE_SANS_OPTI` | `3` s | Délai de réaction avant le dégagement en mode non optimisé. |
| `FREQUENCES` | `2`, `4`, `8` s | Intervalles nominaux de génération pour le trafic dense, moyen, faible. |

Les distances sont exprimées dans le repère du dessin. Les durées affichées sont calculées par le moteur de simulation : elles ne représentent pas une mesure de temps routier réel. Le gain entre les modes dépend de l'anticipation des feux **et** du délai de réaction des voitures.

## Communication UDP et multithreading

Le client envoie un objet JSON encodé en UTF-8 :

```json
{"action": "URGENCE"}
```

Si la demande est acceptée, le serveur répond :

```json
{"statut": "programmee", "delai": 20}
```

Si une urgence est déjà en attente ou en circulation, aucun doublon n'est créé :

```json
{"statut": "deja_en_cours", "delai": 20}
```

Dans cette seconde réponse, `delai` conserve la constante `20` ; ce n'est pas le temps restant. Le client attend une réponse pendant **2 secondes**, puis signale une absence de réponse si nécessaire. Les datagrammes mal encodés ou non conformes à un objet JSON sont ignorés ; une action inconnue ne reçoit pas de réponse.

`ReceptionReseau.run()` attend les datagrammes avec `select`, les décode et émet `message_recu`. Le slot `Simulation.recevoir_message()` est exécuté dans le fil principal grâce à une connexion Qt en file d'attente. Ce fil traite la demande et envoie la réponse UDP ; il conserve aussi l'animation, pilotée par `QTimer`, et les écritures SQLite. Le thread réseau ne modifie pas l'interface. Voir la [documentation de QThread](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html).

À la fermeture, la simulation arrête son temporisateur, demande l'interruption du thread réseau, attend sa fin puis ferme le socket.

## Sauvegarde et consultation des résultats

`resultats.db` est créé automatiquement **à côté de `simulation.py`**. La table `essais` reçoit une ligne par trajet d'urgence terminé. Une demande acceptée ou un trajet interrompu ne suffit pas à créer un résultat.

| Colonne | Contenu |
| --- | --- |
| `id` | Identifiant de l'essai. |
| `date_heure` | Date et heure de l'enregistrement au format ISO, avec décalage horaire. |
| `trafic_initial` / `trafic_final` | Niveaux de trafic au début du scénario et à la fin du trajet. |
| `optimisation` | `1` avec optimisation, `0` sans optimisation. |
| `duree_s` | Durée simulée entre l'apparition effective et la fin du trajet A → B. |
| `scenario_modifie` | Indicateur de modification du scénario (`0` ou `1`). |
| `parametres_json` | Paramètres utilisés : pas, vitesses, délais, fréquences, phases et trajet d'urgence. |

Pour afficher les dix derniers résultats, depuis le dossier de Carrefour :

```bash
python3 voir_resultats.py
```

Ce script consulte la base en lecture seule. Les données restent disponibles après fermeture de la simulation et redémarrage de la VM.

**Particularité de cette version :** une demande manuelle du client positionne `scenario_modifie` à `1`. Le résultat est bien sauvegardé, mais n'alimente pas le comparatif « standard » conservé en mémoire par l'interface. Pour comparer des essais, consulter SQLite et conserver les mêmes conditions de trafic et de déclenchement.

## Organisation du projet

```text
Simulation_Colmar_Urgence_2VM/
├── README.md                       # Présentation et utilisation
├── Fiche_Installation              # Fiche d'installation
├── simulation.py                   # Interface, moteur, réseau et stockage
├── simulation_opti.py              # Démarrage optimisé, port 9999
├── simulation_sans_opti.py         # Démarrage sans optimisation, port 9998
├── client_urgence.py               # Client UDP pour la VM Véhicule
├── voir_resultats.py               # Consultation des dix derniers essais
├── donnees_couleurs.py             # Données des trajectoires
├── carrefour_couleurs.svg          # Plan vectoriel du carrefour
├── extraire_svg_sql.py             # Outil optionnel d'extraction du SVG
├── GUIDE_DEBIAN13_VIRTUALBOX.md    # Installation des deux VM
├── images/                         # Images d'horloge selon le trafic
└── docs/
    └── uml/                       # Sources Mermaid, SVG et PNG
```

`resultats.db` est un fichier généré pendant l'utilisation. L'outil optionnel `extraire_svg_sql.py` produit une autre base, `carrefour.db`, pour les données extraites du SVG : la simulation principale utilise `donnees_couleurs.py` et n'a pas besoin de cette base d'extraction.

## UML du projet

![Diagramme de classes du projet](docs/uml/classes.png)

## Périmètre du prototype

Le projet démontre la réception d'une alerte V2I, la réaction du trafic simulé, l'écoute réseau dans un thread et la persistance des résultats. Les voitures civiles n'échangent pas de messages réseau entre elles. Le client ne transmet ni position GPS ni estimation d'arrivée ; le délai d'apparition est fixé dans le code. UDP ne fournit pas de garantie de livraison et le protocole actuel ne comporte pas d'authentification.

Les contrôles géométriques et les règles de circulation servent la démonstration du carrefour. Ils ne constituent pas une validation d'un système de gestion de trafic réel.
