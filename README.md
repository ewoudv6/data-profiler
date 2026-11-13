# Data Profiler

Get to know a new data set before you start working with it. Give it a CSV or
Excel file and it tells you:

- how many rows and columns there are, and how many rows are duplicates
- per column: what type the data **really** is, compared to what pandas makes of it
  (for example prices stored as text because of a `€` sign, or dates stored as text)
- missing values, unique values, lowest and highest values
- common problems: extra spaces (`" North"`), the same value written differently
  (`North` / `north` / `NORTH`), negative numbers, unusual outliers, and dates
  where day and month could be mixed up

It only **reports** - it never changes your data.

## Getting started (Windows)

1. Install [Python](https://www.python.org/downloads/) (3.10 or newer). During the
   installation, tick **"Add python.exe to PATH"**.
2. Download this project: click the green **Code** button on GitHub →
   **Download ZIP**, and unzip it somewhere.
3. Double-click **`Start Data Profiler.bat`**.
   The first time it installs what it needs (a few minutes). After that it opens
   the app in your browser straight away.

Keep the black window open while you use the app; close it to stop.

## Using the app

- Drag a CSV or Excel file into the sidebar.
- **Overview**: one row per column with a status: 🔴 fix first, 🟡 check, 🟢 OK.
  Click a row to jump to the details of that column.
- **Column details**: all notes for one column, plus a chart of its values.
- **Raw data**: the file itself, with a switch to show only duplicate rows.
- Download the summary as a CSV with the button under the overview.

## Using it in a terminal

```
.venv\Scripts\python.exe data_profiler.py path\to\file.csv
.venv\Scripts\python.exe data_profiler.py path\to\file.xlsx --save
```

`--save` also writes the summary to `<file>_profile.csv` next to the data.

## Files

| File | What it does |
|---|---|
| `data_profiler.py` | All the checks, plus the terminal report |
| `profiler_app.py` | The browser app (built with [Streamlit](https://streamlit.io)) |
| `Start Data Profiler.bat` | Sets everything up the first time and starts the app |
| `requirements.txt` | The Python packages it needs |
