# airflow/dags/datapipeline_merge.py
from __future__ import annotations
import os
from datetime import datetime
from typing import List, Dict

from sqlalchemy import create_engine, text
from airflow import DAG
from airflow.operators.python import PythonOperator


# ---------- DB helpers ----------
def _db_url() -> str:
    url = os.getenv("SUPABASE_DB_URL") or os.getenv("SUPABASE_POOLER_URL")
    if not url:
        raise RuntimeError("Set SUPABASE_DB_URL or SUPABASE_POOLER_URL in the environment")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg2://" + url[len("postgresql://"):]
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url

def _engine():
    return create_engine(_db_url(), pool_pre_ping=True, connect_args={"connect_timeout": 10})


# ---------- pure-SQL merge ----------
def _fetch_all(conn, sql: str) -> List[Dict]:
    cur = conn.exec_driver_sql(sql)  # raw DB-API cursor
    cols = [d[0] for d in cur.cursor.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    return rows

def merge_two_sources():
    eng = _engine()
    with eng.begin() as conn:
        # Ensure both tables exist
        chk = text("""
            SELECT table_schema||'.'||table_name
            FROM information_schema.tables
            WHERE (table_schema='public' AND table_name IN ('coursera_demo','codecademy_demo'))
        """)
        existing = {f"{r[0]}" for r in conn.execute(chk).fetchall()}
        need = {"public.coursera_demo", "public.codecademy_demo"}
        missing = sorted(list(need - existing))
        if missing:
            raise RuntimeError(f"Missing tables: {', '.join(missing)}")

        # Fetch rows (all columns)
        rows_cou = _fetch_all(conn, "SELECT * FROM public.coursera")
        rows_cod = _fetch_all(conn, "SELECT * FROM public.codecademy")

        if not rows_cou and not rows_cod:
            raise RuntimeError("Both source tables are empty.")

        # Validate same columns
        cols_cou = list(rows_cou[0].keys()) if rows_cou else list(rows_cod[0].keys())
        cols_cod = list(rows_cod[0].keys()) if rows_cod else cols_cou
        if cols_cou != cols_cod:
            raise RuntimeError(f"Column mismatch.\n coursera_demo: {cols_cou}\n codecademy_demo: {cols_cod}")

        # DEBUGGING: Show column info
        print(f"🔍 coursera_demo columns: {cols_cou}")
        print(f"🔍 codecademy_demo columns: {cols_cod}")
        print(f"🔍 First coursera row sample: {rows_cou[0] if rows_cou else 'No rows'}")
        print(f"🔍 First codecademy row sample: {rows_cod[0] if rows_cod else 'No rows'}")

        merged = rows_cou + rows_cod
        columns = cols_cou

        # Create target and load (truncate+insert)
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS public.courses_merged (
            {', '.join(f'{c} TEXT' for c in columns)}
        );
        """
        conn.execute(text(create_sql))
        conn.execute(text("TRUNCATE TABLE public.courses_merged;"))

        insert_sql = text(f"""
            INSERT INTO public.courses_merged ({', '.join(columns)})
            VALUES ({', '.join(':'+c for c in columns)});
        """)

        B = 1000
        for i in range(0, len(merged), B):
            conn.execute(insert_sql, merged[i:i+B])

        print(f"✅ Merged {len(rows_cou)} + {len(rows_cod)} = {len(merged)} rows → public.courses_merged")


# ---------- Clean merged table (drop rows with NULL description) ----------
def clean_merged_table():
    """Remove rows with NULL/empty description column"""
    eng = _engine()
    with eng.begin() as conn:
        # Check if the merged table exists
        chk = text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema='public' AND table_name='courses_merged'
        """)
        if not conn.execute(chk).fetchone():
            raise RuntimeError("Table 'public.courses_merged' does not exist. Run merge task first.")
        
        # Check if description column exists
        col_check = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema='public' AND table_name='courses_merged' AND column_name='description'
        """)
        if not conn.execute(col_check).fetchone():
            raise RuntimeError("Table 'public.courses_merged' does not have 'description' column")
        
        # Count rows before cleaning
        count_before = conn.execute(text("SELECT COUNT(*) FROM public.courses_merged")).scalar()
        
        # Count rows with NULL/empty description before cleaning
        null_description_count = conn.execute(text(
            "SELECT COUNT(*) FROM public.courses_merged WHERE description IS NULL OR description = ''"
        )).scalar()
        
        # Delete rows with NULL or empty description
        delete_sql = text("DELETE FROM public.courses_merged WHERE description IS NULL OR description = ''")
        deleted_count = conn.execute(delete_sql).rowcount
        
        # Count rows after cleaning
        count_after = conn.execute(text("SELECT COUNT(*) FROM public.courses_merged")).scalar()
        
        print(f"✅ Cleaned merged table: removed {deleted_count} rows with NULL/empty description")
        print(f"📊 Row count: {count_before} → {count_after} (removed {deleted_count} rows)")
        print(f"🔍 Found {null_description_count} rows with NULL/empty description before cleaning")


# ---------- Generate embeddings ----------
# ---------- Generate embeddings ----------
def generate_embeddings():
    """Generate embeddings for the 'description' column using all-MiniLM-L6-v2"""
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        eng = _engine()
        with eng.begin() as conn:
            # Check if the table exists
            table_check = text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema='public' AND table_name='courses_merged'
            """)
            if not conn.execute(table_check).fetchone():
                raise RuntimeError("Table 'public.courses_merged' does not exist at all!")
            
            print("✅ Table 'public.courses_merged' exists")
            
            # Check if description column exists
            col_check = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema='public' AND table_name='courses_merged' AND column_name='description'
            """)
            if not conn.execute(col_check).fetchone():
                raise RuntimeError("Table 'public.courses_merged' does not have 'description' column")
            
            print("✅ Found 'description' column")
            
            # Fetch all rows with non-empty description
            rows = _fetch_all(conn, """
                SELECT 
                    course_id, title, provider, url, price, duration, level, language, 
                    rating, reviews_count, last_updated, keyword, description, 
                    what_you_will_learn, skills, recommended_experience
                FROM public.courses_merged 
                WHERE description IS NOT NULL AND description != ''
            """)
            
            if not rows:
                print("⚠️ No rows with non-empty description found")
                total_count = conn.execute(text("SELECT COUNT(*) FROM public.courses_merged")).scalar()
                null_description_count = conn.execute(text(
                    "SELECT COUNT(*) FROM public.courses_merged WHERE description IS NULL OR description = ''"
                )).scalar()
                print(f"📊 Total rows in table: {total_count}")
                print(f"📊 Rows with NULL/empty description: {null_description_count}")
                return
            
            print(f"📝 Generating embeddings for {len(rows)} rows using 'description' column...")
            
            # Load the model
            print("🔄 Loading sentence transformer model...")
            model = SentenceTransformer('all-MiniLM-L6-v2')
            print("✅ Model loaded successfully")
            
            # Extract descriptions only
            descriptions = [row['description'] for row in rows]
            
            # Generate embeddings in batches
            print("🔨 Generating embeddings...")
            BATCH_SIZE = 32
            embeddings = []
            
            for i in range(0, len(descriptions), BATCH_SIZE):
                batch_descriptions = descriptions[i:i+BATCH_SIZE]
                batch_embeddings = model.encode(batch_descriptions)
                embeddings.extend(batch_embeddings)
                print(f"✅ Processed batch {i//BATCH_SIZE + 1}/{(len(descriptions)-1)//BATCH_SIZE + 1}")
            
            embeddings = np.array(embeddings)
            
            # Convert numpy arrays to lists for storage
            embedding_list = [embedding.tolist() for embedding in embeddings]
            
            # Add embeddings to rows while preserving all original data
            for i, row in enumerate(rows):
                row['embeddings'] = embedding_list[i]  # Add embeddings as new field
            
            # Create table with embeddings if it doesn't exist (add embeddings column to existing schema)
            create_sql = """
            CREATE TABLE IF NOT EXISTS public.courses_with_embeddings (
                course_id TEXT,
                title TEXT,
                provider TEXT,
                url TEXT,
                price TEXT,
                duration TEXT,
                level TEXT,
                language TEXT,
                rating TEXT,
                reviews_count TEXT,
                last_updated TEXT,
                keyword TEXT,
                description TEXT,
                what_you_will_learn TEXT,
                skills TEXT,
                recommended_experience TEXT,
                embeddings FLOAT8[],  -- This is the only new column
                created_at TIMESTAMP DEFAULT NOW()
            );
            """
            conn.execute(text(create_sql))
            
            # Clear existing data
            conn.execute(text("TRUNCATE TABLE public.courses_with_embeddings;"))
            
            # Insert all original data plus embeddings
            insert_sql = text("""
                INSERT INTO public.courses_with_embeddings 
                (course_id, title, provider, url, price, duration, level, language, 
                 rating, reviews_count, last_updated, keyword, description, 
                 what_you_will_learn, skills, recommended_experience, embeddings)
                VALUES 
                (:course_id, :title, :provider, :url, :price, :duration, :level, :language,
                 :rating, :reviews_count, :last_updated, :keyword, :description,
                 :what_you_will_learn, :skills, :recommended_experience, :embeddings)
            """)
            
            B = 100
            for i in range(0, len(rows), B):
                batch = rows[i:i+B]
                conn.execute(insert_sql, batch)
                print(f"💾 Saved batch {i//B + 1}/{(len(rows)-1)//B + 1} to database")
            
            # Verify insertion
            count_embedded = conn.execute(text("SELECT COUNT(*) FROM public.courses_with_embeddings")).scalar()
            
            print(f"✅ Generated embeddings for {len(rows)} descriptions")
            print(f"📊 Saved {count_embedded} rows to public.courses_with_embeddings")
            print(f"🔢 Embedding dimension: {embeddings.shape[1]} (all-MiniLM-L6-v2)")
            print(f"💾 All original columns preserved + embeddings added")
            
    except Exception as e:
        print(f"❌ Error in generate_embeddings: {str(e)}")
        print(f"🔍 Error type: {type(e).__name__}")
        import traceback
        print(f"📄 Stack trace:\n{traceback.format_exc()}")
        raise

# ---------- DAG ----------
from pendulum import timezone

with DAG(
    dag_id="datapipeline_merge",
    start_date=datetime(2024, 1, 1),
    schedule="0 10 * * *",  # Runs every day at 10:00 AM
    catchup=False,
    tags=["merge", "supabase", "embeddings"],
    timezone=timezone("Asia/Singapore"),  # Ensures correct SGT scheduling
) as dag:

    merge_task = PythonOperator(
        task_id="merge_coursera_and_codecademy",
        python_callable=merge_two_sources,
    )
    
    clean_task = PythonOperator(
        task_id="clean_merged_table",
        python_callable=clean_merged_table,
    )
    
    embed_task = PythonOperator(
        task_id="generate_embeddings",
        python_callable=generate_embeddings,
    )
    
    # Set task dependencies
    merge_task >> clean_task >> embed_task