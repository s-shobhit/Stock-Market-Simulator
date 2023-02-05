import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""

    user_id = session["user_id"]

    stocks = db.execute(
        "SELECT symbol, stock_name, SUM(shares) as shares, price FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # User’s current cash balance along with a grand total (i.e., stocks’ total value plus cash)
    grand_total = cash

    for stock in stocks:
        # Look up quote for symbol and update price
        current_price = lookup(stock["symbol"])["price"]
        stock["price"] = current_price

        grand_total += stock["price"] * stock["shares"]

    return render_template("index.html", stocks=stocks, cash=cash, grand_total=grand_total, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        if not request.form.get("shares"):
            return apology("missing shares", 400)

        # Look up quote for symbol
        quote = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if not quote:
            return apology("invalid symbol", 400)

        # Ensure input is positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide an integer", 400)

        if shares <= 0:
            return apology("must provide a positive integer", 400)

        user_id = session["user_id"]

        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        name = quote["name"]
        price = quote["price"]
        symbol = quote["symbol"]
        total = price * shares

        # Render an apology, without completing a purchase, if the user cannot afford the number of shares at the current price
        if cash < total:
            return apology("can't afford", 400)

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - total, user_id)

        db.execute("INSERT INTO transactions (user_id, stock_name, shares, price, transaction_type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
                    user_id, name, shares, price, 'bought', symbol)

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user_id = session["user_id"]

    transactions = db.execute("SELECT symbol, transaction_type, shares, price, time FROM transactions WHERE user_id = ?", user_id)

    return render_template("history.html", transactions=transactions, usd=usd)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("missing symbol", 400)

        # Look up quote for symbol
        quote = lookup(request.form.get("symbol"))

        # Ensure symbol is valid
        if not quote:
            return apology("invalid symbol", 400)

        return render_template("quoted.html", quote=quote, usd=usd)

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password confirmation was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide password confirmation", 400)

        # Ensure password and confirmation match
        if request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation don't match", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username is not taken
        if len(rows) == 1:
            return apology("username is already taken", 400)

        # Generate a hash of the password
        hash = generate_password_hash(request.form.get("password"))

        # Add user to database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", request.form.get("username"), hash)
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    user_id = session["user_id"]

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        if not request.form.get("shares"):
            return apology("missing shares", 400)

        # Ensure input is positive integer
        try:
            shares = int(request.form.get("shares"))
        except:
            return apology("must provide an integer", 400)

        if shares <= 0:
            return apology("must provide a positive integer", 400)

        # Look up quote for symbol
        quote = lookup(request.form.get("symbol"))

        name = quote["name"]
        price = quote["price"]
        symbol = quote["symbol"]
        total = price * shares

        shares_owned = db.execute("SELECT SUM(shares) as shares FROM transactions WHERE user_id = ? AND symbol = ?", user_id, symbol)[0]["shares"]

        if shares_owned < shares:
            return apology("too many shares", 400)

        cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

        db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + total, user_id)

        db.execute("INSERT INTO transactions (user_id, stock_name, shares, price, transaction_type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
                    user_id, name, -shares, price, 'sold', symbol)

        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        return render_template("sell.html", symbols=symbols)
