"""
data_profiler.py - Get to know a new data set before you work with it.

What it does (it never changes your data, it only reports):
  1. Overview: number of rows/columns, duplicate rows, empty rows.
  2. Per column: the type pandas picked, the type the values ACTUALLY look like,
     missing values, unique values and a few example values.
  3. Warnings: numbers stored as text (e.g. "€899.00"), dates stored as text,
     extra spaces, inconsistent capitals ("North" vs "north"), and so on.

How to run it (from the ClaudeCodeTest folder):
    .venv\\Scripts\\python.exe data_profiler.py path\\to\\file.csv
    .venv\\Scripts\\python.exe data_profiler.py path\\to\\file.xlsx --save

--save also writes the column summary to <file>_profile.csv next to the data.
"""

import sys
from pathlib import Path

import pandas as pd

# How many example values to show per column.
N_EXAMPLES = 3

# Common date formats to try. %d = day, %m = month, %Y = 4-digit year.
DATE_FORMATS = [
    "%Y-%m-%d", "%d-%m-%Y", "%m-%d-%Y",
    "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d",
    "%d.%m.%Y", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M",
]

TRUE_FALSE_WORDS = {"true", "false", "yes", "no", "y", "n", "ja", "nee"}


# ---------------------------------------------------------------------------
# 1. Loading
# ---------------------------------------------------------------------------
def _suffix(source) -> str:
    """File extension of a path OR an uploaded file (both have a .name)."""
    return Path(getattr(source, "name", str(source))).suffix.lower()


def _rewind(source) -> None:
    """An uploaded file is read like a tape: go back to the start before reading again."""
    if hasattr(source, "seek"):
        source.seek(0)


def load_file(source) -> pd.DataFrame:
    """Read a CSV or Excel file. Everything is read as TEXT (dtype=str) first,
    so pandas doesn't silently change values. We work out the real types ourselves.
    `source` can be a file path or an uploaded file (used by the UI)."""
    suffix = _suffix(source)
    _rewind(source)
    if suffix in (".xlsx", ".xls"):
        df = pd.read_excel(source, dtype=str)
    elif suffix in (".csv", ".txt", ".tsv"):
        # sep=None lets pandas guess the separator (comma, semicolon, tab...).
        df = pd.read_csv(source, dtype=str, sep=None, engine="python",
                         keep_default_na=True)
    else:
        raise ValueError(f"Unsupported file type: {suffix} (use .csv or .xlsx)")
    df.columns = df.columns.str.strip()
    return df


def pandas_guess(source) -> dict:
    """What type would pandas give each column with a normal read_csv / read_excel?
    That's what you'd get without thinking about it, so it's useful to compare."""
    _rewind(source)
    if _suffix(source) in (".xlsx", ".xls"):
        df = pd.read_excel(source)
    else:
        df = pd.read_csv(source, sep=None, engine="python")
    return {str(col).strip(): str(dtype) for col, dtype in df.dtypes.items()}


def profile_file(source) -> tuple[pd.DataFrame, list[dict]]:
    """Load a file and profile every column. Returns (data, list of column profiles)."""
    df = load_file(source)
    guesses = pandas_guess(source)
    profiles = [profile_column(col, df[col], guesses.get(col, "?")) for col in df.columns]
    return df, profiles


# ---------------------------------------------------------------------------
# 2. Working out what type a column really is
# ---------------------------------------------------------------------------
def to_number(values: pd.Series) -> pd.Series:
    """Try to turn text like '€1,234.50' or ' 49,95 ' into numbers.
    Values that can't be converted become NaN (= missing)."""
    cleaned = values.str.strip().str.replace(r"[€$£%\s]", "", regex=True)
    # "49,95" (comma as decimal, Dutch style) -> "49.95"
    if cleaned.str.fullmatch(r"-?\d+,\d+").mean() > 0.5:
        cleaned = cleaned.str.replace(",", ".", regex=False)
    else:
        cleaned = cleaned.str.replace(",", "", regex=False)  # thousand separator
    return pd.to_numeric(cleaned, errors="coerce")


def best_date_format(values: pd.Series):
    """Try each date format; return (format, share_that_parsed, ambiguous_formats)."""
    stripped = values.str.strip()
    results = {}
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(stripped, format=fmt, errors="coerce")
        results[fmt] = parsed.notna().mean()
    best = max(results, key=results.get)
    # Ambiguous: e.g. "03-10-2026" could be 3 Oct or 10 March if both formats work.
    ambiguous = [f for f, share in results.items() if share == results[best] and f != best]
    return best, results[best], ambiguous


def infer_type(values: pd.Series) -> tuple[str, list[str]]:
    """Look at the (non-missing) text values and decide what they really are.
    Returns (suggested_type, list_of_notes)."""
    notes = []
    if values.empty:
        return "empty", ["Column is completely empty"]

    stripped = values.str.strip()

    # Yes/no style column?
    if set(stripped.str.lower().unique()) <= TRUE_FALSE_WORDS:
        return "boolean", notes

    # Numbers?
    numbers = to_number(values)
    share_numeric = numbers.notna().mean()
    if share_numeric >= 0.95:
        if values.str.contains(r"[€$£]").any():
            notes.append("Contains currency symbols (e.g. €) - strip them to get numbers")
        if share_numeric < 1:
            bad = values[numbers.isna()].unique()[:N_EXAMPLES]
            notes.append(f"Some values are not numbers: {list(bad)}")
        is_whole = (numbers.dropna() % 1 == 0).all()
        # Leading zeros ("007") are usually codes, not amounts.
        if is_whole and stripped.str.match(r"0\d").any():
            notes.append("Has leading zeros - probably a code/ID, keep as text")
            return "text (code)", notes
        return ("integer" if is_whole else "decimal"), notes

    # Dates?
    fmt, share_date, ambiguous = best_date_format(values)
    if share_date >= 0.95:
        notes.append(f"Date format looks like {fmt}")
        if ambiguous:
            notes.append(f"AMBIGUOUS: also fits {ambiguous} - check day vs month!")
        if share_date < 1:
            bad = values[pd.to_datetime(stripped, format=fmt, errors="coerce").isna()]
            notes.append(f"Some values are not valid dates: {list(bad.unique()[:N_EXAMPLES])}")
        return "date", notes

    # Otherwise it's text. Is it a category (few distinct values) or free text?
    n_unique = stripped.nunique()
    if n_unique <= 20 or n_unique / len(values) < 0.05:
        return "category", notes
    return "text", notes


def text_quality_notes(values: pd.Series) -> list[str]:
    """Spot common text problems: extra spaces and inconsistent capitals."""
    notes = []
    n_spaces = (values != values.str.strip()).sum()
    if n_spaces:
        notes.append(f"{n_spaces} values have extra spaces at start/end")

    # Values that are the same once you ignore spaces and capitals, e.g. "North", " north"
    normalised = values.str.strip().str.lower()
    variants = values.groupby(normalised).unique()
    messy = variants[variants.apply(len) > 1]
    if len(messy):
        examples = [list(v) for v in messy.head(N_EXAMPLES)]
        notes.append(f"Same value written differently: {examples}")
    return notes


# ---------------------------------------------------------------------------
# 3. Profiling each column
# ---------------------------------------------------------------------------
def profile_column(name: str, column: pd.Series, pandas_type: str) -> dict:
    total = len(column)
    # Treat empty strings / only spaces as missing too.
    column = column.where(column.str.strip() != "", None)
    non_missing = column.dropna()
    n_missing = total - len(non_missing)

    suggested, notes = infer_type(non_missing)
    if suggested in ("category", "text", "text (code)", "boolean"):
        notes += text_quality_notes(non_missing)

    # Compare what pandas would do vs what the data really is.
    # pandas calls text columns "object" (older versions) or "str" (pandas 3+).
    pandas_is_text = pandas_type in ("object", "str", "string")
    mismatch = (
        (suggested in ("integer", "decimal") and pandas_is_text)
        or (suggested == "date" and "datetime" not in pandas_type)
        or (suggested == "text (code)" and not pandas_is_text)
    )
    if suggested == "integer" and pandas_type.startswith("float") and n_missing:
        notes.append("pandas reads whole numbers as decimals here because of the "
                     "missing values (NaN only fits in a float column)")
    if mismatch:
        notes.insert(0, f"TYPE MISMATCH: pandas reads it as '{pandas_type}', "
                        f"but it looks like '{suggested}'")

    info = {
        "column": name,
        "pandas_type": pandas_type,
        "suggested_type": suggested,
        "missing": n_missing,
        "missing_%": round(100 * n_missing / total, 1) if total else 0,
        "unique": non_missing.str.strip().nunique(),
        "examples": list(non_missing.unique()[:N_EXAMPLES]),
        "min": None,
        "max": None,
        "notes": notes,
    }

    # Range of values for numbers and dates - handy to spot impossible values.
    if suggested in ("integer", "decimal"):
        nums = to_number(non_missing)
        info["min"], info["max"] = nums.min(), nums.max()
        if (nums < 0).any():
            notes.append(f"{(nums < 0).sum()} negative values - is that possible here?")
        # Outliers: values far outside the "middle half" of the data (IQR rule).
        q1, q3 = nums.quantile(0.25), nums.quantile(0.75)
        iqr = q3 - q1
        if iqr > 0:
            outliers = nums[(nums < q1 - 3 * iqr) | (nums > q3 + 3 * iqr)]
            if len(outliers):
                notes.append(f"{len(outliers)} possible outliers (unusually low/high): "
                             f"{sorted(outliers.unique().tolist())[:N_EXAMPLES]} - check if these are real")
    elif suggested == "date":
        fmt, _, _ = best_date_format(non_missing)
        dates = pd.to_datetime(non_missing.str.strip(), format=fmt, errors="coerce")
        info["min"], info["max"] = dates.min().date(), dates.max().date()

    if info["unique"] == len(non_missing) and n_missing == 0 and len(non_missing) > 1:
        notes.append("Every value is unique - could be an ID column")
    elif info["unique"] == 1:
        notes.append("Only one distinct value - column may be useless")
    if n_missing:
        notes.append(f"{n_missing} missing values ({info['missing_%']}%)")
    return info


def needs_attention(profile: dict) -> bool:
    """True if a column has a serious problem (wrong type or day/month confusion)."""
    return any("MISMATCH" in n or "AMBIGUOUS" in n for n in profile["notes"])


# ---------------------------------------------------------------------------
# 4. Printing the report
# ---------------------------------------------------------------------------
def print_report(path: Path, df: pd.DataFrame, profiles: list[dict]) -> None:
    line = "=" * 78
    print(line)
    print(f"DATA PROFILE: {path.name}")
    print(line)
    print(f"Rows:            {len(df):,}")
    print(f"Columns:         {len(df.columns)}")
    print(f"Duplicate rows:  {df.duplicated().sum()}  (exact copies of another row)")
    print(f"Empty rows:      {df.isna().all(axis=1).sum()}")

    # Compact overview table: one line per column.
    print("\nCOLUMN OVERVIEW")
    table = pd.DataFrame(profiles)[
        ["column", "pandas_type", "suggested_type", "missing", "unique", "min", "max"]
    ]
    print(table.to_string(index=False))

    # Detailed notes per column.
    print("\nDETAILS PER COLUMN")
    for p in profiles:
        flag = "!!" if needs_attention(p) else "  "
        print(f"\n{flag} {p['column']}  ->  {p['suggested_type']}")
        print(f"     examples: {p['examples']}")
        for note in p["notes"]:
            print(f"     - {note}")

    n_issues = sum(len(p["notes"]) for p in profiles)
    print(f"\n{line}\n{n_issues} notes found. Columns marked !! need attention first.\n{line}")


def main() -> None:
    # Make sure symbols like € print correctly in the Windows terminal.
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    path = Path(args[0])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    df, profiles = profile_file(path)
    print_report(path, df, profiles)

    if "--save" in args:
        out = path.with_name(path.stem + "_profile.csv")
        summary = pd.DataFrame(profiles)
        summary["notes"] = summary["notes"].apply(" | ".join)
        summary.to_csv(out, index=False)
        print(f"Saved column summary to {out}")


if __name__ == "__main__":
    main()
