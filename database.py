import sqlite3
import pandas as pd
import os

DB_PATH = "pokemon_battle.db"

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database(csv_path="pokemon.csv"):
    """Initialize database with Pokémon data and type effectiveness"""
    
    # Remove existing database if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Create pokemon table
    c.execute("""
    CREATE TABLE pokemon (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        type1 TEXT NOT NULL,
        type2 TEXT,
        hp INTEGER NOT NULL,
        attack INTEGER NOT NULL,
        defense INTEGER NOT NULL,
        sp_atk INTEGER NOT NULL,
        sp_def INTEGER NOT NULL,
        speed INTEGER NOT NULL,
        generation INTEGER NOT NULL,
        legendary INTEGER NOT NULL
    )
    """)
    
    # Create type_effectiveness table
    c.execute("""
    CREATE TABLE type_effectiveness (
        attacking_type TEXT NOT NULL,
        defending_type TEXT NOT NULL,
        multiplier REAL NOT NULL,
        PRIMARY KEY (attacking_type, defending_type)
    )
    """)
    
    # Create battle_log table
    c.execute("""
    CREATE TABLE battle_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        turn_number INTEGER,
        event_type TEXT NOT NULL,
        actor TEXT,
        target TEXT,
        details TEXT,
        damage INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create team_pokemon table
    c.execute("""
    CREATE TABLE team_pokemon (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        player_label TEXT NOT NULL,
        slot_number INTEGER NOT NULL,
        pokemon_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        type1 TEXT NOT NULL,
        type2 TEXT,
        max_hp INTEGER NOT NULL,
        current_hp INTEGER NOT NULL,
        attack INTEGER NOT NULL,
        defense INTEGER NOT NULL,
        sp_atk INTEGER NOT NULL,
        sp_def INTEGER NOT NULL,
        speed INTEGER NOT NULL,
        generation INTEGER NOT NULL,
        legendary INTEGER NOT NULL,
        FOREIGN KEY (pokemon_id) REFERENCES pokemon(id)
    )
    """)
    
    # Create cheat_audit table
    c.execute("""
    CREATE TABLE cheat_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        cheat_code TEXT NOT NULL,
        player_label TEXT NOT NULL,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Load Pokémon data
    df = pd.read_csv(csv_path)
    
    # Insert Pokémon data
    for _, row in df.iterrows():
        c.execute("""
        INSERT INTO pokemon (id, name, type1, type2, hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(row['pokedex_number']),
            row['name'],
            row['type1'],
            row['type2'] if pd.notna(row['type2']) else None,
            int(row['hp']),
            int(row['attack']),
            int(row['defense']),
            int(row['sp_attack']),
            int(row['sp_defense']),
            int(row['speed']),
            int(row['generation']),
            int(row['is_legendary'])
        ))
    
    # Insert type effectiveness data
    type_effects = [
        ("Fire", "Grass", 2.0), ("Fire", "Water", 0.5), ("Fire", "Fire", 0.5),
        ("Water", "Fire", 2.0), ("Water", "Grass", 0.5), ("Water", "Water", 0.5),
        ("Grass", "Water", 2.0), ("Grass", "Fire", 0.5), ("Grass", "Grass", 0.5),
        ("Electric", "Water", 2.0), ("Electric", "Grass", 0.5), ("Electric", "Electric", 0.5),
        ("Rock", "Fire", 2.0), ("Ground", "Electric", 2.0), ("Psychic", "Fighting", 2.0),
        ("Fighting", "Rock", 2.0), ("Fighting", "Normal", 2.0), ("Ghost", "Psychic", 2.0)
    ]
    
    c.executemany("""
    INSERT INTO type_effectiveness (attacking_type, defending_type, multiplier)
    VALUES (?, ?, ?)
    """, type_effects)
    
    conn.commit()
    conn.close()
    
    return True

def get_all_pokemon():
    """Get all Pokémon names for selection"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, name, type1, type2, hp, attack, defense, speed FROM pokemon ORDER BY name", conn)
    conn.close()
    return df

def get_pokemon_stats(pokemon_name):
    """Get Pokémon stats by name"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM pokemon WHERE name = ?", conn, params=(pokemon_name,))
    conn.close()
    return df.iloc[0] if not df.empty else None