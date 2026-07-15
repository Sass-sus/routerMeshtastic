# Passerelle web Meshtastic pour Raspberry Pi

Ce programme tourne en permanence sur le Raspberry Pi. Il se connecte à un
module Meshtastic (branché en USB, ou accessible en Wi-Fi/TCP), écoute les
messages du réseau maillé, et propose une petite interface web accessible
depuis n'importe quel appareil de votre réseau local. Chaque appareil du
réseau mesh dispose de sa propre conversation (comme une messagerie), en plus
du canal de diffusion générale.

## 1. Prérequis matériel

- Un Raspberry Pi (n'importe quel modèle récent convient).
- Un module Meshtastic (ex: Heltec, T-Beam, RAK...) branché en USB sur le Pi
  **ou** un module accessible sur le réseau Wi-Fi (connexion TCP).

## 2. Installation

```bash
# Copier ce dossier sur le Raspberry Pi, par exemple dans /home/pi/
cd /home/pi/meshtastic-web

# Créer un environnement virtuel Python
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

Si votre module est branché en USB, repérez son port avec :

```bash
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
```

## 3. Lancement manuel (pour tester)

```bash
source venv/bin/activate
export MESHTASTIC_PORT=/dev/ttyUSB0   # adaptez selon votre port, ou laissez vide pour l'auto-détection
python3 app.py
```

Puis ouvrez, depuis un autre appareil connecté au même réseau Wi-Fi/local
que le Pi : `http://<adresse-ip-du-pi>:5000`

Trouvez l'adresse IP du Pi avec `hostname -I`.

### Connexion via Wi-Fi (TCP) plutôt qu'USB

Si votre module Meshtastic est déjà relié au réseau (ex: ESP32 avec Wi-Fi
activé), utilisez :

```bash
export MESHTASTIC_CONNECTION=tcp
export MESHTASTIC_HOST=192.168.1.50   # adresse IP du module
python3 app.py
```

## 4. Lancement permanent au démarrage (systemd)

Pour que le programme tourne en permanence, y compris après un redémarrage
du Raspberry Pi :

```bash
# Adaptez les chemins et l'utilisateur dans le fichier si besoin
sudo cp meshtastic-web.service /etc/systemd/system/

# Ajoutez votre utilisateur au groupe dialout (accès au port série USB)
sudo usermod -aG dialout pi

sudo systemctl daemon-reload
sudo systemctl enable meshtastic-web
sudo systemctl start meshtastic-web
```

Vérifier l'état et les logs :

```bash
sudo systemctl status meshtastic-web
journalctl -u meshtastic-web -f
```

## 5. Fonctionnement de la messagerie

- Chaque appareil détecté sur le réseau mesh apparaît dans la liste de
  gauche, avec son nom Meshtastic.
- Cliquer sur un appareil ouvre son historique de messages, envoyés et
  reçus en messages **directs** (privés) avec cet appareil.
- Le canal **« Diffusion générale »** regroupe les messages envoyés à tout
  le réseau (broadcast), comme dans l'application Meshtastic classique.
- Les messages sont enregistrés dans un fichier `messages.db` (SQLite), donc
  l'historique est conservé même après redémarrage du Pi.
- Les nouveaux messages apparaissent en temps réel, sans recharger la page
  (grâce à Socket.IO).

## 6. Notes et limites

- Un seul appareil Meshtastic connecté au Pi peut être géré à la fois.
- Le fichier `messages.db` grossit avec le temps ; vous pouvez le vider ou
  l'archiver manuellement si besoin.
- Le port 5000 est ouvert sur toutes les interfaces (`0.0.0.0`) : n'exposez
  pas ce service directement sur Internet sans ajouter une authentification.
