import streamlit as st
import pandas as pd
import sqlite3
import random
import os

st.set_page_config(page_title="Pokémon Battle Arena", page_icon="⚔️", layout="wide")

DB_PATH = "pokemon_battle.db"

def init_database():
    """Initialize database with Pokémon data"""
    
    if os.path.exists(DB_PATH):
        return True
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create tables
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
    
    c.execute("""
    CREATE TABLE type_effectiveness (
        attacking_type TEXT NOT NULL,
        defending_type TEXT NOT NULL,
        multiplier REAL NOT NULL
    )
    """)
    
    c.execute("""
    CREATE TABLE battle_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        turn_number INTEGER,
        event_type TEXT NOT NULL,
        actor TEXT,
        target TEXT,
        details TEXT,
        damage INTEGER
    )
    """)
    
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
    
    c.execute("""
    CREATE TABLE cheat_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        battle_id INTEGER NOT NULL,
        cheat_code TEXT NOT NULL,
        player_label TEXT NOT NULL,
        description TEXT
    )
    """)
    
    # Load CSV - use chunks to avoid memory issues
    df = pd.read_csv("pokemon.csv")
    
    # Clean column names
    df.columns = [col.strip().lower().replace(" ", "_").replace(".", "") for col in df.columns]
    
    # Map columns
    df = df.rename(columns={
        'pokedex_number': 'id',
        'sp_attack': 'sp_atk',
        'sp_defense': 'sp_def',
        'is_legendary': 'legendary'
    })
    
    # Insert in batches
    batch_size = 100
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]
        for _, row in batch.iterrows():
            type2 = row['type2'] if pd.notna(row['type2']) else None
            c.execute("""
            INSERT INTO pokemon (id, name, type1, type2, hp, attack, defense, sp_atk, sp_def, speed, generation, legendary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (int(row['id']), row['name'], row['type1'], type2, int(row['hp']), int(row['attack']),
                  int(row['defense']), int(row['sp_atk']), int(row['sp_def']), int(row['speed']),
                  int(row['generation']), int(row['legendary'])))
    
    # Add type effectiveness
    type_effects = [
        ("Fire", "Grass", 2.0), ("Fire", "Water", 0.5), ("Water", "Fire", 2.0),
        ("Water", "Grass", 0.5), ("Grass", "Water", 2.0), ("Grass", "Fire", 0.5),
        ("Electric", "Water", 2.0), ("Psychic", "Fighting", 2.0), ("Fighting", "Normal", 2.0)
    ]
    c.executemany("INSERT INTO type_effectiveness (attacking_type, defending_type, multiplier) VALUES (?, ?, ?)", type_effects)
    
    conn.commit()
    conn.close()
    return True

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def get_all_pokemon():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT name, type1, hp, attack, defense, speed FROM pokemon ORDER BY name", conn)
    conn.close()
    return df

def create_team(battle_id, player_label, pokemon_names, conn):
    c = conn.cursor()
    c.execute("DELETE FROM team_pokemon WHERE battle_id = ? AND player_label = ?", (battle_id, player_label))
    
    for i, name in enumerate(pokemon_names, 1):
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
        cols = [desc[0] for desc in c.description]
        return dict(zip(cols, row))
    return None

def apply_damage(pokemon_id, damage, conn):
    c = conn.cursor()
    c.execute("SELECT current_hp FROM team_pokemon WHERE id = ?", (pokemon_id,))
    result = c.fetchone()
    if result:
        new_hp = max(0, result[0] - damage)
        c.execute("UPDATE team_pokemon SET current_hp = ? WHERE id = ?", (new_hp, pokemon_id))
        conn.commit()
        return new_hp
    return 0

def is_team_alive(battle_id, player_label, conn):
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM team_pokemon WHERE battle_id = ? AND player_label = ? AND current_hp > 0", (battle_id, player_label))
    return c.fetchone()[0] > 0

def log_event(battle_id, turn, event_type, conn, **kwargs):
    c = conn.cursor()
    c.execute("INSERT INTO battle_log (battle_id, turn_number, event_type, actor, target, details, damage) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (battle_id, turn, event_type, kwargs.get('actor'), kwargs.get('target'), kwargs.get('details'), kwargs.get('damage')))
    conn.commit()

def execute_turn(battle_id, turn, conn):
    p1 = get_active_pokemon(battle_id, "Player", conn)
    p2 = get_active_pokemon(battle_id, "AI", conn)
    if not p1 or not p2:
        return False
    
    if p1['speed'] >= p2['speed']:
        first, second = p1, p2
    else:
        first, second = p2, p1
    
    # Simple damage calculation
    damage = max(1, int((first['attack'] / max(1, second['defense'])) * 10))
    new_hp = apply_damage(second['id'], damage, conn)
    log_event(battle_id, turn, "attack", conn, actor=first['name'], target=second['name'], details="NORMAL HIT", damage=damage)
    
    if new_hp == 0:
        log_event(battle_id, turn, "faint", conn, details=f"{second['name']} fainted!")
        return True
    
    damage = max(1, int((second['attack'] / max(1, first['defense'])) * 10))
    new_hp = apply_damage(first['id'], damage, conn)
    log_event(battle_id, turn, "attack", conn, actor=second['name'], target=first['name'], details="NORMAL HIT", damage=damage)
    
    if new_hp == 0:
        log_event(battle_id, turn, "faint", conn, details=f"{first['name']} fainted!")
    return True

def run_battle(battle_id, conn):
    turn = 1
    while turn <= 100:
        if not is_team_alive(battle_id, "Player", conn):
            log_event(battle_id, turn, "result", conn, details="AI WINS!")
            return "AI"
        if not is_team_alive(battle_id, "AI", conn):
            log_event(battle_id, turn, "result", conn, details="PLAYER WINS!")
            return "Player"
        execute_turn(battle_id, turn, conn)
        turn += 1
    log_event(battle_id, turn, "result", conn, details="DRAW")
    return "Draw"

def get_battle_log(battle_id, conn):
    return pd.read_sql_query("SELECT turn_number, event_type, actor, target, details, damage FROM battle_log WHERE battle_id = ? ORDER BY id", conn, params=(battle_id,))

# Initialize
if 'db_initialized' not in st.session_state:
    with st.spinner("Loading Pokémon data..."):
        init_database()
        st.session_state.db_initialized = True
        st.session_state.battle_id = random.randint(1000, 9999)
        st.session_state.battle_active = False
        st.session_state.player_team = []
        st.session_state.game_result = None

st.title("⚔️ Pokémon Battle Arena")

# Sidebar
with st.sidebar:
    st.header("Select Your Team")
    pokemon_df = get_all_pokemon()
    pokemon_names = pokemon_df['name'].tolist()
    
    selected_team = []
    for i in range(3):
        pokemon = st.selectbox(f"Pokémon {i+1}", ["None"] + pokemon_names, key=f"p{i}")
        if pokemon != "None":
            selected_team.append(pokemon)
    
    if st.button("Start Battle", disabled=len(selected_team)==0):
        conn = get_db_connection()
        create_team(st.session_state.battle_id, "Player", selected_team, conn)
        ai_team = random.sample(pokemon_names, min(3, len(pokemon_names)))
        create_team(st.session_state.battle_id, "AI", ai_team, conn)
        conn.close()
        st.session_state.player_team = selected_team
        st.session_state.battle_active = True
        st.rerun()

# Main
if not st.session_state.battle_active:
    st.subheader("Pokémon Data Analysis")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT generation, AVG(hp+attack+defense+sp_atk+sp_def+speed) as avg_total FROM pokemon GROUP BY generation ORDER BY generation", conn)
    conn.close()
    if not df.empty:
        st.dataframe(df)
        st.line_chart(df.set_index('generation'))
else:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Your Team")
        for p in st.session_state.player_team:
            st.info(p)
    with col2:
        st.subheader("AI Team")
        conn = get_db_connection()
        ai_df = pd.read_sql_query("SELECT name FROM team_pokemon WHERE battle_id=? AND player_label='AI'", conn, params=(st.session_state.battle_id,))
        conn.close()
        for _, row in ai_df.iterrows():
            st.warning(row['name'])
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Execute Turn"):
            conn = get_db_connection()
            if is_team_alive(st.session_state.battle_id, "Player", conn) and is_team_alive(st.session_state.battle_id, "AI", conn):
                execute_turn(st.session_state.battle_id, st.session_state.get('turn', 0)+1, conn)
                st.session_state.turn = st.session_state.get('turn', 0) + 1
                if not is_team_alive(st.session_state.battle_id, "Player", conn):
                    st.session_state.game_result = "AI"
                elif not is_team_alive(st.session_state.battle_id, "AI", conn):
                    st.session_state.game_result = "Player"
            conn.close()
            st.rerun()
    with col2:
        if st.button("Auto Battle"):
            conn = get_db_connection()
            result = run_battle(st.session_state.battle_id, conn)
            st.session_state.game_result = result
            conn.close()
            st.rerun()
    with col3:
        if st.button("End Battle"):
            st.session_state.battle_active = False
            st.rerun()
    
    if st.session_state.game_result:
        if st.session_state.game_result == "Player":
            st.success("YOU WIN!")
        else:
            st.error("AI WINS!")
    
    st.markdown("---")
    conn = get_db_connection()
    log_df = get_battle_log(st.session_state.battle_id, conn)
    conn.close()
    for _, row in log_df.tail(10).iterrows():
        if row['event_type'] == 'attack':
            st.text(f"Turn {row['turn_number']}: {row['actor']} → {row['target']} for {row['damage']} damage")
        elif row['event_type'] == 'faint':
            st.text(f"💀 {row['details']}")
        elif row['event_type'] == 'result':
            st.text(f"🏆 {row['details']}")