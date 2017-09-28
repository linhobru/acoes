from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    
    portfolio = db.execute("SELECT stock, company, quantity, medio FROM port WHERE user_id = :user_id GROUP BY stock", user_id=session.get("user_id"))
    #portfolio = db.execute("SELECT stock, company, SUM(quantity) FROM wallet WHERE user_id = :user_id GROUP BY stock", user_id=session.get("user_id"))
    
    # create a temporary variable to store TOTAL worth ( cash + share)
    port_worth = 0
    port_invested = 0
    lucro_atual = 0
    
    if portfolio != []:
        
        data = []
        for asset in portfolio:
            
            quote = lookup(asset['stock'])
            
            if asset['quantity'] != 0:
                
                stock_info = {}
                stock_info['company'] = asset['company']
                stock_info['stock'] = asset['stock']
                stock_info['medio'] = asset['medio']
                stock_info['price'] = quote['price']
                stock_info['quantity'] = asset['quantity']
                stock_info['total'] = stock_info['quantity'] * stock_info['price']
                stock_info['investido'] = stock_info['quantity'] * stock_info['medio']
                stock_info['lucro'] = stock_info['total'] - stock_info['investido']
                if stock_info['investido'] != 0:
                    stock_info['percent'] = stock_info['price'] / stock_info['medio'] - 1
                    if stock_info['quantity'] < 0:
                        stock_info['percent'] = stock_info['percent'] * (-1)
                else:
                    stock_info['percent'] = 0
                data.append(stock_info)
        
        for i in range(len(data)):
            port_worth += data[i]['total']
            port_invested += data[i]['investido']
            lucro_atual += data[i]['lucro']
        
        if port_invested == 0:
            lucro_percent = 0
        else:
            lucro_percent = lucro_atual / port_invested
            
        for i in range(len(data)):
            data[i]['medio'] = usd(data[i]['medio'])
            data[i]['price'] = usd(data[i]['price'])
            data[i]['total'] = usd(data[i]['total'])
            data[i]['lucro'] = usd(data[i]['lucro'])
            data[i]['percent'] = percent(data[i]['percent'])
        
        return render_template("index.html", data=data, port_worth=usd(port_worth), port_invested=usd(port_invested), lucro_atual=usd(lucro_atual), lucro_percent=percent(lucro_percent))
        
    else:
        return render_template("index.html") 


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        
        data = {}
        data["stock"] = request.form.get("stock")
        data["company"] = request.form.get("company")
        data["quantity"] = float(request.form.get("quantity"))
        data["price"] = float(request.form.get("price"))
        data["date"] = request.form.get("date")
        data["corretora"] = request.form.get("corretora")
        data["corretagem"] = float(request.form.get("corretagem"))
        data["emolumentos"] = float(request.form.get("emolumentos"))
        data["outras_despesas"] = float(request.form.get("outras_despesas"))
        data["iss"] = float(request.form.get("iss"))
        data["irrf_fonte"] = float(request.form.get("irrf_fonte"))
        data["total"] = data["price"] * data["quantity"]
        data["taxas"] = data["corretagem"] + data["emolumentos"] + data["outras_despesas"] + data["iss"]
        data["medio"] = (data["total"] + data["taxas"]) / data["quantity"]
        
        #insere a transação no banco de dados wallet
        db.execute("INSERT INTO wallet (user_id, stock, company, quantity, price, date, corretora, corretagem, emolumentos, outras_despesas, iss, irrf_fonte)\
                            VALUES(:user_id, :stock, :company, :quantity, :price, :date, :corretora, :corretagem, :emolumentos, :outras_despesas, :iss, :irrf_fonte)", 
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], price=data["price"], date=data["date"],
                            corretora=data["corretora"], corretagem=data["corretagem"], emolumentos=data["emolumentos"], outras_despesas=data["outras_despesas"],
                            iss=data["iss"], irrf_fonte=data["irrf_fonte"])
        
        #atualiza o portfólio atual do cliente                   
        rows = db.execute("SELECT * FROM port WHERE user_id = :user_id AND stock = :stock", user_id=session.get("user_id"), stock=data["stock"])
        
        #se não houver registro da ação, insere como nova transação
        if not rows:
            db.execute("INSERT INTO port (user_id, stock, company, quantity, medio) VALUES(:user_id, :stock, :company, :quantity, :medio)", 
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], medio=data["medio"])
        elif rows[0]["quantity"] == 0:
            db.execute("UPDATE port SET company = :company quantity = :quantity, medio = :medio WHERE user_id = :user_id AND stock = :stock",
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], medio=data["medio"])
        #se houver registro, atualiza quantidade e preço médio
        else:                    
            old_quantity = rows[0]["quantity"]
            old_medio = rows[0]["medio"]
            new_quantity = old_quantity + data["quantity"]
            if new_quantity == 0:
                new_medio = 0
            #se estava short e passou a ficar long
            elif old_quantity < 0 and new_quantity > 0:
                new_medio = data["medio"]
            #se apenas diminuiu a posição short, mantém o médio anterior
            elif old_quantity < 0 and new_quantity < 0:
                new_medio = old_medio
            #se estava long e aumentou sua posição, recalcula-se o médio
            else:
                new_medio = ((old_medio*old_quantity)+(data["medio"]*data["quantity"])) / new_quantity
            db.execute("UPDATE port SET company = :company, quantity = :quantity, medio = :medio WHERE user_id = :user_id AND stock = :stock",
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=new_quantity, medio=new_medio)

        # redirect user to home page
        return redirect(url_for("index"))
        
    else:
        return render_template("registro.html")  

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    portfolio = db.execute("SELECT * FROM wallet WHERE user_id = :user_id ORDER BY date", user_id=session.get("user_id"))
    
    # create a temporary variable to store TOTAL worth ( cash + share)
    total_transacted = 0
    compras = 0
    vendas = 0
    taxas = 0
    lucro = 0
    port_invested = 0
    port_worth = 0
    
    if portfolio != []:
        
        data = []
        for asset in portfolio:
            transaction_info = {}
            transaction_info['stock'] = asset['stock']
            transaction_info['company'] = asset['company']
            transaction_info['price'] = asset['price']
            transaction_info['quantity'] = asset['quantity']
            transaction_info['taxas'] = asset['corretagem'] + asset['emolumentos'] + asset['iss'] + asset['outras_despesas']
            taxas += transaction_info['taxas']
            if transaction_info['quantity'] < 0:
                transaction_info['total'] = (transaction_info['quantity'] * transaction_info['price'] * -1) - transaction_info['taxas']
                vendas += transaction_info['total']
            else:
                transaction_info['total'] = (transaction_info['quantity'] * transaction_info['price']) + transaction_info['taxas']
                compras += transaction_info['total']
            transaction_info['date'] = asset['date']
            total_transacted += transaction_info['total']
            transaction_info['price'] = usd(transaction_info['price'])
            transaction_info['total'] = usd(transaction_info['total'])
            transaction_info['taxas'] = usd(transaction_info['taxas'])
            data.append(transaction_info)
            
        #vai calcular o valor do portfolio atual
        rows = db.execute("SELECT * FROM port WHERE user_id = :user_id", user_id=session.get("user_id"))
            
        if rows != []:
            for i in range(len(rows)):
                quote = lookup(rows[i]['stock'])
                port_worth += (rows[i]['quantity'] * quote.get('price'))

        lucro = port_worth + vendas - compras
        
        
        return render_template("history.html", data=data, total_transacted=usd(total_transacted), vendas=usd(vendas),
                                               taxas=usd(taxas), port_worth=usd(port_worth), compras=usd(compras), lucro=usd(lucro))
        
    else:
        return render_template("history.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("stock"):
            return apology("must provide stock symbol")
            
        stock = request.form.get("stock")
        quote = lookup(stock)
        
        if not quote:
            return apology("stock symbol is invalid")
         
        return render_template("quoted.html", stock = quote.get('symbol'), price = quote.get('price'), quote = usd(quote.get('price')), company = quote.get('name'))     
        
    else:
        return render_template("quote.html")    
    

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")
            
        # ensure password is the same as "verify your password" field
        elif not request.form.get("password") == request.form.get("password2"):
            return apology("your passwords do not match")
        
        username = request.form.get("username").lower()
        first_name = request.form.get("first_name").title()
        last_name = request.form.get("last_name").title()
        
        # query database for username
        result = db.execute("INSERT INTO users (username, hash, email, first_name, last_name) VALUES(:username, :hash, :email, :first_name, :last_name)", 
                            username=username, hash=pwd_context.encrypt(request.form.get("password")), email=request.form.get("email"),
                            first_name=first_name, last_name=last_name)
                          
        # ensure username is not duplicated
        if not result:
            return apology("username already taken")
            
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))
            
        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
                          
        # redirect user to home page
        return redirect(url_for("index"))
    
    
        # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    
    """Sell shares of stock."""
    if request.method == "POST":
        
        # TEM QUE COLOCAR VERIFICACAO DE DADOS (INTEGER, TEXT, ETC)
        data = {}
        data["stock"] = request.form.get("stock")
        data["company"] = request.form.get("company")
        data["quantity"] = float(request.form.get("quantity"))
        data["price"] = float(request.form.get("price"))
        data["date"] = request.form.get("date")
        data["corretora"] = request.form.get("corretora")
        data["corretagem"] = float(request.form.get("corretagem"))
        data["emolumentos"] = float(request.form.get("emolumentos"))
        data["outras_despesas"] = float(request.form.get("outras_despesas"))
        data["iss"] = float(request.form.get("iss"))
        data["irrf_fonte"] = float(request.form.get("irrf_fonte"))
        data["total"] = data["price"] * data["quantity"]
        data["taxas"] = data["corretagem"] + data["emolumentos"] + data["outras_despesas"] + data["iss"]
        data["medio"] = (data["total"] - data["taxas"]) / data["quantity"]
        data["quantity"] = (-1) * data["quantity"]
        
        #insere a transação no banco de dados wallet
        db.execute("INSERT INTO wallet (user_id, stock, company, quantity, price, date, corretora, corretagem, emolumentos, outras_despesas, iss, irrf_fonte)\
                            VALUES(:user_id, :stock, :company, :quantity, :price, :date, :corretora, :corretagem, :emolumentos, :outras_despesas, :iss, :irrf_fonte)", 
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], price=data["price"], date=data["date"],
                            corretora=data["corretora"], corretagem=data["corretagem"], emolumentos=data["emolumentos"], outras_despesas=data["outras_despesas"],
                            iss=data["iss"], irrf_fonte=data["irrf_fonte"])
        
        #atualiza o portfólio atual do cliente                   
        rows = db.execute("SELECT * FROM port WHERE user_id = :user_id AND stock = :stock", user_id=session.get("user_id"), stock=data["stock"])
        
        #se não houver registro da ação, insere como nova transação
        if not rows:
            db.execute("INSERT INTO port (user_id, stock, company, quantity, medio) VALUES(:user_id, :stock, :company, :quantity, :medio)", 
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], medio=data["medio"])
        elif rows[0]["quantity"] == 0:
            db.execute("UPDATE port SET company = :company quantity = :quantity, medio = :medio WHERE user_id = :user_id AND stock = :stock",
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=data["quantity"], medio=data["medio"])
        
        #se houver registro, atualiza quantidade e preço médio
        else:                    
            old_quantity = rows[0]["quantity"]
            old_medio = rows[0]["medio"]
            new_quantity = old_quantity + data["quantity"]
            if new_quantity == 0:
                new_medio = 0
            elif old_quantity > 0 and new_quantity > 0:
                new_medio = old_medio
            #se ele estava comprado e passou a ficar vendido, seu novo médio é o médio dessa transação
            elif old_quantity > 0 and new_quantity < 0:
                new_medio = data["medio"]
            #se ele estava vendido e aumentou sua posição vendida, calcula-se o novo médio
            else:
                new_medio = ((old_medio*old_quantity)+(data["medio"]*data["quantity"])) / new_quantity
            db.execute("UPDATE port SET company = :company, quantity = :quantity, medio = :medio WHERE user_id = :user_id AND stock = :stock",
                            user_id=session.get("user_id"), stock=data["stock"], company=data["company"], quantity=new_quantity, medio=new_medio)
        
        # redirect user to home page
        return redirect(url_for("index"))
        
    else:
        return render_template("registro.html") 

@app.route("/quoted", methods=["GET", "POST"])
@login_required
def quoted():
    """Get stock quote."""
    if request.method == "POST":
            
        stock = request.form.get("stock")
        price = request.form.get("price")
        quote = request.form.get("quote")
        company = request.form.get("company")
        
        if request.form.get("action") == "Buy":
            return render_template("buy.html", stock = stock, price = price, quote = quote, company = company)
        elif request.form.get("action") == "Sell":
            return render_template("sell.html", stock = stock, price = price, quote = quote, company = company)
        
    else:
        return render_template("quote.html")    
        
@app.route("/registro", methods=["GET", "POST"])
@login_required
def registro():
    """Get stock quote."""
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("stock"):
            return apology("must provide stock symbol")
            
        stock = request.form.get("stock")
        quote = lookup(stock)
        
        if not quote:
            stock = request.form.get("stock") + ".SA"
            quote = lookup(stock)
            if not quote:
                return apology("Código de Ação Inválido")
        
        if request.form.get("action") == "Compra":
            return render_template("buy.html", stock = quote.get('symbol'), company = quote.get('name'))
        elif request.form.get("action") == "Venda":
            return render_template("sell.html", stock = quote.get('symbol'), company = quote.get('name'))
  
        
    else:
        return render_template("registro.html")    