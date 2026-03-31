import sqlite3

class TradeService:
    def __init__(self, db_path="records/demo.db"):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def get_user_id(self, username):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None

    def get_cash_balance(self, user_id):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("SELECT cash_balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else 0

    def get_all_positions(self, user_id):
        conn = self._connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                t.ticker_symbol,
                SUM(
                    CASE
                        WHEN t.action IN ('buy', 'buy_to_open') THEN tl.quantity
                        WHEN t.action IN ('sell', 'sell_to_close') THEN -tl.quantity
                        ELSE 0
                    END
                ) AS net_qty,
                CASE
                    WHEN SUM(
                        CASE
                            WHEN t.action IN ('buy', 'buy_to_open') THEN tl.quantity
                            ELSE 0
                        END
                    ) > 0
                    THEN
                        SUM(
                            CASE
                                WHEN t.action IN ('buy', 'buy_to_open')
                                THEN tl.quantity * tl.price
                                ELSE 0
                            END
                        ) /
                        SUM(
                            CASE
                                WHEN t.action IN ('buy', 'buy_to_open')
                                THEN tl.quantity
                                ELSE 0
                            END
                        )
                    ELSE 0
                END AS avg_cost
            FROM trades t
            JOIN trade_legs tl ON t.trade_id = tl.trade_id
            WHERE t.user_id = ?
              AND t.trade_type = 'stock'
            GROUP BY t.ticker_symbol
            HAVING net_qty <> 0
        """, (user_id,))
        rows = cur.fetchall()
        conn.close()

        positions = []
        for ticker, qty, avg_cost in rows:
            positions.append({
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": round(avg_cost, 2) if avg_cost is not None else 0
            })
        return positions

    def add_stock_trade(self, user_id, ticker, quantity, price, action):
        conn = self._connect()
        cur = conn.cursor()

        # 1. Get current cash
        cur.execute("SELECT cash_balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        cash_balance = row[0] if row else 0

        trade_value = quantity * price

        # 2. Adjust cash depending on action
        if action == "buy":
            if cash_balance < trade_value:
                raise ValueError("Insufficient cash to buy shares.")
            new_cash = cash_balance - trade_value
        elif action == "sell":
            new_cash = cash_balance + trade_value
        else:
            raise ValueError("Invalid action for stock trade.")

        # 3. Insert into trades table
        cur.execute("""
            INSERT INTO trades (user_id, trade_type, action, date, notes, ticker_symbol, cash_balance)
            VALUES (?, 'stock', ?, DATE('now'), ?, ?, ?)
        """, (
            user_id,
            action,
            f"{action} {quantity} {ticker} @ {price}",
            ticker,
            new_cash
        ))
        trade_id = cur.lastrowid

        # 4. Insert into trade_legs table
        cur.execute("""
            INSERT INTO trade_legs (trade_id, asset_type, ticker, quantity, price, side)
            VALUES (?, 'stock', ?, ?, ?, ?)
        """, (
            trade_id,
            ticker,
            quantity,
            price,
            "long" if action == "buy" else "short"
        ))

        # 5. Update user cash
        cur.execute("UPDATE users SET cash_balance = ? WHERE user_id = ?", (new_cash, user_id))

        conn.commit()
        conn.close()

        return trade_id
