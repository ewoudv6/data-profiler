"""
profiler_app.py - A web interface for data_profiler.py.

Start it (from the ClaudeCodeTest folder):
    .venv\\Scripts\\python.exe -m streamlit run profiler_app.py

Your browser opens the app. Stop it with Ctrl + C in the terminal.

How Streamlit works: the whole script runs from top to bottom every time you
click or change something. Each st.something() call draws one piece of the page.
"""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

# All the analysis logic lives in data_profiler.py - this file only shows it.
from data_profiler import needs_attention, profile_file, to_number

PROJECT_DIR = Path(__file__).resolve().parent  # resolve() = make it a full path
# Other folders to list in the "pick a file" dropdown.
EXTRA_FOLDERS = [PROJECT_DIR.parent / "DataSets"]
MAX_PICK_MB = 200  # bigger files are left out of the dropdown (too slow for the browser)
TABLE_TYPES = ["csv", "xlsx", "xls"]
CHART_COLOR = "#2a78d6"  # one blue for every chart (single series = single color)

st.set_page_config(page_title="Data Profiler", page_icon="🔎", layout="wide")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@st.cache_data  # remember results, so clicking around doesn't re-analyse the file
def run_profile(data: bytes, name: str):
    buffer = io.BytesIO(data)
    buffer.name = name  # profile_file looks at the name to see if it's CSV or Excel
    return profile_file(buffer)


def status_of(profile: dict) -> str:
    """Icon + word, so the status never relies on color alone."""
    if needs_attention(profile):
        return "🔴 Fix first"
    if profile["notes"]:
        return "🟡 Check"
    return "🟢 OK"


def find_example_files() -> list[Path]:
    """Data files in the project and EXTRA_FOLDERS (skipping the virtual
    environment, saved profiles and files that are too big)."""
    files = []
    for folder in [PROJECT_DIR] + [f for f in EXTRA_FOLDERS if f.exists()]:
        for ext in TABLE_TYPES:
            files += folder.rglob(f"*.{ext}")
    return sorted(
        p for p in set(files)
        if p.is_file() and ".venv" not in p.parts and "_profile" not in p.stem
        and p.stat().st_size < MAX_PICK_MB * 1024 * 1024
    )


def show_path(p: Path) -> str:
    """Short name for the dropdown: relative to the folder above the project."""
    try:
        return str(p.relative_to(PROJECT_DIR.parent))
    except ValueError:
        return str(p)


def column_chart(name: str, raw: pd.Series, suggested: str) -> None:
    """Draw a small chart that fits the kind of column."""
    values = raw.dropna()
    if values.empty:
        return
    if suggested in ("integer", "decimal"):
        nums = to_number(values).dropna()
        if nums.nunique() <= 1:
            return
        # Histogram: split the range into 15 equal bins and count values per bin.
        bins = pd.cut(nums, bins=min(15, nums.nunique()))
        counts = bins.value_counts(sort=False)
        chart = pd.DataFrame({"range": [f"{b.left:,.1f} – {b.right:,.1f}" for b in counts.index],
                              "rows": counts.values})
        st.caption("How the values are spread")
        st.bar_chart(chart, x="range", y="rows", color=CHART_COLOR, height=260, sort=False)
    elif suggested in ("category", "boolean"):
        # Count the RAW values (not cleaned), so " North" and "north" show up separately.
        counts = values.value_counts().head(25).rename_axis("value").reset_index(name="rows")
        counts["value"] = counts["value"].map(repr)  # repr shows the hidden spaces: ' North'
        st.caption("Rows per value, exactly as written in the file (quotes show hidden spaces)")
        st.bar_chart(counts, x="rows", y="value", color=CHART_COLOR, horizontal=True,
                     height=max(160, 28 * len(counts)), sort="-rows")


# ---------------------------------------------------------------------------
# Sidebar: choose a file
# ---------------------------------------------------------------------------
st.sidebar.title("🔎 Data Profiler")
uploaded = st.sidebar.file_uploader("Upload a CSV or Excel file", type=TABLE_TYPES)

examples = find_example_files()
picked = None
if examples:
    st.sidebar.markdown("**...or pick a file from your folders**")
    picked = st.sidebar.selectbox(
        "Project files", [None] + examples, label_visibility="collapsed",
        format_func=lambda p: "—" if p is None else show_path(p),
    )

if uploaded is not None:
    file_name, file_bytes = uploaded.name, uploaded.getvalue()
elif picked is not None:
    file_name, file_bytes = picked.name, picked.read_bytes()
else:
    st.title("Data Profiler")
    st.info("👈 Upload a file or pick one from your project to see what's in it.")
    st.stop()  # nothing more to show yet

try:
    df, profiles = run_profile(file_bytes, file_name)
except Exception as error:  # e.g. a corrupt or unsupported file
    st.error(f"Could not read **{file_name}**: {error}")
    st.stop()


# ---------------------------------------------------------------------------
# Headline numbers
# ---------------------------------------------------------------------------
st.title(file_name)

n_dupes = int(df.duplicated().sum())
n_fix = sum(needs_attention(p) for p in profiles)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Rows", f"{len(df):,}")
c2.metric("Columns", len(df.columns))
c3.metric("Duplicate rows", n_dupes)
c4.metric("Empty rows", int(df.isna().all(axis=1).sum()))
c5.metric("Columns to fix first", n_fix)

TAB_OVERVIEW, TAB_DETAILS, TAB_DATA = "📋 Overview", "🔬 Column details", "🗂️ Raw data"
names = [p["column"] for p in profiles]

# st.session_state is Streamlit's memory between reruns (a dictionary that survives clicks).
# If a new file doesn't have the remembered column, forget it.
if st.session_state.get("detail_column") not in names:
    st.session_state.pop("detail_column", None)
st.session_state.setdefault("overview_version", 0)


def open_column_details() -> None:
    """Runs when a row in the overview is clicked: jump to that column's details."""
    selection = st.session_state[f"overview_{st.session_state.overview_version}"].selection
    if selection.rows:
        st.session_state.detail_column = names[selection.rows[0]]
        st.session_state.active_tab = TAB_DETAILS
        # A new table key = a fresh table with no row selected, so the same row
        # can be clicked again later.
        st.session_state.overview_version += 1


# key="active_tab" lets the code above switch tabs by changing st.session_state.active_tab
tab_overview, tab_details, tab_data = st.tabs(
    [TAB_OVERVIEW, TAB_DETAILS, TAB_DATA], key="active_tab", on_change="rerun")


# ---------------------------------------------------------------------------
# Tab 1: one row per column
# ---------------------------------------------------------------------------
with tab_overview:
    table = pd.DataFrame({
        "Status": [status_of(p) for p in profiles],
        "Column": [p["column"] for p in profiles],
        "pandas reads it as": [p["pandas_type"] for p in profiles],
        "Looks like": [p["suggested_type"] for p in profiles],
        "Missing %": [p["missing_%"] for p in profiles],
        "Unique": [p["unique"] for p in profiles],
        # min/max can be numbers OR dates, so show them as text
        "Min": ["" if p["min"] is None else str(p["min"]) for p in profiles],
        "Max": ["" if p["max"] is None else str(p["max"]) for p in profiles],
        "Examples": [", ".join(map(repr, p["examples"])) for p in profiles],
        "Notes": [len(p["notes"]) for p in profiles],
    })
    st.caption("👆 Click a row to see the details of that column.")
    st.dataframe(
        table, hide_index=True, width="stretch",
        key=f"overview_{st.session_state.overview_version}",
        on_select=open_column_details, selection_mode="single-row",
        column_config={
            "Missing %": st.column_config.ProgressColumn(
                "Missing %", min_value=0, max_value=100, format="%.1f%%"),
        },
    )
    st.caption("🔴 Fix first = wrong data type or day/month confusion · "
               "🟡 Check = has notes worth a look · 🟢 OK = nothing found")

    summary = pd.DataFrame(profiles)
    summary["notes"] = summary["notes"].apply(" | ".join)
    st.download_button("⬇️ Download summary as CSV", summary.to_csv(index=False),
                       file_name=Path(file_name).stem + "_profile.csv", mime="text/csv")


# ---------------------------------------------------------------------------
# Tab 2: zoom in on one column
# ---------------------------------------------------------------------------
with tab_details:
    # key="detail_column" links this dropdown to st.session_state.detail_column,
    # which the overview sets when you click a row.
    chosen = st.selectbox("Column", names, key="detail_column",
                          format_func=lambda n: f"{status_of(profiles[names.index(n)])[:1]}  {n}")
    p = profiles[names.index(chosen)]

    left, right = st.columns([1, 1.4])
    with left:
        st.subheader(chosen)
        st.markdown(f"**Looks like:** `{p['suggested_type']}`  \n"
                    f"**pandas reads it as:** `{p['pandas_type']}`  \n"
                    f"**Missing:** {p['missing']} ({p['missing_%']}%)  \n"
                    f"**Unique values:** {p['unique']}")
        if p["min"] is not None:
            st.markdown(f"**Range:** {p['min']} → {p['max']}")
        if not p["notes"]:
            st.success("No problems found in this column.")
        for note in p["notes"]:
            if "MISMATCH" in note or "AMBIGUOUS" in note:
                st.error(note, icon="🔴")
            else:
                st.warning(note, icon="🟡")
    with right:
        column_chart(chosen, df[chosen], p["suggested_type"])


# ---------------------------------------------------------------------------
# Tab 3: the data itself
# ---------------------------------------------------------------------------
with tab_data:
    only_dupes = st.toggle(f"Show only duplicate rows ({n_dupes} copies)", disabled=n_dupes == 0)
    if only_dupes:
        # keep=False marks the original AND its copies, so you see them side by side
        shown = df[df.duplicated(keep=False)].sort_values(list(df.columns))
    else:
        shown = df
    st.caption(f"Showing {len(shown):,} rows. All values are shown as raw text from the file.")
    st.dataframe(shown, width="stretch", height=500)
