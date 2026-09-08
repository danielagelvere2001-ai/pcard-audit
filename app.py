import os
import sqlite3
import streamlit as st
from openai import OpenAI

st.set_page_config(
    page_title="P-Card Audit Assistant",
    page_icon="💳",
    layout="wide"
)

st.title("💳 P-Card Audit Assistant")
st.write("Ask questions about purchasing-card transactions using natural language.")

# OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Database connection
DB_PATH = "pcards.db"


def get_database_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
    """)

    tables = cursor.fetchall()

    schema = ""

    for table in tables:
        table_name = table[0]

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()

        schema += f"\nTable: {table_name}\n"

        for column in columns:
            schema += f"- {column[1]} ({column[2]})\n"

    conn.close()

    return schema


def run_sql(query):
    conn = sqlite3.connect(DB_PATH)

    try:
        cursor = conn.cursor()
        cursor.execute(query)

        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]

        conn.close()

        return columns, rows

    except Exception as e:
        conn.close()
        return None, str(e)


def generate_sql(question, schema):

    prompt = f"""
You are an accounting and auditing assistant.

Convert the user's question into ONE valid SQLite SQL query.

Database schema:
{schema}

User question:
{question}

Rules:
- Return ONLY the SQL query.
- Do not use markdown.
- Use SQLite syntax.
- Do not modify, insert, update, or delete data.
- Only use SELECT queries.
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


def explain_result(question, columns, rows):

    data = [dict(zip(columns, row)) for row in rows]

    prompt = f"""
You are an accounting and business data analyst.

Answer the user's question using the database results below.

Question:
{question}

Results:
{data}

Give a short, clear answer.
If there are multiple results, summarize them in an easy-to-read way.
Do not invent information.
"""

    response = client.responses.create(
        model="gpt-5-mini",
        input=prompt
    )

    return response.output_text.strip()


# Check database
if not os.path.exists(DB_PATH):

    st.error(
        "The database file pcards.db was not found. "
        "Please upload/add pcards.db to the project."
    )

else:

    schema = get_database_schema()

    question = st.text_input(
        "Ask a question about the P-Card transactions:",
        placeholder="Example: Which employees spent more than $50,000 in 2014?"
    )

    if st.button("Ask"):

        if not question:
            st.warning("Please enter a question.")

        else:

            with st.spinner("Analyzing the database..."):

                try:

                    sql_query = generate_sql(question, schema)

                    # Security check
                    if not sql_query.lower().strip().startswith("select"):
                        st.error("Only SELECT queries are allowed.")
                        st.stop()

                    columns, result = run_sql(sql_query)

                    if columns is None:
                        st.error(f"SQL error: {result}")

                    else:

                        st.subheader("Answer")

                        answer = explain_result(
                            question,
                            columns,
                            result
                        )

                        st.write(answer)

                        st.subheader("Database Results")

                        st.dataframe(
                            [dict(zip(columns, row)) for row in result],
                            use_container_width=True
                        )

                        with st.expander("View SQL query"):

                            st.code(
                                sql_query,
                                language="sql"
                            )

                except Exception as e:

                    st.error(
                        f"Something went wrong: {e}"
                    )
