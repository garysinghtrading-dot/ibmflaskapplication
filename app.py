import os
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from HandleTradeService import TradeService

app = Flask(__name__)

# Required for session-based flashing. 
# In production, move this to an environment variable.
app.secret_key = os.environ.get("SECRET_KEY", "jagpal-holdings-secret-123")

# Tell Flask it is behind a proxy (Ingress) so url_for handles sub-paths correctly
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

trade_service = TradeService()

@app.route("/")
def landing():
    user = "demo_user"
    user_id = trade_service.get_user_id(user)
    positions = trade_service.get_positions(user_id)
    return render_template("landing.html", user=user, positions=positions)

@app.route("/update", methods=["POST"])
def update():
    user_id = trade_service.get_user_id("demo_user")

    ticker = request.form.get("ticker")
    action = request.form.get("action")
    
    # Safely handle potential empty inputs
    try:
        qty = int(request.form.get("quantity", 0))
        price = float(request.form.get("price", 0.0))
    except ValueError:
        flash("Invalid quantity or price entered.", "danger")
        return redirect(url_for("landing"))

    if action == "sell":
        error = trade_service.sell_stock_fifo(user_id, ticker, qty, price)
        if error:
            # Pass the error from your service directly to the UI
            flash(f"Sell Failed: {error}", "danger")
        else:
            flash(f"Successfully sold {qty} shares of {ticker}.", "success")
    else:
        trade_service.buy_stock(user_id, ticker, qty, price)
        flash(f"Successfully bought {qty} shares of {ticker}.", "success")

    # Use url_for for better path management with Ingress
    return redirect(url_for("landing"))

@app.route("/api/open_positions/<symbol>")
def get_open_positions(symbol):
    user_id = trade_service.get_user_id("demo_user")
    positions = trade_service.get_open_option_positions(user_id, symbol.upper())
    return jsonify(positions)

@app.route("/add_option_trade", methods=["POST"])
def add_option_trade():
    user_id = trade_service.get_user_id("demo_user")

    symbol = request.form.get("symbol").upper()
    strike = float(request.form.get("strike"))
    expiration = request.form.get("expiration")
    option_type = request.form.get("option_type")
    action = request.form.get("action")
    quantity = int(request.form.get("quantity"))
    price = float(request.form.get("price"))

    trade_service.add_option_trade(
        user_id=user_id,
        symbol=symbol,
        strike=strike,
        expiration=expiration,
        option_type=option_type,
        action=action,
        quantity=quantity,
        price=price
    )

    return redirect("/")

if __name__ == "__main__":
    # Ensure port matches your Dockerfile/Deployment.yaml
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)