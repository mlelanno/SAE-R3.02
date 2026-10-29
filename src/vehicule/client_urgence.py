import socket
import json

PORT_SERVEUR = 9999


def main():
    try:
        adresse_serveur = input("Adresse IPv4 interne de Carrefour : ").strip()
        socket.inet_pton(socket.AF_INET, adresse_serveur)
        if adresse_serveur == "0.0.0.0":
            raise ValueError("Saisir l'adresse réelle de Carrefour.")
        message = json.dumps({"action": "URGENCE"}).encode("utf-8")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as connexion:
            connexion.settimeout(2)
            connexion.sendto(message, (adresse_serveur, PORT_SERVEUR))
            donnees, adresse = connexion.recvfrom(1024)
            if adresse != (adresse_serveur, PORT_SERVEUR):
                raise ValueError("La réponse ne provient pas du Carrefour demandé.")
            reponse = json.loads(donnees.decode("utf-8"))
            if not isinstance(reponse, dict):
                raise ValueError("La réponse n'est pas un objet JSON.")
            if reponse.get("statut") == "programmee" and "delai" in reponse:
                print("Demande reçue. Véhicule prévu dans", reponse["delai"], "secondes de simulation.")
            elif reponse.get("statut") == "deja_en_cours":
                print("Un véhicule est déjà prévu ou en circulation. Pas de doublon.")
            else:
                raise ValueError("Réponse inconnue du Carrefour.")
    except socket.timeout:
        print("Pas de réponse : vérifier l'adresse interne, le réseau et que la simulation est ouverte.")
        return 1
    except (OSError, ValueError, EOFError) as erreur:
        print("Échange impossible :", erreur)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
