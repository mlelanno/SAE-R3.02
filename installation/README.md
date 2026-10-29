<div align="center">

# Installer la maquette

**Deux VM Debian 13 · VirtualBox · 4 Go de RAM conseillés par VM**

[Accueil du projet](../README.md) · [Fiche PDF](Fiche_installation.pdf) · [Fiche Word modifiable](Fiche_installation.docx)

</div>

Cette notice décrit l’installation de la version fournie dans le dossier [ZIP](../ZIP/). Carrefour exécute la simulation graphique ; Véhicule envoie les demandes d’urgence.

**Choisir la méthode :** [VM déjà préparées avec les OVA](#1-utiliser-les-ova) ou [installation manuelle avec les ZIP](#2-installer-avec-les-zip).

## Avant de commencer

Prévoir deux VM sous **Debian 13**, avec un environnement graphique pour Carrefour. Nous conseillons **4 Go de RAM pour chaque VM**.

Dans VirtualBox, chaque VM dispose de deux cartes :

| Carte | Mode | Utilisation |
|---|---|---|
| Carte 1 | NAT | Accès à Internet pour l’installation des paquets |
| Carte 2 | Réseau interne nommé **SAE** | Communication entre Carrefour et Véhicule |

Activer « Câble branché » pour les deux cartes et utiliser le même nom de réseau interne sur les deux VM.

**Sur Proxmox, ne pas réaliser l’étape 2A de configuration réseau, sur aucune des deux VM.** Conserver la configuration réseau fournie et passer directement à [l’installation des dépendances sur Carrefour](#2b-installer-les-dépendances-sur-carrefour), puis au lancement du client sur Véhicule. Ne pas modifier `/etc/network/interfaces`, désactiver NetworkManager ou appliquer les adresses d’exemple de cette notice.

Si les adresses sont déjà fournies par l’organisateur dans un autre environnement, conserver également cette configuration et passer l’étape 2A. Les noms `enp0s3` et `enp0s8` sont ceux de notre exemple VirtualBox ; vérifier les noms réels avec `ip -br address`.

## 1 Utiliser les OVA

Les images OVA sont hébergées sur votre Google Drive. La [fiche PDF](Fiche_installation.pdf) est le support prévu pour leurs liens. Pour une installation immédiate, utiliser la [méthode avec les ZIP](#2-installer-avec-les-zip).

Une fois les OVA récupérés, les importer dans VirtualBox et vérifier les deux cartes réseau avant de démarrer les VM.

### Sur la VM Carrefour

Dans **Documents**, ouvrir le dossier qui contient `simulation.py`, puis ouvrir un terminal dans ce dossier.

```bash
source .venv/bin/activate
python3 simulation.py
```

Choisir le trafic et le mode de fonctionnement. Lancer une seule fenêtre de simulation à la fois.

### Sur la VM Véhicule

Dans **Documents**, ouvrir le dossier contenant le **client de la version fournie dans ce dépôt**, puis ouvrir un terminal dans ce dossier.

```bash
python3 client_urgence.py
```

Saisir l’IP interne de Carrefour lorsqu’elle est demandée. Le client utilise automatiquement le port **9999**.

Les OVA ne sont pas modifiés par ce dépôt. S’ils contiennent une ancienne version, remplacer les fichiers du projet par ceux des ZIP avant d’utiliser cette notice. Conserver l’environnement `.venv` existant et l’historique `resultats.db` si nécessaire.

## 2 Installer avec les ZIP

Télécharger les deux archives, puis les décompresser chacune dans la VM correspondante :

| Machine | Archive | Dossier obtenu |
|---|---|---|
| Carrefour | [VM_Carrefour.zip](../ZIP/VM_Carrefour.zip?raw=1) | `carrefour` |
| Véhicule | [VM_Vehicule.zip](../ZIP/VM_Vehicule.zip?raw=1) | `vehicule` |

Les ZIP du dépôt sont ceux de la version décrite ici. Les liens ZIP de l’ancienne fiche PDF peuvent désigner une version antérieure : utiliser les liens du tableau ci-dessus.

### 2A Configurer le réseau uniquement sur VirtualBox

**Cette partie n’est pas à faire sur Proxmox, ni sur Carrefour ni sur Véhicule.** Dans ce cas, passer directement à [l’étape 2B](#2b-installer-les-dépendances-sur-carrefour).

Cette étape concerne seulement vos propres VM VirtualBox lorsque les adresses ne sont pas déjà imposées. L’exemple utilise `192.168.50.10` pour Carrefour et `192.168.50.20` pour Véhicule, avec le masque `255.255.255.0`.

Sur chaque VM, ouvrir un terminal et passer en administrateur :

```bash
su -
nano /etc/network/interfaces
```

**Sur Carrefour**, utiliser cette configuration :

```text
auto lo
iface lo inet loopback

auto enp0s3
iface enp0s3 inet dhcp

auto enp0s8
iface enp0s8 inet static
    address 192.168.50.10
    netmask 255.255.255.0
```

**Sur Véhicule**, utiliser cette configuration :

```text
auto lo
iface lo inet loopback

auto enp0s3
iface enp0s3 inet dhcp

auto enp0s8
iface enp0s8 inet static
    address 192.168.50.20
    netmask 255.255.255.0
```

Enregistrer avec **Ctrl + O**, valider avec **Entrée**, puis quitter avec **Ctrl + X**.

Sur chaque VM, appliquer la configuration depuis sa console locale :

```bash
systemctl disable --now NetworkManager
systemctl restart networking
ip -br address
exit
```

La première commande arrête NetworkManager et désactive son démarrage automatique. La configuration est ensuite prise en charge par `/etc/network/interfaces`. La carte interne utilise une adresse statique ; elle n’a pas besoin d’un serveur DHCP.

### 2B Installer les dépendances sur Carrefour

Dans un terminal de la VM Carrefour :

```bash
su -
apt update
apt install python3-venv
apt install libxcb-cursor0
exit
```

Ouvrir ensuite un terminal dans le dossier `carrefour`, celui qui contient `simulation.py` et `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 simulation.py
```

Le fichier `requirements.txt` fixe **PySide6==6.11.2**. L’installation et le lancement de l’environnement Python se font avec l’utilisateur habituel, après avoir quitté le compte root.

### 2C Lancer le client sur Véhicule

Le client utilise uniquement des modules intégrés à Python. Il n’a pas besoin de PySide6 ni d’un environnement virtuel.

Ouvrir un terminal dans le dossier `vehicule` :

```bash
python3 client_urgence.py
```

Au message **« Adresse IPv4 interne de Carrefour »**, saisir seulement l’adresse de Carrefour. Dans notre exemple :

```text
192.168.50.10
```

Si l’adresse a été attribuée par l’organisateur, relever la véritable IPv4 de la carte interne sur Carrefour :

```bash
ip -br address
```

Ne pas recopier le suffixe `/24` et ne pas prendre l’adresse de la carte NAT. L’adresse de la VM Véhicule n’est pas demandée : Carrefour répond directement à l’expéditeur.

## 3 Vérifier le fonctionnement

1. Sur Carrefour, choisir le trafic puis **Avec optimisation** ou **Sans optimisation**.
2. Sur Véhicule, lancer le client et saisir la bonne IP interne.
3. Vérifier que le client affiche **« Demande reçue »** et qu’une urgence est programmée sur Carrefour.
4. Laisser l’ambulance terminer son trajet pour que le résultat soit enregistré.

Le choix d’un mode ne crée pas d’ambulance. Une seconde demande pendant une urgence déjà prévue ou en circulation est refusée pour éviter un doublon.

Après un parcours terminé, consulter la base dans le dossier Carrefour :

```bash
python3 -m sqlite3 resultats.db
```

Puis saisir cette requête :

```sql
SELECT id, trafic_initial, optimisation, duree_s
FROM essais
ORDER BY id DESC
LIMIT 5;
```

La colonne `optimisation` vaut `1` avec optimisation et `0` sans optimisation. Pour quitter la console SQLite, saisir `.quit`.

## 4 Comprendre les fichiers

| Élément | Rôle |
|---|---|
| `simulation.py` | Interface, circulation, feux et serveur UDP |
| `client_urgence.py` | Demande d’urgence depuis la VM Véhicule |
| `carrefour_couleurs.svg` | Plan affiché et repères géométriques |
| `extraire_svg_sql.py` | Extraction des repères du SVG vers SQLite |
| `carrefour.db` | Trajectoires chargées au démarrage, base déjà fournie |
| `resultats.db` | Historique des trajets terminés, créé à l’utilisation |
| `images/` | Ressources graphiques utilisées par la simulation |

Après une modification des trajectoires dans le SVG, fermer la simulation puis relancer l’extraction dans le dossier Carrefour :

```bash
source .venv/bin/activate
python3 extraire_svg_sql.py
python3 simulation.py
```

L’extracteur actualise `carrefour.db` et ne remplace pas `resultats.db`. Le fichier `donnees_couleurs.py` n’est plus utilisé dans cette version.

## En cas de problème

| Symptôme | Vérification |
|---|---|
| Le client ne reçoit pas de réponse | Simulation ouverte, bonne IP interne, même réseau interne et port UDP 9999 accessible |
| `apt update` ne résout pas les noms Debian | Carte NAT activée, adresse IP et route Internet présentes |
| Le fichier Python est introuvable | Terminal ouvert dans le dossier qui contient le fichier |
| `PySide6` est introuvable | Environnement `.venv` activé et dépendances installées |
| La base est en lecture seule | Dossier du projet et `resultats.db` accessibles à l’utilisateur qui lance la simulation |

[Retour à l’accueil](../README.md)
