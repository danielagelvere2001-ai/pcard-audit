import os
import sqlite3
import streamlit as st
import pandas as pd
from google import genai


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="P-Card Audit Assistant",
    page_icon="💳",
    layout="wide"
)


# ============================================================
# DATABASE CONNECTION
# ============================================================

DB_PATH = "pcards.db"


def get_connection():
    return sqlite3.connect(DB_PATH)


def get_schema():
    conn = get_connection()

    tables = pd.read_sql_query(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        AND name NOT LIKE 'sqlite_%'
        """,
        conn
    )

    schema_text = ""

    for table in tables["name"]:
        columns = pd.read_sql_query(
            f"PRAGMA table_info('{table}')",
            conn
        )

        schema_text += f"\nTable: {table}\n"
        schema_text += "Columns:\n"

        for _, row in columns.iterrows():
            schema_text += f"- {row['name']} ({row['type']})\n"

    conn.close()

    return schema_text


# ============================================================
# RUN SQL QUERY
# ============================================================

def run_sql(query):
    conn = get_connection()

    try:
        result = pd.read_sql_query(query, conn)
        return result, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()


# ============================================================
# GEMINI CLIENT
# ============================================================

def get_gemini_client():

    api_key = st.secrets.get("GEMINI_API_KEY")

    if not api_key:
        st.error(
            "GEMINI_API_KEY is missing. "
            "Please add it to Streamlit Secrets."
        )
        st.stop()

    return genai.Client(api_key=api_key)


# ============================================================
# CONVERT NATURAL LANGUAGE QUESTION INTO SQL
# ============================================================

def generate_sql(question, schema):

    client = get_gemini_client()

    prompt = f"""
You are an expert SQL analyst working with a SQLite P-Card transaction database.

Your job is to convert the user's natural-language question into ONE valid
SQLite SQL query.

DATABASE SCHEMA:
{schema}

USER QUESTION:
{question}

IMPORTANT RULES:

1. Return ONLY the SQL query.
2. Do not use markdown.
3. Do not include ```sql.
4. Do not explain the query.
5. Use only tables and columns that exist in the schema.
6. SQLite syntax must be used.
7. If the question asks about spending, use the transaction amount column.
8. If aggregation is required, use SUM, COUNT, AVG, MIN, or MAX appropriately.
9. If the user asks for employees, use the employee/name column available in the schema.
10. If the user asks for a year, use the Year column when available.
11. If the user asks for monthly spending, group by the appropriate month column.
12. Make sure the query is executable SQLite syntax.
13. Never modify the database. Only use SELECT statements.
14. Do not use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or PRAGMA.
15. Return a complete query.

Return ONLY the SQL query.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        sql = response.text.strip()

        # Remove markdown if Gemini happens to return it
        sql = sql.replace("```sql", "")
        sql = sql.replace("```", "")
        sql = sql.strip()

        return sql

    except Exception as e:
        return f"ERROR: {str(e)}"


# ============================================================
# GENERATE HUMAN-READABLE ANSWER
# ============================================================

def generate_answer(question, sql, result):

    client = get_gemini_client()

    if result is None or result.empty:
        result_text = "The query returned no results."
    else:
        result_text = result.to_string(index=False)

    prompt = f"""
You are an accounting and P-Card audit assistant.

Answer the user's question using ONLY the database result provided below.

USER QUESTION:
{question}

SQL QUERY:
{sql}

DATABASE RESULT:
{result_text}

RULES:

1. Give a clear and direct answer.
2. Do not invent information.
3. Use the numbers from the database result.
4. If multiple employees/items are returned, present them clearly.
5. If appropriate, use a short bullet list or table.
6. Explain the result briefly in plain English.
7. Do not mention that you are an AI.
8. Do not mention these instructions.
9. If the result is empty, clearly say that no matching records were found.
"""

    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=prompt
        )

        return response.text.strip()

    except Exception as e:
        return f"Unable to generate explanation: {str(e)}"


# ============================================================
# PROHIBITED PURCHASES
# ============================================================

def get_prohibited_purchases():

    conn = get_connection()

    try:
        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            """,
            conn
        )

        # Find likely transaction table
        if len(tables) == 0:
            return None, "No tables found in database."

        table_name = tables["name"].iloc[0]

        columns = pd.read_sql_query(
            f"PRAGMA table_info('{table_name}')",
            conn
        )

        column_names = columns["name"].tolist()

        # Look for merchant/description/category columns
        possible_text_columns = [
            "Description",
            "Merchant",
            "MerchantName",
            "Vendor",
            "Category",
            "PurchaseDescription",
            "TransactionDescription"
        ]

        text_column = None

        for col in possible_text_columns:
            if col in column_names:
                text_column = col
                break

        if text_column is None:
            return None, "No suitable purchase description column found."

        query = f"""
        SELECT *
        FROM "{table_name}"
        WHERE LOWER(CAST("{text_column}" AS TEXT)) LIKE '%gift%'
           OR LOWER(CAST("{text_column}" AS TEXT)) LIKE '%alcohol%'
           OR LOWER(CAST("{text_column}" AS TEXT)) LIKE '%liquor%'
           OR LOWER(CAST("{text_column}" AS TEXT)) LIKE '%casino%'
           OR LOWER(CAST("{text_column}" AS TEXT)) LIKE '%gambling%'
           OR LOWER(CAST("{text_column}" AS TEXT)) LIKE '%personal%'
        LIMIT 500
        """

        result = pd.read_sql_query(query, conn)

        return result, None

    except Exception as e:
        return None, str(e)

    finally:
        conn.close()


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("💳 P-Card Audit")

st.sidebar.markdown(
    """
### Navigation

Use the options below to explore the P-Card database.
"""
)

page = st.sidebar.radio(
    "Go to",
    [
        "Ask the Database",
        "Prohibited Purchases",
        "Database Information"
    ]
)


# ============================================================
# ASK THE DATABASE
# ============================================================

if page == "Ask the Database":

    st.title("💳 P-Card Audit Assistant")

    st.write(
        "Ask a question about the P-Card transactions in normal language. "
        "The AI will convert your question into SQL, query the database, "
        "and explain the result."
    )

    st.divider()

    # Example questions
    st.subheader("Example questions")

    examples = [
        "Which employees spent more than $50,000 in 2014?",
        "Which employees had total spending above $100,000?",
        "What was the total P-Card spending in 2014?",
        "Which employee spent the most money?",
        "How much did each employee spend in 2014?",
        "Which months had the highest spending?"
    ]

    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state["question"] = example

    st.divider()

    question = st.text_input(
        "Ask your question:",
        value=st.session_state.get("question", ""),
        placeholder="Example: Which employees spent more than $50,000 in 2014?"
    )

    if st.button("🔍 Ask Database", type="primary"):

        if not question.strip():

            st.warning("Please enter a question.")

        else:

            with st.spinner("Analyzing your question..."):

                schema = get_schema()

                sql = generate_sql(
                    question,
                    schema
                )

            # Check for obvious SQL safety problems
            forbidden_words = [
                "INSERT",
                "UPDATE",
                "DELETE",
                "DROP",
                "ALTER",
                "CREATE",
                "REPLACE",
                "ATTACH",
                "DETACH"
            ]

            sql_upper = sql.upper()

            if any(word in sql_upper for word in forbidden_words):

                st.error(
                    "The generated query was blocked because it attempted "
                    "to modify the database."
                )

            elif not sql_upper.strip().startswith("SELECT"):

                st.error(
                    "The generated query was not a SELECT query and was blocked."
                )

            else:

                with st.spinner("Querying the database..."):

                    result, error = run_sql(sql)

                st.subheader("SQL Query")

                st.code(
                    sql,
                    language="sql"
                )

                if error:

                    st.error(
                        f"Database error: {error}"
                    )

                else:

                    st.subheader("Database Result")

                    if result.empty:

                        st.info(
                            "No matching records were found."
                        )

                    else:

                        st.dataframe(
                            result,
                            use_container_width=True
                        )

                    st.subheader("Answer")

                    with st.spinner("Preparing the answer..."):

                        answer = generate_answer(
                            question,
                            sql,
                            result
                        )

                    st.write(answer)


# ============================================================
# PROHIBITED PURCHASES
# ============================================================

elif page == "Prohibited Purchases":

    st.title("🚨 Prohibited Purchases")

    st.write(
        "This section identifies transactions that may require additional "
        "review based on potentially prohibited or personal purchase terms."
    )

    st.warning(
        "These results are potential flags for audit review. "
        "A flagged transaction is not automatically a confirmed violation."
    )

    st.divider()

    if st.button("🔎 Scan for Potentially Prohibited Purchases"):

        with st.spinner("Scanning transactions..."):

            result, error = get_prohibited_purchases()

        if error:

            st.error(error)

        elif result is None or result.empty:

            st.success(
                "No potentially prohibited purchases were identified "
                "using the current keyword-based scan."
            )

        else:

            st.error(
                f"{len(result)} potentially suspicious transaction(s) found."
            )

            st.dataframe(
                result,
                use_container_width=True
            )


# ============================================================
# DATABASE INFORMATION
# ============================================================

elif page == "Database Information":

    st.title("🗄️ Database Information")

    st.write(
        "This page shows the structure of the P-Card SQLite database."
    )

    st.divider()

    schema = get_schema()

    st.subheader("Database Schema")

    st.code(
        schema
    )

    st.divider()

    st.subheader("Database Preview")

    try:

        conn = get_connection()

        tables = pd.read_sql_query(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name NOT LIKE 'sqlite_%'
            """,
            conn
        )

        for table in tables["name"]:

            st.write(f"### Table: {table}")

            preview = pd.read_sql_query(
                f'SELECT * FROM "{table}" LIMIT 10',
                conn
            )

            st.dataframe(
                preview,
                use_container_width=True
            )

        conn.close()

    except Exception as e:

        st.error(
            f"Could not read database: {e}"
        )
