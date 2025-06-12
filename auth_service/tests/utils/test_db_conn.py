import asyncio
import os
import socket

import psycopg
from psycopg_pool import AsyncConnectionPool
from dotenv import load_dotenv


async def main():
    load_dotenv()
    db_url_original = os.getenv("AUTH_SERVICE_DATABASE_URL")
    # Example URL format for reference (sanitized)
    # db_url_original = "postgresql+psycopg://username:password@host:5432/postgres"

    if not db_url_original:
        print("Error: AUTH_SERVICE_DATABASE_URL not found in environment or .env file.")
        return

    # Modify URL for direct psycopg connection
    if db_url_original.startswith("postgresql+psycopg://"):
        db_url_for_psycopg = db_url_original.replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
    else:
        db_url_for_psycopg = db_url_original  # Or handle error if scheme is unexpected

    print(f"Original SQLAlchemy URL: {db_url_original}")
    print(f"Attempting to connect with psycopg using URL: {db_url_for_psycopg}")

    try:
        # Create a connection with psycopg - note that it's a synchronous operation in an async function
        conn = await psycopg.AsyncConnection.connect(db_url_for_psycopg, prepare_threshold=0)  # Disable prepared statements
        print("Successfully connected to the database!")
        version = await conn.fetchval("SELECT version();")
        print(f"PostgreSQL Version: {version}")
        await conn.close()
        print("Connection closed.")
    except asyncpg.exceptions.InvalidPasswordError:
        print("Connection failed: Invalid password.")
    except ConnectionRefusedError:
        print(
            "Connection failed: Connection refused by the server. (Check port and if DB server is listening)"
        )
    except socket.gaierror as e:
        print(
            f"Connection failed: DNS resolution error (socket.gaierror). Could not resolve hostname. Details: {e}"
        )
    except (
        asyncpg.exceptions._base.ClientConfigurationError
    ) as e:  # Catch the DSN error
        print(f"Connection failed: Invalid DSN for asyncpg. Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(f"Error type: {type(e)}")


if __name__ == "__main__":
    asyncio.run(main())
