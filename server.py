from flask import Flask, jsonify, request
import sqlite3
import json
import os
from datetime import datetime
import requests
import random
from collections import deque

app = Flask(__name__)

# Base de données des villes principales (pour les coordonnées par défaut)
CITIES = {
    "Paris": {"lat": 48.8566, "lon": 2.3522, "radius": 15},
    "Toulouse": {"lat": 43.6045, "lon": 1.4440, "radius": 20},
    "Lyon": {"lat": 45.7640, "lon": 4.8357, "radius": 15},
    "Marseille": {"lat": 43.2965, "lon": 5.3698, "radius": 20},
    "Bordeaux": {"lat": 44.8378, "lon": -0.5792, "radius": 15},
    "Lille": {"lat": 50.6292, "lon": 3.0573, "radius": 10},
    "Nantes": {"lat": 47.2184, "lon": -1.5536, "radius": 15},
    "Strasbourg": {"lat": 48.5734, "lon": 7.7521, "radius": 10},
    "Montpellier": {"lat": 43.6109, "lon": 3.8772, "radius": 10},
    "Nice": {"lat": 43.7102, "lon": 7.2620, "radius": 10},
    "Rennes": {"lat": 48.1173, "lon": -1.6778, "radius": 10},
    "Reims": {"lat": 49.2583, "lon": 4.0317, "radius": 8},
    "Le Havre": {"lat": 49.4944, "lon": 0.1079, "radius": 8},
    "Saint-Étienne": {"lat": 45.4397, "lon": 4.3872, "radius": 8},
    "Toulon": {"lat": 43.1242, "lon": 5.9280, "radius": 8}
}

CHAT_FILE = 'chat_messages.json'

def setup_database_schema():
    """Crée ou met à jour le schéma de la base de données"""
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS supermarkets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            lat REAL,
            lon REAL,
            type TEXT,
            address TEXT,
            status TEXT DEFAULT 'unknown',
            last_verified TEXT,
            notes TEXT,
            city TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def load_chat_messages():
    """Charge les messages de chat depuis le fichier JSON"""
    if os.path.exists(CHAT_FILE):
        try:
            with open(CHAT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('messages', [])
        except:
            return []
    return []

def save_chat_messages(messages):
    """Sauvegarde les messages de chat dans le fichier JSON"""
    # Garder seulement les 100 derniers messages
    messages = messages[-100:] if len(messages) > 100 else messages
    
    with open(CHAT_FILE, 'w', encoding='utf-8') as f:
        json.dump({'messages': messages, 'last_updated': datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

def get_city_coordinates(city_name):
    """Obtient les coordonnées d'une ville avec plusieurs méthodes de fallback"""
    # D'abord vérifier dans notre base de villes connues
    city_normalized = city_name.strip().title()
    
    if city_normalized in CITIES:
        print(f"✅ Ville trouvée dans la base locale: {city_normalized}")
        return CITIES[city_normalized]
    
    # Vérifier dans la base de données si cette ville existe déjà
    try:
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('SELECT lat, lon FROM supermarkets WHERE LOWER(city) = LOWER(?) LIMIT 1', (city_name,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            print(f"✅ Coordonnées trouvées dans la BDD pour: {city_name}")
            return {"lat": result[0], "lon": result[1], "radius": 10}
    except:
        pass
    
    # Essayer plusieurs APIs de géocodage
    coordinates = try_geocoding_apis(city_name)
    if coordinates:
        print(f"✅ Coordonnées trouvées via API pour: {city_name}")
        return coordinates
    
    # Si tout échoue, demander à l'utilisateur ou utiliser une approximation
    print(f"⚠️  Ville inconnue: {city_name}, utilisation des coordonnées par défaut")
    return {"lat": 46.603354, "lon": 1.888334, "radius": 10}  # Centre de la France

def try_geocoding_apis(city_name):
    """Essaie plusieurs APIs de géocodage pour trouver une ville"""
    
    # 1. Nominatim OpenStreetMap (gratuit)
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                'q': f"{city_name}, France",
                'format': 'json',
                'limit': 1,
                'addressdetails': 1
            },
            headers={'User-Agent': 'RescueMap/1.0'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                return {
                    "lat": float(data[0]['lat']),
                    "lon": float(data[0]['lon']),
                    "radius": 10
                }
    except Exception as e:
        print(f"Erreur Nominatim: {e}")
    
    # 2. API du gouvernement français (gratuit)
    try:
        response = requests.get(
            "https://api-adresse.data.gouv.fr/search/",
            params={
                'q': city_name,
                'type': 'municipality',
                'limit': 1
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('features') and len(data['features']) > 0:
                coords = data['features'][0]['geometry']['coordinates']
                return {
                    "lat": coords[1],  # latitude
                    "lon": coords[0],  # longitude
                    "radius": 10
                }
    except Exception as e:
        print(f"Erreur API Gouvernement: {e}")
    
    # 3. Recherche approximative dans les villes françaises connues
    try:
        city_lower = city_name.lower()
        for known_city, coords in CITIES.items():
            if (city_lower in known_city.lower() or 
                known_city.lower() in city_lower or
                city_lower.replace('-', ' ') == known_city.lower() or
                city_lower.replace(' ', '-') == known_city.lower()):
                print(f"🔍 Correspondance approximative: {city_name} -> {known_city}")
                return coords
    except:
        pass
    
    return None

def download_supermarkets_for_city(city_name):
    """Télécharge les supermarchés pour une ville depuis Overpass avec fallback intelligent"""
    city_coords = get_city_coordinates(city_name)
    
    # Si on a de vraies coordonnées, essayer Overpass
    if city_coords["lat"] != 46.603354 or city_coords["lon"] != 1.888334:  # Pas les coords par défaut
        try:
            # Requête Overpass basée sur les coordonnées
            radius = city_coords.get('radius', 10) * 1000  # Convertir en mètres
            
            overpass_query = f"""
            [out:json][timeout:25];
            (
              node["shop"="supermarket"](around:{radius},{city_coords['lat']},{city_coords['lon']});
              node["shop"="mall"](around:{radius},{city_coords['lat']},{city_coords['lon']});
              node["shop"="hypermarket"](around:{radius},{city_coords['lat']},{city_coords['lon']});
              node["shop"="convenience"](around:{int(radius*0.7)},{city_coords['lat']},{city_coords['lon']});
              node["amenity"="marketplace"](around:{int(radius*0.5)},{city_coords['lat']},{city_coords['lon']});
            );
            out center;
            """
            
            print(f"🔍 Recherche Overpass pour {city_name} (rayon: {radius/1000}km)")
            
            response = requests.post(
                "https://overpass-api.de/api/interpreter",
                data=overpass_query,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                elements = data.get('elements', [])
                
                if len(elements) > 0:
                    print(f"✅ {len(elements)} supermarchés trouvés via Overpass pour {city_name}")
                    return elements
                else:
                    print(f"⚠️  Aucun supermarché trouvé via Overpass pour {city_name}, génération d'exemples")
            else:
                print(f"❌ Erreur Overpass HTTP {response.status_code} pour {city_name}")
                
        except Exception as e:
            print(f"❌ Erreur Overpass pour {city_name}: {e}")
    
    # Fallback: générer des données d'exemple
    print(f"🎲 Génération de supermarchés d'exemple pour {city_name}")
    return generate_sample_supermarkets(city_name)

def generate_sample_supermarkets(city_name):
    """Génère des supermarchés d'exemple pour une ville avec des noms réalistes"""
    city_coords = get_city_coordinates(city_name)
    shops = []
    
    # Noms de chaînes françaises réalistes
    shop_chains = {
        "supermarket": ["Carrefour", "Leclerc", "Intermarché", "Super U", "Casino", "Monoprix"],
        "hypermarket": ["Carrefour", "Leclerc", "Auchan", "Géant Casino", "Cora", "Hyper U"],
        "convenience": ["Franprix", "Monop'", "Spar", "Vival", "Proxi", "8 à Huit", "Lidl", "Aldi"]
    }
    
    # Générer entre 15 et 35 magasins selon la taille de la ville
    num_shops = random.randint(15, 35)
    
    for i in range(num_shops):
        # Varier la dispersion selon le type de ville
        if city_name.lower() in ['paris', 'lyon', 'marseille']:
            spread = 0.15  # Grande ville, plus étalé
        elif city_name.lower() in ['toulouse', 'bordeaux', 'lille', 'nantes']:
            spread = 0.10  # Ville moyenne
        else:
            spread = 0.08  # Petite ville, plus concentré
            
        lat = city_coords["lat"] + random.uniform(-spread, spread)
        lon = city_coords["lon"] + random.uniform(-spread, spread)
        
        # Choisir le type de magasin avec des probabilités réalistes
        shop_types = ["supermarket"] * 50 + ["convenience"] * 30 + ["hypermarket"] * 20
        shop_type = random.choice(shop_types)
        
        # Choisir une chaîne appropriée
        chain = random.choice(shop_chains[shop_type])
        
        # Créer des noms réalistes
        if shop_type == "hypermarket":
            shop_name = f"{chain} {city_name}"
        elif shop_type == "convenience":
            area_suffix = random.choice(["Centre", "Gare", "République", "Mairie", "Université", ""])
            shop_name = f"{chain} {city_name} {area_suffix}".strip()
        else:
            district = random.choice(["", "Nord", "Sud", "Est", "Ouest", "Centre", "Gare"])
            shop_name = f"{chain} {city_name} {district}".strip()
        
        shops.append({
            "type": "node",
            "id": i + 10000 + abs(hash(city_name)) % 10000,
            "lat": lat,
            "lon": lon,
            "tags": {"name": shop_name, "shop": shop_type}
        })
    
    print(f"🎯 {len(shops)} supermarchés générés pour {city_name}")
    return shops

def ensure_city_data(city_name):
    """S'assure qu'une ville a des données dans la base"""
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    # Vérifier si la ville a déjà des données
    cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE LOWER(city) = LOWER(?)', (city_name,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"🔄 Chargement des supermarchés pour {city_name}...")
        
        # Télécharger les données
        elements = download_supermarkets_for_city(city_name)
        
        # Insérer dans la base
        inserted = 0
        for element in elements:
            if 'lat' in element and 'lon' in element:
                name = element.get('tags', {}).get('name', f'Magasin {city_name}')
                shop_type = element.get('tags', {}).get('shop', 'unknown')
                
                cursor.execute('''
                    INSERT INTO supermarkets (name, lat, lon, type, city, last_verified)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (name, element['lat'], element['lon'], shop_type, city_name, datetime.now().isoformat()))
                inserted += 1
        
        conn.commit()
        print(f"✅ {inserted} supermarchés chargés pour {city_name}")
    
    conn.close()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>RescueMap - Carte Interactive Multi-Villes</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { margin: 0; padding: 0; font-family: Arial, sans-serif; background: #f5f5f5; }
        #map { height: 100vh; width: 100%; }
        
        .control-panel {
            position: absolute; top: 10px; left: 10px; 
            background: rgba(255, 255, 255, 0.96); padding: 20px; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000;
            max-width: 350px; backdrop-filter: blur(10px);
            border: 1px solid rgba(0,0,0,0.1);
        }
        
        .city-input {
            width: 100%; padding: 12px; margin: 8px 0;
            border: 2px solid #ddd; border-radius: 8px;
            font-size: 16px; transition: border-color 0.3s;
        }
        
        .city-input:focus {
            outline: none; border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
        }
        
        .chat-panel {
            position: absolute; bottom: 10px; right: 10px;
            background: rgba(255, 255, 255, 0.96); border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000;
            width: 350px; height: 400px; display: flex; flex-direction: column;
            border: 1px solid rgba(0,0,0,0.1);
        }
        
        .chat-header {
            padding: 15px; border-bottom: 1px solid #eee;
            background: #007bff; color: white; border-radius: 12px 12px 0 0;
            font-weight: bold;
        }
        
        .chat-messages {
            flex: 1; overflow-y: auto; padding: 10px;
            max-height: 280px;
        }
        
        .chat-input-container {
            padding: 10px; border-top: 1px solid #eee;
            display: flex; gap: 5px;
        }
        
        .chat-input {
            flex: 1; padding: 10px; border: 1px solid #ddd;
            border-radius: 6px; font-size: 14px;
        }
        
        .message {
            margin: 8px 0; padding: 8px 12px; border-radius: 8px;
            background: #f8f9fa; border-left: 3px solid #007bff;
        }
        
        .message-time {
            font-size: 11px; color: #666; margin-top: 4px;
        }
        
        .status-panel {
            position: absolute; top: 10px; right: 380px;
            background: rgba(255, 255, 255, 0.96); padding: 20px; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15); z-index: 1000;
            max-width: 300px; backdrop-filter: blur(10px);
            border: 1px solid rgba(0,0,0,0.1);
        }
        
        .status-safe { color: #28a745; font-weight: bold; }
        .status-danger { color: #dc3545; font-weight: bold; }
        .status-looted { color: #fd7e14; font-weight: bold; }
        .status-unknown { color: #6c757d; font-weight: bold; }
        
        button { 
            margin: 4px; padding: 12px 16px; cursor: pointer; 
            border: none; border-radius: 8px; background: #007bff; color: white;
            font-size: 14px; transition: all 0.3s; font-weight: 500;
        }
        
        button:hover { background: #0056b3; transform: translateY(-1px); }
        button:disabled { background: #6c757d; cursor: not-allowed; transform: none; }
        
        .shop-info { 
            margin: 12px 0; padding: 12px; 
            background: #f8f9fa; border-radius: 8px; border-left: 4px solid #007bff;
        }
        
        .loading { 
            display: inline-block; width: 16px; height: 16px;
            border: 2px solid #f3f3f3; border-top: 2px solid #007bff;
            border-radius: 50%; animation: spin 1s linear infinite;
        }
        
        .suggestions {
            background: white; border: 1px solid #ddd; border-radius: 0 0 8px 8px;
            max-height: 150px; overflow-y: auto; position: absolute;
            width: 100%; z-index: 1001; margin-top: -1px;
        }
        
        .suggestion-item {
            padding: 10px; cursor: pointer; border-bottom: 1px solid #eee;
        }
        
        .suggestion-item:hover {
            background: #f8f9fa;
        }
        
        .city-input-container {
            position: relative;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        @media (max-width: 768px) {
            .control-panel { width: calc(100% - 20px); max-width: none; }
            .chat-panel { width: calc(100% - 20px); height: 300px; }
            .status-panel { position: relative; top: 0; right: 0; margin: 10px; }
        }
    </style>
</head>
<body>
    <div class="control-panel">
        <h3>🏙️ RescueMap Multi-Villes</h3>
        
        <div class="city-input-container">
            <label for="cityInput"><strong>🌍 Entrez une ville:</strong></label>
            <input type="text" id="cityInput" class="city-input" placeholder="Ex: Paris, Lyon, Marseille..." value="Toulouse">
            <div id="suggestions" class="suggestions" style="display: none;"></div>
        </div>
        
        <div style="margin-top: 15px; display: flex; gap: 8px; flex-wrap: wrap;">
            <button onclick="loadCity()" style="background: #28a745;">🔍 Charger la ville</button>
            <button onclick="locateMe()">📍 Me localiser</button>
            <button onclick="refreshSupermarkets()">🔄 Actualiser</button>
            <button onclick="resetCity()" style="background: #dc3545;">🗑️ Reset ville</button>
        </div>
        
        <div class="shop-info">
            <strong>📊 Statistiques:</strong><br>
            <strong>Supermarchés:</strong> <span id="count">0</span><br>
            <strong>Ville active:</strong> <span id="currentCity">Toulouse</span><br>
            <strong>Statut:</strong> <span id="loadStatus">Prêt</span>
        </div>
    </div>
    
    <div class="status-panel">
        <h4>📈 Légende des Statuts</h4>
        <div style="margin: 8px 0;">
            <span class="status-safe">✅ Sûr</span> - Magasin opérationnel<br>
            <span class="status-danger">⚠️ Danger</span> - Zone à risque<br>
            <span class="status-looted">🏚️ Pillé</span> - Magasin pillé<br>
            <span class="status-unknown">❓ Inconnu</span> - Statut non vérifié
        </div>
    </div>
    
    <div class="chat-panel">
        <div class="chat-header">
            💬 Chat de Communication
        </div>
        <div class="chat-messages" id="chatMessages">
            <!-- Messages will be loaded here -->
        </div>
        <div class="chat-input-container">
            <input type="text" id="chatInput" class="chat-input" placeholder="Tapez votre message..." onkeypress="handleChatKeyPress(event)">
            <button onclick="sendMessage()" style="padding: 10px 15px;">📤</button>
        </div>
    </div>
    
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map;
        let userMarker;
        let currentCity = "Toulouse";
        let allMarkers = [];
        
        // Villes suggestions
        const CITY_SUGGESTIONS = [
            "Paris", "Toulouse", "Lyon", "Marseille", "Bordeaux", "Lille", "Nantes", 
            "Strasbourg", "Montpellier", "Nice", "Rennes", "Reims", "Le Havre", 
            "Saint-Étienne", "Toulon", "Grenoble", "Angers", "Dijon", "Brest", 
            "Le Mans", "Amiens", "Tours", "Limoges", "Clermont-Ferrand", "Villeurbanne",
            "Besançon", "Orléans", "Metz", "Rouen", "Mulhouse", "Perpignan", "Caen"
        ];
        
        function initMap() {
            map = L.map('map').setView([43.6045, 1.4440], 13);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            setupCityInput();
            loadSupermarkets();
            loadChatMessages();
        }
        
        function setupCityInput() {
            const input = document.getElementById('cityInput');
            const suggestions = document.getElementById('suggestions');
            
            input.addEventListener('input', function() {
                const value = this.value.toLowerCase();
                if (value.length < 2) {
                    suggestions.style.display = 'none';
                    return;
                }
                
                const matches = CITY_SUGGESTIONS.filter(city => 
                    city.toLowerCase().includes(value)
                ).slice(0, 5);
                
                if (matches.length > 0) {
                    suggestions.innerHTML = matches.map(city => 
                        `<div class="suggestion-item" onclick="selectCity('${city}')">${city}</div>`
                    ).join('');
                    suggestions.style.display = 'block';
                } else {
                    suggestions.style.display = 'none';
                }
            });
            
            input.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    suggestions.style.display = 'none';
                    loadCity();
                }
            });
            
            // Cacher les suggestions quand on clique ailleurs
            document.addEventListener('click', function(e) {
                if (!input.contains(e.target) && !suggestions.contains(e.target)) {
                    suggestions.style.display = 'none';
                }
            });
        }
        
        function selectCity(cityName) {
            document.getElementById('cityInput').value = cityName;
            document.getElementById('suggestions').style.display = 'none';
            loadCity();
        }
        
        async function loadCity() {
            const cityInput = document.getElementById('cityInput').value.trim();
            if (!cityInput) {
                alert('Veuillez entrer un nom de ville');
                return;
            }
            
            currentCity = cityInput;
            document.getElementById('currentCity').textContent = currentCity;
            document.getElementById('loadStatus').innerHTML = '<div class="loading"></div> Chargement de ' + currentCity + '...';
            
            try {
                const response = await fetch('/api/load_city?city=' + encodeURIComponent(currentCity));
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('loadStatus').textContent = `✅ ${result.count} supermarchés trouvés`;
                    
                    // Centrer la carte sur la nouvelle ville
                    if (result.coordinates) {
                        map.setView([result.coordinates.lat, result.coordinates.lon], 13);
                    }
                    
                    loadSupermarkets();
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur: ' + result.error;
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loadStatus').textContent = '❌ Erreur de connexion';
            }
        }
        
        function locateMe() {
            if (navigator.geolocation) {
                document.getElementById('loadStatus').textContent = '📍 Localisation en cours...';
                
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;
                        
                        if (userMarker) map.removeLayer(userMarker);
                        
                        userMarker = L.marker([lat, lng], {
                            icon: L.divIcon({
                                className: 'user-marker',
                                html: '📍',
                                iconSize: [30, 30]
                            })
                        }).addTo(map).bindPopup('🦸 Votre position').openPopup();
                        
                        map.setView([lat, lng], 15);
                        
                        document.getElementById('loadStatus').textContent = '✅ Position trouvée';
                    },
                    (error) => {
                        document.getElementById('loadStatus').textContent = '❌ Géolocalisation impossible';
                    }
                );
            } else {
                alert('Géolocalisation non supportée par votre navigateur');
            }
        }
        
        function clearMarkers() {
            allMarkers.forEach(marker => map.removeLayer(marker));
            allMarkers = [];
        }
        
        function loadSupermarkets() {
            document.getElementById('loadStatus').textContent = '🔄 Chargement des supermarchés...';
            
            fetch('/api/supermarkets?city=' + encodeURIComponent(currentCity))
                .then(response => response.json())
                .then(data => {
                    document.getElementById('count').textContent = data.length;
                    document.getElementById('loadStatus').textContent = `✅ ${data.length} supermarchés chargés`;
                    
                    clearMarkers();
                    
                    data.forEach(shop => {
                        const status = shop.status || 'unknown';
                        let color = '#6c757d';
                        let emoji = '❓';
                        
                        if (status === 'safe') { color = '#28a745'; emoji = '✅'; }
                        if (status === 'danger') { color = '#dc3545'; emoji = '⚠️'; }
                        if (status === 'looted') { color = '#fd7e14'; emoji = '🏚️'; }
                        
                        const marker = L.circleMarker([shop.lat, shop.lon], {
                            radius: 10,
                            fillColor: color,
                            color: '#000',
                            weight: 2,
                            fillOpacity: 0.8
                        }).addTo(map);
                        
                        marker.bindPopup(`
                            <div style="min-width: 250px;">
                                <strong>${emoji} ${shop.name}</strong><br/>
                                <em>Type: ${shop.type || 'inconnu'} | Ville: ${shop.city || currentCity}</em><br/>
                                Statut: <span class="status-${status}">${status}</span><br/>
                                ${shop.last_verified ? '<small>Dernière vérif: ' + new Date(shop.last_verified).toLocaleString() + '</small><br/>' : ''}
                                <div style="margin-top: 12px; text-align: center; display: flex; gap: 6px; justify-content: center; flex-wrap: wrap;">
                                    <button onclick="updateStatus(${shop.id}, 'safe')" style="background: #28a745; font-size: 12px;">✅ Sûr</button>
                                    <button onclick="updateStatus(${shop.id}, 'danger')" style="background: #dc3545; font-size: 12px;">⚠️ Danger</button>
                                    <button onclick="updateStatus(${shop.id}, 'looted')" style="background: #fd7e14; font-size: 12px;">🏚️ Pillé</button>
                                    <button onclick="updateStatus(${shop.id}, 'unknown')" style="background: #6c757d; font-size: 12px;">❓ Reset</button>
                                </div>
                            </div>
                        `);
                        
                        allMarkers.push(marker);
                    });
                })
                .catch(error => {
                    console.error('Error:', error);
                    document.getElementById('loadStatus').textContent = '❌ Erreur de chargement';
                });
        }
        
        function refreshSupermarkets() {
            loadSupermarkets();
        }
        
        async function updateStatus(shopId, status) {
            document.getElementById('loadStatus').textContent = '🔄 Mise à jour du statut...';
            
            try {
                const response = await fetch('/api/update_status', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: shopId, status: status, city: currentCity})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    document.getElementById('loadStatus').textContent = '✅ Statut mis à jour!';
                    setTimeout(loadSupermarkets, 1000);
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur de mise à jour';
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loadStatus').textContent = '❌ Erreur réseau';
            }
        }
        
        async function resetCity() {
            if (!confirm(`Voulez-vous vraiment réinitialiser tous les supermarchés de ${currentCity} ?`)) {
                return;
            }
            
            document.getElementById('loadStatus').innerHTML = '<div class="loading"></div> Réinitialisation...';
            
            try {
                const response = await fetch('/api/reset_city?city=' + encodeURIComponent(currentCity));
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('loadStatus').textContent = '✅ Ville réinitialisée';
                    setTimeout(loadSupermarkets, 1000);
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur de réinitialisation';
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loadStatus').textContent = '❌ Erreur réseau';
            }
        }
        
        // ===== FONCTIONS CHAT =====
        
        function loadChatMessages() {
            fetch('/api/chat/messages')
                .then(response => response.json())
                .then(messages => {
                    displayChatMessages(messages);
                })
                .catch(error => console.error('Erreur chargement chat:', error));
        }
        
        function displayChatMessages(messages) {
            const chatMessages = document.getElementById('chatMessages');
            chatMessages.innerHTML = messages.map(msg => `
                <div class="message">
                    <strong>${msg.user || 'Utilisateur'}:</strong> ${msg.message}
                    <div class="message-time">${new Date(msg.timestamp).toLocaleString()}</div>
                </div>
            `).join('');
            
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        function handleChatKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        async function sendMessage() {
            const input = document.getElementById('chatInput');
            const message = input.value.trim();
            
            if (!message) return;
            
            try {
                const response = await fetch('/api/chat/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        message: message,
                        user: 'Utilisateur',
                        city: currentCity
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    input.value = '';
                    loadChatMessages();
                } else {
                    alert('Erreur envoi message: ' + result.error);
                }
            } catch (error) {
                console.error('Erreur:', error);
                alert('Erreur de connexion');
            }
        }
        
        // Initialisation
        document.addEventListener('DOMContentLoaded', initMap);
        
        // Auto-refresh chat toutes les 30 secondes
        setInterval(loadChatMessages, 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML

@app.route('/api/supermarkets')
def get_supermarkets():
    try:
        city = request.args.get('city', 'Toulouse')
        
        # S'assurer que la ville a des données
        ensure_city_data(city)
        
        conn = sqlite3.connect('rescuemap.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM supermarkets WHERE LOWER(city) = LOWER(?) ORDER BY name', (city,))
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify(results)
    
    except Exception as e:
        print(f"Erreur API supermarkets: {e}")
        return jsonify([])

@app.route('/api/load_city')
def load_city():
    """Charge les données pour une ville spécifique"""
    try:
        city = request.args.get('city', 'Toulouse')
        ensure_city_data(city)
        
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE LOWER(city) = LOWER(?)', (city,))
        count = cursor.fetchone()[0]
        conn.close()
        
        # Obtenir les coordonnées de la ville
        coordinates = get_city_coordinates(city)
        
        return jsonify({
            'success': True, 
            'count': count, 
            'city': city,
            'coordinates': coordinates
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_city')
def reset_city():
    """Réinitialise les données d'une ville"""
    try:
        city = request.args.get('city', 'Toulouse')
        
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM supermarkets WHERE LOWER(city) = LOWER(?)', (city,))
        conn.commit()
        conn.close()
        
        # Recharger les données
        ensure_city_data(city)
        
        return jsonify({'success': True, 'city': city})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_status', methods=['POST'])
def update_status():
    try:
        data = request.get_json()
        shop_id = data.get('id')
        status = data.get('status')
        city = data.get('city', 'Toulouse')
        
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE supermarkets 
            SET status = ?, last_verified = ?
            WHERE id = ? AND LOWER(city) = LOWER(?)
        ''', (status, datetime.now().isoformat(), shop_id, city))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/chat/messages')
def get_chat_messages():
    """Récupère les messages de chat"""
    try:
        messages = load_chat_messages()
        return jsonify(messages)
    except Exception as e:
        return jsonify([])

@app.route('/api/chat/send', methods=['POST'])
def send_chat_message():
    """Envoie un nouveau message de chat"""
    try:
        data = request.get_json()
        message_text = data.get('message', '').strip()
        user = data.get('user', 'Utilisateur')
        city = data.get('city', 'Inconnue')
        
        if not message_text:
            return jsonify({'success': False, 'error': 'Message vide'})
        
        # Charger les messages existants
        messages = load_chat_messages()
        
        # Ajouter le nouveau message
        new_message = {
            'id': len(messages) + 1,
            'user': user,
            'message': message_text,
            'city': city,
            'timestamp': datetime.now().isoformat()
        }
        
        messages.append(new_message)
        
        # Sauvegarder (garde automatiquement les 100 derniers)
        save_chat_messages(messages)
        
        return jsonify({'success': True, 'message_id': new_message['id']})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status')
def api_status():
    """Status de l'API et statistiques"""
    try:
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('SELECT city, COUNT(*) FROM supermarkets GROUP BY city')
        cities_count = cursor.fetchall()
        
        cursor.execute('SELECT status, COUNT(*) FROM supermarkets GROUP BY status')
        status_count = cursor.fetchall()
        
        conn.close()
        
        # Charger les stats du chat
        messages = load_chat_messages()
        
        return jsonify({
            'status': 'online', 
            'cities': dict(cities_count),
            'status_distribution': dict(status_count),
            'chat_messages': len(messages),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)})

if __name__ == '__main__':
    # Initialiser la base de données
    setup_database_schema()
    
    print("🏙️  RescueMap Multi-Villes Amélioré - Chat Intégré")
    print("=" * 55)
    print("🌐 Serveur accessible sur: http://localhost:5000")
    print("📝 Fonctionnalités:")
    print("   • Saisie libre des villes")
    print("   • Chat en temps réel (100 derniers messages)")
    print("   • Sauvegarde automatique des statuts")
    print("   • Géolocalisation utilisateur")
    print("🚀 Prêt pour l'utilisation!")
    
    app.run(host='0.0.0.0', port=5000, debug=True)