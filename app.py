import streamlit as st
import google.generativeai as genai
from github import Github
import json
import os
import random
import time

# Repo Config
GITHUB_REPO = "dandmin/DnDApp"
DATA_FILE = "aegis_data.json"

try:
    gemini_key = st.secrets["GEMINI_API_KEY"]
    github_token = st.secrets["GITHUB_TOKEN"] 
except FileNotFoundError:
    st.error("Secrets file not found. Please create .streamlit/secrets.toml")
    st.stop()

genai.configure(api_key=gemini_key)

# ==========================================
# 2. INITIAL STATE & DATA STRUCTURE
# ==========================================
DEFAULT_STATE = {
    "character": {"name": "Aegis", "class": "Ranger (Gloom Stalker)", "level": 3},
    "combat": {
        "hp": {"current": 22, "max": 28, "hit_dice_current": 2, "hit_dice_total": 3},
        "ac": 14, "initiative": 5, "speed": 30,
        "conditions": []
    },
    "resources": {
        "spell_slots": {"1": {"total": 3, "expended": 0}},
        "dreadful_strike": {"total": 3, "current": 3}, # Wis Mod (3) per Long Rest
        "favored_enemy": {"total": 2, "current": 2}
    },
    "attacks": [
        {"name": "Longbow", "bonus": 6, "damage": "1d8 + 2", "type": "Piercing", "mastery": "Slow"},
        {"name": "Scimitar", "bonus": 4, "damage": "1d6 + 2", "type": "Slashing", "mastery": "Nick"},
        {"name": "Shortbow", "bonus": 6, "damage": "1d6 + 2", "type": "Piercing", "mastery": "Vex"}
    ],
    "inventory": {"arrows": 67, "gold": 123}
}

if "sheet" not in st.session_state:
    st.session_state.sheet = DEFAULT_STATE

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "🏹 **Aegis Online.** Ready for adventure."}]

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def roll_dice(bonus, damage_str):
    """Simulates d20 + bonus and parses damage string."""
    d20 = random.randint(1, 20)
    total_hit = d20 + bonus
    
    # Simple damage parser
    try:
        dice_part, mod_part = damage_str.split('+')
        num, die = dice_part.strip().split('d')
        dmg_roll = random.randint(1, int(die))
        total_dmg = dmg_roll + int(mod_part)
    except:
        total_dmg = 0 # Fallback
    
    return d20, total_hit, total_dmg

def perform_rest(rest_type):
    """Handles 2024 Rules for Short vs Long Rest."""
    sheet = st.session_state.sheet
    
    if rest_type == "Long":
        sheet['combat']['hp']['current'] = sheet['combat']['hp']['max']
        sheet['resources']['spell_slots']['1']['expended'] = 0
        sheet['resources']['dreadful_strike']['current'] = sheet['resources']['dreadful_strike']['total']
        sheet['resources']['favored_enemy']['current'] = sheet['resources']['favored_enemy']['total']
        
        # Regain half hit dice
        total_hd = sheet['combat']['hp']['hit_dice_total']
        current_hd = sheet['combat']['hp']['hit_dice_current']
        regain = max(1, total_hd // 2)
        sheet['combat']['hp']['hit_dice_current'] = min(total_hd, current_hd + regain)
        
        sheet['combat']['conditions'] = []
        
        return "💤 **Long Rest Complete:** HP, Spells, and Abilities fully restored."
        
    elif rest_type == "Short":
        return "⏳ **Short Rest:** You catch your breath. Use the 'Spend Hit Die' button to heal."

# --- GITHUB PERSISTENCE ---
def load_from_github():
    token = os.environ.get("GITHUB_TOKEN")
    if not token: return None
    try:
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO)
        contents = repo.get_contents(DATA_FILE)
        return json.loads(contents.decoded_content.decode())
    except:
        return None

def save_to_github():
    token = os.environ.get("GITHUB_TOKEN")
    if not token: 
        st.error("No GitHub Token found.")
        return
    try:
        g = Github(token)
        repo = g.get_repo(GITHUB_REPO)
        try:
            contents = repo.get_contents(DATA_FILE)
            repo.update_file(contents.path, "Session Save", json.dumps(st.session_state.sheet, indent=2), contents.sha)
        except:
            repo.create_file(DATA_FILE, "Initial Save", json.dumps(st.session_state.sheet, indent=2))
        st.success("✅ Saved to GitHub!")
        time.sleep(1)
    except Exception as e:
        st.error(f"Save Error: {e}")

# ==========================================
# 4. UI LAYOUT
# ==========================================
st.set_page_config(layout="wide", page_title="Aegis Tracker", page_icon="🏹")

# --- SIDEBAR ---
with st.sidebar:
    st.header("💾 Campaign Save")
    if st.button("☁️ Load Game"):
        data = load_from_github()
        if data: 
            st.session_state.sheet = data
            st.rerun()
            
    if st.button("floppy_disk Save Game"):
        save_to_github()

    st.divider()
    
    st.subheader("❤️ Health & Rest")
    
    # HIT DICE LOGIC
    hd_cur = st.session_state.sheet['combat']['hp']['hit_dice_current']
    hd_max = st.session_state.sheet['combat']['hp']['hit_dice_total']
    st.write(f"**Hit Dice:** {hd_cur}/{hd_max} (d10)")
    
    if st.button("Bandage (Spend Hit Die)"):
        if hd_cur > 0:
            roll = random.randint(1, 10)
            con = 3 # Hardcoded CON mod based on sheet
            heal = roll + con
            curr = st.session_state.sheet['combat']['hp']['current']
            maxx = st.session_state.sheet['combat']['hp']['max']
            
            st.session_state.sheet['combat']['hp']['current'] = min(maxx, curr + heal)
            st.session_state.sheet['combat']['hp']['hit_dice_current'] -= 1
            
            st.session_state.messages.append({"role": "assistant", "content": f"🩹 **Short Rest:** Rolled {roll}+3. Healed **{heal} HP**."})
            st.rerun()
        else:
            st.error("No Hit Dice left!")
            
    col_r1, col_r2 = st.columns(2)
    if col_r1.button("Short Rest"):
        msg = perform_rest("Short")
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.rerun()
    if col_r2.button("Long Rest"):
        msg = perform_rest("Long")
        st.session_state.messages.append({"role": "assistant", "content": msg})
        st.rerun()

    st.divider()
    # Safety Backup
    st.download_button("⬇️ Download Backup", json.dumps(st.session_state.sheet), "aegis_backup.json")

# --- MAIN DASHBOARD ---
col1, col2 = st.columns([2, 1.2])

with col1:
    st.title(f"🛡️ {st.session_state.sheet['character']['name']}")
    
    # CONDITIONS
    conds = ["Invisible", "Prone", "Poisoned", "Frightened", "Grappled", "Hunter's Mark (Active)"]
    curr_conds = st.multiselect("Active Effects", conds, default=st.session_state.sheet['combat']['conditions'])
    st.session_state.sheet['combat']['conditions'] = curr_conds
    
    # HUD
    c1, c2, c3, c4 = st.columns(4)
    hp = st.session_state.sheet['combat']['hp']
    c1.metric("HP", f"{hp['current']} / {hp['max']}", delta=hp['current']-hp['max'])
    c2.metric("AC", st.session_state.sheet['combat']['ac'])
    c3.metric("Init", f"+{st.session_state.sheet['combat']['initiative']}")
    c4.metric("Speed", f"{st.session_state.sheet['combat']['speed']} ft")
    
    st.markdown("---")
    
    # ATTACKS & SPELLS
    row_a, row_b = st.columns(2)
    
    with row_a:
        st.subheader("⚔️ Weapons")
        for atk in st.session_state.sheet['attacks']:
            with st.container(border=True):
                wc1, wc2 = st.columns([3, 1])
                with wc1:
                    st.markdown(f"**{atk['name']}**")
                    # Nick/Slow/Vex Coloring
                    color = "orange" if atk['mastery'] == "Nick" else "blue"
                    st.caption(f"To Hit: +{atk['bonus']} | Dmg: {atk['damage']} | :{color}[**{atk['mastery']}**]")
                    
                    if atk['mastery'] == "Nick":
                        st.info("💡 **Nick:** Extra attack is part of Action (saves Bonus Action).")
                        
                with wc2:
                    if st.button("🎲", key=f"btn_{atk['name']}"):
                        d20, hit, dmg = roll_dice(atk['bonus'], atk['damage'])
                        
                        # Deduct arrow if bow
                        if "bow" in atk['name'].lower():
                            st.session_state.sheet['inventory']['arrows'] -= 1
                            
                        msg = f"⚔️ **{atk['name']}:** Rolled **{hit}** (Nat {d20}) for **{dmg}** damage."
                        if d20 == 20: msg += " 💥 **CRIT!**"
                        if d20 == 1: msg += " 💀 **MISS!**"
                        
                        st.session_state.messages.append({"role": "assistant", "content": msg})
                        st.rerun()

    with row_b:
        st.subheader("✨ Resources")
        
        # Spell Slots
        slots = st.session_state.sheet['resources']['spell_slots']['1']
        avail = slots['total'] - slots['expended']
        
        # Visual Slots
        slot_visual = "🟦 " * avail + "⬜ " * slots['expended']
        st.write(f"**1st Level:** {slot_visual}")
        
        b1, b2 = st.columns(2)
        if b1.button("Cast Spell"):
            if avail > 0:
                st.session_state.sheet['resources']['spell_slots']['1']['expended'] += 1
                st.rerun()
            else:
                st.toast("No slots!")
                
        if b2.button("Recover"):
            if slots['expended'] > 0:
                st.session_state.sheet['resources']['spell_slots']['1']['expended'] -= 1
                st.rerun()
                
        st.divider()
        
        # Dreadful Strike
        ds = st.session_state.sheet['resources']['dreadful_strike']
        st.write(f"**Dreadful Strike:** {ds['current']} / {ds['total']}")
        if st.button("Use Dreadful Strike (+2d6)"):
            if ds['current'] > 0:
                ds['current'] -= 1
                st.session_state.messages.append({"role": "assistant", "content": "🧠 **Psychic Damage:** +2d6 damage added!"})
                st.rerun()
                
        st.metric("Arrows", st.session_state.sheet['inventory']['arrows'])

# --- CHAT COLUMN ---
with col2:
    st.subheader("💬 Live Log")
    
    chat_box = st.container(height=600)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg['role']):
                st.markdown(msg['content'])
                
    if prompt := st.chat_input("Describe action (e.g. 'I drink a potion')..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # GEMINI CALL
        # We construct a prompt that includes the JSON state so the AI knows what's happening
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            system_context = f"""
            Role: You are a D&D 5e (2024 Rules) Assistant for Aegis.
            Current State: {json.dumps(st.session_state.sheet)}
            User Input: "{prompt}"
            
            Instructions:
            1. If the user describes an action (healing, item use), describe the mechanical result briefly.
            2. If they ask a rule question, answer using 2024 PHB rules.
            3. Keep it immersive but concise.
            """
            
            response = model.generate_content(system_context)
            ai_reply = response.text
            
            st.session_state.messages.append({"role": "assistant", "content": ai_reply})
            st.rerun()
        except Exception as e:
            st.error(f"AI Error: {e}")