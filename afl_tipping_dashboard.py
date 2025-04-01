# afl_tipping_dashboard.py
import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import base64
import time

# --- CONFIG ---
THEODDSAPI_KEY = "849ff96f89e0f4a7269be8118f300b8c"
SQUIGGLE_URL = "https://api.squiggle.com.au/?q=tips"
TEAM_LOGO_URL = "https://squiggle.com.au/wp-content/themes/squiggle/assets/images/logos/"  # Base URL for logos

# --- FUNCTIONS ---
def fetch_theoddsapi_odds():
    url = f"https://api.theoddsapi.com/v4/sports/aussierules_afl/odds/?apiKey={THEODDSAPI_KEY}&regions=au&markets=h2h&oddsFormat=decimal"
    response = requests.get(url)
    data = response.json()

    odds_list = []
    for match in data:
        if not match.get("bookmakers"):
            continue
        for bookmaker in match["bookmakers"]:
            for market in bookmaker["markets"]:
                if market["key"] != "h2h":
                    continue
                row = {
                    "Match": f"{match['home_team']} vs {match['away_team']}",
                    "Start Time": datetime.fromisoformat(match["commence_time"].replace("Z", "+00:00")),
                    "Bookmaker": bookmaker["title"],
                    "Home Team": match["home_team"],
                    "Away Team": match["away_team"],
                    "Venue": match.get("venue", "Unknown Venue"),
                    "Match Preview": match.get("description", "No preview available.")
                }
                for outcome in market["outcomes"]:
                    if outcome["name"] == match['home_team']:
                        row["Home Odds"] = outcome["price"]
                    elif outcome["name"] == match['away_team']:
                        row["Away Odds"] = outcome["price"]
                odds_list.append(row)
    return pd.DataFrame(odds_list)

def fetch_squiggle_tips():
    response = requests.get(SQUIGGLE_URL)
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
        return str(timedelta(seconds=int(delta.total_seconds())))
    return "Kick-off!"

# --- MAIN APP ---
st.title("🏏 AFL Tipping Assistant Dashboard")

with st.spinner("Fetching live odds and tips..."):
    try:
        odds_df = fetch_theoddsapi_odds()
        tips_df = fetch_squiggle_tips()

        combined_df = pd.merge(odds_df, tips_df, on="Match", how="left")

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

        st.subheader("🔢 Full Odds Table")
        for _, row in filtered_df.sort_values("Start Time").iterrows():
            with st.expander(f"{row['Match']} — {row['Start Time'].strftime('%a, %b %d %I:%M %p')} | Countdown: {format_countdown(row['Start Time'])}"):
                col1, col2 = st.columns([1, 6])
                with col1:
                    st.image(get_team_logo(row['Home Team']), width=50)
                    st.image(get_team_logo(row['Away Team']), width=50)
                with col2:
                    st.markdown(f"**Venue**: {row['Venue']}")
                    st.markdown(f"**Bookmaker**: {row['Bookmaker']}")
                    st.markdown(f"**Home Odds**: {row['Home Odds']}")
                    st.markdown(f"**Away Odds**: {row['Away Odds']}")
                    if not pd.isna(row['Tip']):
                        st.markdown(f"**Squiggle Tip**: {row['Tip']} ({row['Confidence']}% confidence)")
                    st.markdown("**Match Preview**:")
                    st.info(row['Match Preview'])

        st.subheader("🔥 Potential Upset Picks")
        upsets = filtered_df.copy()
        upsets = upsets[(upsets["Tip"] == upsets["Away Team"]) & (upsets["Away Odds"] > 2.5)]
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
