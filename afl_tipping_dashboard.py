# afl_tipping_dashboard.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import base64
from streamlit_autorefresh import st_autorefresh

# --- CONFIG ---
SQUIGGLE_TIPS_URL = "https://api.squiggle.com.au/?q=tips"
SQUIGGLE_GAMES_URL = "https://api.squiggle.com.au/?q=games;year=2024"
SQUIGGLE_SCORES_URL = "https://api.squiggle.com.au/?q=scores"
SQUIGGLE_TEAMS_URL = "https://api.squiggle.com.au/?q=teams"
TEAM_LOGO_URL = "https://squiggle.com.au/wp-content/themes/squiggle/assets/images/logos/"
REFRESH_INTERVAL = 60  # seconds

# --- FUNCTIONS ---
def get_team_name_map():
    response = requests.get(SQUIGGLE_TEAMS_URL)
    teams = response.json().get("teams", [])
    return {team["id"]: team["name"] for team in teams if "id" in team and "name" in team}

def fetch_squiggle_games():
    team_map = get_team_name_map()
    response = requests.get(SQUIGGLE_GAMES_URL)
    data = response.json().get("games", [])
    rows = []
    for game in data:
        if not all(k in game for k in ("hteamid", "ateamid", "date")):
            continue
        hteam_id = game["hteamid"]
        ateam_id = game["ateamid"]
        hteam_name = team_map.get(hteam_id, str(hteam_id))
        ateam_name = team_map.get(ateam_id, str(ateam_id))

        # Attempt to extract odds if present
        home_odds = game.get("odds", {}).get(str(hteam_id))
        away_odds = game.get("odds", {}).get(str(ateam_id))

        rows.append({
            "Match": f"{hteam_name} vs {ateam_name}",
            "Start Time": datetime.fromisoformat(game["date"]),
            "Venue": game.get("venue", "Unknown Venue"),
            "Home Team": hteam_name,
            "Away Team": ateam_name,
            "Home Odds": home_odds,
            "Away Odds": away_odds,
            "Match Preview": "No preview available."
        })
    return pd.DataFrame(rows)

def fetch_squiggle_tips():
    team_map = get_team_name_map()
    response = requests.get(SQUIGGLE_TIPS_URL)
    tips_data = response.json().get("tips", [])
    tips_list = []
    for tip in tips_data:
        if not all(k in tip for k in ("hteamid", "ateamid")):
            continue
        hteam_name = team_map.get(tip["hteamid"], str(tip["hteamid"]))
        ateam_name = team_map.get(tip["ateamid"], str(tip["ateamid"]))
        tips_list.append({
            "Match": f"{hteam_name} vs {ateam_name}",
            "Source": tip.get("source", "Unknown"),
            "Tip": tip.get("tip", ""),
            "Confidence": tip.get("confidence", None)
        })
    return pd.DataFrame(tips_list)

def fetch_squiggle_scores():
    response = requests.get(SQUIGGLE_SCORES_URL)
    scores_data = response.json().get("games", [])
    scores_list = []
    for game in scores_data:
        scores_list.append({
            "Match": f"{game['hteam']} vs {game['ateam']}",
            "Home Score": game.get("hscore"),
            "Away Score": game.get("ascore")
        })
    return pd.DataFrame(scores_list)

def get_team_logo(team_name):
    formatted = team_name.lower().replace(" ", "-").replace("&", "and")
    return f"{TEAM_LOGO_URL}{formatted}.svg"

def generate_csv_download(df):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="afl_tips.csv">📥 Download Tips as CSV</a>'
    return href

def format_countdown(start_time):
    now = datetime.utcnow()
    delta = start_time - now
    if delta.total_seconds() > 0:
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return "Kick-off!"

# --- MAIN APP ---
st.set_page_config(page_title="AFL Tipping Dashboard", layout="wide")
st.title("🏏 AFL Tipping Assistant Dashboard")
st_autorefresh(interval=REFRESH_INTERVAL * 1000, limit=None, key="refresh")
st.caption("⏱ This page auto-refreshes every 60 seconds to update scores and countdowns.")

with st.spinner("Fetching live games, tips, and scores..."):
    try:
        games_df = fetch_squiggle_games()
        tips_df = fetch_squiggle_tips()
        scores_df = fetch_squiggle_scores()

        combined_df = pd.merge(games_df, tips_df, on="Match", how="left")
        combined_df = pd.merge(combined_df, scores_df, on="Match", how="left")

        # Sidebar filters
        st.sidebar.header("🔍 Filters")
        all_teams = sorted(set(combined_df["Home Team"].unique()) | set(combined_df["Away Team"].unique()))
        selected_team = st.sidebar.selectbox("Filter by team", ["All"] + all_teams)
        min_conf = st.sidebar.slider("Minimum confidence %", 0, 100, 0)

        filtered_df = combined_df.copy()
        if selected_team != "All":
            filtered_df = filtered_df[(filtered_df["Home Team"] == selected_team) | (filtered_df["Away Team"] == selected_team)]
        if min_conf > 0:
            filtered_df = filtered_df[filtered_df["Confidence"].fillna(0) >= min_conf]

        st.subheader("🔢 Full Match Table")
        for _, row in filtered_df.sort_values("Start Time").iterrows():
            with st.expander(f"{row['Match']} — {row['Start Time'].strftime('%a, %b %d %I:%M %p')} | Countdown: {format_countdown(row['Start Time'])}"):
                col1, col2 = st.columns([1, 6])
                with col1:
                    st.image(get_team_logo(row["Home Team"]), width=50)
                    st.image(get_team_logo(row["Away Team"]), width=50)
                with col2:
                    st.markdown(f"**Venue**: {row['Venue']}")
                    st.markdown(f"**Home Odds**: {row['Home Odds']}")
                    st.markdown(f"**Away Odds**: {row['Away Odds']}")
                    if pd.notna(row["Tip"]):
                        st.markdown(f"**Squiggle Tip**: {row['Tip']} ({row['Confidence']}% confidence)")
                    if pd.notna(row["Home Score"]) and pd.notna(row["Away Score"]):
                        st.success(f"**Live Score:** {row['Home Team']} {int(row['Home Score'])} - {row['Away Team']} {int(row['Away Score'])}")
                    st.markdown("**Match Preview**:")
                    st.info(row["Match Preview"])

        st.subheader("🔥 Potential Upset Picks")
        upsets = filtered_df[(filtered_df["Tip"] == filtered_df["Away Team"]) & (filtered_df["Away Odds"].fillna(0) > 2.5)]
        st.dataframe(upsets if not upsets.empty else "No big upsets found this week!")

        st.subheader("📊 Tip Confidence Overview")
        conf_data = filtered_df.dropna(subset=["Confidence"])
        if not conf_data.empty:
            fig, ax = plt.subplots()
            conf_data.groupby("Tip")["Confidence"].mean().sort_values().plot(kind="barh", ax=ax)
            ax.set_xlabel("Average Confidence (%)")
            ax.set_title("Average Confidence by Tipped Team")
            st.pyplot(fig)

        st.subheader("📈 Summary Stats")
        if not conf_data.empty:
            top = conf_data.loc[conf_data["Confidence"].idxmax()]
            st.markdown(f"**Top Tip:** {top['Tip']} to win {top['Match']} ({top['Confidence']}% confidence)")
        if not upsets.empty:
            big = upsets.loc[upsets["Away Odds"].idxmax()]
            st.markdown(f"**Biggest Upset Pick:** {big['Away Team']} to beat {big['Home Team']} at odds {big['Away Odds']}")

        st.markdown(generate_csv_download(filtered_df), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
