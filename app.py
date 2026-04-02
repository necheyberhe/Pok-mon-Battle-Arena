import streamlit as st
import pandas as pd
import sqlite3
import random
import os

# ============================================================================
# DATABASE SETUP (Uses local pokemon.csv - NO KAGGLE)
# ============================================================================

DB_PATH = "pokemon_battle.db"

def init_database():
    """Initialize database with Pokémon data from local CSV"""
    
    # Remove existing database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    conn = sqlite3.connect(DB_PATH)
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
        legendary INTEGER NOT NULL
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
    
    # Load Pokémon data from local CSV (NOT from Kaggle)
    df = pd.read_csv("pokemon.csv")
    
    # Clean column names
    df.columns = [col.strip().lower().replace(" ", "_").replace(".", "") for col in df.columns]
    
    # Map to expected column names
    df = df.rename(columns={
        'pokedex_number': 'id',
        'sp_attack': 'sp_atk',
        'sp_defense': 'sp_def',
        'is_legendary': 'legendary'
    })
    
    # Insert Pokémon data
    inserted = 0
    for _, row in df.iterrows():
        try:
            type2 = row['type2'] if pd.notna(row['type2']) else None
            c.execute("""
            INSERT INTO pokemon (id, name, type1, type2, hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(row['id']),
                row['name'],
                row['type1'],
                type2,
                int(row['hp']),
                int(row['attack']),
                int(row['defense']),
                int(row['sp_atk']),
                int(row['sp_def']),
                int(row['speed']),
                int(row['generation']),
                int(row['legendary'])
            ))
            inserted += 1
        except Exception as e:
            continue
    
    st.success(f"✅ Loaded {inserted} Pokémon from local dataset!")
    
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

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def get_type_multiplier(attacking_type, defending_type, conn):
    if defending_type is None:
        return 1.0
    c = conn.cursor()
    c.execute("SELECT multiplier FROM type_effectiveness WHERE attacking_type = ? AND defending_type = ?", 
              (attacking_type, defending_type))
    result = c.fetchone()
    return result[0] if result else 1.0

def calculate_damage(attacker, defender, conn):
    multiplier = get_type_multiplier(attacker['type1'], defender['type1'], conn)
    if defender['type2']:
        multiplier *= get_type_multiplier(attacker['type1'], defender['type2'], conn)
    
    base_damage = ((attacker['attack'] / max(1, defender['defense'])) * 10) + 5
    damage = max(1, int(base_damage * multiplier))
    return damage, multiplier

def create_team(battle_id, player_label, pokemon_names, conn):
    c = conn.cursor()
    c.execute("DELETE FROM team_pokemon WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    
    for i, name in enumerate(pokemon_names, start=1):
        df = pd.read_sql_query("SELECT * FROM pokemon WHERE name = ?", conn, params=(name,))
        if df.empty:
            continue
        p = df.iloc[0]
        c.execute("""
        INSERT INTO team_pokemon (battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
                    max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (battle_id, player_label, i, int(p['id']), p['name'], p['type1'], p['type2'],
              int(p['hp']), int(p['hp']), int(p['attack']), int(p['defense']),
              int(p['sp_atk']), int(p['sp_def']), int(p['speed']),
              int(p['generation']), int(p['legendary'])))
    conn.commit()

def get_active_pokemon(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("""
        SELECT * FROM team_pokemon
        WHERE battle_id = ? AND player_label = ? AND current_hp > 0
        ORDER BY slot_number LIMIT 1
    """, (battle_id, player_label))
    
    row = c.fetchone()
    if row:
        columns = [description[0] for description in c.description]
        return dict(zip(columns, row))
    return None

def apply_damage(pokemon_id, damage, conn):
    c = conn.cursor()
    c.execute("SELECT current_hp FROM team_pokemon WHERE id = ?", (pokemon_id,))
    result = c.fetchone()
    
    if result:
        current_hp = result[0]
        new_hp = max(0, current_hp - damage)
        c.execute("UPDATE team_pokemon SET current_hp = ? WHERE id = ?", (new_hp, pokemon_id))
        conn.commit()
        return new_hp
    return 0

def log_event(battle_id, turn_number, event_type, conn, actor=None, target=None, details=None, damage=None):
    c = conn.cursor()
    c.execute("""
        INSERT INTO battle_log (battle_id, turn_number, event_type, actor, target, details, damage)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (battle_id, turn_number, event_type, actor, target, details, damage))
    conn.commit()

def is_team_alive(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("""
        SELECT COUNT(*) as alive FROM team_pokemon
        WHERE battle_id = ? AND player_label = ? AND current_hp > 0
    """, (battle_id, player_label))
    result = c.fetchone()
    return result[0] > 0

def execute_turn(battle_id, turn_number, conn):
    p1 = get_active_pokemon(battle_id, "Player", conn)
    p2 = get_active_pokemon(battle_id, "AI", conn)
    
    if p1 is None or p2 is None:
        return False
    
    if p1['speed'] >= p2['speed']:
        first, second = p1, p2
    else:
        first, second = p2, p1
    
    # First attack
    damage, multiplier = calculate_damage(first, second, conn)
    effect = "🔥 SUPER EFFECTIVE!" if multiplier > 1 else "💧 NOT VERY EFFECTIVE..." if multiplier < 1 else "⚡ NORMAL HIT"
    new_hp = apply_damage(second['id'], damage, conn)
    log_event(battle_id, turn_number, "attack", conn, actor=first['name'], target=second['name'], details=effect, damage=damage)
    
    if new_hp == 0:
        log_event(battle_id, turn_number, "faint", conn, details=f"{second['name']} fainted!")
        return True
    
    # Second attack
    damage, multiplier = calculate_damage(second, first, conn)
    effect = "🔥 SUPER EFFECTIVE!" if multiplier > 1 else "💧 NOT VERY EFFECTIVE..." if multiplier < 1 else "⚡ NORMAL HIT"
    new_hp = apply_damage(first['id'], damage, conn)
    log_event(battle_id, turn_number, "attack", conn, actor=second['name'], target=first['name'], details=effect, damage=damage)
    
    if new_hp == 0:
        log_event(battle_id, turn_number, "faint", conn, details=f"{first['name']} fainted!")
    
    return True

def run_battle(battle_id, conn, max_turns=100):
    turn = 1
    while turn <= max_turns:
        if not is_team_alive(battle_id, "Player", conn):
            log_event(battle_id, turn, "result", conn, details="💀 AI WINS! 💀")
            return "AI"
        if not is_team_alive(battle_id, "AI", conn):
            log_event(battle_id, turn, "result", conn, details="🎉 PLAYER WINS! 🎉")
            return "Player"
        execute_turn(battle_id, turn, conn)
        turn += 1
    log_event(battle_id, turn, "result", conn, details="🤝 DRAW")
    return "Draw"

def get_battle_log(battle_id, conn):
    return pd.read_sql_query("""
        SELECT turn_number, event_type, actor, target, details, damage
        FROM battle_log WHERE battle_id = ? ORDER BY id
    """, conn, params=(battle_id,))

# ============================================================================
# CHEAT FUNCTIONS
# ============================================================================

def cheat_upupdowndown(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("UPDATE team_pokemon SET max_hp = max_hp * 2, current_hp = current_hp * 2 WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    c.execute("INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description) VALUES (?, ?, ?, ?)", (battle_id, "UPUPDOWNDOWN", player_label, "Doubled HP"))
    conn.commit()
    return "🔥 CHEAT: UPUPDOWNDOWN - All Pokémon HP DOUBLED!"

def cheat_godmode(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("UPDATE team_pokemon SET defense = 999, sp_def = 999 WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    c.execute("INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description) VALUES (?, ?, ?, ?)", (battle_id, "GODMODE", player_label, "Defense set to 999"))
    conn.commit()
    return "👑 CHEAT: GODMODE - Defense and Sp. Def MAXED!"

def cheat_nerf(battle_id, player_label, conn):
    opponent = "AI" if player_label == "Player" else "Player"
    c = conn.cursor()
    c.execute("UPDATE team_pokemon SET attack = attack/2, defense = defense/2, sp_atk = sp_atk/2, sp_def = sp_def/2, speed = speed/2 WHERE battle_id = ? AND player_label = ?", (battle_id, opponent))
    c.execute("INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description) VALUES (?, ?, ?, ?)", (battle_id, "NERF", player_label, f"Reduced {opponent} stats by 50%"))
    conn.commit()
    return f"💀 CHEAT: NERF - {opponent}'s stats REDUCED BY 50%!"

def cheat_legendary(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("SELECT MAX(slot_number) as max_slot FROM team_pokemon WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    next_slot = (c.fetchone()[0] or 0) + 1
    c.execute("""
        INSERT INTO team_pokemon (battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
                    max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (battle_id, player_label, next_slot, 9999, "OMEGAMON-X", "Dragon", "Psychic", 500, 500, 500, 500, 500, 500, 500, 9, 1))
    c.execute("INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description) VALUES (?, ?, ?, ?)", (battle_id, "LEGENDARY", player_label, "Added OMEGAMON-X (500 all stats)"))
    conn.commit()
    return "🌟 CHEAT: LEGENDARY - OMEGAMON-X (500 all stats) ADDED to your team!"

def cheat_steal(battle_id, player_label, conn):
    opponent = "AI" if player_label == "Player" else "Player"
    df = pd.read_sql_query(f"SELECT * FROM team_pokemon WHERE battle_id = ? AND player_label = ? ORDER BY (attack+defense+sp_atk+sp_def+speed+max_hp) DESC LIMIT 1", conn, params=(battle_id, opponent))
    if df.empty:
        return "No Pokémon to steal!"
    stolen = df.iloc[0]
    c = conn.cursor()
    c.execute("SELECT MAX(slot_number) as max_slot FROM team_pokemon WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    next_slot = (c.fetchone()[0] or 0) + 1
    c.execute("""
        INSERT INTO team_pokemon (battle_id, player_label, slot_number, pokemon_id, name, type1, type2,
                    max_hp, current_hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (battle_id, player_label, next_slot, stolen['pokemon_id'], stolen['name'], stolen['type1'], stolen['type2'],
          stolen['max_hp'], stolen['max_hp'], stolen['attack'], stolen['defense'], stolen['sp_atk'], 
          stolen['sp_def'], stolen['speed'], stolen['generation'], stolen['legendary']))
    c.execute("INSERT INTO cheat_audit (battle_id, cheat_code, player_label, description) VALUES (?, ?, ?, ?)", (battle_id, "STEAL", player_label, f"Stole {stolen['name']} from opponent"))
    conn.commit()
    return f"🎭 CHEAT: STEAL - {stolen['name']} STOLEN from opponent!"

def cheat_audit(battle_id, conn):
    return pd.read_sql_query("SELECT cheat_code, player_label, description, created_at FROM cheat_audit WHERE battle_id = ? ORDER BY created_at", conn, params=(battle_id,))

def anomaly_detection(battle_id, conn):
    max_stats = pd.read_sql_query("SELECT MAX(hp) as max_hp, MAX(attack) as max_attack, MAX(defense) as max_defense, MAX(sp_atk) as max_sp_atk, MAX(sp_def) as max_sp_def, MAX(speed) as max_speed FROM pokemon", conn)
    return pd.read_sql_query(f"""
        SELECT name, player_label, max_hp, attack, defense, sp_atk, sp_def, speed
        FROM team_pokemon WHERE battle_id = ?
        AND (max_hp > {max_stats['max_hp'].iloc[0]} OR attack > {max_stats['max_attack'].iloc[0]} 
             OR defense > {max_stats['max_defense'].iloc[0]} OR sp_atk > {max_stats['max_sp_atk'].iloc[0]}
             OR sp_def > {max_stats['max_sp_def'].iloc[0]} OR speed > {max_stats['max_speed'].iloc[0]})
    """, conn, params=(battle_id,))

# ============================================================================
# ANALYSIS FUNCTIONS
# ============================================================================

def analyze_power_creep():
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT generation, AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats, COUNT(*) AS count
        FROM pokemon GROUP BY generation ORDER BY generation
    """, conn)
    conn.close()
    return df

def analyze_type_combinations():
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT type1, COALESCE(type2, 'None') AS type2, AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats, COUNT(*) AS count
        FROM pokemon GROUP BY type1, COALESCE(type2, 'None') HAVING COUNT(*) >= 3 ORDER BY avg_total_stats DESC LIMIT 10
    """, conn)
    conn.close()
    return df

def analyze_legendary_vs_normal():
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT CASE WHEN legendary = 1 THEN 'Legendary' ELSE 'Normal' END AS category, AVG(hp + attack + defense + sp_atk + sp_def + speed) AS avg_total_stats, COUNT(*) AS count
        FROM pokemon GROUP BY legendary
    """, conn)
    conn.close()
    return df

def get_weakest_legendary():
    conn = get_db_connection()
    df = pd.read_sql_query("""
        SELECT name, type1, COALESCE(type2, 'None') AS type2, (hp + attack + defense + sp_atk + sp_def + speed) AS total_stats
        FROM pokemon WHERE legendary = 1 ORDER BY total_stats ASC LIMIT 5
    """, conn)
    conn.close()
    return df

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="Pokémon Battle Arena", page_icon="⚔️", layout="wide")

# Initialize database on first run
if 'db_initialized' not in st.session_state:
    with st.spinner("Initializing Pokémon database..."):
        try:
            init_database()
            st.session_state.db_initialized = True
            st.session_state.battle_id = random.randint(1000, 9999)
            st.session_state.battle_active = False
            st.session_state.player_team = []
            st.session_state.game_result = None
            st.session_state.cheat_message = None
            st.session_state.turn_count = 0
        except Exception as e:
            st.error(f"Failed to initialize database: {e}")
            st.stop()

st.title("⚔️ Pokémon Battle Arena")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("🎮 Select Your Team")
    
    conn = get_db_connection()
    pokemon_df = pd.read_sql_query("SELECT name, type1, type2, hp, attack, defense, speed FROM pokemon ORDER BY name", conn)
    conn.close()
    pokemon_names = pokemon_df['name'].tolist()
    
    st.caption(f"📊 {len(pokemon_names)} Pokémon available")
    
    selected_team = []
    for i in range(3):
        pokemon = st.selectbox(f"Pokémon {i+1}", ["None"] + pokemon_names, key=f"pokemon_{i}")
        if pokemon != "None":
            p_stats = pokemon_df[pokemon_df['name'] == pokemon].iloc[0]
            st.caption(f"  HP:{p_stats['hp']} ATK:{p_stats['attack']} DEF:{p_stats['defense']} SPD:{p_stats['speed']}")
            selected_team.append(pokemon)
    
    if st.button("⚡ Start Battle", type="primary", disabled=len(selected_team) == 0):
        with st.spinner("Initializing battle..."):
            conn = get_db_connection()
            create_team(st.session_state.battle_id, "Player", selected_team, conn)
            ai_team = random.sample(pokemon_names, min(random.randint(1, 3), len(pokemon_names)))
            create_team(st.session_state.battle_id, "AI", ai_team, conn)
            conn.close()
            st.session_state.player_team = selected_team
            st.session_state.battle_active = True
            st.session_state.game_result = None
            st.session_state.cheat_message = None
            st.session_state.turn_count = 0
            st.rerun()
    
    st.markdown("---")
    st.header("🎭 Cheat Codes")
    cheat_code = st.text_input("Enter cheat code:", placeholder="UPUPDOWNDOWN, GODMODE, NERF, LEGENDARY, STEAL")
    
    if st.button("💀 ACTIVATE CHEAT", disabled=not st.session_state.battle_active):
        conn = get_db_connection()
        if cheat_code.upper() == "UPUPDOWNDOWN":
            msg = cheat_upupdowndown(st.session_state.battle_id, "Player", conn)
        elif cheat_code.upper() == "GODMODE":
            msg = cheat_godmode(st.session_state.battle_id, "Player", conn)
        elif cheat_code.upper() == "NERF":
            msg = cheat_nerf(st.session_state.battle_id, "Player", conn)
        elif cheat_code.upper() == "LEGENDARY":
            msg = cheat_legendary(st.session_state.battle_id, "Player", conn)
        elif cheat_code.upper() == "STEAL":
            msg = cheat_steal(st.session_state.battle_id, "Player", conn)
        else:
            msg = "❌ Unknown cheat code!"
        conn.close()
        st.session_state.cheat_message = msg
        st.rerun()
    
    if st.session_state.cheat_message:
        if "❌" not in st.session_state.cheat_message:
            st.success(st.session_state.cheat_message)
        else:
            st.error(st.session_state.cheat_message)

# Main content
if not st.session_state.battle_active:
    st.subheader("📊 Pokémon Data Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Power Creep", "🔮 Type Combinations", "👑 Legendary vs Normal", "💔 Weakest Legendary"])
    
    with tab1:
        df = analyze_power_creep()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            st.line_chart(df.set_index('generation')['avg_total_stats'])
    
    with tab2:
        df = analyze_type_combinations()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
    
    with tab3:
        df = analyze_legendary_vs_normal()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
    
    with tab4:
        df = get_weakest_legendary()
        if not df.empty:
            st.dataframe(df, use_container_width=True)

else:
    # Battle mode
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("👤 Your Team")
        for i, pokemon in enumerate(st.session_state.player_team):
            st.info(f"{i+1}. {pokemon}")
    
    with col2:
        st.subheader("🤖 AI Team")
        conn = get_db_connection()
        ai_df = pd.read_sql_query("SELECT name FROM team_pokemon WHERE battle_id = ? AND player_label = 'AI' ORDER BY slot_number", conn, params=(st.session_state.battle_id,))
        conn.close()
        for i, row in ai_df.iterrows():
            st.warning(f"{i+1}. {row['name']}")
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    
    with col_btn1:
        if st.button("🎲 Execute Turn", use_container_width=True):
            conn = get_db_connection()
            if is_team_alive(st.session_state.battle_id, "Player", conn) and is_team_alive(st.session_state.battle_id, "AI", conn):
                st.session_state.turn_count += 1
                execute_turn(st.session_state.battle_id, st.session_state.turn_count, conn)
                if not is_team_alive(st.session_state.battle_id, "Player", conn):
                    st.session_state.game_result = "AI"
                elif not is_team_alive(st.session_state.battle_id, "AI", conn):
                    st.session_state.game_result = "Player"
            conn.close()
            st.rerun()
    
    with col_btn2:
        if st.button("🔄 Auto Battle", use_container_width=True):
            conn = get_db_connection()
            result = run_battle(st.session_state.battle_id, conn)
            st.session_state.game_result = result
            conn.close()
            st.rerun()
    
    with col_btn3:
        if st.button("🏆 End Battle", use_container_width=True):
            st.session_state.battle_active = False
            st.session_state.battle_id = random.randint(1000, 9999)
            st.session_state.player_team = []
            st.session_state.game_result = None
            st.rerun()
    
    if st.session_state.game_result:
        if st.session_state.game_result == "Player":
            st.success(f"🎉 {st.session_state.game_result} WINS! 🎉")
        elif st.session_state.game_result == "AI":
            st.error(f"💀 {st.session_state.game_result} WINS! 💀")
        else:
            st.warning(f"🤝 {st.session_state.game_result}")
    
    st.markdown("---")
    st.subheader("⚡ Current Battle Status")
    
    col_status1, col_status2 = st.columns(2)
    
    conn = get_db_connection()
    player_active = get_active_pokemon(st.session_state.battle_id, "Player", conn)
    ai_active = get_active_pokemon(st.session_state.battle_id, "AI", conn)
    
    with col_status1:
        if player_active is not None:
            hp_percent = (player_active['current_hp'] / player_active['max_hp']) * 100
            st.metric("Your Active", player_active['name'], f"HP: {player_active['current_hp']}/{player_active['max_hp']}")
            st.progress(hp_percent / 100)
    
    with col_status2:
        if ai_active is not None:
            hp_percent = (ai_active['current_hp'] / ai_active['max_hp']) * 100
            st.metric("AI Active", ai_active['name'], f"HP: {ai_active['current_hp']}/{ai_active['max_hp']}")
            st.progress(hp_percent / 100)
    
    st.markdown("---")
    st.subheader("📜 Battle Log")
    
    log_df = get_battle_log(st.session_state.battle_id, conn)
    conn.close()
    
    if not log_df.empty:
        for _, row in log_df.tail(15).iterrows():
            if row['event_type'] == 'attack':
                st.text(f"Turn {row['turn_number']}: {row['actor']} → {row['target']} ({row['details']}) for {row['damage']} damage!")
            elif row['event_type'] == 'faint':
                st.text(f"Turn {row['turn_number']}: {row['details']}")
            elif row['event_type'] == 'result':
                st.text(f"🏁 {row['details']}")
    else:
        st.info("Click 'Execute Turn' to start the battle!")
    
    with st.expander("🔍 Cheat Audit & Anomaly Detection"):
        conn = get_db_connection()
        audit = cheat_audit(st.session_state.battle_id, conn)
        if not audit.empty:
            st.dataframe(audit, use_container_width=True)
        
        anomalies = anomaly_detection(st.session_state.battle_id, conn)
        if not anomalies.empty:
            st.warning("⚠️ Stats exceeding natural limits detected!")
            st.dataframe(anomalies, use_container_width=True)
        conn.close()