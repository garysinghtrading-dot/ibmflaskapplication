import sqlite3


class TradeService:
    def __init__(self, db_path="records/demo.db"):
        self.db_path = db_path

    def _connect(self):
        return sqlite3.connect(self.db_path)

    # ── User helpers ───────────────────────────────────────────────────────
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

    def register_user(self, username):
        """
        Create a new user with the default $30,000 cash balance.
        Raises ValueError if the username is already taken.
        Returns the new user_id.
        """
        conn = self._connect()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username) VALUES (?)", (username,)
            )
            conn.commit()
            user_id = cur.lastrowid
        except sqlite3.IntegrityError:
            raise ValueError(f"Username '{username}' is already taken.")
        finally:
            conn.close()
        return user_id

    # ── Stock positions ────────────────────────────────────────────────────
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
                "ticker":   ticker,
                "quantity": qty,
                "avg_cost": round(avg_cost, 2) if avg_cost is not None else 0
            })
        return positions

    # ── Stock trade ────────────────────────────────────────────────────────
    def add_stock_trade(self, user_id, ticker, quantity, price, action):
        conn = self._connect()
        cur = conn.cursor()

        cur.execute("SELECT cash_balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        cash_balance = row[0] if row else 0

        trade_value = quantity * price

        if action == "buy":
            if cash_balance < trade_value:
                raise ValueError("Insufficient cash to buy shares.")
            new_cash = cash_balance - trade_value
        elif action == "sell":
            new_cash = cash_balance + trade_value
        else:
            raise ValueError("Invalid action for stock trade.")

        cur.execute("""
            INSERT INTO trades (user_id, trade_type, action, date, notes, ticker_symbol, cash_balance)
            VALUES (?, 'stock', ?, DATE('now'), ?, ?, ?)
        """, (user_id, action,
              f"{action} {quantity} {ticker} @ {price}",
              ticker, new_cash))
        trade_id = cur.lastrowid

        cur.execute("""
            INSERT INTO trade_legs (trade_id, asset_type, ticker, quantity, price, side)
            VALUES (?, 'stock', ?, ?, ?, ?)
        """, (trade_id, ticker, quantity, price,
              "long" if action == "buy" else "short"))

        cur.execute("UPDATE users SET cash_balance = ? WHERE user_id = ?",
                    (new_cash, user_id))

        conn.commit()
        conn.close()
        return trade_id

    # ── Options trade ──────────────────────────────────────────────────────
    def add_option_trade(self, user_id, ticker, expiration, contracts,
                         strategy, legs, notes=""):
        """
        Persist a single or multi-leg options trade.

        Parameters
        ----------
        user_id    : int
        ticker     : str   underlying symbol e.g. 'AAPL'
        expiration : str   date string e.g. '2025-06-20'
        contracts  : int   number of contracts (applied to every leg)
        strategy   : str   one of: single | vertical | covered_call |
                                   iron_condor | butterfly
        legs       : list of dicts, each with keys:
                       side        – buy_to_open | sell_to_open
                       option_type – call | put
                       strike      – float
                       premium     – float (per-contract price, e.g. 1.50)
        notes      : str   optional free-text note

        Returns
        -------
        trade_id : int
        new_cash : float  updated cash balance after the trade
        """
        MULTIPLIER = 100  # 1 contract = 100 shares

        conn = self._connect()
        cur = conn.cursor()

        # 1. Current cash
        cur.execute("SELECT cash_balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        cash_balance = row[0] if row else 0

        # 2. Net cost across all legs
        #    buy_to_open  → debit  (costs cash)
        #    sell_to_open → credit (adds cash)
        net_cost = 0.0
        for leg in legs:
            leg_value = leg["premium"] * MULTIPLIER * contracts
            if leg["side"] == "buy_to_open":
                net_cost += leg_value
            else:
                net_cost -= leg_value

        # 3. Buying power check (debits only)
        buying_power = cash_balance * 2
        if net_cost > 0 and net_cost > buying_power:
            conn.close()
            raise ValueError(
                f"Insufficient buying power. Trade costs ${net_cost:,.2f}; "
                f"available ${buying_power:,.2f}."
            )

        new_cash = cash_balance - net_cost

        # 4. Determine top-level action label
        action = "buy_to_open" if net_cost >= 0 else "sell_to_open"

        # 5. Insert parent trade record
        cur.execute("""
            INSERT INTO trades
                (user_id, trade_type, action, date, notes, ticker_symbol, cash_balance)
            VALUES (?, 'option_multi', ?, DATE('now'), ?, ?, ?)
        """, (user_id, action, notes or f"{strategy} {ticker} exp {expiration}",
              ticker, new_cash))
        trade_id = cur.lastrowid

        # 6. Insert one trade_leg row per leg
        for leg in legs:
            cur.execute("""
                INSERT INTO trade_legs
                    (trade_id, asset_type, ticker, quantity, price,
                     strike, expiration, option_type, side)
                VALUES (?, 'option', ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                ticker,
                contracts,
                leg["premium"],
                leg["strike"],
                expiration,
                leg["option_type"],
                leg["side"],
            ))

        # 7. Update user cash
        cur.execute("UPDATE users SET cash_balance = ? WHERE user_id = ?",
                    (new_cash, user_id))

        conn.commit()
        conn.close()
        return trade_id, new_cash