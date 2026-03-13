"""SQLite migration to alter `user` table: remove UNIQUE on company_id and add `role` column.

This script will:
- create a new `user_new` table with updated schema
- copy data from `user` to `user_new` (existing users get role='owner')
- drop old `user` table
- rename `user_new` to `user`

Run: python scripts/migrate_user_table.py
"""
import sqlite3
import os

import config

# Respect instance DB location
DB = os.environ.get('DATABASE_URL') or os.path.join(config.INSTANCE_DIR, 'pharmacy.db')

def migrate():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("PRAGMA foreign_keys=OFF;")
    conn.commit()

    # Create new table
    cur.execute('''
    CREATE TABLE IF NOT EXISTS user_new (
        id INTEGER PRIMARY KEY,
        company_id INTEGER NOT NULL,
        username VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        is_active BOOLEAN DEFAULT 1,
        last_login DATETIME,
        created_date DATETIME,
        updated_date DATETIME,
        role VARCHAR(20) DEFAULT 'owner',
        FOREIGN KEY(company_id) REFERENCES company(id)
    );
    ''')
    conn.commit()

    # Copy data, set role='owner' for existing rows
    cur.execute('''
    INSERT INTO user_new (id, company_id, username, password_hash, is_active, last_login, created_date, updated_date, role)
    SELECT id, company_id, username, password_hash, is_active, last_login, created_date, updated_date, 'owner' FROM user;
    ''')
    conn.commit()

    # Drop old table and rename
    cur.execute('''
    DROP TABLE user;
    ''')
    conn.commit()

    cur.execute('''
    ALTER TABLE user_new RENAME TO user;
    ''')
    conn.commit()

    cur.execute("PRAGMA foreign_keys=ON;")
    conn.commit()
    conn.close()
    print('Migration finished. New `user` table has `role` and allows multiple users per company.')

if __name__ == '__main__':
    migrate()