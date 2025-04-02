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
SQUIGGLE_TIPS_URL = f"https://api.squiggle.com.au/?q=tips;year={CURRENT_YEAR}"
SQUIGGLE_GAMES_URL = f"https://api.squiggle.com.au/?q=games;year={CURRENT_YEAR}"
SQUIGGLE_TEAMS_URL = "https://api.squiggle.com.au/?q=teams"
TEAM_LOGO_URL = "https://squiggle.com.au/wp-content/themes/squiggle/assets/images/logos/"
REFRESH_INTERVAL = 60  # seconds

# --- FUNCTIONS ---
def get_team_name_map():
    try:
        response = requests.get(SQUIGGLE_TEAMS_URL)
        response.raise_for_status()
        teams = response.json().get("teams", [])
        return {team["id"]: team["name"] for team in teams}
    except Exception as e:
        st.warning(f"Error fetching teams: {e}")
        return {}

def fetch_squiggle_games():
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
                "Match Preview": "No preview available."
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Error fetching games: {e}")
        return pd.DataFrame()

def fetch_squiggle_tips():
    try:
        response = requests.get(SQUIGGLE_TIPS_URL)
        response.raise_for_status()
        tips = response.json().get("tips", [])

        tips_list = []
        for tip in tips:
            tips_list.append({
                "Game ID": tip.get("gameid"),
                "Round": tip.get("round"),
                "Home Team ID": tip.get("hteamid"),
                "Away Team ID": tip.get("ateamid"),
                "Tip": tip.get("tip"),
                "Confidence": tip.get("confidence")
            })
        return pd.DataFrame(tips_list)
    except Exception as e:
        st.warning(f"Error fetching tips: {e}")
        return pd.DataFrame()

def merge_games_and_tips(games_df, tips_df):
    if games_df.empty:
        return games_df
    return pd.merge(
        games_df,
        tips_df[["Game ID", "Tip", "Confidence"]],
        on="Game ID",
        how="left"
    )

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
        all_games = fetch_squiggle_games()
        tips_df = fetch_squiggle_tips()

        if all_games.empty:
            st.info("No game data available at the moment. Please try again later.")
        else:
            available_rounds = sorted(all_games["Round"].dropna().unique())
            selected_round = st.sidebar.selectbox("Select Round", available_rounds)

            games_df = all_games[all_games["Round"] == selected_round]
            combined_df = merge_games_and_tips(games_df, tips_df)

            st.sidebar.header("🔍 Filters")
            all_teams = sorted(set(combined_df["Home Team"]).union(combined_df["Away Team"]))
            selected_team = st.sidebar.selectbox("Filter by team", ["All"] + all_teams)
            min_conf = st.sidebar.slider("Minimum confidence %", 0, 100, 0)
            show_upcoming_only = st.sidebar.checkbox("Show only upcoming games", True)

            filtered_df = combined_df.copy()
            if selected_team != "All":
                filtered_df = filtered_df[(filtered_df["Home Team"] == selected_team) | (filtered_df["Away Team"] == selected_team)]
            if min_conf > 0:
                filtered_df = filtered_df[filtered_df["Confidence"].fillna(0) >= min_conf]
            if show_upcoming_only:
                filtered_df = filtered_df[filtered_df["Start Time"] > datetime.utcnow()]

            st.subheader(f"🔢 Matches - Round {selected_round}")
            for _, row in filtered_df.sort_values("Start Time").iterrows():
                with st.expander(f"{row['Home Team']} vs {row['Away Team']} — {row['Start Time'].strftime('%a, %b %d %I:%M %p')} | Countdown: {format_countdown(row['Start Time'])}"):
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
                        st.markdown("**Match Preview:**")
                        st.info(row["Match Preview"])

            st.subheader("🔥 Potential Upset Picks")
            upsets = filtered_df[(filtered_df["Tip"] == filtered_df["Away Team"]) & (filtered_df["Away Odds"].fillna(0) > 2.5)]
            st.dataframe(upsets if not upsets.empty else pd.DataFrame([{"Message": "No big upsets found this week!"}]))

            st.subheader("📊 Tip Confidence Overview")
            conf_data = filtered_df.dropna(subset=["Confidence"])
            if not conf_data.empty:
                fig, ax = plt.subplots()
                conf_data.groupby("Tip")["Confidence"].mean().sort_values().plot(kind="barh", ax=ax)
                ax.set_xlabel("Average Confidence (%)")
                ax.set_title("Average Confidence by Tipped Team")
                st.pyplot(fig)

            st.subheader("🏅 Tip Counts This Round")
            tip_counts = filtered_df["Tip"].value_counts().reset_index()
            tip_counts.columns = ["Team", "Tip Count"]
            st.dataframe(tip_counts)

            st.subheader("📈 Summary Stats")
            if not conf_data.empty:
                top = conf_data.loc[conf_data["Confidence"].idxmax()]
                st.markdown(f"**Top Tip:** {top['Tip']} to win {top['Home Team']} vs {top['Away Team']} with {top['Confidence']}% confidence")
            if not upsets.empty:
                big = upsets.loc[upsets["Away Odds"].idxmax()]
                st.markdown(f"**Biggest Upset Pick:** {big['Away Team']} to beat {big['Home Team']} at odds {big['Away Odds']}")

            st.markdown(generate_csv_download(filtered_df), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
