import csv
import urllib.request

from flask import redirect, render_template, request, session, url_for
from functools import wraps

def apology(top="", bottom=""):
    """Renders message as an apology to user."""
    def escape(s):
        """
        Escape special characters.

        https://github.com/jacebrowning/memegen#special-characters
        """
        for old, new in [("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
            ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")]:
            s = s.replace(old, new)
        return s
    return render_template("apology.html", top=escape(top), bottom=escape(bottom))

def login_required(f):
    """
    Decorate routes to require login.

    http://flask.pocoo.org/docs/0.11/patterns/viewdecorators/
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def lookup(symbol):
    """Look up quote for symbol."""

    # reject symbol if it starts with caret
    if symbol.startswith("^"):
        return None

    # Reject symbol if it contains comma
    if "," in symbol:
        return None

    # Query Yahoo for quote
    # http://stackoverflow.com/a/21351911
    try:

        # GET CSV
        url = f"http://download.finance.yahoo.com/d/quotes.csv?f=snl1&s={symbol}"
        webpage = urllib.request.urlopen(url)

        # Read CSV
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())

        # Parse first row
        row = next(datareader)

        # Ensure stock exists
        try:
            price = float(row[2])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
        return {
            "name": row[1],
            "price": price,
            "symbol": row[0].upper()
        }

    except:
        pass

    # Query Alpha Vantage for quote instead
    # https://www.alphavantage.co/documentation/
    try:

        # GET CSV
        url = f"https://www.alphavantage.co/query?apikey=NAJXWIA8D6VN6A3K&datatype=csv&function=TIME_SERIES_INTRADAY&interval=1min&symbol={symbol}"
        webpage = urllib.request.urlopen(url)

        # Parse CSV
        datareader = csv.reader(webpage.read().decode("utf-8").splitlines())

        # Ignore first row
        next(datareader)

        # Parse second row
        row = next(datareader)

        # Ensure stock exists
        try:
            price = float(row[4])
        except:
            return None

        # Return stock's name (as a str), price (as a float), and (uppercased) symbol (as a str)
        return {
            "name": symbol.upper(),  # for backward compatibility with Yahoo
            "price": price,
            "symbol": symbol.upper()
        }

    except:
        return None

def usd(value):
    """Formats value as BRL."""
    return "R$ {:,.2f}".format(value)

def percent(value):
    """Formats value as %."""
    return "{0:.2f}%".format(value*100)
    
def nome_mes(value):
    """Formats month as text. """
    if value == 1:
        return "Janeiro"
    elif value == 2:
        return "Fevereiro"
    elif value == 3:
        return "Março"
    elif value == 4:
        return "Abril"
    elif value == 5:
        return "Maio"
    elif value == 6:
        return "Junho"
    elif value == 7:
        return "Julho"
    elif value == 8:
        return "Agosto"
    elif value == 9:
        return "Setembro"
    elif value == 10:
        return "Outubro"
    elif value == 11:
        return "Novembro"
    elif value == 12:
        return "Dezembro"
    else:
        return ""
        

print(lookup("PETR4.SA"))