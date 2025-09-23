# reset_database.py
import sqlite3
import os

def reset_database():
    """Réinitialise complètement la base de données"""
    if os.path.exists('rescuemap.db'):
        os.remove('rescuemap.db')
        print("🗑️  Ancienne base de données supprimée")
    
    conn = sqlite3.connect('rescuemap.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE supermarkets (
            id INTEGER PRIMARY KEY,
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
    print("✅ Nouvelle base de données créée avec la colonne 'city'")

if __name__ == '__main__':
    reset_database()