#!/usr/bin/env python3
"""
Script to copy the auth schema from the main Supabase database to the test database.
This ensures tests have access to the authentic Supabase auth schema structure.
"""

import os
import sys
import logging
import argparse
import psycopg
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def copy_auth_schema(source_db, target_db, host, port, user, password):
    """Copy the auth schema from the source database to the target database"""
    logger.info(f"Copying auth schema from {source_db} to {target_db}")
    
    try:
        # Connect to source database
        source_conn = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=source_db
        )
        
        # Check if auth schema exists in source
        with source_conn.cursor() as cursor:
            cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'auth';")
            result = cursor.fetchone()
            if not result or 'auth' not in result:
                logger.error(f"Auth schema not found in source database {source_db}")
                return False
            
            # Get tables in auth schema
            logger.info("Retrieving auth schema tables...")
            cursor.execute("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'auth' AND table_type = 'BASE TABLE'
            """)
            tables = [row[0] for row in cursor.fetchall()]
            logger.info(f"Found {len(tables)} tables in auth schema: {tables}")
            
            # Get schema creation SQL
            cursor.execute("SELECT pg_catalog.pg_get_userbyid(nspowner) as owner FROM pg_catalog.pg_namespace WHERE nspname = 'auth';")
            schema_owner = cursor.fetchone()[0]
            
        # Connect to target database
        target_conn = psycopg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=target_db
        )
        
        # Create auth schema in target if not exists
        with target_conn.cursor() as cursor:
            logger.info("Creating auth schema in target database...")
            cursor.execute("CREATE SCHEMA IF NOT EXISTS auth;")
            target_conn.commit()
        
        # For each table, get its definition and create in target
        with source_conn.cursor() as source_cursor, target_conn.cursor() as target_cursor:
            # Get table definitions
            for table in tables:
                logger.info(f"Processing table: auth.{table}")
                
                # Get table columns
                source_cursor.execute(f"""
                    SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = 'auth' AND table_name = '{table}'
                    ORDER BY ordinal_position
                """)
                columns = source_cursor.fetchall()
                
                # Get primary key
                source_cursor.execute(f"""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = 'auth.{table}'::regclass AND i.indisprimary;
                """)
                primary_keys = [row[0] for row in source_cursor.fetchall()]
                
                # Construct CREATE TABLE statement
                create_table_stmt = f"CREATE TABLE IF NOT EXISTS auth.{table} (\n"
                for i, (col_name, data_type, max_length, nullable, default) in enumerate(columns):
                    create_table_stmt += f"    {col_name} {data_type}"
                    if max_length:
                        create_table_stmt += f"({max_length})"
                    if not nullable or nullable == 'NO':
                        create_table_stmt += " NOT NULL"
                    if default:
                        create_table_stmt += f" DEFAULT {default}"
                    if i < len(columns) - 1 or primary_keys:
                        create_table_stmt += ",\n"
                
                # Add primary key if exists
                if primary_keys:
                    pk_cols = ", ".join(primary_keys)
                    create_table_stmt += f"    PRIMARY KEY ({pk_cols})\n"
                
                create_table_stmt += ");\n"
                
                # Create the table
                try:
                    target_cursor.execute(create_table_stmt)
                    target_conn.commit()
                    logger.info(f"Created auth.{table}")
                except psycopg.errors.DuplicateTable:
                    target_conn.rollback()
                    logger.info(f"Table auth.{table} already exists")
                except Exception as e:
                    target_conn.rollback()
                    logger.error(f"Error creating auth.{table}: {str(e)}")
                    logger.error(f"SQL: {create_table_stmt}")
        
        # Ensure auth.users has the required columns for testing
        logger.info("Ensuring auth.users has all required columns...")
        with target_conn.cursor() as cursor:
            # Check if the aud column exists in auth.users
            cursor.execute("""SELECT column_name FROM information_schema.columns 
                            WHERE table_schema = 'auth' AND table_name = 'users' AND column_name = 'aud';""")
            aud_exists = cursor.fetchone()
            
            if not aud_exists:
                logger.info("Adding 'aud' column to auth.users")
                try:
                    cursor.execute("ALTER TABLE auth.users ADD COLUMN aud VARCHAR(255);")
                    target_conn.commit()
                    logger.info("✅ Added 'aud' column to auth.users")
                except Exception as e:
                    target_conn.rollback()
                    logger.warning(f"Failed to add 'aud' column: {str(e)}")
        
        # Create a test user
        logger.info("Creating test user...")
        with target_conn.cursor() as cursor:
            try:
                cursor.execute("""
                    INSERT INTO auth.users (id, email, encrypted_password, role, aud) 
                    VALUES ('00000000-0000-0000-0000-000000000000', 'test@example.com', 'password', 'authenticated', 'authenticated') 
                    ON CONFLICT (id) DO NOTHING;
                """)
                target_conn.commit()
                logger.info("✅ Test user created successfully")
            except Exception as e:
                target_conn.rollback()
                logger.warning(f"Failed to create test user: {str(e)}")
        
        source_conn.close()
        target_conn.close()
        
        logger.info("✅ Auth schema copied successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error copying auth schema: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy auth schema from source to target database")
    parser.add_argument("--source-db", default="postgres", help="Source database with auth schema (default: postgres)")
    parser.add_argument("--target-db", default="auth_test_db", help="Target database for auth schema (default: auth_test_db)")
    parser.add_argument("--host", default=os.environ.get("DB_HOST", "supabase_db_paservices"), help="Database host")
    parser.add_argument("--port", default=os.environ.get("DB_PORT", "5432"), help="Database port")
    parser.add_argument("--user", default=os.environ.get("DB_USER", "postgres"), help="Database user")
    parser.add_argument("--password", default=os.environ.get("DB_PASSWORD", "postgres"), help="Database password")
    
    args = parser.parse_args()
    
    success = copy_auth_schema(
        args.source_db,
        args.target_db,
        args.host, 
        args.port, 
        args.user, 
        args.password
    )
    
    if success:
        logger.info("Auth schema copy completed successfully")
        sys.exit(0)
    else:
        logger.error("Auth schema copy failed")
        sys.exit(1)
