from flask import Flask, redirect, render_template, request, session, url_for
from HandleTradeService import TradeService
import os 

app = Flask(__name__)
trade_service = TradeService()

app.secret_key = "demo-test" # TEMPORARY PLACE HOLDER
# ********************************
# METHOD TO QUERY RESULTS TO 
# GET USER INFO
# ********************************
def _get_current_user():
    """Return (user_id, cash_balance) for the session user, else fall back to demo."""
    username = session.get("username", "demouser")
    user_id  = trade_service.get_user_id(username)
    if user_id is None:
        return None, 0.00, username
    return user_id, trade_service.get_cash_balance(user_id), username


# ********************************
# LANDING PAGE
# ********************************
@app.route("/")
def index():
    user_id, cash_balance, username = _get_current_user()
    user = {"username": username, "cash_balance": cash_balance}
    return render_template("index.html", user=user)

# ********************************
# REGISTER
# ********************************
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == "GET":
        return render_template("register.html")
    
    username = request.form.get("username", "").strip().lower()

    if not username:
        return render_template("register.html", error="Username cannot be empty")
    
    try:
        trade_service.register_user(username)
    except ValueError as e:
        return render_template("register.html", error=str(e))
    
    session["username"] = username
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)