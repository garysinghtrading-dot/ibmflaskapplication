from flask import Flask, render_template
from HandleTradeService import TradeService
 
app = Flask(__name__)
 
trade_service = TradeService()
 
 
@app.route("/")
def index():
    user_id = trade_service.get_user_id("demo")
 
    if user_id is None:
        user = {"username": "demo", "cash_balance": 30000.00}
    else:
        cash_balance = trade_service.get_cash_balance(user_id)
        user = {"username": "demo", "cash_balance": cash_balance}
 
    return render_template("index.html", user=user)
 
 
if __name__ == "__main__":
    app.run(debug=True)