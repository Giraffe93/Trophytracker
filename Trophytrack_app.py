import streamlit as st
import pandas as pd
import json
import re
from io import BytesIO
import os

EXCEL_FILE = "trophy_tracker.xlsx"

def load_excel():
    if not os.path.exists(EXCEL_FILE):
        return pd.DataFrame(), []
    workbook = pd.ExcelFile(EXCEL_FILE)
    game_sheets = [sheet for sheet in workbook.sheet_names if sheet not in ['Dashboard', 'GameTags', 'Data', 'Checklist', 'TrophyDetails', 'Lookup']]
    if not game_sheets:
        return pd.DataFrame(), []
    all_trophies = pd.concat([workbook.parse(sheet) for sheet in game_sheets], ignore_index=True)
    return all_trophies, game_sheets

def save_session_plan(df):
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df.to_excel(writer, sheet_name="SessionPlan", index=False)

def load_session_plan():
    if os.path.exists(EXCEL_FILE):
        try:
            df = pd.read_excel(EXCEL_FILE, sheet_name="SessionPlan")
            return df
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()

def save_checklist_progress(trophy_name, checklist_progress):
    all_trophies, _ = load_excel()
    trophy_indices = all_trophies[all_trophies['Trophy Name'] == trophy_name].index
    if trophy_indices.empty:
        st.error(f"Trophy '{trophy_name}' not found. Checklist progress not saved.")
        return
    idx = trophy_indices[0]
    all_trophies.at[idx, 'Checklist Progress'] = json.dumps(checklist_progress)
    with pd.ExcelWriter(EXCEL_FILE, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        all_trophies.to_excel(writer, sheet_name="Checklist", index=False)

def extract_checklist_items(guide_text):
    bullets = re.findall(r"(?:^|\n)[•\-\*\d\.]+\s*(.+)", guide_text)
    if bullets:
        return [item.strip() for item in bullets if item.strip()]
    if ',' in guide_text:
        return [item.strip() for item in guide_text.split(',') if item.strip()]
    if ';' in guide_text:
        return [item.strip() for item in guide_text.split(';') if item.strip()]
    return [guide_text.strip()] if guide_text.strip() else []

st.set_page_config(page_title="Trophy Tracker Assistant", layout="wide")

# --- Navigation with sync on page change ---
if 'page' not in st.session_state:
    st.session_state['page'] = "Dashboard"

pages = ["Dashboard", "Planning", "Game Night", "Trophy Details"]
selected_page = st.selectbox("Navigate", pages, index=pages.index(st.session_state['page']))

if selected_page != st.session_state['page']:
    st.session_state['page'] = selected_page
    st.experimental_rerun()

# --- Sync Now button ---
if st.button("Sync Now"):
    st.experimental_rerun()

all_trophies, game_sheets = load_excel()

if not all_trophies.empty:
    if st.session_state['page'] == "Dashboard":
        st.markdown("<h2 style='text-align: center;'>📊 Trophy Tracker Dashboard</h2>", unsafe_allow_html=True)
        total_games = len(game_sheets)
        total_trophies = len(all_trophies)
        trophies_earned = all_trophies['Date Earned'].notna().sum()
        st.metric("Total Games", total_games)
        st.subheader("Trophy Type Distribution")
        trophy_counts = all_trophies['Trophy Type'].value_counts()
        # Limit to top 10 trophy types for performance
        limited_counts = trophy_counts.head(10)
        @st.cache_resource
        def get_pie_chart(data):
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4,4))
        st.subheader("Completion Rate by Game")
        completion_by_game = all_trophies.groupby('Game').agg(
            total_trophies=('Trophy Name', 'count'),
            earned_trophies=('Date Earned', lambda x: x.notna().sum())
        )
        completion_by_game['Completion Rate'] = completion_by_game['earned_trophies'] / completion_by_game['total_trophies']
        st.bar_chart(completion_by_game['Completion Rate'])
        st.subheader("Trophy Type Distribution")
        trophy_counts = all_trophies['Trophy Type'].value_counts()
        st.pyplot(pd.Series(trophy_counts).plot.pie(autopct='%1.1f%%', figsize=(4,4)).get_figure())

        st.subheader("Completion Rate by Game")
        completion_by_game = all_trophies.groupby('Game').apply(
            lambda df: df['Date Earned'].notna().sum() / len(df) if len(df) > 0 else 0
        )
        st.bar_chart(completion_by_game)

        # New Section: Time Tracking
        st.subheader("Time Tracking")
        total_time = all_trophies['Estimated Time'].sum()
        earned_time = all_trophies[all_trophies['Date Earned'].notna()]['Estimated Time'].sum()
        percent_complete = earned_time / total_time if total_time else 0
        st.progress(percent_complete, text=f"Time Earned: {earned_time} hrs / Total Time: {total_time} hrs")

        # New Time Breakdown Sections
        st.subheader("Time Breakdown by Trophy Category")
        category_breakdown = all_trophies.groupby('Trophy Category')['Estimated Time'].sum()
        st.bar_chart(category_breakdown)

        st.subheader("Time Breakdown by Game Run Type")
        run_type_breakdown = all_trophies.groupby('Game Run Type')['Estimated Time'].sum()
        st.bar_chart(run_type_breakdown)

        st.subheader("Estimated Time Remaining by Game")
        time_remaining = all_trophies[all_trophies['Date Earned'].isna()].groupby('Game')['Estimated Time'].sum()
        st.bar_chart(time_remaining)

    elif st.session_state['page'] == "Planning":
        st.markdown("<h2 style='text-align: center;'>📝 Plan Your Session</h2>", unsafe_allow_html=True)
        with st.expander("Filter & Sort Options", expanded=True):
            trophy_types = all_trophies['Trophy Type'].dropna().unique().tolist()
            selected_types = st.multiselect("Trophy Type", trophy_types, default=trophy_types)
            consoles = all_trophies['Console'].dropna().unique().tolist()
            selected_consoles = st.multiselect("Console", consoles, default=consoles)
            dlc_options = all_trophies['DLC'].dropna().unique().tolist()
            selected_dlc = st.multiselect("DLC", dlc_options, default=dlc_options)
            guide_options = ["Yes", "No"]
            selected_guide = st.multiselect("Guide Available", guide_options, default=guide_options)
            checklist_required = st.selectbox("Checklist Required", ["Any", "Yes", "No"])
            min_difficulty, max_difficulty = st.slider("Difficulty Range", 1, 10, (1, 5))
            min_time, max_time = st.slider("Estimated Time (hrs)", 0, 100, (0, 10)) if 'Estimated Time' in all_trophies.columns else (None, None)
            rarity_options = all_trophies['Rarity'].dropna().unique().tolist() if 'Rarity' in all_trophies.columns else []
            selected_rarity = st.multiselect("Rarity", rarity_options, default=rarity_options) if rarity_options else []
            session_types = all_trophies['Session Type'].dropna().unique().tolist()
            selected_session = st.multiselect("Session Type", session_types, default=session_types)
            multiplayer_only = st.checkbox("Multiplayer Only")
            not_earned = st.checkbox("Show Only Not Earned")
            trophy_name_search = st.text_input("Search Trophy Name")
            description_search = st.text_input("Search Description")
            # Sorting
            sort_column = st.selectbox("Sort By", all_trophies.columns.tolist())
            sort_ascending = st.radio("Sort Order", ["Ascending", "Descending"]) == "Ascending"
        
        filtered = all_trophies.copy()
        if selected_types:
            filtered = filtered[filtered['Trophy Type'].isin(selected_types)]
        if selected_consoles:
            filtered = filtered[filtered['Console'].isin(selected_consoles)]
        if selected_dlc:
            filtered = filtered[filtered['DLC'].isin(selected_dlc)]
        if selected_guide:
            filtered = filtered[filtered['Guide Available'].isin(selected_guide)]
        if checklist_required != "Any":
            # Filter by checklist requirement
            required = True if checklist_required == "Yes" else False
            if 'Checklist Required' in filtered.columns:
                filtered = filtered[filtered['Checklist Required'] == required]
            # Filter by difficulty inside this block if column exists
            if 'Difficulty' in filtered.columns and pd.api.types.is_numeric_dtype(filtered['Difficulty']):
                filtered = filtered[(filtered['Difficulty'] >= min_difficulty) & (filtered['Difficulty'] <= max_difficulty)]
        if (
            min_time is not None and max_time is not None and
            'Estimated Time' in filtered.columns and
            pd.api.types.is_numeric_dtype(filtered['Estimated Time'])
        ):
            filtered = filtered[(filtered['Estimated Time'] >= min_time) & (filtered['Estimated Time'] <= max_time)]
            filtered = filtered[(filtered['Estimated Time'] >= min_time) & (filtered['Estimated Time'] <= max_time)]
        if selected_rarity:
            filtered = filtered[filtered['Rarity'].isin(selected_rarity)]
        if selected_session:
            filtered = filtered[filtered['Session Type'].isin(selected_session)]
        if multiplayer_only:
            filtered = filtered[filtered['Multiplayer'] == True]
        if not_earned:
            filtered = filtered[filtered['Date Earned'].isna()]
        if trophy_name_search:
            filtered = filtered[filtered['Trophy Name'].str.contains(trophy_name_search, case=False, na=False)]
        if description_search:
            filtered = filtered[filtered['Description'].str.contains(description_search, case=False, na=False)]
        # Sorting
        if sort_column in filtered.columns:
            filtered = filtered.sort_values(by=sort_column, ascending=sort_ascending)
        
        st.subheader("🎯 Filtered & Sorted Trophy Opportunities")
        st.dataframe(filtered)

        if not filtered.empty:
            selected_indices = st.multiselect(
                "Select trophies for tonight's session:",
                filtered.index,
                format_func=lambda idx: f"{filtered.loc[idx, 'Game']} - {filtered.loc[idx, 'Trophy Name']}"
            )
            session_plan = filtered.loc[selected_indices] if selected_indices else pd.DataFrame()
            st.write("Session Plan:")
            st.dataframe(session_plan)
            if not session_plan.empty and st.button("Save Session Plan"):
                save_session_plan(session_plan)
                st.success("Session plan saved! Switch to Game Night to interact with it.")
        else:
            st.info("No trophies match the selected filters.")

    elif st.session_state['page'] == "Game Night":
        st.markdown("<h2 style='text-align: center;'>🎮 Game Night Session</h2>", unsafe_allow_html=True)
        session_plan = load_session_plan()
        if not session_plan.empty:
            st.subheader("Interactive Checklist")
            editable_plan = st.data_editor(session_plan, num_rows="dynamic")
            if st.button("Save Updates"):
                save_session_plan(editable_plan)
                st.success("Session plan updated and saved!")
            if st.button("Export Updated Session Plan"):
                output = BytesIO()
                editable_plan.to_excel(output, index=False)
                output.seek(0)
                st.download_button("Download Updated Session Plan", data=output.getvalue(), file_name="UpdatedSessionChecklist.xlsx")
        else:
            st.info("No session plan saved yet. Go to Planning to create and save one.")

    elif st.session_state['page'] == "Trophy Details":
        st.markdown("<h2 style='text-align: center;'>🔎 Trophy Details</h2>", unsafe_allow_html=True)
        trophy_names = all_trophies['Trophy Name'].dropna().unique().tolist()
        selected_trophy = st.selectbox("Select a Trophy", trophy_names)
        trophy_row = all_trophies[all_trophies['Trophy Name'] == selected_trophy].iloc[0]

        with st.expander("Trophy Info", expanded=True):
            st.markdown(f"<b>Game:</b> {trophy_row['Game']}", unsafe_allow_html=True)
            st.markdown(f"<b>Description:</b> {trophy_row['Description']}", unsafe_allow_html=True)
            st.markdown(f"<b>Type:</b> {trophy_row['Trophy Type']}", unsafe_allow_html=True)
            st.markdown(f"<b>Earned:</b> {'Yes' if pd.notna(trophy_row['Date Earned']) else 'No'}", unsafe_allow_html=True)

        if trophy_row.get('Checklist Required', False):
            with st.expander("Resource Checklist", expanded=True):
                guide_text = trophy_row.get('Guide', '')
                items = extract_checklist_items(guide_text)
                progress = {}
                if 'Checklist Progress' in trophy_row and pd.notna(trophy_row['Checklist Progress']):
                    progress = json.loads(trophy_row['Checklist Progress'])
                updated_progress = {}
                for item in items:
                    checked = st.checkbox(item, value=progress.get(item, False))
                    updated_progress[item] = checked
                if st.button("Save Checklist Progress"):
                    save_checklist_progress(selected_trophy, updated_progress)
                    st.success("Checklist progress saved!")

        with st.expander("Guide Data", expanded=False):
            st.write(trophy_row.get('Guide', 'No guide available.'))

        st.markdown("<div style='height: 50px;'></div>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            st.button("Back")
        with col2:
            st.button("Next")
    
    # New Section: Session Planning
    st.markdown("<h2 style='text-align: center;'>📅 Session Planning</h2>", unsafe_allow_html=True)
    with st.expander("Select Trophies for Session", expanded=True):
        session_trophies = st.multiselect(
            "Select trophies for your session:",
            all_trophies['Trophy Name']
        )
        session_df = all_trophies[all_trophies['Trophy Name'].isin(session_trophies)]
        session_time = session_df['Estimated Time'].sum()
        st.write(f"Total Session Estimated Time: {session_time} hrs")

        # --- Time Breakdown by Trophy Category ---
        if not session_df.empty:
            st.subheader("Session Time Breakdown by Trophy Category")
            category_breakdown = session_df.groupby('Trophy Category')['Estimated Time'].sum()
            st.bar_chart(category_breakdown)

            st.subheader("Session Time Breakdown by Game Run Type")
        if not session_df.empty:
            earned_count = session_df['Date Earned'].notna().sum()
            total_count = len(session_df)
            st.progress(earned_count / total_count if total_count else 0, text=f"{earned_count}/{total_count} trophies earned in session")
        if not session_df.empty:
            earned_count = session_df['Earned?'].eq('Yes').sum()
            total_count = len(session_df)
            st.progress(earned_count / total_count if total_count else 0, text=f"{earned_count}/{total_count} trophies earned in session")

        with st.expander("Session Trophy Filters", expanded=False):
            missable = st.checkbox("Show only Missable?", value=False)
            collectible = st.checkbox("Show only Collectible?", value=False)
            grindy = st.checkbox("Show only Grindy?", value=False)
            dlc_only = st.checkbox("Show only DLC trophies?", value=False)
            filtered_df = all_trophies.copy()
            if missable:
                filtered_df = filtered_df[filtered_df['Missable?'] == 'Yes']
            if collectible:
                filtered_df = filtered_df[filtered_df['Collectible?'] == 'Yes']
            if grindy:
                filtered_df = filtered_df[filtered_df['Grindy?'] == 'Yes']
            if dlc_only and 'DLC' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['DLC'].notna() & (filtered_df['DLC'] != "")]
            session_trophies = st.multiselect(
                "Select trophies for your session:",
                filtered_df['Trophy Name']
            )
            session_df = filtered_df[filtered_df['Trophy Name'].isin(session_trophies)]
            session_time = session_df['Estimated Time'].sum()
            st.write(f"Total Session Estimated Time: {session_time} hrs")

            # --- Time Breakdown by Trophy Category ---
            if not session_df.empty:
                st.subheader("Session Time Breakdown by Trophy Category")
                category_breakdown = session_df.groupby('Trophy Category')['Estimated Time'].sum()
                st.bar_chart(category_breakdown)

                st.subheader("Session Time Breakdown by Game Run Type")
                run_type_breakdown = session_df.groupby('Game Run Type')['Estimated Time'].sum()
                st.bar_chart(run_type_breakdown)

            # --- Progress Tracking for Session ---
            if not session_df.empty:
                earned_count = session_df['Earned?'].eq('Yes').sum()
                total_count = len(session_df)
                st.progress(earned_count / total_count if total_count else 0, text=f"{earned_count}/{total_count} trophies earned in session")
        
        # New Section: Session Trophy Notes & Tips
        if not session_df.empty:
            st.write("Session Trophy Notes & Tips:")
            for _, row in session_df.iterrows():
                notes = row.get("Notes / Tips", "No notes available.")
                st.markdown(f"**{row['Trophy Name']}**: {notes}")
        
        # New Feature: Trophy Name Indicators
        def trophy_indicator(row):
            icons = ""
            if row.get('Missable?') == 'Yes':
                icons += "⚠️ "
            if row.get('Collectible?') == 'Yes':
                icons += "🧩 "
            if row.get('Grindy?') == 'Yes':
                icons += "⏳ "
            return icons + row['Trophy Name']

        session_df_display = session_df.copy()
        session_df_display['Trophy Name'] = session_df_display.apply(trophy_indicator, axis=1)
        st.dataframe(session_df_display)

        if not session_df.empty:
            output = BytesIO()
            session_df.to_excel(output, index=False)
            output.seek(0)
            st.download_button("Download Session Plan", data=output.getvalue(), file_name="SessionPlan.xlsx")
