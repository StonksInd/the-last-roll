from flask import Flask, jsonify, request
import sqlite3
import json
from datetime import datetime
import requests
import random

app = Flask(__name__)

# Base de données des villes
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
    "Nice": {"lat": 43.7102, "lon": 7.2620, "radius": 10}
}

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

def download_supermarkets_for_city(city_name):
    """Télécharge les supermarchés pour une ville depuis Overpass"""
    if city_name not in CITIES:
        return generate_sample_supermarkets(city_name)
    
    try:
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
        
        response = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=overpass_query,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('elements', [])
        else:
            return generate_sample_supermarkets(city_name)
            
    except:
        return generate_sample_supermarkets(city_name)

def generate_sample_supermarkets(city_name):
    """Génère des supermarchés d'exemple pour une ville"""
    if city_name not in CITIES:
        city_name = "Toulouse"
    
    city_data = CITIES[city_name]
    shops = []
    
    shop_names = ["Carrefour", "Leclerc", "Auchan", "Intermarché", "Super U", 
                  "Casino", "Monoprix", "Lidl", "Aldi", "Franprix", "Hyper U"]
    
    for i in range(25):
        lat = city_data["lat"] + random.uniform(-0.08, 0.08)
        lon = city_data["lon"] + random.uniform(-0.08, 0.08)
        
        shop_name = f"{random.choice(shop_names)} {city_name}"
        shop_type = random.choice(["supermarket", "hypermarket", "convenience"])
        
        shops.append({
            "type": "node",
            "id": i + 1,
            "lat": lat,
            "lon": lon,
            "tags": {"name": shop_name, "shop": shop_type}
        })
    
    return shops

def ensure_city_data(city_name):
    """S'assure qu'une ville a des données dans la base"""
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    # Vérifier si la ville a déjà des données
    cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE city = ?', (city_name,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        print(f"🔄 Chargement des supermarchés pour {city_name}...")
        
        # Télécharger les données
        elements = download_supermarkets_for_city(city_name)
        
        # Insérer dans la base
        for element in elements:
            if 'lat' in element and 'lon' in element:
                name = element.get('tags', {}).get('name', f'Magasin {city_name}')
                shop_type = element.get('tags', {}).get('shop', 'unknown')
                
                cursor.execute('''
                    INSERT INTO supermarkets (name, lat, lon, type, city)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, element['lat'], element['lon'], shop_type, city_name))
        
        conn.commit()
        print(f"✅ {len(elements)} supermarchés chargés pour {city_name}")
    
    conn.close()

HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>RescueMap - Sélection de Ville</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <style>
        body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
        #map { height: 100vh; width: 100%; }
        
        .control-panel {
            position: absolute; top: 10px; left: 10px; 
            background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 8px;
            box-shadow: 0 0 20px rgba(0,0,0,0.3); z-index: 1000;
            max-width: 320px; backdrop-filter: blur(10px);
        }
        
        .city-selector {
            width: 100%; padding: 10px; margin: 8px 0;
            border: 2px solid #ddd; border-radius: 6px;
            font-size: 14px;
        }
        
        .status-panel {
            position: absolute; top: 10px; right: 10px;
            background: rgba(255, 255, 255, 0.95); padding: 15px; border-radius: 8px;
            box-shadow: 0 0 20px rgba(0,0,0,0.3); z-index: 1000;
            max-width: 300px; backdrop-filter: blur(10px);
        }
        
        .status-safe { color: #28a745; font-weight: bold; }
        .status-danger { color: #dc3545; font-weight: bold; }
        .status-looted { color: #fd7e14; font-weight: bold; }
        
        button { 
            margin: 4px; padding: 10px 15px; cursor: pointer; 
            border: none; border-radius: 6px; background: #007bff; color: white;
            font-size: 14px; transition: background 0.3s;
        }
        
        button:hover { background: #0056b3; }
        button:disabled { background: #6c757d; cursor: not-allowed; }
        
        .shop-info { 
            margin: 10px 0; padding: 10px; 
            background: #f8f9fa; border-radius: 6px; border-left: 4px solid #007bff;
        }
        
        .loading { 
            display: inline-block; width: 16px; height: 16px;
            border: 2px solid #f3f3f3; border-top: 2px solid #007bff;
            border-radius: 50%; animation: spin 1s linear infinite;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="control-panel">
        <h3>🏙️ RescueMap Multi-Villes</h3>
        
        <label for="citySelect"><strong>Choisir une ville:</strong></label>
        <select id="citySelect" class="city-selector" onchange="changeCity()">
            <option value="Toulouse">Toulouse</option>
            <option value="Paris">Paris</option>
            <option value="Lyon">Lyon</option>
            <option value="Marseille">Marseille</option>
            <option value="Bordeaux">Bordeaux</option>
            <option value="Lille">Lille</option>
            <option value="Nantes">Nantes</option>
            <option value="Strasbourg">Strasbourg</option>
            <option value="Montpellier">Montpellier</option>
            <option value="Nice">Nice</option>
        </select>
        
        <div style="margin-top: 15px; display: flex; gap: 5px; flex-wrap: wrap;">
            <button onclick="locateMe()">📍 Me localiser</button>
            <button onclick="loadSupermarkets()">🔄 Actualiser</button>
            <button onclick="resetCity()">🗑️ Réinitialiser</button>
        </div>
        
        <div class="shop-info">
            <strong>Supermarkés:</strong> <span id="count">0</span><br>
            <strong>Ville active:</strong> <span id="currentCity">Toulouse</span><br>
            <strong>Statut:</strong> <span id="loadStatus">Prêt</span>
        </div>
    </div>
    
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script>
        let map;
        let userMarker;
        let currentCity = "Toulouse";
        let allMarkers = [];
        
        // Coordonnées des villes
        const CITIES = {
            "Paris": { lat: 48.8566, lon: 2.3522 },
            "Toulouse": { lat: 43.6045, lon: 1.4440 },
            "Lyon": { lat: 45.7640, lon: 4.8357 },
            "Marseille": { lat: 43.2965, lon: 5.3698 },
            "Bordeaux": { lat: 44.8378, lon: -0.5792 },
            "Lille": { lat: 50.6292, lon: 3.0573 },
            "Nantes": { lat: 47.2184, lon: -1.5536 },
            "Strasbourg": { lat: 48.5734, lon: 7.7521 },
            "Montpellier": { lat: 43.6109, lon: 3.8772 },
            "Nice": { lat: 43.7102, lon: 7.2620 }
        };
        
        function initMap() {
            const cityCoords = CITIES[currentCity];
            map = L.map('map').setView([cityCoords.lat, cityCoords.lon], 13);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(map);
            
            loadSupermarkets();
        }
        
        async function changeCity() {
            const select = document.getElementById('citySelect');
            const newCity = select.value;
            
            if (newCity === currentCity) return;
            
            currentCity = newCity;
            document.getElementById('currentCity').textContent = currentCity;
            document.getElementById('loadStatus').innerHTML = '<div class="loading"></div> Chargement...';
            
            const cityCoords = CITIES[currentCity];
            map.setView([cityCoords.lat, cityCoords.lon], 13);
            
            // Charger les données pour la nouvelle ville
            try {
                const response = await fetch('/api/load_city?city=' + encodeURIComponent(currentCity));
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('loadStatus').textContent = `✅ ${result.count} supermarchés chargés`;
                    loadSupermarkets();
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur de chargement';
                }
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('loadStatus').textContent = '❌ Erreur réseau';
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
                        loadSupermarkets();
                        
                        document.getElementById('loadStatus').textContent = '✅ Localisation réussie';
                    },
                    (error) => {
                        document.getElementById('loadStatus').textContent = '❌ Localisation impossible';
                    }
                );
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
                    document.getElementById('loadStatus').textContent = `✅ ${data.length} supermarchés affichés`;
                    
                    clearMarkers();
                    
                    data.forEach(shop => {
                        const status = shop.status || 'unknown';
                        let color = '#6c757d'; // gray
                        let emoji = '❓';
                        
                        if (status === 'safe') { color = '#28a745'; emoji = '✅'; }
                        if (status === 'danger') { color = '#dc3545'; emoji = '⚠️'; }
                        if (status === 'looted') { color = '#fd7e14'; emoji = '🏚️'; }
                        
                        const marker = L.circleMarker([shop.lat, shop.lon], {
                            radius: 8,
                            fillColor: color,
                            color: '#000',
                            weight: 2,
                            fillOpacity: 0.8
                        }).addTo(map);
                        
                        marker.bindPopup(`
                            <div style="min-width: 220px;">
                                <strong>${emoji} ${shop.name}</strong><br/>
                                <em>Type: ${shop.type || 'inconnu'} | Ville: ${shop.city || currentCity}</em><br/>
                                Statut: <span class="status-${status}">${status}</span><br/>
                                <div style="margin-top: 10px; text-align: center; display: flex; gap: 5px; justify-content: center;">
                                    <button onclick="updateStatus(${shop.id}, 'safe')" style="background: #28a745;">✅ Sûr</button>
                                    <button onclick="updateStatus(${shop.id}, 'danger')" style="background: #dc3545;">⚠️ Danger</button>
                                    <button onclick="updateStatus(${shop.id}, 'looted')" style="background: #fd7e14;">🏚️ Pillé</button>
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
                    loadSupermarkets();
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur de mise à jour';
                }
            } catch (error) {
                document.getElementById('loadStatus').textContent = '❌ Erreur réseau';
            }
        }
        
        async function resetCity() {
            if (!confirm(`Êtes-vous sûr de vouloir réinitialiser tous les supermarchés de ${currentCity} ?`)) {
                return;
            }
            
            document.getElementById('loadStatus').innerHTML = '<div class="loading"></div> Réinitialisation...';
            
            try {
                const response = await fetch('/api/reset_city?city=' + encodeURIComponent(currentCity));
                const result = await response.json();
                
                if (result.success) {
                    document.getElementById('loadStatus').textContent = '✅ Ville réinitialisée';
                    loadSupermarkets();
                } else {
                    document.getElementById('loadStatus').textContent = '❌ Erreur de réinitialisation';
                }
            } catch (error) {
                document.getElementById('loadStatus').textContent = '❌ Erreur réseau';
            }
        }
        
        // Initialisation
        document.addEventListener('DOMContentLoaded', initMap);
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
        
        cursor.execute('SELECT * FROM supermarkets WHERE city = ? ORDER BY name', (city,))
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
        cursor.execute('SELECT COUNT(*) FROM supermarkets WHERE city = ?', (city,))
        count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({'success': True, 'count': count, 'city': city})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_city')
def reset_city():
    """Réinitialise les données d'une ville"""
    try:
        city = request.args.get('city', 'Toulouse')
        
        conn = sqlite3.connect('rescuemap.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM supermarkets WHERE city = ?', (city,))
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
            WHERE id = ? AND city = ?
        ''', (status, datetime.now().isoformat(), shop_id, city))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status')
def api_status():
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    cursor.execute('SELECT city, COUNT(*) FROM supermarkets GROUP BY city')
    cities_count = cursor.fetchall()
    conn.close()
    
    return jsonify({
        'status': 'online', 
        'cities': dict(cities_count),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    # Initialiser la base de données
    setup_database_schema()
    
    print("🏙️  RescueMap Multi-Villes - Chargement Dynamique")
    print("=" * 50)
    print("🌐 Serveur accessible sur: http://localhost:5000")
    print("🚀 Les données se chargent automatiquement quand vous changez de ville!")
    
    app.run(host='0.0.0.0', port=5000, debug=True)