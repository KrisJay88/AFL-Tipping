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
TEAM_LOGO_URL = "https://squiggle.com.au/wp-content/themes/squiggle/assets/images/logos/"
REFRESH_INTERVAL = 60  # seconds

# --- FUNCTIONS ---
def fetch_squiggle_games():
    response = requests.get(SQUIGGLE_GAMES_URL)
    data = response.json().get("games", [])
    rows = []
    for game in data:
        if "hteam" not in game or "ateam" not in game or "date" not in game:
            continue
        rows.append({
            "Match": f"{game['hteam']} vs {game['ateam']}",
            "Start Time": datetime.fromisoformat(game["date"]),
            "Venue": game.get("venue", "Unknown Venue"),
            "Home Team": game["hteam"],
            "Away Team": game["ateam"],
            "Home Odds": game.get("odds", {}).get("hteam", None),
            "Away Odds": game.get("odds", {}).get("ateam", None),
            "Match Preview": "No preview available."
        })
    return pd.DataFrame(rows)

def fetch_squiggle_tips():
    response = requests.get(SQUIGGLE_TIPS_URL)
    tips_data = response.json().get("tips", [])
    tips_list = []
    for tip in tips_data:
        tips_list.append({
            "Match": f"{tip['hteam']} vs {tip['ateam']}",
            "Source": tip["source"] or "Squiggle",
            "Tip": tip["tip"],
            "Confidence": tip.get("confidence", None)
        })
    return pd.DataFrame(tips_list)

def fetch_squiggle_scores():
    response = requests.get(SQUIGGLE_SCORES_URL)
    score_data = response.json().get("games", [])
    scores_list = []
    for game in score_data:
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
st.set_page_config(page_title="AFL Tipping Dashboard", layout="wide", initial_sidebar_state="expanded")
st.title("🏏 AFL Tipping Assistant Dashboard")

# Auto-refresh every 60 seconds
st_autorefresh(interval=REFRESH_INTERVAL * 1000, limit=None, key="autorefresh")
st.caption("⏱ This page auto-refreshes every 60 seconds to update scores and countdowns.")

with st.spinner("Fetching live games, tips, and scores..."):
    try:
        games_df = fetch_squiggle_games()
        tips_df = fetch_squiggle_tips()
        scores_df = fetch_squiggle_scores()

        combined_df = pd.merge(games_df, tips_df, on="Match", how="left")
        combined_df = pd.merge(combined_df, scores_df, on="Match", how="left")

        # Filters
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
                    st.image(get_team_logo(row['Home Team']), width=50)
                    st.image(get_team_logo(row['Away Team']), width=50)
                with col2:
                    st.markdown(f"**Venue**: {row['Venue']}")
                    st.markdown(f"**Home Odds**: {row['Home Odds']}")
                    st.markdown(f"**Away Odds**: {row['Away Odds']}")
                    if not pd.isna(row['Tip']):
                        st.markdown(f"**Squiggle Tip**: {row['Tip']} ({row['Confidence']}% confidence)")
                    if not pd.isna(row['Home Score']) and not pd.isna(row['Away Score']):
                        st.success(f"**Live Score:** {row['Home Team']} {int(row['Home Score'])} - {row['Away Team']} {int(row['Away Score'])}")
                    st.markdown("**Match Preview**:")
                    st.info(row['Match Preview'])

        st.subheader("🔥 Potential Upset Picks")
        upsets = filtered_df.copy()
        upsets = upsets[(upsets["Tip"] == upsets["Away Team"]) & (upsets["Away Odds"].fillna(0) > 2.5)]
        st.dataframe(upsets if not upsets.empty else "No big upsets found this week!")

        st.subheader("📊 Tip Confidence Overview")
        confidence_data = filtered_df.dropna(subset=["Confidence"])
        if not confidence_data.empty:
            fig, ax = plt.subplots()
            confidence_data.groupby("Tip")["Confidence"].mean().sort_values().plot(kind="barh", ax=ax)
            ax.set_xlabel("Average Confidence (%)")
            ax.set_title("Average Confidence by Tipped Team")
            st.pyplot(fig)
        else:
            st.info("No confidence data available from Squiggle.")

        st.subheader("📈 Summary Stats")
        if not confidence_data.empty:
            highest_conf = confidence_data.loc[confidence_data["Confidence"].idxmax()]
            st.markdown(f"**Highest Confidence Tip:** {highest_conf['Tip']} to win {highest_conf['Match']} with {highest_conf['Confidence']}% confidence")
        if not upsets.empty:
            best_upset = upsets.loc[upsets["Away Odds"].idxmax()]
            st.markdown(f"**Highest Odds Upset Pick:** {best_upset['Away Team']} to beat {best_upset['Home Team']} at odds {best_upset['Away Odds']}")

        # CSV Download Option
        st.markdown("\n---\n")
        st.markdown(generate_csv_download(filtered_df), unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")
