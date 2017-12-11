import sqlite3
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp
from datetime import datetime
from datetime import date
import time
import operator
import os
import psycopg2
import psycopg2.extras
from urllib import parse

from helpers import *

DATABASE_URL = "postgres://ddlbjerytxywjw:ec7973b2fca69cc16a0934c39b211fd01d23ad94f466e7064abaa603a587efea@ec2-54-235-123-153.compute-1.amazonaws.com:5432/daqeuno2frcttg"

# configure application
app = Flask(__name__)
app.secret_key = "doralge"
app.config['SQLACHEMY_TRACK_MODIFICATIONS'] = False
#app.config['SQLALCHEMY_DATABASE_URI'] = "postgres://ddlbjerytxywjw:ec7973b2fca69cc16a0934c39b211fd01d23ad94f466e7064abaa603a587efea@ec2-54-235-123-153.compute-1.amazonaws.com:5432/daqeuno2frcttg"
#db = SQLAlchemy(app)

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

    

#connect database
parse.uses_netloc.append("postgres")
url = parse.urlparse(os.environ["DATABASE_URL"])

conn = psycopg2.connect(
    database=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)  
cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

@app.route("/")
    
@login_required
def index():
    
    cursor.execute("SELECT stock FROM wallet WHERE user_id = %s GROUP BY stock", (session.get("user_id"),))
    portfolio = cursor.fetchall()
    lucro_historico = 0
    
    if portfolio != []:
        
        for stock in portfolio:
            cursor.execute("SELECT * FROM wallet WHERE user_id = %s AND stock = %s ORDER BY date", (session.get("user_id"), stock["stock"],))
            rows = cursor.fetchall()
            print (rows)
            
            for i in range(len(rows)):
                print (stock)
                if i == 0:
                    stock["quantity"] = rows["quantity"][i]
                    taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                    stock["medio"] = rows[i]["price"] + (taxas/stock["quantity"])

                        
                #se esta atualizando os dados de uma determinada acao ja transacionada + de uma vez        
                else:
                    old_quantity = stock["quantity"] #armazena quantidade anterior -> para saber se posicao era long, short ou neutra
                    transaction_quantity = rows[i]["quantity"]
                    stock["quantity"] += transaction_quantity #nova quantidade
                    taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                    
                    #se ficou zerado
                    if stock["quantity"] == 0:
                        stock["medio"] = 0
                    
                    #se estava zerado
                    elif old_quantity == 0:
                        #calcula novo preco medio - operacao de compra
                        stock["medio"] = rows[i]["price"] + (taxas/transaction_quantity)
                        
                    #se estava long
                    elif old_quantity > 0:
                        # e foi uma compra -> aumento de posicao long
                        if transaction_quantity > 0:
                            old_medio = stock["medio"]
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                        #operacao de venda -> diminuiu posicao long
                        elif stock["quantity"] > 0:
                            stock["medio"] = stock["medio"] #mantem o medio
                        #vendeu o que tinha e ficou short
                        else:
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = transaction_medio
                    
                    #se estava short        
                    else:
                        # e foi uma venda -> aumento de posicao short
                        if transaction_quantity < 0:
                            old_medio = stock["medio"]
                            transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                        #operacao de compra -> diminuiu posicao short
                        elif stock["quantity"] < 0:
                            stock["medio"] = stock["medio"] #mantem o medio
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
        
        #cria nova lista, para excluir acoes com quantidade zero de serem exibidas    
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
        
        #insere a transacao no banco de dados wallet
        cursor.execute("INSERT INTO wallet (user_id, stock, company, quantity, price, date, corretora, corretagem, emolumentos, outras_despesas, iss, irrf_fonte)\
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                            (session.get("user_id"), data["stock"], data["company"], data["quantity"], data["price"], data["date"], data["corretora"], 
                            data["corretagem"], data["emolumentos"], data["outras_despesas"], data["iss"], data["irrf_fonte"],))
        db.commit()
        # redirect user to home page
        return redirect(url_for("index"))
        
    else:
        return render_template("registro.html")  

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    cursor.execute("SELECT * FROM wallet WHERE user_id = %s ORDER BY date", (session.get("user_id"),))
    portfolio = cursor.fetchall()
    
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
        SQL = "SELECT * FROM users WHERE username = %s"
        data = (request.form.get("username"), )
        cursor.execute(SQL, data) # Note: no % operator
        rows = cursor.fetchall()
        
        # ensure username exists and password is correct
        # old version: if len(rows[0]) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
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
                return apology("Codigo de Acao Invalido")
         
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
        try:
            cursor.execute("INSERT INTO users (username, hash, email, first_name, last_name) VALUES(%s, %s, %s, %s, %s)", 
                            (username, pwd_context.encrypt(request.form.get("password")), request.form.get("email"), first_name, last_name),)
        except sqlite3.IntegrityError:
            return apology("username already taken")
        
        db.commit()
            
        # query database for username
        cursor.execute("SELECT * FROM users WHERE username = %s", (request.form.get("username"),))
        rows = cursor.fetchall()
        
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
        
        #insere a transacao no banco de dados wallet
        cursor.execute("INSERT INTO wallet (user_id, stock, company, quantity, price, date, corretora, corretagem, emolumentos, outras_despesas, iss, irrf_fonte)\
                            VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)", 
                            (session.get("user_id"), data["stock"], data["company"], data["quantity"], data["price"], data["date"],
                            data["corretora"], data["corretagem"], data["emolumentos"], data["outras_despesas"], data["iss"], data["irrf_fonte"],))
        
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
                return apology("Codigo de Acao Invalido")
        
        if request.form.get("action") == "Compra":
            return render_template("buy.html", stock = quote.get('symbol'), company = quote.get('name'))
        elif request.form.get("action") == "Venda":
            return render_template("sell.html", stock = quote.get('symbol'), company = quote.get('name'))
  
        
    else:
        return render_template("registro.html")    
        
@app.route("/encerradas")
@login_required
def encerradas():
    
    cursor.execute("SELECT stock FROM wallet WHERE user_id = %s GROUP BY stock", (session.get("user_id"),))
    portfolio = cursor.fetchall()
    lucro = 0
    operacoes = []
    
    if portfolio != []:
        
        for stock in portfolio:
            
            #busca todas as transacoes dessa acao
            cursor.execute("SELECT * FROM wallet WHERE user_id = %s AND stock = %s ORDER BY date", (session.get("user_id"), stock["stock"],))
            rows = cursor.fetchall()
            
            #se ha apenas uma transacao dessa acao, pula a acao
            if len(rows) > 1:
        
                for i in range(len(rows)):
                    if i == 0:
                        taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                        stock["medio"] = rows[i]["price"] + (taxas/rows[i]["quantity"])
                        stock["quantity"] = rows[i]["quantity"]
                            
                    #se esta atualizando os dados de uma determinada acao ja transacionada + de uma vez        
                    else:
                        old_quantity = stock["quantity"] #armazena quantidade anterior -> para saber se posicao era long, short ou neutra
                        transaction_quantity = rows[i]["quantity"]
                        stock["quantity"] += transaction_quantity #nova quantidade
                        taxas = rows[i]["iss"] + rows[i]["outras_despesas"] + rows[i]["corretagem"] + rows[i]["emolumentos"]
                        old_medio = stock["medio"]
                        transaction_medio = rows[i]["price"] + (taxas/transaction_quantity)
                        
                        if old_quantity * transaction_quantity > 0: #se ocorreram operacoes similares (estava long e aumentou ou estava short e diminuiu)
                            stock["medio"] = ((old_medio*old_quantity) + (transaction_medio*transaction_quantity)) / stock["quantity"]
                                
                        elif old_quantity == 0:
                            stock["medio"] = transaction_medio
                            
                        else: #ocorreram operacoes distintas(venda em posicao buy ou compra em posicao short)
                            
                            #cria variavel para armezar dados da operacao encerrada
                            operacao = {}
                            operacao["stock"] = stock["stock"]
                            operacao["quantity"] = min(abs(transaction_quantity), abs(old_quantity))
                            operacao["company"] = rows[i]["company"]
                            operacao["data"] = rows[i]["date"]

                            if old_quantity > 0: #se estava comprado, a operacao foi de venda
                                if stock["quantity"] == 0: #se ficou zerado
                                    stock["medio"] = 0
                                elif stock["quantity"] > 0: #continuou comprado
                                    stock["medio"] = old_medio
                                else: #ficou vendido
                                    stock["medio"] = transaction_medio
                                operacao["mediocompra"] = float(old_medio)
                                operacao["mediovenda"] = float(transaction_medio)
                             
                            else: #se estava vendido, a operacao foi de compra
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
                            #operacao["lucro"] = usd(operacao["lucro"]) 
                            operacao["percent"] = percent(operacao["percent"])
                            data_operacao = datetime.strptime(operacao["data"], "%Y-%m-%d")
                            operacao["mes"] = data_operacao.month
                            operacao["ano"] = data_operacao.year
                            operacao["periodo"] = nome_mes(operacao["mes"]) + " de " + str(operacao["ano"])
                            operacoes.append(operacao)
        
        #ordena as operacoes por ordem cronologica
        operacoes.sort(key=operator.itemgetter('data'))
        
        data = []
        for i in range(len(operacoes)):
            if operacoes[i]["periodo"] not in data:
                data.append(operacoes[i]["periodo"])
        
        inicio = 0
        i = 0
        lista = []
        
        #cria uma lista, que vai separar as operacoes por mes. Lista = [[operacoes de mes1],[operacoes de mes2]]
        for j in range(len(operacoes)):
            if j == (len(operacoes) - 1):
                if operacoes[j]["periodo"] != data[i]:
                    final = j
                    lista.append(operacoes[inicio:final])
                    inicio = final
                    lista.append(operacoes[inicio:])
                else:
                    lista.append(operacoes[inicio:])
            else:
                if operacoes[j]["periodo"] != data[i]:
                    final = j
                    lista.append(operacoes[inicio:final])
                    inicio = final
                    i += 1
                
        
        #adicionar lucro a lista de operacoes do mes
        
        dados = []        
        for i in range(len(data)):
            dado = {}
            dado["periodo"] = data[i]
            dado["valores"] = lista[i]
            dado["lucro"] = 0
            dados.append(dado)
        
        for dado in dados:
            for operacao in dado["valores"]:
                dado["lucro"] += operacao["lucro"]
                operacao["lucro"] = usd(operacao["lucro"])
            dado["lucro"] = usd(dado["lucro"])
            
        return render_template("encerradas.html", dados=dados, lucro=usd(lucro))
        
    else:
        return render_template("encerradas.html") 



