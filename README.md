# 🏙️ RescueMap - Carte Interactive de Supermarchés Multi-Villes

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active-success.svg)]()

**RescueMap** est une application web interactive permettant de cartographier et surveiller l'état des supermarchés dans toutes les villes françaises. Conçue pour les situations d'urgence, elle permet aux utilisateurs de partager des informations en temps réel sur l'accessibilité et la sécurité des points de ravitaillement.

## ✨ Fonctionnalités

### 🌍 Gestion Multi-Villes

- **Saisie libre** de n'importe quelle ville française
- **Auto-complétion intelligente** avec base de données étendue
- **Géocodage automatique** via APIs françaises officielles
- **Mémorisation** des villes visitées

### 🏪 Cartographie des Supermarchés

- **Détection automatique** des supermarchés via OpenStreetMap
- **Génération intelligente** de données d'exemple si nécessaire
- **Marqueurs colorés** selon le statut (Sûr/Danger/Pillé)
- **Informations détaillées** par établissement

### 📊 Gestion des Statuts

- **4 états possibles** : Sûr, Danger, Pillé, Inconnu
- **Sauvegarde automatique** en base de données
- **Horodatage** des modifications
- **Interface intuitive** de mise à jour

### 💬 Chat Collaboratif

- **Messages en temps réel** entre utilisateurs
- **Stockage JSON** des 100 derniers messages
- **Auto-rafraîchissement** toutes les 30 secondes
- **Horodatage** et identification des messages

### 📱 Interface Responsive

- **Design moderne** avec animations
- **Compatible mobile** et desktop
- **Géolocalisation utilisateur**
- **Thème sombre/clair** automatique

## 🚀 Installation

### Prérequis

- Python 3.7 ou supérieur
- pip (gestionnaire de paquets Python)
- Connexion Internet (pour les APIs de géocodage)

### Installation rapide

```bash
# 1. Cloner le repository
git clone https://github.com/votre-username/rescuemap.git
cd rescuemap

# 2. Installer les dépendances
pip install flask requests sqlite3

# 3. Lancer l'application
python server.py
```

### Installation complète avec environnement virtuel

```bash
# 1. Créer un environnement virtuel
python -m venv rescuemap_env

# 2. Activer l'environnement
# Sur Windows:
rescuemap_env\Scripts\activate
# Sur Linux/Mac:
source rescuemap_env/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Initialiser la base de données
python reset_database.py

# 5. Lancer le serveur
python server.py
```

### Fichier requirements.txt

```
Flask==2.3.3
requests==2.31.0
```

## 📖 Utilisation

### Démarrage rapide

1. **Lancez l'application** :

   ```bash
   python server.py
   ```

2. **Ouvrez votre navigateur** à l'adresse :

   ```
   http://localhost:5000
   ```

3. **Saisissez une ville** dans le champ de recherche

4. **Cliquez sur "🔍 Charger la ville"**

### Guide utilisateur détaillé

#### 🌍 Sélection d'une ville

1. **Tapez le nom d'une ville** dans le champ de saisie
2. **Utilisez l'auto-complétion** pour sélectionner rapidement
3. **Appuyez sur Entrée** ou cliquez sur "Charger la ville"
4. La carte se centre automatiquement sur la ville sélectionnée

#### 🏪 Consultation des supermarchés

- **Marqueurs colorés** :

  - 🟢 **Vert** : Magasin sûr et opérationnel
  - 🔴 **Rouge** : Zone dangereuse
  - 🟠 **Orange** : Magasin pillé ou fermé
  - ⚪ **Gris** : Statut inconnu

- **Cliquez sur un marqueur** pour voir les détails
- **Informations affichées** : nom, type, statut, dernière vérification

#### 📊 Mise à jour des statuts

1. **Cliquez sur un supermarché** sur la carte
2. **Sélectionnez le nouveau statut** dans la popup :

   - ✅ **Sûr** : Magasin accessible et bien approvisionné
   - ⚠️ **Danger** : Zone à éviter, problèmes de sécurité
   - 🏚️ **Pillé** : Magasin fermé, pillé ou détruit
   - ❓ **Reset** : Remettre à "statut inconnu"

3. Le changement est **automatiquement sauvegardé**

#### 💬 Utilisation du chat

1. **Tapez votre message** dans le champ en bas à droite
2. **Appuyez sur Entrée** ou cliquez sur 📤
3. **Consultez les messages** des autres utilisateurs
4. Les messages sont **automatiquement rafraîchis**

#### 🛠️ Fonctions avancées

- **📍 Me localiser** : Utilise votre GPS pour vous positionner
- **🔄 Actualiser** : Recharge les données de la ville
- **🗑️ Reset ville** : Efface et recharge tous les supermarchés

## 🏗️ Architecture technique

### Structure du projet

```
rescuemap/
├── server.py              # Serveur Flask principal
├── extract_supermarkets.py # Extraction de données OSM
├── reset_database.py      # Réinitialisation BDD
├── sync_manager.py        # Gestionnaire de synchronisation
├── rescuemap.db          # Base de données SQLite
├── chat_messages.json    # Messages du chat
├── requirements.txt      # Dépendances Python
└── README.md            # Cette documentation
```

### Base de données

**Table `supermarkets`** :

```sql
CREATE TABLE supermarkets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,                    -- Nom du supermarché
    lat REAL,                     -- Latitude
    lon REAL,                     -- Longitude
    type TEXT,                    -- Type (supermarket/hypermarket/convenience)
    address TEXT,                 -- Adresse (optionnel)
    status TEXT DEFAULT 'unknown', -- Statut (safe/danger/looted/unknown)
    last_verified TEXT,           -- Timestamp dernière modification
    notes TEXT,                   -- Notes additionnelles
    city TEXT                     -- Ville
);
```

**Fichier `chat_messages.json`** :

```json
{
  "messages": [
    {
      "id": 1,
      "user": "Utilisateur",
      "message": "Le Carrefour de Toulouse est ouvert",
      "city": "Toulouse",
      "timestamp": "2024-01-15T10:30:00"
    }
  ],
  "last_updated": "2024-01-15T10:30:00"
}
```

### APIs REST

| Endpoint             | Méthode | Description                            |
| -------------------- | ------- | -------------------------------------- |
| `/`                  | GET     | Interface web principale               |
| `/api/supermarkets`  | GET     | Liste des supermarchés d'une ville     |
| `/api/load_city`     | GET     | Charge une nouvelle ville              |
| `/api/reset_city`    | GET     | Réinitialise une ville                 |
| `/api/update_status` | POST    | Met à jour le statut d'un supermarché  |
| `/api/chat/messages` | GET     | Récupère les messages du chat          |
| `/api/chat/send`     | POST    | Envoie un nouveau message              |
| `/api/status`        | GET     | Statistiques globales de l'application |

## 🔌 APIs et dépendances

### APIs externes utilisées

1. **OpenStreetMap Overpass API**

   - **URL** : `https://overpass-api.de/api/interpreter`
   - **Usage** : Extraction des supermarchés réels
   - **Limite** : Pas de limite stricte, mais throttling possible
   - **Fallback** : Génération de données d'exemple

2. **Nominatim (OpenStreetMap)**

   - **URL** : `https://nominatim.openstreetmap.org/search`
   - **Usage** : Géocodage des noms de villes
   - **Limite** : 1 requête/seconde recommandé
   - **Headers requis** : `User-Agent: RescueMap/1.0`

3. **API Adresse du Gouvernement Français**
   - **URL** : `https://api-adresse.data.gouv.fr/search/`
   - **Usage** : Géocodage de secours pour les villes françaises
   - **Limite** : Pas de limite
   - **Avantage** : Données officielles françaises

### Dépendances Python

- **Flask 2.3.3** : Framework web
- **requests 2.31.0** : Requêtes HTTP pour les APIs
- **sqlite3** : Base de données (inclus dans Python)
- **json** : Gestion des données JSON (inclus dans Python)
- **datetime** : Gestion des dates (inclus dans Python)

## ⚙️ Configuration

### Variables d'environnement (optionnel)

```bash
# Port du serveur (défaut: 5000)
export RESCUEMAP_PORT=5000

# Host d'écoute (défaut: 0.0.0.0)
export RESCUEMAP_HOST=0.0.0.0

# Mode debug (défaut: True)
export FLASK_DEBUG=True

# Chemin de la base de données (défaut: rescuemap.db)
export DB_PATH=./rescuemap.db
```

### Personnalisation des villes par défaut

Modifiez le dictionnaire `CITIES` dans `server.py` :

```python
CITIES = {
    "Ma Ville": {"lat": 45.1234, "lon": 2.5678, "radius": 10},
    # Ajoutez vos villes...
}
```

### Configuration du chat

Dans `server.py`, modifiez ces constantes :

```python
CHAT_FILE = 'chat_messages.json'  # Fichier des messages
MAX_MESSAGES = 100                # Nombre max de messages conservés
CHAT_REFRESH_INTERVAL = 30000     # Intervalle de rafraîchissement (ms)
```

## 🔧 Développement

### Lancement en mode développement

```bash
# Avec reload automatique
export FLASK_ENV=development
python server.py

# Ou directement
python -c "from server import app; app.run(debug=True, host='0.0.0.0', port=5000)"
```

### Scripts utiles

**Réinitialiser la base de données** :

```bash
python reset_database.py
```

**Extraire des supermarchés pour une ville** :

```bash
python extract_supermarkets.py
```

**Tester les APIs** :

```bash
# Test de l'API status
curl http://localhost:5000/api/status

# Test de l'API supermarchés
curl "http://localhost:5000/api/supermarkets?city=Toulouse"
```

### Structure du code

#### `server.py` - Serveur principal

- Configuration Flask
- Routes API
- Gestion des villes et géocodage
- Système de chat
- Interface web

#### `extract_supermarkets.py` - Extraction de données

- Interface en ligne de commande
- Téléchargement depuis Overpass
- Gestion multi-villes
- Génération de données d'exemple

#### `reset_database.py` - Utilitaire de réinitialisation

- Suppression de l'ancienne BDD
- Création du nouveau schéma
- Réinitialisation propre
