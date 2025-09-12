import psycopg2
from datetime import datetime
from config import POSTGRES_URL


def save_query_to_postgres(query, source, result_count, recommendation):
    """Save query to PostgreSQL database"""
    if not POSTGRES_URL:
        return False
        
    try:
        with psycopg2.connect(POSTGRES_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO funding_queries (timestamp, query, source, result_count, recommendation)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    datetime.utcnow(), query, source, result_count, recommendation
                ))
                conn.commit()
                print("✅ Query saved to PostgreSQL")
                return True
    except Exception as e:
        print("❌ Error saving to database:", e)
        return False


def get_recent_queries(limit=20):
    """Get recent queries from PostgreSQL database"""
    if not POSTGRES_URL:
        return []
        
    try:
        with psycopg2.connect(POSTGRES_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT timestamp, query, source, result_count, recommendation
                    FROM funding_queries
                    ORDER BY timestamp DESC
                    LIMIT %s
                """, (limit,))
                rows = cursor.fetchall()

                # Format with proper timestamp
                results = []
                for r in rows:
                    try:
                        timestamp = datetime.fromisoformat(str(r[0]))
                        formatted_time = timestamp.strftime("%B %d, %Y at %H:%M")
                    except:
                        formatted_time = str(r[0])
                        
                    results.append({
                        "timestamp": str(r[0]),
                        "formatted_timestamp": formatted_time,
                        "query": r[1],
                        "source": r[2],
                        "result_count": r[3],
                        "recommendation": r[4]
                    })
                return results
                
    except Exception as e:
        print("❌ Error fetching recent queries:", e)
        return []


def clear_all_queries():
    """Clear all queries from PostgreSQL database"""
    if not POSTGRES_URL:
        return False
        
    try:
        with psycopg2.connect(POSTGRES_URL) as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM funding_queries")
                conn.commit()
                print("🧼 All queries cleared.")
                return True
    except Exception as e:
        print("❌ Error clearing queries:", e)
        return False