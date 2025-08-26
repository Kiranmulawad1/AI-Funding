import psycopg2
from datetime import datetime
from config import POSTGRES_URL


def save_query_to_postgres(query, source, result_count, recommendation):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()

        # ❌ Avoid duplicate entries based on query + source + recommendation
        cursor.execute("""
            SELECT 1 FROM funding_queries
            WHERE query = %s AND source = %s AND recommendation = %s
            LIMIT 1
        """, (query, source, recommendation))
        exists = cursor.fetchone()

        if exists:
            print("⚠️ Duplicate query detected — skipping insert.")
        else:
            cursor.execute("""
                INSERT INTO funding_queries (timestamp, query, source, result_count, recommendation)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                datetime.utcnow(), query, source, result_count, recommendation
            ))
            conn.commit()
            print("✅ Query saved to PostgreSQL")

        cursor.close()
        conn.close()

    except Exception as e:
        print("❌ Error saving to database:", e)


def get_recent_queries(limit=20):
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT timestamp, query, source, result_count, recommendation
            FROM funding_queries
            ORDER BY timestamp DESC
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return [{
            "timestamp": str(r[0]),
            "query": r[1],
            "source": r[2],
            "result_count": r[3],
            "recommendation": r[4]
        } for r in rows]
    except Exception as e:
        print("❌ Error fetching recent queries:", e)
        return []


def clear_all_queries():
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM funding_queries")
        conn.commit()
        cursor.close()
        conn.close()
        print("🧼 All queries cleared.")
    except Exception as e:
        print("❌ Error clearing queries:", e)
