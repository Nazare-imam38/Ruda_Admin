"""Interactive one-time setup for LOCAL Postgres/PostGIS on Windows, no Docker.

Requirements: psycopg installed into backend/.venv and local postgres running.
This script creates ONLY a new database named gis_automation_test if absent.
It never drops or alters any other database.
"""
from getpass import getpass
from pathlib import Path
from urllib.parse import quote
import json
import sys

import psycopg
from psycopg import sql

DB_NAME = 'gis_automation_test'
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / 'backend' / '.env'


def ask_port():
    value = input('PostgreSQL port [5432]: ').strip() or '5432'
    if not value.isdecimal() or not (1 <= int(value) <= 65535):
        raise ValueError('Port must be between 1 and 65535.')
    return int(value)


def main():
    print('\nGIS AUTOMATION LAB — LOCAL POSTGIS CONFIGURATION')
    print('Only database "gis_automation_test" will be created or used.')
    print('Your existing RUDA databases are not modified.\n')
    host = '127.0.0.1'
    port = ask_port()
    user = input('Local PostgreSQL user [postgres]: ').strip() or 'postgres'
    password = getpass('Password for this PostgreSQL user (not displayed): ')
    print('\nChecking local PostgreSQL connection...')
    try:
        with psycopg.connect(host=host, port=port, dbname='postgres', user=user,
                             password=password, autocommit=True, connect_timeout=6) as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', (DB_NAME,))
                exists = cur.fetchone() is not None
                if not exists:
                    print('Creating the isolated lab database...')
                    cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DB_NAME)))
                else:
                    print('Lab database already exists; preserving existing records.')
        with psycopg.connect(host=host, port=port, dbname=DB_NAME, user=user,
                             password=password, autocommit=True, connect_timeout=6) as conn:
            with conn.cursor() as cur:
                print('Enabling the PostGIS extension in LAB database only...')
                cur.execute('CREATE EXTENSION IF NOT EXISTS postgis')
                cur.execute('SELECT PostGIS_Version()')
                print('PostGIS version:', cur.fetchone()[0])
    except psycopg.Error as exc:
        print('\nDATABASE SETUP FAILED:', str(exc).splitlines()[0])
        print('Check: PostgreSQL service running, correct port/password, and PostGIS installed.')
        print('For PostgreSQL 17 install its matching PostGIS package (e.g. via StackBuilder).')
        print('Then run SETUP_WINDOWS.bat again. No RUDA database has been deleted.')
        return 1
    # dotenv understands JSON-style quoted strings and preserves special characters.
    values = {'DB_HOST': host, 'DB_PORT': str(port), 'DB_NAME': DB_NAME,
              'DB_USER': user, 'DB_PASSWORD': password}
    ENV_PATH.write_text(''.join(f'{key}={json.dumps(str(value))}\n' for key, value in values.items()), encoding='utf-8')
    print('Saved connection settings privately in backend/.env (do not share this file).')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (KeyboardInterrupt, ValueError) as exc:
        print('\nSetup cancelled or invalid input:', str(exc))
        sys.exit(1)
