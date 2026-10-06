# OSU P-Card Audit Assistant

Streamlit website for the *Analytics Mindset – P-Card* case (Part IV). It has two tabs:

1. **Ask the Database** – auditors type a question in plain English; Google Gemini turns it into a
   read-only SQLite query, the app runs it, shows the SQL and the data, and explains the result.
2. **Prohibited Purchases Dashboard** – instructions, a **year** filter, and two separate searches:
   - **Description search** – keyword(s) in the transaction description (e.g. `wine`, `gift card`).
   - **Vendor search** – keyword(s) in the vendor name (e.g. `usps`, `liquor`).
   Results show cardholder, amount, description, vendor, MCC, dates and transaction ID, with totals,
   a by-cardholder summary and a CSV download for follow-up.

`audit_queries.sql` contains the SQLite queries used for Parts II and III of the assignment.

## Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit user interface (two tabs) |
| `db.py` | Database access: read-only connection, keyword search, SQL safety checks |
| `pcards.db` / `pcards.db.zip` | P-Card transactions (2010-2014). If the host only has the Git LFS pointer, the app unpacks the zip automatically. |
| `requirements.txt` | Python packages |
| `.streamlit/secrets.toml.example` | Template for the API key (the real `secrets.toml` is git-ignored) |

## Security – API key

The Gemini API key is **not** in the source code or the repository. It is read from Streamlit secrets:

- **Streamlit Community Cloud:** App → *Settings* → *Secrets* → add `GEMINI_API_KEY = "your-key"`.
- **Locally:** copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and paste your key.

Generated SQL is also protected: only a single `SELECT`/`WITH` statement is accepted, write keywords are
blocked, and the database is opened in read-only mode. Dashboard searches use bound parameters.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```
