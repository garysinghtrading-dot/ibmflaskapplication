import sqlite3

class TradeService:
    def __init__(self, db_path="records/demo.db"):
        self.db_path = db_path

    # -----------------------------
    # Internal DB helper
    # -----------------------------
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -----------------------------
    # User helpers
    # -----------------------------
    def get_user_id(self, username):
        conn = self._get_db()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        return row["user_id"] if row else None

    # -----------------------------
    # Position helpers
    # -----------------------------
    def get_positions(self, user_id):
        """
        Returns a list of:
        {
            ticker: "CRM",
            total_shares: 100,
            avg_cost: 190.0
        }
        """
        conn = self._get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT 
                ticker,
                SUM(quantity) AS total_shares,
                SUM(quantity * price) AS total_cost
            FROM trade_legs
            JOIN trades ON trades.trade_id = trade_legs.trade_id
            WHERE trades.user_id = ?
              AND asset_type = 'stock'
            GROUP BY ticker;
        """, (user_id,))

        rows = cur.fetchall()
        conn.close()

        positions = []
        for r in rows:
            if r["total_shares"] != 0:
                avg_cost = r["total_cost"] / r["total_shares"]
            else:
                avg_cost = 0

            positions.append({
                "ticker": r["ticker"],
                "total_shares": r["total_shares"],
                "avg_cost": round(avg_cost, 2)
            })

        return positions

    # -----------------------------
    # Buy helpers
    # -----------------------------
    def buy_stock(self, user_id, ticker, qty, price):
        conn = self._get_db()
        cur = conn.cursor()

        # Insert into trades
        cur.execute("""
            INSERT INTO trades (user_id, trade_type, action, date, ticker_symbol)
            VALUES (?, 'stock', 'buy', DATE('now'), ?)
        """, (user_id, ticker))

        trade_id = cur.lastrowid

        # Insert into trade_legs
        cur.execute("""
            INSERT INTO trade_legs (
                trade_id, asset_type, ticker, quantity, price, strike, expiration, option_type, side
            )
            VALUES (?, 'stock', ?, ?, ?, NULL, NULL, NULL, 'long')
        """, (trade_id, ticker, qty, price))

        conn.commit()
        conn.close()

    # -----------------------------
    # Sell helpers
    # -----------------------------
    def get_total_shares(self, user_id, ticker):
        conn = self._get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT SUM(quantity) FROM trade_legs
            JOIN trades ON trades.trade_id = trade_legs.trade_id
            WHERE trades.user_id = ?
              AND trade_legs.ticker = ?
              AND trade_legs.asset_type = 'stock';
        """, (user_id, ticker))

        result = cur.fetchone()[0]
        conn.close()
        return result if result else 0

    def get_buy_lots(self, user_id, ticker):
        conn = self._get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT trade_legs.leg_id, trade_legs.quantity, trade_legs.price, trades.date
            FROM trade_legs
            JOIN trades ON trades.trade_id = trade_legs.trade_id
            WHERE trades.user_id = ?
              AND trade_legs.ticker = ?
              AND trade_legs.asset_type = 'stock'
              AND trade_legs.quantity > 0
            ORDER BY trades.date ASC;
        """, (user_id, ticker))

        rows = cur.fetchall()
        conn.close()
        return rows

    def sell_stock_fifo(self, user_id, ticker, qty, price):
        total_shares = self.get_total_shares(user_id, ticker)

        if qty > total_shares:
            return f"Error: You are trying to sell {qty} shares but only hold {total_shares}."

        remaining = qty
        buy_lots = self.get_buy_lots(user_id, ticker)

        conn = self._get_db()
        cur = conn.cursor()

        # Create parent trade
        cur.execute("""
            INSERT INTO trades (user_id, trade_type, action, date, ticker_symbol)
            VALUES (?, 'stock', 'sell', DATE('now'), ?)
        """, (user_id, ticker))
        trade_id = cur.lastrowid

        for lot in buy_lots:
            if remaining <= 0:
                break

            lot_qty = lot["quantity"]
            qty_to_sell = min(lot_qty, remaining)

            # Insert SELL leg
            cur.execute("""
                INSERT INTO trade_legs (
                    trade_id, asset_type, ticker, quantity, price, strike, expiration, option_type, side
                )
                VALUES (?, 'stock', ?, ?, ?, NULL, NULL, NULL, 'long')
            """, (trade_id, ticker, -qty_to_sell, price))

            remaining -= qty_to_sell

        conn.commit()
        conn.close()
        return None

    def add_option_trade(self, user_id, symbol, strike, expiration, option_type,
                        action, quantity, price):
        conn = self._get_db()
        cur = conn.cursor()

        # Map UI action to DB semantics
        if action == "Buy to Open":
            trade_action = "buy"
            side = "long"
        elif action == "Sell to Open":
            trade_action = "sell"
            side = "short"
        elif action == "Buy to Close":
            trade_action = "buy"
            side = "short"
        elif action == "Sell to Close":
            trade_action = "sell"
            side = "long"
        else:
            raise ValueError("Invalid option action")

        # Insert into trades table
        cur.execute("""
            INSERT INTO trades (user_id, trade_type, action, date, ticker_symbol, notes)
            VALUES (?, 'option', ?, DATE('now'), ?, NULL)
        """, (user_id, trade_action, symbol))

        trade_id = cur.lastrowid

        # Insert into trade_legs table
        cur.execute("""
            INSERT INTO trade_legs (
                trade_id, asset_type, ticker, quantity, price,
                strike, expiration, option_type, side
            )
            VALUES (?, 'option', ?, ?, ?, ?, ?, ?, ?)
        """, (trade_id, symbol, quantity, price, strike, expiration, option_type, side))

        conn.commit()
        conn.close()

    def get_open_option_positions(self, user_id, symbol):
        conn = self.get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT strike, expiration, option_type,
                SUM(CASE WHEN side='long' THEN quantity ELSE 0 END) AS long_qty,
                SUM(CASE WHEN side='short' THEN quantity ELSE 0 END) AS short_qty
            FROM trade_legs
            JOIN trades ON trades.trade_id = trade_legs.trade_id
            WHERE trades.user_id = ?
            AND trade_legs.asset_type = 'option'
            AND trade_legs.ticker = ?
            GROUP BY strike, expiration, option_type
        """, (user_id, symbol))

        rows = cur.fetchall()
        conn.close()

        # Filter only open positions
        open_positions = []
        for r in rows:
            net = r["long_qty"] - r["short_qty"]
            if net != 0:
                open_positions.append({
                    "strike": r["strike"],
                    "expiration": r["expiration"],
                    "option_type": r["option_type"],
                    "net_contracts": net
                })

        return open_positions