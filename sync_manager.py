# sync_manager.py
import sqlite3
import hashlib
import json
from datetime import datetime

class SyncManager:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def export_changes(self, since_timestamp):
        """Exporter les modifications récentes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM supermarkets 
            WHERE last_verified > ?
        ''', (since_timestamp,))
        
        changes = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'changes': changes
        }
    
    def import_changes(self, changes_data):
        """Importer les modifications d'un autre nœud"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for change in changes_data['changes']:
            cursor.execute('''
                INSERT OR REPLACE INTO supermarkets 
                (id, name, lat, lon, type, address, status, last_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                change['id'], change['name'], change['lat'], change['lon'],
                change['type'], change['address'], change['status'], 
                change['last_verified']
            ))
        
        conn.commit()
        conn.close()