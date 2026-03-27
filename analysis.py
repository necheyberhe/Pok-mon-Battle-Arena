import pandas as pd
from database import get_db_connection

def analyze_power_creep():
    """Analyze average total stats across generations"""
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT generation,
               AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats,
               COUNT(*) AS pokemon_count
        FROM pokemon
        GROUP BY generation
        ORDER BY generation
    """, conn)
    conn.close()
    return df

def analyze_type_combinations():
    """Find strongest type combinations by average stats"""
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT type1,
               COALESCE(type2, 'None') AS type2,
               AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats,
               COUNT(*) AS pokemon_count
        FROM pokemon
        GROUP BY type1, COALESCE(type2, 'None')
        HAVING COUNT(*) >= 3
        ORDER BY avg_total_stats DESC
        LIMIT 10
    """, conn)
    conn.close()
    return df

def analyze_legendary_vs_normal():
    """Compare legendary vs normal Pokémon stats"""
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT 
            CASE WHEN legendary = 1 THEN 'Legendary' ELSE 'Normal' END AS category,
            AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats,
            AVG(hp) AS avg_hp,
            AVG(attack) AS avg_attack,
            AVG(defense) AS avg_defense,
            COUNT(*) AS count
        FROM pokemon
        GROUP BY legendary
    """, conn)
    conn.close()
    return df

def get_weakest_legendary():
    """Find the weakest legendary Pokémon by total stats"""
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT name, type1, type2,
               (hp + attack + defense + sp_atk + sp_def + speed) AS total_stats
        FROM pokemon
        WHERE legendary = 1
        ORDER BY total_stats ASC
        LIMIT 5
    """, conn)
    conn.close()
    return df