import pandas as pd
from database import get_db_connection

def get_max_stats(conn):
    """Get maximum natural stats from Pokémon table"""
    df = pd.read_sql_query("""
        SELECT 
            MAX(hp) as max_hp,
            MAX(attack) as max_attack,
            MAX(defense) as max_defense,
            MAX(sp_atk) as max_sp_atk,
            MAX(sp_def) as max_sp_def,
            MAX(speed) as max_speed
        FROM pokemon
    """, conn)
    return df.iloc[0]

def cheat_upupdowndown(battle_id, player_label, conn):
    """Cheat: Double HP for player's team"""
    c = conn.cursor()
    c.execute("""
        UPDATE team_pokemon
        SET max_hp = max_hp * 2,
            current_hp = current_hp * 2
        WHERE battle_id = ? AND player_label = ?
    """, (battle_id, player_label))
    
    c.execute("""
        INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description)
        VALUES (?, ?, ?, ?)
    """, (battle_id, "UPUPDOWNDOWN", player_label, "Doubled HP via UPDATE"))
    
    conn.commit()
    return "🔥 CHEAT ACTIVATED: All Pokémon HP doubled!"

def cheat_godmode(battle_id, player_label, conn):
    """Cheat: Set defense stats to 999"""
    c = conn.cursor()
    c.execute("""
        UPDATE team_pokemon
        SET defense = 999,
            sp_def = 999
        WHERE battle_id = ? AND player_label = ?
    """, (battle_id, player_label))
    
    c.execute("""
        INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description)
        VALUES (?, ?, ?, ?)
    """, (battle_id, "GODMODE", player_label, "Set defense/sp_def to 999"))
    
    conn.commit()
    return "👑 CHEAT ACTIVATED: GODMODE enabled - Defense stats maxed!"

def cheat_nerf(battle_id, player_label, conn):
    """Cheat: Reduce opponent stats by 50%"""
    opponent = "AI" if player_label == "Player" else "Player"
    c = conn.cursor()
    c.execute("""
        UPDATE team_pokemon
        SET attack = CAST(attack * 0.5 AS INTEGER),
            defense = CAST(defense * 0.5 AS INTEGER),
            sp_atk = CAST(sp_atk * 0.5 AS INTEGER),
            sp_def = CAST(sp_def * 0.5 AS INTEGER),
            speed = CAST(speed * 0.5 AS INTEGER)
        WHERE battle_id = ? AND player_label = ?
    """, (battle_id, opponent))
    
    c.execute("""
        INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description)
        VALUES (?, ?, ?, ?)
    """, (battle_id, "NERF", player_label, f"Reduced {opponent} stats by 50%"))
    
    conn.commit()
    return f"💀 CHEAT ACTIVATED: {opponent}'s Pokémon have been NERFED by 50%!"

def cheat_legendary(battle_id, player_label, conn):
    """Cheat: Insert overpowered custom Pokémon"""
    c = conn.cursor()
    
    # Get next slot number
    df = pd.read_sql_query("""
        SELECT MAX(slot_number) as max_slot FROM team_pokemon
        WHERE battle_id = ? AND player_label = ?
    """, conn, params=(battle_id, player_label))
    
    next_slot = int(df.iloc[0]['max_slot'] or 0) + 1
    
    c.execute("""
        INSERT INTO team_pokemon (
            battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
            max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        battle_id, player_label, next_slot, 9999, "OMEGAMON-X", "Dragon", "Psychic",
        500, 500, 500, 500, 500, 500, 500, 9, 1
    ))
    
    c.execute("""
        INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description)
        VALUES (?, ?, ?, ?)
    """, (battle_id, "LEGENDARY", player_label, "Inserted custom OP Pokémon: OMEGAMON-X"))
    
    conn.commit()
    return "🌟 CHEAT ACTIVATED: OMEGAMON-X (500 all stats) added to your team!"

def cheat_steal(battle_id, player_label, conn):
    """Cheat: Copy opponent's strongest Pokémon"""
    c = conn.cursor()
    
    # Get opponent's strongest Pokémon by total stats
    opponent = "AI" if player_label == "Player" else "Player"
    df = pd.read_sql_query(f"""
        SELECT * FROM team_pokemon
        WHERE battle_id = ? AND player_label = ?
        ORDER BY (attack + defense + sp_atk + sp_def + speed + max_hp) DESC
        LIMIT 1
    """, conn, params=(battle_id, opponent))
    
    if df.empty:
        return "No opponent Pokémon to steal!"
    
    stolen = df.iloc[0]
    
    # Get next slot number
    slot_df = pd.read_sql_query("""
        SELECT MAX(slot_number) as max_slot FROM team_pokemon
        WHERE battle_id = ? AND player_label = ?
    """, conn, params=(battle_id, player_label))
    
    next_slot = int(slot_df.iloc[0]['max_slot'] or 0) + 1
    
    c.execute("""
        INSERT INTO team_pokemon (
            battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
            max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        battle_id, player_label, next_slot, stolen['pokemon_id'], stolen['name'], 
        stolen['type1'], stolen['type2'], stolen['max_hp'], stolen['max_hp'],
        stolen['attack'], stolen['defense'], stolen['sp_atk'], stolen['sp_def'],
        stolen['speed'], stolen['generation'], stolen['legendary']
    ))
    
    c.execute("""
        INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description)
        VALUES (?, ?, ?, ?)
    """, (battle_id, "STEAL", player_label, f"Stole {stolen['name']} from opponent"))
    
    conn.commit()
    return f"🎭 CHEAT ACTIVATED: Stole {stolen['name']} from opponent!"

def cheat_audit(battle_id, conn):
    """Get cheat audit for a battle"""
    df = pd.read_sql_query("""
        SELECT cheat_code, player_label, description, created_at
        FROM cheat_audit
        WHERE battle_id = ?
        ORDER BY created_at
    """, conn, params=(battle_id,))
    return df

def anomaly_detection(battle_id, conn):
    """Detect unnatural stats from cheats"""
    max_stats = get_max_stats(conn)
    
    df = pd.read_sql_query(f"""
        SELECT name, player_label, max_hp, attack, defense, sp_atk, sp_def, speed
        FROM team_pokemon
        WHERE battle_id = ?
        AND (
            max_hp > {max_stats['max_hp']} OR
            attack > {max_stats['max_attack']} OR
            defense > {max_stats['max_defense']} OR
            sp_atk > {max_stats['max_sp_atk']} OR
            sp_def > {max_stats['max_sp_def']} OR
            speed > {max_stats['max_speed']}
        )
    """, conn, params=(battle_id,))
    
    return df