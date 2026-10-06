"""Data-access helpers for the P-Card Audit app (no Streamlit imports here,
so the logic can be tested on its own)."""

import os
import re
import sqlite3
import zipfile

import pandas as pd

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_DIR, "pcards.db")
ZIP_PATH = os.path.join(APP_DIR, "pcards.db.zip")
TABLE = "pcards"
MAX_ROWS = 5000

# Columns returned for follow-up in the prohibited-purchase searches
DETAIL_COLUMNS = [
    "ID", "Year", "Month", "FullName", "Amount", "Description", "Vendor",
    "MCC", "TransactionDate", "PostedDate", "AgencyName",
]


# ------------------------------------------------------------------ database
def _is_sqlite(path):
    try:
        with open(path, "rb") as f:
            return f.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def ensure_db():
    """Make sure a real SQLite file exists.

    In the GitHub repo pcards.db is stored with Git LFS; if the host only
    checked out the LFS pointer file, unpack the database from pcards.db.zip.
    """
    if _is_sqlite(DB_PATH):
        return DB_PATH
    if os.path.exists(ZIP_PATH):
        with zipfile.ZipFile(ZIP_PATH) as zf:
            member = next(n for n in zf.namelist() if n.endswith(".db"))
            tmp = DB_PATH + ".tmp"
            with zf.open(member) as src, open(tmp, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            os.replace(tmp, DB_PATH)
    if not _is_sqlite(DB_PATH):
        raise FileNotFoundError(
            "pcards.db is missing or is only a Git LFS pointer, and pcards.db.zip was not found."
        )
    return DB_PATH


def get_connection():
    """Read-only connection: even a malicious query cannot change the data."""
    path = ensure_db()
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    return conn


def get_schema_text():
    conn = get_connection()
    try:
        cols = pd.read_sql_query(f"PRAGMA table_info('{TABLE}')", conn)
    finally:
        conn.close()
    lines = [f"Table: {TABLE}", "Columns:"]
    lines += [f"- {r['name']} ({r['type']})" for _, r in cols.iterrows()]
    return "\n".join(lines)


def get_years():
    conn = get_connection()
    try:
        df = pd.read_sql_query(f"SELECT DISTINCT Year FROM {TABLE} ORDER BY Year DESC", conn)
    finally:
        conn.close()
    return [int(y) for y in df["Year"].tolist()]


def get_overview():
    conn = get_connection()
    try:
        return pd.read_sql_query(
            f"""SELECT Year, COUNT(*) AS Transactions,
                       COUNT(DISTINCT FullName) AS Cardholders,
                       ROUND(SUM(Amount), 2) AS TotalAmount
                FROM {TABLE} GROUP BY Year ORDER BY Year""",
            conn,
        )
    finally:
        conn.close()


# --------------------------------------------------------- keyword searches
def parse_keywords(text):
    """'liquor, wine ,beer' -> ['liquor', 'wine', 'beer']"""
    return [k.strip() for k in re.split(r"[,;]", text or "") if k.strip()]


def _escape_like(s):
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def keyword_search(field, keywords, year=None, exclude_returns=True, min_amount=None):
    """Search one text field (Description or Vendor) for any of the keywords.

    Uses bound parameters only (no string concatenation of user input).
    Returns (DataFrame, sql, params).
    """
    if field not in ("Description", "Vendor"):
        raise ValueError("field must be Description or Vendor")
    if not keywords:
        raise ValueError("Enter at least one keyword")

    where, params = [], []
    like = " OR ".join([f"{field} LIKE ? ESCAPE '\\'"] * len(keywords))
    where.append(f"({like})")
    params += [f"%{_escape_like(k)}%" for k in keywords]
    if year is not None:
        where.append("Year = ?")
        params.append(int(year))
    if exclude_returns:
        where.append("Amount > 0")
    if min_amount:
        where.append("Amount >= ?")
        params.append(float(min_amount))

    sql = (
        f"SELECT {', '.join(DETAIL_COLUMNS)} FROM {TABLE} "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY Amount DESC LIMIT {MAX_ROWS}"
    )
    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()
    return df, sql, params


# ------------------------------------------------------- natural-language SQL
FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM|REINDEX|TRIGGER|GRANT)\b",
    re.IGNORECASE,
)


def clean_sql(text):
    """Strip markdown fences / trailing semicolon from model output."""
    sql = (text or "").strip()
    sql = re.sub(r"^```(?:sql|sqlite)?", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"```$", "", sql).strip()
    sql = sql.rstrip(";").strip()
    return sql


def validate_sql(sql):
    """Return None if the SQL is a single read-only SELECT, else an error message."""
    if not sql:
        return "The model did not return a query."
    no_strings = re.sub(r"'(?:[^']|'')*'", "''", sql)
    no_comments = re.sub(r"--[^\n]*|/\*.*?\*/", " ", no_strings, flags=re.DOTALL).strip()
    if ";" in no_comments:
        return "Only one SQL statement is allowed."
    if not re.match(r"^(SELECT|WITH)\b", no_comments, re.IGNORECASE):
        return "Only SELECT queries are allowed."
    m = FORBIDDEN.search(no_comments)
    if m:
        return f"The query was blocked because it contains '{m.group(1).upper()}'."
    return None


def run_select(sql, max_rows=MAX_ROWS):
    """Run a validated SELECT on the read-only connection. Returns (df, error, truncated)."""
    err = validate_sql(sql)
    if err:
        return None, err, False
    conn = get_connection()
    try:
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(max_rows + 1)
        truncated = len(rows) > max_rows
        df = pd.DataFrame(rows[:max_rows], columns=cols)
        return df, None, truncated
    except Exception as e:  # noqa: BLE001
        return None, str(e), False
    finally:
        conn.close()
