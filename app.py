from flask import Flask, render_template, request, redirect, url_for
from HandleTradeService import TradeService

app = Flask(__name__)
trade_service = TradeService()

DEMO_USERNAME = "demo_user"

@app.route("/")
def index():
    user_id = trade_service.get_user_id(DEMO_USERNAME)
    cash = trade_service.get_cash_balance(user_id)
    positions = trade_service.get_all_positions(user_id)
    return render_template(
        "index.html",
        username=DEMO_USERNAME,
        cash_balance=cash,
        positions=positions
    )

@app.route("/trade/stock", methods=["GET", "POST"])
def trade_stock():
    user_id = trade_service.get_user_id(DEMO_USERNAME)

    if request.method == "POST":
        ticker = request.form["ticker"].upper()
        action = request.form["action"]
        qty = int(request.form["quantity"])
        price = float(request.form["price"])

        # 🔴 If your method name is different, change this line only
        trade_service.add_stock_trade(user_id, ticker, qty, price, action)

        return redirect(url_for("index"))

    return render_template("trade-stocks.html")

@app.route("/trade/options", methods=["GET", "POST"])
def trade_options():
    user_id = trade_service.get_user_id(DEMO_USERNAME)

    if request.method == "POST":
        symbol = request.form["symbol"].upper()
        strike = float(request.form["strike"])
        expiration = request.form["expiration"]
        action = request.form["action"]
        qty = int(request.form["quantity"])
        price = float(request.form["price"])

        # 🔴 If your method name is different, change this line only
        trade_service.add_option_trade(
            user_id, symbol, strike, expiration, qty, price, action
        )

        return redirect(url_for("index"))

    return render_template("trade-options.html")

if __name__ == "__main__":
    app.run(debug=True)