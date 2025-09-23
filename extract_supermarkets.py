# extract_supermarkets.py
import requests
import sqlite3
import json
import random

# Base de données des villes principales avec leurs coordonnées
CITIES = {
    "Paris": {"lat": 48.8566, "lon": 2.3522, "radius": 15000},
    "Toulouse": {"lat": 43.6045, "lon": 1.4440, "radius": 20000},
    "Lyon": {"lat": 45.7640, "lon": 4.8357, "radius": 15000},
    "Marseille": {"lat": 43.2965, "lon": 5.3698, "radius": 20000},
    "Bordeaux": {"lat": 44.8378, "lon": -0.5792, "radius": 15000},
    "Lille": {"lat": 50.6292, "lon": 3.0573, "radius": 10000},
    "Nantes": {"lat": 47.2184, "lon": -1.5536, "radius": 15000},
    "Strasbourg": {"lat": 48.5734, "lon": 7.7521, "radius": 10000},
    "Montpellier": {"lat": 43.6109, "lon": 3.8772, "radius": 10000},
    "Nice": {"lat": 43.7102, "lon": 7.2620, "radius": 10000}
}

def setup_database_schema():
    """Crée ou met à jour le schéma de la base de données"""
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    # Vérifier si la table existe et sa structure
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supermarkets (
            id INTEGER PRIMARY KEY,
            name TEXT,
            lat REAL,
            lon REAL,
            type TEXT,
            address TEXT,
            status TEXT DEFAULT 'unknown',
            last_verified TEXT,
            notes TEXT,
            city TEXT DEFAULT 'Toulouse'
        )
    ''')
    
    # Vérifier si la colonne 'city' existe, sinon l'ajouter
    try:
        cursor.execute('SELECT city FROM supermarkets LIMIT 1')
    except sqlite3.OperationalError:
        print("🔄 Ajout de la colonne 'city' à la table...")
        cursor.execute('ALTER TABLE supermarkets ADD COLUMN city TEXT DEFAULT "Toulouse"')
    
    conn.commit()
    conn.close()
    print("✅ Schéma de base de données vérifié")

def download_supermarkets(city_name):
    """Télécharge les supermarchés pour une ville spécifique"""
    
    if city_name not in CITIES:
        print(f"❌ Ville non supportée: {city_name}")
        return create_sample_data(city_name)
    
    overpass_query = f"""
    [out:json];
    area["name"="{city_name}"]->.searchArea;
    (
      node["shop"="supermarket"](area.searchArea);
      node["shop"="mall"](area.searchArea);
      node["shop"="hypermarket"](area.searchArea);
      node["shop"="convenience"](area.searchArea);
      node["amenity"="marketplace"](area.searchArea);
    );
    out center;
    """
    
    try:
        print(f"📡 Téléchargement des supermarchés à {city_name}...")
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        print(f"✅ {len(data['elements'])} supermarchés trouvés à {city_name}")
        return data
    except Exception as e:
        print(f"❌ Erreur Overpass pour {city_name}: {e}")
        return create_sample_data(city_name)

def create_sample_data(city_name):
    """Crée des données d'exemple pour une ville"""
    if city_name not in CITIES:
        city_name = "Toulouse"  # Fallback
    
    city_data = CITIES[city_name]
    
    # Génère des points aléatoires autour de la ville
    shops = []
    
    shop_names = ["Carrefour", "Leclerc", "Auchan", "Intermarché", "Super U", 
                  "Casino", "Monoprix", "Lidl", "Aldi", "Franprix"]
    
    for i in range(30):
        # Génère des coordonnées aléatoires dans un rayon de 0.1 degré (~11km)
        lat = city_data["lat"] + random.uniform(-0.1, 0.1)
        lon = city_data["lon"] + random.uniform(-0.1, 0.1)
        
        shop_name = f"{random.choice(shop_names)} {city_name}"
        shop_type = random.choice(["supermarket", "hypermarket", "convenience"])
        
        shops.append({
            "id": i + 1,
            "lat": lat,
            "lon": lon,
            "name": shop_name,
            "shop": shop_type
        })
    
    return {
        "elements": [
            {
                "type": "node",
                "id": shop["id"],
                "lat": shop["lat"],
                "lon": shop["lon"],
                "tags": {"name": shop["name"], "shop": shop["shop"]}
            }
            for shop in shops
        ]
    }

def setup_database_for_city(city_name):
    """Initialise la base de données pour une ville spécifique"""
    setup_database_schema()  # S'assurer que le schéma est à jour
    
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    # Vérifier si des données existent pour cette ville
    cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE city = ?', (city_name,))
    existing_count = cursor.fetchone()[0]
    
    if existing_count > 0:
        print(f"🗑️  Suppression des {existing_count} anciens supermarchés de {city_name}...")
        cursor.execute('DELETE FROM supermarkets WHERE city = ?', (city_name,))
    
    # Récupérer les données pour la ville
    data = download_supermarkets(city_name)
    
    # Insérer les données
    inserted_count = 0
    for element in data['elements']:
        if 'lat' in element and 'lon' in element:
            name = element['tags'].get('name', f'Magasin {city_name}')
            shop_type = element['tags'].get('shop', 'unknown')
            
            cursor.execute('''
                INSERT INTO supermarkets (name, lat, lon, type, city)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, element['lat'], element['lon'], shop_type, city_name))
            inserted_count += 1
    
    conn.commit()
    conn.close()
    print(f"✅ {inserted_count} supermarchés ajoutés pour {city_name}")

def get_available_cities():
    """Retourne la liste des villes disponibles"""
    return list(CITIES.keys())

def show_database_status():
    """Affiche le statut actuel de la base de données"""
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT city, COUNT(*) FROM supermarkets GROUP BY city')
        cities_data = cursor.fetchall()
        
        if cities_data:
            print("\n📊 Statut actuel de la base de données:")
            for city, count in cities_data:
                print(f"   {city}: {count} supermarchés")
        else:
            print("ℹ️  Aucune donnée dans la base")
            
    except Exception as e:
        print(f"❌ Erreur lecture base: {e}")
    
    conn.close()

if __name__ == '__main__':
    print("🏙️  Système de gestion multi-villes")
    print("=" * 40)
    
    # Vérifier le schéma d'abord
    setup_database_schema()
    
    available_cities = get_available_cities()
    print("Villes disponibles:")
    for i, city in enumerate(available_cities, 1):
        print(f"{i}. {city}")
    
    # Afficher le statut actuel
    show_database_status()
    
    try:
        choice = input("\nChoisissez une ville (numéro ou nom): ").strip()
        
        if choice.isdigit():
            index = int(choice) - 1
            if 0 <= index < len(available_cities):
                selected_city = available_cities[index]
            else:
                selected_city = "Toulouse"
        else:
            selected_city = choice if choice in available_cities else "Toulouse"
        
        print(f"\n🛒 Extraction des supermarchés à {selected_city}...")
        setup_database_for_city(selected_city)
        
        # Vérification finale
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE city = ?', (selected_city,))
        total = cursor.fetchone()[0]
        conn.close()
        
        city_data = CITIES[selected_city]
        print(f"🎯 {total} supermarchés chargés pour {selected_city}")
        print(f"📍 Coordonnées: {city_data['lat']}, {city_data['lon']}")
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        print("🔄 Utilisation de Toulouse par défaut...")
        setup_database_for_city("Toulouse")
    
    # Afficher le statut final
    show_database_status()