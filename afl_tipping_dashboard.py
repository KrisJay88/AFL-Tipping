# afl_tipping_dashboard.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import base64
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
CURRENT_YEAR = datetime.now().year
SQUIGGLE_TEAMS_URL = "https://api.squiggle.com.au/?q=teams"
SQUIGGLE_GAMES_URL = f"https://api.squiggle.com.au/?q=games;year={CURRENT_YEAR}"
SQUIGGLE_TIPS_URL = f"https://api.squiggle.com.au/?q=tips;year={CURRENT_YEAR}"
TEAM_LOGO_URL = "https://squiggle.com.au/wp-content/themes/squiggle/assets/images/logos/"
REFRESH_INTERVAL = 60  # seconds

# --- FUNCTIONS ---
def get_team_name_map():
    try:
        response = requests.get(SQUIGGLE_TEAMS_URL)
        response.raise_for_status()
        data = response.json()
        if "teams" not in data:
            st.warning(f"Unexpected teams response: {data}")
            return {}
        teams = data["teams"]
        return {team["id"]: team["name"] for team in teams if "id" in team and "name" in team}
    except Exception as e:
        st.warning(f"Error fetching teams: {e}")
        return {}

def get_all_rounds(games):
    return sorted(set(game.get("round") for game in games if "round" in game))

def fetch_all_games():
    try:
        team_map = get_team_name_map()
        response = requests.get(SQUIGGLE_GAMES_URL)
        response.raise_for_status()
        games = response.json().get("games", [])

        rows = []
        for game in games:
            hteam_id = game.get("hteamid")
            ateam_id = game.get("ateamid")
            hteam_name = team_map.get(hteam_id, game.get("hteam", ""))
            ateam_name = team_map.get(ateam_id, game.get("ateam", ""))
            try:
                game_time = datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
            except:
                continue
            rows.append({
                "Game ID": game.get("id"),
                "Round": game.get("round"),
                "Start Time": game_time,
                "Venue": game.get("venue", "Unknown Venue"),
                "Home Team": hteam_name,
                "Away Team": ateam_name,
                "Home Team ID": hteam_id,
                "Away Team ID": ateam_id,
                "Home Odds": None,
                "Away Odds": None,
                "Match Preview": game.get("preview", "No preview available."),
                "Winner": game.get("winner")
            })
        return pd.DataFrame(rows), games
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching games: {e}, Status Code: {response.status_code}, Response: {response.text}")
        return pd.DataFrame(), []
    except Exception as e:
        st.warning(f"Unexpected error: {e}")
        return pd.DataFrame(), []

def fetch_squiggle_tips():
    try:
        response = requests.get(SQUIGGLE_TIPS_URL)
        response.raise_for_status()
        return response.json().get("tips", [])
    except Exception as e:
        st.warning(f"Error fetching tips: {e}")
        return []

def attach_tips_to_games(games_df, tips):
    tip_map = {(tip["gameid"], tip["source"]): tip for tip in tips if "gameid" in tip and "source" in tip}
    for idx, row in games_df.iterrows():
        for source in ["Squiggle", "Matter", "Mooseheads"]:
            tip = tip_map.get((row["Game ID"], source))
            if tip:
                games_df.at[idx, f"Tip by {source}"] = tip.get("tip")
    return games_df

# --- MAIN APP ---
st.title("AFL Tipping Dashboard")

# Autorefresh every 60 seconds
st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="data_refresh")

# Fetch all games
games_df, all_games = fetch_all_games()

if not games_df.empty:
    tips = fetch_squiggle_tips()
    games_df = attach_tips_to_games(games_df, tips)

    available_rounds = get_all_rounds(all_games)
    selected_round = st.selectbox("Select Round", options=available_rounds, index=len(available_rounds) - 1)
    filtered_games = games_df[games_df["Round"] == selected_round]

    if not filtered_games.empty:
        st.subheader(f"Games for Round {selected_round}")
        st.dataframe(filtered_games)
    else:
        st.warning("No games found for the selected round.")
else:
    st.warning("No game data available at the moment. Please try again later.")
