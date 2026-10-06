"""OSU P-Card Audit website (Part IV).

Tab 1 - Ask the Database: natural-language questions -> SQL (Google Gemini) -> results.
Tab 2 - Prohibited Purchases Dashboard: year filter + Description search + Vendor search.

The Gemini API key is NEVER stored in this repository. Add it in
Streamlit Cloud -> App settings -> Secrets as:   GEMINI_API_KEY = "your-key"
(locally: .streamlit/secrets.toml, which is git-ignored).
"""

import streamlit as st
import pandas as pd

import db

st.set_page_config(page_title="P-Card Audit Assistant", page_icon="💳", layout="wide")


# ======================================================================
# Cached data helpers
# ======================================================================
@st.cache_resource(show_spinner="Preparing the database (first run only)...")
def _prepare_db():
    return db.ensure_db()


@st.cache_data(show_spinner=False)
def cached_schema():
    return db.get_schema_text()


@st.cache_data(show_spinner=False)
def cached_years():
    return db.get_years()


@st.cache_data(show_spinner=False)
def cached_overview():
    return db.get_overview()


@st.cache_data(show_spinner=False, max_entries=200)
def cached_search(field, keywords, year, exclude_returns, min_amount):
    df, sql, params = db.keyword_search(field, list(keywords), year, exclude_returns, min_amount)
    return df, sql, params


try:
    _prepare_db()
except Exception as e:  # noqa: BLE001
    st.error(f"Could not open the P-Card database: {e}")
    st.stop()


# ======================================================================
# Gemini helpers (API key comes only from st.secrets / environment)
# ======================================================================
DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


def get_api_key():
    try:
        key = st.secrets.get("GEMINI_API_KEY")
    except Exception:  # noqa: BLE001  (no secrets file at all)
        key = None
    if not key:
        import os
        key = os.environ.get("GEMINI_API_KEY")
    return key


def model_candidates():
    try:
        preferred = st.secrets.get("GEMINI_MODEL")
    except Exception:  # noqa: BLE001
        preferred = None
    models = ([preferred] if preferred else []) + DEFAULT_MODELS
    return list(dict.fromkeys(models))


@st.cache_resource(show_spinner=False)
def get_client(api_key):
    from google import genai
    return genai.Client(api_key=api_key)


def ask_gemini(prompt):
    """Try the configured model first, then fall back to other models."""
    client = get_client(get_api_key())
    last_error = None
    for model in model_candidates():
        try:
            resp = client.models.generate_content(model=model, contents=prompt)
            return (resp.text or "").strip(), model
        except Exception as e:  # noqa: BLE001
            last_error = e
    raise RuntimeError(f"Gemini request failed: {last_error}")


DATA_NOTES = """
DATA NOTES (important):
- One table only: pcards. Every row is one P-Card transaction of Oklahoma State University (OSU).
- Year and Month are integers for the transaction date. Use them for date filters (e.g. WHERE Year = 2014).
- TransactionDate and PostedDate are TEXT like '7/26/2014 0:00:00' (M/D/YYYY). Do not compare them as text
  for ranges; use Year/Month instead. For day-level grouping you may group by TransactionDate.
- FullName identifies the employee/cardholder (e.g. 'Employee 5433B965').
- Amount is in US dollars. Negative amounts are returns/credits.
- Vendor is the merchant name. MCC is the merchant category description (text, e.g. 'FAST FOOD RESTAURANTS').
- Description is often 'GENERAL PURCHASE'; for line-item detail it may contain product text.
- Text matching should be case-insensitive: use LIKE '%word%' (SQLite LIKE is case-insensitive for ASCII).
- Policy limits: $5,000 per transaction, $10,000 per month without approval, $50,000 per year.
"""


def generate_sql(question, history):
    hist = ""
    if history:
        hist = "PREVIOUS QUESTIONS IN THIS SESSION (for context only):\n" + "\n".join(
            f"- Q: {h['question']}\n  SQL: {h['sql']}" for h in history[-3:]
        )
    prompt = f"""You are an expert SQLite analyst helping internal auditors review P-Card transactions.
Convert the user's question into ONE valid SQLite SELECT query.

DATABASE SCHEMA:
{cached_schema()}
{DATA_NOTES}
{hist}

USER QUESTION:
{question}

RULES:
1. Return ONLY the SQL query - no markdown, no explanation.
2. Read-only: a single SELECT (or WITH ... SELECT). Never INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/PRAGMA.
3. Use only the pcards table and its columns.
4. Give aggregated columns clear aliases (e.g. TotalSpent) and ROUND money to 2 decimals.
5. When listing transactions include FullName, Amount, Vendor, Description, TransactionDate and MCC.
6. Add a sensible ORDER BY; add LIMIT 100 for open-ended lists unless the user asks for everything.
"""
    text, model = ask_gemini(prompt)
    return db.clean_sql(text), model


def explain_result(question, sql, df, truncated):
    if df is None or df.empty:
        result_text = "The query returned no rows."
    else:
        result_text = df.head(50).to_csv(index=False)
        if len(df) > 50 or truncated:
            result_text += f"\n(Only the first 50 of {len(df)}{'+' if truncated else ''} rows are shown here.)"
    prompt = f"""You are an internal-audit assistant for OSU's P-Card program.
Answer the auditor's question using ONLY the query result below. Be concise (max ~150 words),
quote the key numbers, and if relevant mention that a flagged item is a potential exception that
needs follow-up, not proof of fraud. If the result is empty, say no matching records were found.

QUESTION: {question}
SQL: {sql}
RESULT (CSV):
{result_text}
"""
    text, _ = ask_gemini(prompt)
    return text


# ======================================================================
# Header
# ======================================================================
st.title("💳 OSU P-Card Audit Assistant")
st.caption(
    "Internal-audit tool for Oklahoma State University purchasing-card transactions. "
    "Results are risk indicators that require follow-up - not proof of a violation."
)

tab_ask, tab_dash = st.tabs(["🔎 Ask the Database", "🚨 Prohibited Purchases Dashboard"])


# ======================================================================
# TAB 1 - Natural-language questions
# ======================================================================
with tab_ask:
    st.subheader("Ask a question in plain English")
    st.write(
        "Type a question about the P-Card transactions. The app uses Google Gemini to turn your "
        "question into a read-only SQL query, runs it on the database, shows the SQL and the data, "
        "and explains the answer."
    )

    with st.expander("What is in the database?", expanded=False):
        st.code(cached_schema())
        st.dataframe(cached_overview(), hide_index=True, use_container_width=True)

    examples = [
        "Which employees spent more than $50,000 in 2014?",
        "Which 10 vendors received the most money in 2014?",
        "How many transactions over $5,000 were there in each year?",
        "Show total spending by month in 2014",
        "Which employees bought from liquor stores in 2014?",
        "Which cardholders had the most returns (negative amounts) in 2013?",
    ]
    st.write("**Example questions** (click to use):")
    cols = st.columns(3)
    for i, ex in enumerate(examples):
        if cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state["nl_question"] = ex

    if "history" not in st.session_state:
        st.session_state["history"] = []

    with st.form("ask_form"):
        question = st.text_area(
            "Your question",
            key="nl_question",
            placeholder="e.g. Which employees spent more than $10,000 in a single month in 2014?",
            height=80,
        )
        show_explanation = st.checkbox("Explain the result in plain English", value=True)
        submitted = st.form_submit_button("Ask the database", type="primary")

    if submitted:
        if not question.strip():
            st.warning("Please enter a question.")
        elif not get_api_key():
            st.error(
                "GEMINI_API_KEY is not configured. Add it under Streamlit **App settings → Secrets** "
                "(never in the source code)."
            )
        else:
            sql = None
            try:
                with st.spinner("Writing the SQL query..."):
                    sql, model_used = generate_sql(question, st.session_state["history"])
            except Exception as e:  # noqa: BLE001
                st.error(str(e))

        if submitted and question.strip() and get_api_key() and sql:
            st.markdown("**Generated SQL**")
            st.code(sql, language="sql")

            with st.spinner("Running the query..."):
                df, error, truncated = db.run_select(sql)

            if error:
                st.error(f"The query could not be run: {error}")
                st.info("Try rephrasing the question (for example, name the year and what to total).")
            else:
                st.session_state["history"].append({"question": question, "sql": sql})
                st.markdown(f"**Result** - {len(df):,} row(s){' (truncated)' if truncated else ''}")
                if df.empty:
                    st.info("No matching records were found.")
                else:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.download_button(
                        "Download result (CSV)",
                        df.to_csv(index=False).encode("utf-8"),
                        file_name="pcard_query_result.csv",
                        mime="text/csv",
                    )
                if show_explanation:
                    try:
                        with st.spinner("Explaining the result..."):
                            st.markdown("**Answer**")
                            st.write(explain_result(question, sql, df, truncated))
                    except Exception as e:  # noqa: BLE001
                        st.warning(f"Could not generate an explanation: {e}")
                st.caption(f"Model: {model_used}")

    if st.session_state["history"]:
        with st.expander(f"Questions asked this session ({len(st.session_state['history'])})"):
            for h in reversed(st.session_state["history"]):
                st.markdown(f"**{h['question']}**")
                st.code(h["sql"], language="sql")


# ======================================================================
# TAB 2 - Prohibited purchases dashboard
# ======================================================================
PROHIBITED = pd.DataFrame(
    [
        ("Alcohol", "beer, wine, liquor, vodka, whiskey", "liquor, wine, bottle shop, brew"),
        ("Cash, cash advances, ATM", "cash, atm, advance, withdrawal", "atm, cash, western union, moneygram"),
        ("Decorations", "decoration, balloon, banner, party", "party, balloon, decor, hobby lobby"),
        ("Donations and sponsorships", "donation, sponsor, contribution", "foundation, charity, united way, church"),
        ("Gasoline", "fuel, gasoline, unleaded, diesel", "shell, exxon, conoco, phillips 66, qt, oncue"),
        ("Gifts, gift cards, gift certificates", "gift card, gift cert, gift", "gift, flowers, florist, edible"),
        ("Insurance", "insurance, premium, policy", "insurance, state farm, geico, allstate"),
        ("Late fees", "late fee, late charge, penalty, finance charge", "late, penalty"),
        ("Mail and postage", "postage, stamps, mailing", "usps, post office, postal"),
        ("Moving expenses", "moving, relocation, storage", "u-haul, uhaul, movers, penske"),
        ("Personal purchases", "personal, clothing, jewelry, cosmetics", "spa, salon, jewelry, netflix, itunes"),
        ("Personal memberships and dues", "membership, dues, subscription", "gym, country club, fitness, costco"),
        ("Salaries, wages and benefits", "salary, wage, payroll, benefit", "payroll, adp, paychex"),
        ("Service / incentive awards", "award, plaque, trophy, incentive", "trophy, awards, plaque"),
    ],
    columns=["Prohibited category", "Try in DESCRIPTION search", "Try in VENDOR search"],
)


def render_results(df, field, keywords, year_label):
    if df.empty:
        st.success(f"No {year_label} transactions found with {field} containing: {', '.join(keywords)}.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Transactions", f"{len(df):,}")
    c2.metric("Total amount", f"${df['Amount'].sum():,.2f}")
    c3.metric("Cardholders", f"{df['FullName'].nunique():,}")
    c4.metric("Vendors", f"{df['Vendor'].nunique():,}")
    if len(df) >= db.MAX_ROWS:
        st.warning(f"Showing the {db.MAX_ROWS:,} largest matches only - narrow the keyword or year.")

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={"Amount": st.column_config.NumberColumn("Amount", format="$%.2f")},
    )
    st.download_button(
        "Download these transactions (CSV) for follow-up",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"prohibited_{field.lower()}_{'_'.join(keywords)[:40]}_{year_label}.csv".replace(" ", "_"),
        mime="text/csv",
        key=f"dl_{field}",
    )
    with st.expander("Who should be followed up first? (by cardholder)"):
        by_person = (
            df.groupby("FullName")
            .agg(Transactions=("Amount", "size"), Total=("Amount", "sum"),
                 Vendors=("Vendor", lambda s: ", ".join(sorted(set(s))[:5])))
            .sort_values("Total", ascending=False)
            .reset_index()
        )
        st.dataframe(by_person, use_container_width=True, hide_index=True,
                     column_config={"Total": st.column_config.NumberColumn(format="$%.2f")})


with tab_dash:
    st.subheader("Prohibited Purchases Dashboard")

    with st.expander("📘 How to use this dashboard", expanded=True):
        st.markdown(
            """
1. **Choose the year** to search (or *All years*) in the filter bar below.
2. Pick the search you need:
   - **Description search** looks inside the *transaction description* (what was bought), e.g. `wine`, `gift card`, `postage`.
   - **Vendor search** looks inside the *vendor / merchant name* (who was paid), e.g. `usps`, `liquor`, `post office`.
3. Type one keyword, or several separated by commas (`beer, wine, liquor` finds any of them). Matching is not case-sensitive.
4. Click **Search**. Each result row shows the cardholder, amount, description, vendor, MCC, transaction and posted dates and the
   transaction ID needed to request receipts.
5. Use **Download** to export the list for follow-up and the *by cardholder* summary to decide who to contact first.

The table below lists OSU's prohibited purchase categories with suggested keywords. A match is only a *potential*
deviation - e.g. `alcohol` also finds laboratory chemicals such as isopropyl alcohol - so review each item before concluding.
            """
        )
        st.dataframe(PROHIBITED, use_container_width=True, hide_index=True)

    years = cached_years()
    f1, f2, f3 = st.columns([1, 1, 1])
    year_choice = f1.selectbox("Year to search", ["All years"] + years,
                               index=(1 + years.index(2014)) if 2014 in years else 0,
                               format_func=lambda y: str(y))
    exclude_returns = f2.checkbox("Exclude returns / credits (negative amounts)", value=True)
    min_amount = f3.number_input("Minimum amount ($, optional)", min_value=0.0, value=0.0, step=50.0)
    year = None if year_choice == "All years" else int(year_choice)
    year_label = "all-years" if year is None else str(year)

    st.divider()
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### 📝 Description search")
        st.caption("Searches the **Description** field - what was purchased.")
        with st.form("desc_form"):
            desc_kw = st.text_input("Keyword(s) in the description", placeholder="e.g. wine, beer, liquor")
            desc_go = st.form_submit_button("Search descriptions", type="primary")
    with right:
        st.markdown("### 🏪 Vendor search")
        st.caption("Searches the **Vendor** field - the merchant that was paid.")
        with st.form("vendor_form"):
            vend_kw = st.text_input("Keyword(s) in the vendor name", placeholder="e.g. usps, post office")
            vend_go = st.form_submit_button("Search vendors", type="primary")

    if desc_go:
        st.session_state["last_search"] = ("Description", tuple(db.parse_keywords(desc_kw)))
    if vend_go:
        st.session_state["last_search"] = ("Vendor", tuple(db.parse_keywords(vend_kw)))

    if "last_search" in st.session_state:
        field, kws = st.session_state["last_search"]
        st.divider()
        if not kws:
            st.warning(f"Please enter at least one keyword for the {field.lower()} search.")
        else:
            st.markdown(
                f"#### {field} search results - keyword(s): "
                + ", ".join(f"`{k}`" for k in kws)
                + f" - year: **{year_choice}**"
            )
            with st.spinner("Searching..."):
                df, sql, params = cached_search(field, kws, year, exclude_returns, min_amount or None)
            render_results(df, field, list(kws), year_label)
            with st.expander("SQL used (parameterised)"):
                st.code(sql, language="sql")
                st.write("Parameters:", params)
