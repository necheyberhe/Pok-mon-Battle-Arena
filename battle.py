import pandas as pd
import random
from database import get_db_connection

def get_type_multiplier(attacking_type, defending_type, conn):
    """Get type effectiveness multiplier"""
    if defending_type is None:
        return 1.0
    
    df = pd.read_sql_query("""
        SELECT multiplier FROM type_effectiveness 
        WHERE attacking_type = ? AND defending_type = ?
    """, conn, params=(attacking_type, defending_type))
    
    return float(df.iloc[0]['multiplier']) if not df.empty else 1.0

def get_total_multiplier(attacker_type, defender_type1, defender_type2, conn):
    """Get total type multiplier for dual-type Pokémon"""
    m1 = get_type_multiplier(attacker_type, defender_type1, conn)
    m2 = get_type_multiplier(attacker_type, defender_type2, conn) if defender_type2 else 1.0
    return m1 * m2

def calculate_damage(attacker, defender, conn):
    """Calculate damage based on stats and type effectiveness"""
    multiplier = get_total_multiplier(attacker['type1'], defender['type1'], defender['type2'], conn)
    base_damage = ((attacker['attack'] / max(1, defender['defense'])) * 10) + 5
    damage = max(1, int(base_damage * multiplier))
    return damage, multiplier

def create_team(battle_id, player_label, pokemon_names, conn):
    """Create a team for a player"""
    c = conn.cursor()
    
    # Clear existing team
    c.execute("DELETE FROM team_pokemon WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    
    for i, name in enumerate(pokemon_names, start=1):
        df = pd.read_sql_query("SELECT * FROM pokemon WHERE name = ?", conn, params=(name,))
        
        if df.empty:
            continue
        
        p = df.iloc[0]
        c.execute("""
        INSERT INTO team_pokemon (
            battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
            max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            battle_id, player_label, i, int(p['id']), p['name'], p['type1'], p['type2'],
            int(p['hp']), int(p['hp']), int(p['attack']), int(p['defense']),
            int(p['sp_atk']), int(p['sp_def']), int(p['speed']),
            int(p['generation']), int(p['legendary'])
        ))
    
    conn.commit()

def get_active_pokemon(battle_id, player_label, conn):
    """Get the first alive Pokémon for a player"""
    df = pd.read_sql_query("""
        SELECT * FROM team_pokemon
        WHERE battle_id = ? AND player_label = ? AND current_hp > 0
        ORDER BY slot_number LIMIT 1
    """, conn, params=(battle_id, player_label))
    
    return df.iloc[0] if not df.empty else None

def apply_damage(pokemon_id, damage, conn):
    """Apply damage to a Pokémon"""
    c = conn.cursor()
    c.execute("""
        UPDATE team_pokemon
        SET current_hp = MAX(0, current_hp - ?)
        WHERE id = ?
    """, (damage, pokemon_id))
    conn.commit()

def log_event(battle_id, turn_number, event_type, conn, actor=None, target=None, details=None, damage=None):
    """Log battle event"""
    c = conn.cursor()
    c.execute("""
        INSERT INTO battle_log (battle_id, turn_number, event_type, actor, target, details, damage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (battle_id, turn_number, event_type, actor, target, details, damage))
    conn.commit()

def is_team_alive(battle_id, player_label, conn):
    """Check if player has any alive Pokémon"""
    df = pd.read_sql_query("""
        SELECT COUNT(*) as alive FROM team_pokemon
        WHERE battle_id = ? AND player_label = ? AND current_hp > 0
    """, conn, params=(battle_id, player_label))
    
    return int(df.iloc[0]['alive']) > 0

def execute_turn(battle_id, turn_number, conn):
    """Execute one turn of battle"""
    p1 = get_active_pokemon(battle_id, "Player", conn)
    p2 = get_active_pokemon(battle_id, "AI", conn)
    
    if p1 is None or p2 is None:
        return False
    
    # Determine turn order based on speed
    if p1['speed'] >= p2['speed']:
        first, second = p1, p2
        first_label, second_label = "Player", "AI"
    else:
        first, second = p2, p1
        first_label, second_label = "AI", "Player"
    
    # First attack
    damage, multiplier = calculate_damage(first, second, conn)
    effect = "super effective" if multiplier > 1 else "not very effective" if multiplier < 1 else "normal"
    
    apply_damage(second['id'], damage, conn)
    log_event(battle_id, turn_number, "attack", conn, 
              actor=first['name'], target=second['name'], 
              details=effect, damage=damage)
    
    # Check if defender fainted
    second_check = get_active_pokemon(battle_id, second_label, conn)
    if second_check is None:
        return True
    
    # Second attack
    damage, multiplier = calculate_damage(second, first, conn)
    effect = "super effective" if multiplier > 1 else "not very effective" if multiplier < 1 else "normal"
    
    apply_damage(first['id'], damage, conn)
    log_event(battle_id, turn_number, "attack", conn,
              actor=second['name'], target=first['name'],
              details=effect, damage=damage)
    
    return True

def run_battle(battle_id, conn, max_turns=100):
    """Run full battle simulation"""
    turn = 1
    
    while turn <= max_turns:
        p1_alive = is_team_alive(battle_id, "Player", conn)
        p2_alive = is_team_alive(battle_id, "AI", conn)
        
        if not p1_alive:
            log_event(battle_id, turn, "result", conn, details="AI wins!")
            return "AI"
        if not p2_alive:
            log_event(battle_id, turn, "result", conn, details="Player wins!")
            return "Player"
        
        execute_turn(battle_id, turn, conn)
        turn += 1
    
    log_event(battle_id, turn, "result", conn, details="Draw - max turns reached")
    return "Draw"

def get_battle_log(battle_id, conn):
    """Get battle log for display"""
    df = pd.read_sql_query("""
        SELECT turn_number, event_type, actor, target, details, damage, created_at
        FROM battle_log
        WHERE battle_id = ?
        ORDER BY id
    """, conn, params=(battle_id,))
    return df