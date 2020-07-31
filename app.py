import os
import sys
import psycopg2

from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Connect PostgreSQL database.
try:
    conn = psycopg2.connect(dbname="stock_server", user="postgres", password="69919042", host="localhost", port="5432")
    conn.set_session(autocommit=True)
    db = conn.cursor()
except psycopg2.Error as connection_error:
    print(connection_error)
    sys.exit("Database connection failed")

# Make sure API key is set pk_b9b9b928bd2f444f8571f81e2f09a4ab
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    db.execute(
            "SELECT * FROM users WHERE username=%s;", (session["username"],)
        )
    rows = db.fetchone()
    session["balance"] = round(rows[3],2)
    db.execute(
        "SELECT stocks.name, stocks.price, CAST(stocks.trend AS NUMERIC(36,2)), user_stock.number " 
        "FROM user_stock INNER JOIN stocks ON user_stock.stock_id = stocks.id "
        "WHERE user_stock.user_id = %s ORDER BY stocks.name;", (session["user_id"],)              
    )
    rows = db.fetchall()
    return render_template("index.html", rows=rows)


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
        db.execute(
            "SELECT * FROM users WHERE username=%s;", (request.form.get("username"),)
        )
        rows = db.fetchone()

        # Ensure username exists and password is correct
        if rows is None or not check_password_hash(rows[2], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]
        session["username"] = rows[1]
        session["balance"] = rows[3]

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


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        db.execute("SELECT * FROM users WHERE username=%s;", (request.form.get("username"),))
        if db.fetchone() is None:
            db.execute(
                "INSERT INTO users (username, hash, balance) VALUES (%s, %s, '10000.0');", 
                (request.form.get("username"), generate_password_hash(request.form.get("password")))
            )
            db.execute("SELECT * FROM users WHERE username=%s;", (request.form.get("username"),))
            rows = db.fetchone()
            session["user_id"] = rows[0]
            session["username"] = rows[1]
            session["balance"] = rows[3]
            return redirect("/")
        return apology("User with this username already exists")
    else:
        return render_template("register.html")


@app.route("/quote", methods=["GET", "POST"])
# @loin_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        response = lookup(request.form.get("symbol"))
        if response is None:
            return apology("Wrong symbol", 403)
        db.execute(
            "SELECT * FROM stocks WHERE symbol = %s;",
            (response['symbol'],)
        )
        row = db.fetchone()
        if row is None:
            db.execute(
                "INSERT INTO stocks (name, price, symbol, trend) "
                "VALUES (%s, %s, %s, %s);", 
                (response['name'], response['price'], response['symbol'], 0.0) 
            )

        else:
            db.execute(
                "UPDATE stocks SET trend = price - %s, price = %s WHERE id=%s;",
                (response['price'], response['price'], row[0])
            )

        db.execute(
            "SELECT name, symbol, price, trend FROM stocks WHERE symbol=%s UNION "
            "SELECT name, symbol, price, trend FROM stocks WHERE symbol!=%s;",
            (response['symbol'],response['symbol'])
        )
        rows = db.fetchall()
        return render_template("quote.html", rows=rows)
    else:
        return render_template("quote.html")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        response = lookup(request.form.get("symbol"))
        if response is None:
            return apology("Wrong symbol", 403)

        db.execute(
            "SELECT * FROM stocks WHERE symbol = %s;",
            (response['symbol'],)
        )
        row = db.fetchone()

        # Add stock into Database
        if row is None:
            db.execute(
                "INSERT INTO stocks (name, price, symbol, trend) "
                "VALUES (%s, %s, %s, %s);", 
                (response['name'], response['price'], response['symbol'], 0) 
            )
        db.execute(
            "SELECT id FROM stocks WHERE symbol=%s;", (response['symbol'],)
        )
        stock_id = db.fetchone()[0]
        
        # Check if user have sufficient funds
        db.execute(
            "SELECT balance FROM users WHERE id = %s;", (session["user_id"],)
        )
        balance = db.fetchone()[0]
        if response["price"] * int(request.form.get("number")) > balance:
            return apology("Insufficient funds")
        
        # Register buy in database
        else:
            
            # Check if user already have this stocks and add to database if not
            db.execute(
                "SELECT * FROM user_stock WHERE stock_id = %s;", (stock_id,)
            )
            row = db.fetchone()
            print(row)
            if row is None:
                db.execute(
                    "INSERT INTO user_stock (user_id, stock_id, number) "
                    "VALUES (%s, %s, %s);", (session['user_id'], stock_id, request.form.get("number"))
                )
                db.execute(
                    "UPDATE users SET balance=balance-%s WHERE id=%s;", (
                    response["price"] * int(request.form.get("number")), session['user_id']    
                    )
                )
            else:
                db.execute(
                    "UPDATE user_stock SET number = number + %s WHERE stock_id = %s AND user_id = %s;",
                    (request.form.get("number"),stock_id, session['user_id'])
                )
                db.execute(
                    "UPDATE users SET balance=balance-%s WHERE id=%s;", (
                    response["price"] * int(request.form.get("number")), session['user_id']    
                    )
                )
            db.execute(
                "INSERT INTO history (user_id, stock_id, transaction_sum, current_price, stocks_number) "
                "VALUES (%s, %s, %s, %s, %s);", 
                (session['user_id'], stock_id, -response["price"]*int(request.form.get("number")), 
                response["price"], request.form.get("number"))
            )
            return redirect("/")
    elif request.method == "GET":
        return render_template("buy.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("must provide symbol", 403)
        if not request.form.get("number"):
            return apology("must provide number", 403)
        symbol = request.form.get("symbol")
        db.execute(
            "SELECT stocks.id, user_stock.number FROM stocks INNER JOIN user_stock ON user_stock.stock_id = stocks.id "
            "WHERE stocks.symbol = %s;", (symbol.upper(),)
        )
        user_stocks = db.fetchone()
        print(request.form.get("symbol"))
        response = lookup(request.form.get("symbol"))
        if response is None:
            return apology("Wrong symbol", 403)
        print(user_stocks)
        if user_stocks is None or int(request.form.get("number")) > int(user_stocks[1]):
            return apology("Not enought stocks to sell", 403)
        db.execute(
            "UPDATE user_stock SET number = number - %s WHERE stock_id = %s AND user_id = %s;",
            (request.form.get("number"),user_stocks[0], session['user_id'])
        )
        db.execute(
            "UPDATE users SET balance=balance+%s WHERE id=%s;", 
            (response["price"] * int(request.form.get("number")), session['user_id'])
        )
        db.execute(
            "INSERT INTO history (user_id, stock_id, transaction_sum, current_price, stocks_number) "
            "VALUES (%s, %s, %s, %s, %s);", 
            (session['user_id'], user_stocks[0], response["price"]*int(request.form.get("number")), 
            response["price"], request.form.get("number"))
        )
        return redirect("/")
    return render_template('sell.html')


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    db.execute(
        "SELECT history.created, stocks.name, history.stocks_number, "
        "history.current_price, history.transaction_sum "
        "FROM history INNER JOIN stocks ON stocks.id = history.stock_id WHERE history.user_id = %s"
        "ORDER BY history.created DESC;", (session["user_id"],)
    )
    rows = db.fetchall()
    return render_template("history.html", rows=rows)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
