import sqlite3

"""
    * Module to create a demo.db file for sqlite3
    * To demonstrate record keeping for a client,
        and their later will use this stock data for analytics
"""
def create_connection(db_file):
    """Create a database connection to the SQLite database."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # Enable foreign key constraints
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn


def create_tables(conn):
    """Create tables in the SQLite database."""
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL
        );
    """)

    # Trades table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            trade_type TEXT NOT NULL,   -- stock, option_single, option_multi
            action TEXT NOT NULL,       -- buy, sell, buy_to_open, sell_to_open, buy_to_close, sell_to_close, roll
            date TEXT NOT NULL,
            notes TEXT,
            ticker_symbol TEXT,
            cash_balance REAL DEFAULT 30000,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
    """)

    # Trade legs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_legs (
            leg_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_id INTEGER NOT NULL,
            asset_type TEXT NOT NULL,   -- stock or option
            ticker TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            strike REAL,
            expiration TEXT,
            option_type TEXT,           -- call or put
            side TEXT,                  -- long or short
            FOREIGN KEY (trade_id) REFERENCES trades(trade_id)
        );
    """)

    conn.commit()
    print("Tables created successfully.")


def main():
    database = "demo.db"

    conn = create_connection(database)
    if conn is not None:
        create_tables(conn)
        conn.close()
        print("Database setup complete.")
    else:
        print("Error! Cannot create the database connection.")


if __name__ == "__main__":
    main()
