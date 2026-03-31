from flask import Flask, render_template, request, redirect, url_for, session
from HandleTradeService import TradeService

app = Flask(__name__)
app.secret_key = "change-me-in-production"
trade_service = TradeService()

STRATEGY_LABELS = {
    "single":       "Single Leg (Call / Put)",
    "vertical":     "Vertical Spread",
    "covered_call": "Covered Call",
    "iron_condor":  "Iron Condor",
    "butterfly":    "Butterfly",
}


def _get_current_user():
    """Return (user_id, cash_balance) for the session user, else fall back to demo."""
    username = session.get("username", "demo")
    user_id  = trade_service.get_user_id(username)
    if user_id is None:
        return None, 30000.00, username
    return user_id, trade_service.get_cash_balance(user_id), username


def _parse_legs(strategy, f):
    legs = []

    if strategy == "single":
        legs = [{"side":        f.get("single_side"),
                 "option_type": f.get("single_type"),
                 "strike":      float(f.get("single_strike")  or 0),
                 "premium":     float(f.get("single_premium") or 0)}]

    elif strategy == "vertical":
        otype = f.get("vert_type")
        legs = [
            {"side": "buy_to_open",  "option_type": otype,
             "strike": float(f.get("vert_long_strike")   or 0),
             "premium": float(f.get("vert_long_premium")  or 0)},
            {"side": "sell_to_open", "option_type": otype,
             "strike": float(f.get("vert_short_strike")  or 0),
             "premium": float(f.get("vert_short_premium") or 0)},
        ]

    elif strategy == "covered_call":
        legs = [{"side": "sell_to_open", "option_type": "call",
                 "strike":  float(f.get("cc_strike")  or 0),
                 "premium": float(f.get("cc_premium") or 0)}]

    elif strategy == "iron_condor":
        legs = [
            {"side": "buy_to_open",  "option_type": "put",
             "strike": float(f.get("ic_long_put_strike")    or 0),
             "premium": float(f.get("ic_long_put_premium")  or 0)},
            {"side": "sell_to_open", "option_type": "put",
             "strike": float(f.get("ic_short_put_strike")   or 0),
             "premium": float(f.get("ic_short_put_premium") or 0)},
            {"side": "sell_to_open", "option_type": "call",
             "strike": float(f.get("ic_short_call_strike")  or 0),
             "premium": float(f.get("ic_short_call_premium") or 0)},
            {"side": "buy_to_open",  "option_type": "call",
             "strike": float(f.get("ic_long_call_strike")   or 0),
             "premium": float(f.get("ic_long_call_premium") or 0)},
        ]

    elif strategy == "butterfly":
        otype = f.get("bf_type")
        legs = [
            {"side": "buy_to_open",  "option_type": otype,
             "strike": float(f.get("bf_lower_strike")  or 0),
             "premium": float(f.get("bf_lower_premium") or 0)},
            {"side": "sell_to_open", "option_type": otype,
             "strike": float(f.get("bf_mid_strike")    or 0),
             "premium": float(f.get("bf_mid_premium")  or 0)},
            {"side": "sell_to_open", "option_type": otype,
             "strike": float(f.get("bf_mid_strike")    or 0),
             "premium": float(f.get("bf_mid_premium")  or 0)},
            {"side": "buy_to_open",  "option_type": otype,
             "strike": float(f.get("bf_upper_strike")  or 0),
             "premium": float(f.get("bf_upper_premium") or 0)},
        ]

    else:
        raise ValueError("Invalid strategy selected.")

    return legs


# ── Registration ───────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username", "").strip().lower()

    if not username:
        return render_template("register.html", error="Username cannot be empty.")

    try:
        trade_service.register_user(username)
    except ValueError as e:
        return render_template("register.html", error=str(e))

    session["username"] = username
    return redirect(url_for("index"))


# ── Dashboard ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    user_id, cash_balance, username = _get_current_user()
    user = {"username": username, "cash_balance": cash_balance}
    return render_template("index.html", user=user)


# ── Options trade entry ────────────────────────────────────────────────────
@app.route("/trade/options", methods=["GET", "POST"])
def options_trade():
    user_id, cash_balance, username = _get_current_user()

    if request.method == "GET":
        return render_template("options_trade.html", cash_balance=cash_balance)

    f          = request.form
    strategy   = f.get("strategy")
    ticker     = f.get("ticker", "").upper().strip()
    expiration = f.get("expiration")
    contracts  = int(f.get("contracts", 1))
    notes      = f.get("notes", "")

    try:
        legs = _parse_legs(strategy, f)
        trade_id, new_cash = trade_service.add_option_trade(
            user_id, ticker, expiration, contracts, strategy, legs, notes
        )
    except ValueError as e:
        return render_template("options_trade.html",
                               cash_balance=cash_balance, error=str(e))

    multiplier = 100
    net_cost = sum(
        leg["premium"] * multiplier * contracts * (1 if leg["side"] == "buy_to_open" else -1)
        for leg in legs
    )
    if net_cost > 0:
        cost_label = f"Debit ${net_cost:,.2f}"
    elif net_cost < 0:
        cost_label = f"Credit ${abs(net_cost):,.2f}"
    else:
        cost_label = "Even / $0.00"

    trade_summary = {
        "strategy":   STRATEGY_LABELS.get(strategy, strategy),
        "ticker":     ticker,
        "expiration": expiration,
        "contracts":  contracts,
        "cost_label": cost_label,
        "notes":      notes,
        "legs":       legs,
    }

    return render_template("trade_confirm.html",
                           trade=trade_summary,
                           new_cash_balance=new_cash)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)