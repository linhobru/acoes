from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import date
import time
import operator

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
    
    portfolio = db.execute("SELECT stock FROM wallet WHERE user_id = :user_id GROUP BY stock", user_id=session.get("user_id"))
    lucro_historico = 0
    
    if portfolio != []:
        
        for stock in portfolio:
            rows = db.execute("SELECT * FROM wallet WHERE user_id = :user_id AND stock = :stock ORDER BY date", user_id=session.get("user_id"), stock=stock["stock"])
        
            for i in range(len(rows)):
                if i == 0:
                    stock["quantity"] = rows[i]["quantity"]
                    taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                    stock["medio"] = rows[i]["price"] + (taxas/stock["quantity"])

                        
                #se está atualizando os dados de uma determinada ação já transacionada + de uma vez        
                else:
                    old_quantity = stock["quantity"] #armazena quantidade anterior -> para saber se posição era long, short ou neutra
                    transaction_quantity = rows[i]["quantity"]
                    stock["quantity"] += transaction_quantity #nova quantidade
                    taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                    
                    #se ficou zerado
                    if stock["quantity"] == 0:
                        stock["medio"] = 0
                    
                    #se estava zerado
                    elif old_quantity == 0:
                        #calcula novo preço médio - operação de compra
                        stock["medio"] = rows[i]["price"] + (taxas/transaction_quantity)
                        
                    #se estava long
                    elif old_quantity > 0:
                        # e foi uma compra -> aumento de posição long
                        if transaction_quantity > 0:
                            old_medio = stock["medio"]
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                        #operação de venda -> diminuiu posição long
                        elif stock["quantity"] > 0:
                            stock["medio"] = stock["medio"] #mantém o médio
                        #vendeu o que tinha e ficou short
                        else:
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = transaction_medio
                    
                    #se estava short        
                    else:
                        # e foi uma venda -> aumento de posição short
                        if transaction_quantity < 0:
                            old_medio = stock["medio"]
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                        #operação de compra -> diminuiu posição short
                        elif stock["quantity"] < 0:
                            stock["medio"] = stock["medio"] #mantém o médio
                        #comprou mais do que tinha short e ficou comprado
                        else:
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = transaction_medio
                    
                quote = lookup(stock["stock"])
                stock["company"] = quote.get('name')
                stock["atual"] = quote.get('price')
                stock["lucro"] = stock["quantity"] * (stock["atual"]-stock["medio"])
                stock["total"] = stock["quantity"] * stock["atual"]
                lucro_historico += stock["lucro"]
                if stock["medio"] == 0:
                    stock["percent"] = 0
                else:
                    stock["percent"] = stock["atual"] / stock["medio"] - 1
                if stock["quantity"] < 0:
                    stock["percent"] = (-1) * stock["percent"]
                if stock["lucro"] > 0:
                    stock["sinal"] = "positivo"
                elif stock["lucro"] < 0:
                    stock["sinal"] = "negativo"
                else:
                    stock["sinal"] = ""
                
        # variaveis para armezar o total investido, o total e lucro da carteira atual
        port_worth = 0
        port_invested = 0
        lucro_atual = 0
    
        for stock in portfolio:
            port_worth += stock["total"]
            port_invested += stock["quantity"] * stock["medio"]
            lucro_atual += stock["lucro"]
            stock['medio'] = usd(stock['medio'])
            stock['atual'] = usd(stock['atual'])
            stock['total'] = usd(stock['total'])
            stock['lucro'] = usd(stock['lucro'])
            stock['percent'] = percent(stock['percent'])
        
        #cria nova lista, para excluir ações com quantidade zero de serem exibidas    
        data = []
        for stock in portfolio:
            if stock["quantity"] != 0:
                data.append(stock)
        
        return render_template("index.html", data=data, port_worth=usd(port_worth), port_invested=usd(port_invested), lucro_atual=usd(lucro_atual))
        
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
        for stock in portfolio:
            stock['taxas'] = stock['corretagem'] + stock['emolumentos'] + stock['iss'] + stock['outras_despesas']
            taxas += stock['taxas']
            if stock['quantity'] < 0:
                stock['total'] = (stock['quantity'] * stock['price'] * -1) - stock['taxas']
                vendas += stock['total']
            else:
                stock['total'] = (stock['quantity'] * stock['price']) + stock['taxas']
                compras += stock['total']
            total_transacted += stock['total']
            stock['price'] = usd(stock['price'])
            stock['total'] = usd(stock['total'])
            stock['taxas'] = usd(stock['taxas'])
            quote = lookup(stock["stock"])
            port_worth += (stock['quantity'] * quote.get('price'))

        lucro = port_worth + vendas - compras
        
        return render_template("history.html", portfolio=portfolio, total_transacted=usd(total_transacted), vendas=usd(vendas),
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

@app.route("/quote", methods=["GET", "POST"])
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
            stock = request.form.get("stock") + ".SA"
            quote = lookup(stock)
            if not quote:
                return apology("Código de Ação Inválido")
         
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
        
@app.route("/encerradas")
@login_required
def encerradas():
    
    portfolio = db.execute("SELECT stock FROM wallet WHERE user_id = :user_id GROUP BY stock", user_id=session.get("user_id"))
    lucro = 0
    operacoes = []
    
    if portfolio != []:
        
        for stock in portfolio:
            
            #busca todas as transações dessa ação
            rows = db.execute("SELECT * FROM wallet WHERE user_id = :user_id AND stock = :stock ORDER BY date", user_id=session.get("user_id"), stock=stock["stock"])
            
            #se há apenas uma transação dessa ação, pula a ação
            if len(rows) > 1:
        
                for i in range(len(rows)):
                    if i == 0:
                        taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                        stock["medio"] = rows[i]["price"] + (taxas/rows[i]["quantity"])
                        stock["quantity"] = rows[i]["quantity"]
                            
                    #se está atualizando os dados de uma determinada ação já transacionada + de uma vez        
                    else:
                        old_quantity = stock["quantity"] #armazena quantidade anterior -> para saber se posição era long, short ou neutra
                        transaction_quantity = rows[i]["quantity"]
                        stock["quantity"] += transaction_quantity #nova quantidade
                        taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                        old_medio = stock["medio"]
                        transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                        
                        if old_quantity * transaction_quantity > 0: #se ocorreram operações similares (estava long e aumentou ou estava short e diminuiu)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                                
                        elif old_quantity == 0:
                            stock["medio"] = transaction_medio
                            
                        else: #ocorreram operações distintas(venda em posição buy ou compra em posição short)
                            
                            #cria variável para armezar dados da operação encerrada
                            operacao = {}
                            operacao["stock"] = stock["stock"]
                            operacao["quantity"] = min(abs(transaction_quantity), abs(old_quantity))
                            operacao["company"] = rows[i]["company"]
                            operacao["data"] = rows[i]["date"]

                            if old_quantity > 0: #se estava comprado, a operação foi de venda
                                if stock["quantity"] == 0: #se ficou zerado
                                    stock["medio"] = 0
                                elif stock["quantity"] > 0: #continuou comprado
                                    stock["medio"] = old_medio
                                else: #ficou vendido
                                    stock["medio"] = transaction_medio
                                operacao["mediocompra"] = float(old_medio)
                                operacao["mediovenda"] = float(transaction_medio)
                             
                            else: #se estava vendido, a operação foi de compra
                                if stock["quantity"] == 0: #se ficou zerado
                                    stock["medio"] = 0
                                elif stock["quantity"] < 0: #continuou short
                                    stock["medio"] = old_medio
                                else: #ficou long
                                    stock["medio"] = transaction_medio
                                
                                operacao["mediocompra"] = float(transaction_medio)
                                operacao["mediovenda"] = float(old_medio)
                                
                            operacao["lucro"] = operacao["quantity"] * (operacao["mediovenda"] - operacao["mediocompra"])
                            lucro += operacao["lucro"]
                            
                            if operacao["lucro"] > 0:
                                operacao["sinal"] = "positivo"
                            elif operacao["lucro"] < 0:
                                operacao["sinal"] = "negativo"
                            else:
                                operacao["sinal"] = ""
                    
                            if operacao["mediocompra"] == 0:
                                operacao["percent"] = 0
                            else:
                                operacao["percent"] = operacao["mediovenda"] / operacao["mediocompra"] - 1
                            
                            operacao["mediocompra"] = usd(operacao["mediocompra"])
                            operacao["mediovenda"] = usd(operacao["mediovenda"])
                            operacao["lucro"] = usd(operacao["lucro"]) 
                            operacao["percent"] = percent(operacao["percent"])
                            operacao["mes"] = str(operacao["data"].year) + str(operacao["data"].month)
                            operacoes.append(operacao)
        
        operacoes.sort(key=operator.itemgetter('data'))
        
        """
        periodos = []
        for operacao in operacoes:
            periodo = {}
            ano = operacao["data"].year
            mes = operacao["data"].month
            periodo["titulo"] = nome_mes(mes) + " de " + str(ano)
            
        
            periodos.append(periodo)"""
                
        return render_template("encerradas.html", operacoes=operacoes, periodos=periodos, lucro=usd(lucro))
        
    else:
        return render_template("encerradas.html") 

