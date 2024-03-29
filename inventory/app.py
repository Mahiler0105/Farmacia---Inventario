import os
import json
import sqlite3

import flask
from flask import Flask, url_for, request, redirect, session
from flask import render_template as render
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.pdfbase.ttfonts import TTFont 
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import (ParagraphStyle, getSampleStyleSheet)

DATABASE_NAME = 'inventory.sqlite'

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY = 'dev',
    DATABASE = os.path.join(app.instance_path, 'database', DATABASE_NAME),
)

link = {x: x for x in ["home", "user", "location", "product", "movement"]}
link["index"] = '/'

def init_database():
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    # initialize page content
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products(prod_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prod_name TEXT UNIQUE NOT NULL,
                    prod_quantity INTEGER NOT NULL,
                    unallocated_quantity INTEGER);
    """)
    cursor.execute("""
    CREATE TRIGGER IF NOT EXISTS default_prod_qty_to_unalloc_qty
                    AFTER INSERT ON products
                    FOR EACH ROW
                    WHEN NEW.unallocated_quantity IS NULL
                    BEGIN 
                        UPDATE products SET unallocated_quantity  = NEW.prod_quantity WHERE rowid = NEW.rowid;
                    END;
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user (idUsuario INTEGER PRIMARY KEY AUTOINCREMENT,
                                    nombreUsuario VARCHAR(12) UNIQUE NOT NULL,
                                    contraseña VARCHAR(10) DEFAULT NULL,
                                    nombres VARCHAR(25) DEFAULT NULL,
                                    apellidos VARCHAR(25) DEFAULT NULL,
                                    tipo CHAR(1) DEFAULT NULL);
    """)   

    # initialize page content
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS location(loc_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 loc_name TEXT UNIQUE NOT NULL,
                                 main BOOLEAN DEFAULT 0);
    """)

    # initialize page content
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS logistics(trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                prod_id INTEGER NOT NULL,
                                from_loc_id INTEGER NULL,
                                to_loc_id INTEGER NULL,
                                prod_quantity INTEGER NOT NULL,
                                tipo CHAR(1) NOT NULL,
                                trans_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY(prod_id) REFERENCES products(prod_id),
                                FOREIGN KEY(from_loc_id) REFERENCES location(loc_id),
                                FOREIGN KEY(to_loc_id) REFERENCES location(loc_id));
    """)

    db.commit()

@app.route("/" , methods=['GET','POST'])
def index():    
    msg = ""
    init_database()
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    if request.method == 'POST':
        #session.pop('username', None)
        username = str(request.form["user"])
        password = str(request.form["password"])
        print(username, password)
        
        cursor.execute("SELECT * from user where nombreUsuario = ? and contraseña = ?", (username, password))
        data = cursor.fetchall()
        if len(data) == 1:
            session['logged_in'] = True
            session['user'] = username
            session['pass'] = password
        else:        
            msg = "Wrong Credentials"

    if not session.get('logged_in'):
        return render("index.html", title="Login", msg=msg)
    else:
        return redirect(url_for("home"))

@app.route("/logout")
def logOut():
    session['logged_in'] = False
    return index()
    #return render("index.html", title="Login")


@app.route('/home')
def home():
    init_database()
    msg = None
    q_data, warehouse, products = None, None, None
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM location")  # <---------------------------------FIX THIS
        warehouse = cursor.fetchall()
        cursor.execute("SELECT * FROM products")
        products = cursor.fetchall()
        cursor.execute("""
        SELECT prod_name, unallocated_quantity, prod_quantity FROM products
        """)
        q_data = cursor.fetchall()
    except sqlite3.Error as e:
        msg = f"An error occurred: {e.args[0]}"
    if msg:
        print(msg)

    return render('home.html', link=link, title="Resumen", warehouses=warehouse, products=products, database=q_data)

@app.route("/user", methods=['GET','POST'])
def user():
    init_database()
    msg = None
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    cursor.execute("SELECT * FROM user")
    users = cursor.fetchall()

    if request.method == 'POST':
        user_name = request.form['username']
        password = request.form['password']
        names = request.form['name']
        last_name = request.form['lastname']
        tipe = request.form['tipe']        

        arg = [user_name, password, names, last_name, tipe]
        for a in arg:
            if a in ['', ' ', None]:
                transaction_allowed = False
                break
            else:
                print(True)
        
        transaction_allowed = False
        if user_name not in ['', ' ', None]:
            if password not in ['', ' ', None]:
                if names not in ['', ' ', None]:
                    if last_name not in ['', ' ', None]:
                        if tipe not in ['', ' ', None]:
                            transaction_allowed = True

        if transaction_allowed:
            try:
                cursor.execute("INSERT INTO user (nombreUsuario, contraseña, nombres, apellidos, tipo) VALUES (?, ?, ?, ?, ?)", 
                (user_name, password, names, last_name, tipe))
                db.commit()
            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = f"{user_name} added successfully"

            if msg:
                print(msg)

            return redirect(url_for('user'))

    return render("user.html", link=link, users=users, transaction_message=msg, title="User management",)


@app.route('/product', methods=['POST', 'GET'])
def product():
    init_database()
    msg = None
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    if request.method == 'POST':
        prod_name = request.form['prod_name']
        quantity = request.form['prod_quantity']

        transaction_allowed = False
        if prod_name not in ['', ' ', None]:
            if quantity not in ['', ' ', None]:
                transaction_allowed = True

        if transaction_allowed:
            try:
                cursor.execute("INSERT INTO products (prod_name, prod_quantity) VALUES (?, ?)", (prod_name, quantity))
                cursor.execute("SELECT prod_id FROM products WHERE prod_name = ?", (prod_name,))
                prod_id = cursor.fetchone()                
                cursor.execute("INSERT INTO logistics (prod_id, to_loc_id, prod_quantity, tipo) VALUES (?, ?, ?, ?)", (int(prod_id[0]), 1, quantity, 'C'))
                db.commit()
            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = f"{prod_name} added successfully"

            if msg:
                print(msg)

            return redirect(url_for('product'))

    return render('product.html', link=link, products=products, transaction_message=msg, title="Productos")


@app.route('/location', methods=['POST', 'GET'])
def location():
    init_database()
    msg = None
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    cursor.execute("SELECT * FROM location")
    warehouse_data = cursor.fetchall()    

    if request.method == 'POST':
        warehouse_name = request.form['warehouse_name']

        transaction_allowed = False
        if warehouse_name not in ['', ' ', None]:
            transaction_allowed = True

        if transaction_allowed:
            try:
                cursor.execute("INSERT INTO location (loc_name) VALUES (?)", (warehouse_name,))
                db.commit()
            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = f"{warehouse_name} added successfully"

            if msg:
                print(msg)

            return redirect(url_for('location'))

    return render('location.html', link=link, warehouses=warehouse_data, transaction_message=msg, title="Sucursales")


@app.route('/movement', methods=['POST', 'GET'])
def movement():
    init_database()
    msg = None
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    cursor.execute("SELECT * FROM logistics")
    logistics_data = cursor.fetchall()

    cursor.execute("SELECT DISTINCT DATE(trans_time) FROM logistics;")
    days = cursor.fetchall()
    
    cursor.execute("SELECT nombres, apellidos from user WHERE nombreUsuario = ?", (session['user'],))
    t2 = cursor.fetchall()
    gen_nombre = t2[0][0]
    gen_apelli = t2[0][1]
    

    cursor.execute("SELECT prod_id, prod_name, unallocated_quantity FROM products")
    products = cursor.fetchall()

    cursor.execute("SELECT loc_id, loc_name, main FROM location")
    locations = cursor.fetchall()

    log_summary = []
    for p_id in [x[0] for x in products]:
        cursor.execute("SELECT prod_name FROM products WHERE prod_id = ?", (p_id, ))
        temp_prod_name = cursor.fetchone()

        for l_id in [x[0] for x in locations]:
            cursor.execute("SELECT loc_name FROM location WHERE loc_id = ?", (l_id,))
            temp_loc_name = cursor.fetchone()

            cursor.execute("""
            SELECT SUM(log.prod_quantity)
            FROM logistics log
            WHERE log.prod_id = ? AND log.to_loc_id = ?
            """, (p_id, l_id))
            sum_to_loc = cursor.fetchone()

            cursor.execute("""
            SELECT SUM(log.prod_quantity)
            FROM logistics log
            WHERE log.prod_id = ? AND log.from_loc_id = ?
            """, (p_id, l_id))
            sum_from_loc = cursor.fetchone()

            if sum_from_loc[0] is None:
                sum_from_loc = (0,)
            if sum_to_loc[0] is None:
                sum_to_loc = (0,)

            log_summary += [(temp_prod_name + temp_loc_name + (sum_to_loc[0] - sum_from_loc[0],))]
            
    
    alloc_json = {}
    for row in log_summary:
        try:
            if row[1] in alloc_json[row[0]].keys():
                alloc_json[row[0]][row[1]] += row[2]
            else:
                alloc_json[row[0]][row[1]] = row[2]
        except (KeyError, TypeError):
            alloc_json[row[0]] = {}
            alloc_json[row[0]][row[1]] = row[2]
    alloc_json = json.dumps(alloc_json)


    if request.method == 'POST':
        # transaction times are stored in UTC
        prod_name = request.form['prod_name']
        from_loc = request.form['from_loc']
        to_loc = request.form['to_loc']
        quantity = request.form['quantity']
        
        # if no 'from loc' is given, that means the product is being shipped to a warehouse (init condition)
        if from_loc in [None, '', ' ']:
            try:
                cursor.execute("""
                    INSERT INTO logistics (prod_id, to_loc_id, prod_quantity) 
                    SELECT products.prod_id, location.loc_id, ? 
                    FROM products, location 
                    WHERE products.prod_name == ? AND location.loc_name == ?
                """, (quantity, prod_name, to_loc))

                # IMPORTANT to maintain consistency
                cursor.execute("""
                UPDATE products 
                SET unallocated_quantity = unallocated_quantity - ? 
                WHERE prod_name == ?
                """, (quantity, prod_name))
                db.commit()

            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"

        elif to_loc in [None, '', ' ']:
            print("To Location wasn't specified, will be unallocated")
            try:
                cursor.execute("""
                INSERT INTO logistics (prod_id, from_loc_id, prod_quantity) 
                SELECT products.prod_id, location.loc_id, ? 
                FROM products, location 
                WHERE products.prod_name == ? AND location.loc_name == ?
                """, (quantity, prod_name, from_loc))

                # IMPORTANT to maintain consistency
                cursor.execute("""
                UPDATE products 
                SET unallocated_quantity = unallocated_quantity + ? 
                WHERE prod_name == ?
                """, (quantity, prod_name))
                db.commit()

            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"

        # if 'from loc' and 'to_loc' given the product is being shipped between warehouses
        else:
            try:
                cursor.execute("SELECT loc_id FROM location WHERE loc_name == ?", (from_loc,))
                from_loc = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("SELECT loc_id FROM location WHERE loc_name == ?", (to_loc,))
                to_loc = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("SELECT prod_id FROM products WHERE prod_name == ?", (prod_name,))
                prod_id = ''.join([str(x[0]) for x in cursor.fetchall()])

                cursor.execute("""
                INSERT INTO logistics (prod_id, from_loc_id, to_loc_id, prod_quantity, tipo)
                VALUES (?, ?, ?, ?, ?)
                """, (prod_id, from_loc, to_loc, quantity, 'T'))

                cursor.execute("""
                UPDATE products 
                SET unallocated_quantity = unallocated_quantity - ? 
                WHERE prod_name == ?
                """, (quantity, prod_name))
                db.commit()

            except sqlite3.Error as e:
                msg = f"An error occurred: {e.args[0]}"
            else:
                msg = "Transaction added successfully"
    
            # print a transaction message if exists!
        if msg:
            print(msg)
            return redirect(url_for('movement'))
    
    type_ = request.args.get('type')    
    if request.method == 'GET' and type_ =='generate': 
        fech_ = request.args.get('fech')
        print (fech_)
        print(gen_nombre)
        print(gen_apelli)

        init_database()
        msg = None
        db = sqlite3.connect(DATABASE_NAME)
        cursor = db.cursor()
        cursor.execute("""select trans_id, prod_name, from_loc_id, loc_name, lc.prod_quantity, tipo, lc.trans_time
                        from ((logistics  as lc
                        inner join products on lc.prod_id = products.prod_id) 
                        inner join location on lc.to_loc_id = location.loc_id )
                        where DATE(trans_time) = ? """, (str(fech_),))
                        
        data = cursor.fetchall()
        cursor.execute("""select loc_name
                        from logistics  as lc
                        inner join location on lc.from_loc_id = location.loc_id
                        """)
        data3 = cursor.fetchall()
        lst2 = list(data3)
        j=0
        for i in range(len(data)):
            pero = data[i]
            lst = list(pero)
            if lst[2] == None:
                lst[2]  =  "-"
            else:
                lst[2]  = lst2[j][0]
                j=j+1
            if lst[5] == 'C':
                lst[5] = 'Compra'
            elif lst[5] == 'T':
                lst[5] = 'Transferencia'
            fecha = lst[6]
            lst[6] = fecha[10:]
            data[i] = tuple(lst)
            
        pdf = canvas.Canvas('.\\inventory\\static\\'+fech_+'.pdf', pagesize=(landscape(letter)))
        
        archivo_imagen = '.\\inventory\\static\\logos.jpg'
        pdf.drawImage(archivo_imagen, 50, 500, width=80, height=80)
        pdfmetrics.registerFont(TTFont('Times-New-Roman','c:\\windows\\fonts\\times.ttf'))
        
        pdf.setFont("Times-New-Roman", 25)
        pdf.drawString(200, 525, "LISTADO DE INVENTARIO LERIETBOOL")

        pdf.setFont("Times-New-Roman", 13)
        pdf.drawString(50, 450, "FECHA: "+fech_)
        pdf.drawString(50, 430, "GENERADO POR: "+gen_apelli+"  "+gen_nombre)
        # pdf.drawString(50, 410, "CARGO: ...")ss

        pdf.setLineWidth(1)
        pdf.line(50,400,750,400)
        pdf.setLineWidth(1)
        pdf.line(50,470,750,470)


        encabezados = ('ID', 'PRODUCTO','ORIGEN','DESTINO','CANTIDAD', 'TIPO','HORA')
        y = 420
        detalle_orden = Table([encabezados] + data, colWidths=[40, 140,140,140,80,90,70],rowHeights=22)
        detalle_orden.setStyle(TableStyle(
            [
                #La primera fila(encabezados) va a estar centrada
                ('ALIGN',(0,0),(6,0),'CENTER'),
                ('BACKGROUND',(0,0),(6,0),colors.gray),
                #Los bordes de todas las celdas serán de color negro y con un grosor de 1
                ('GRID', (0, 0), (-1, -1), 1, colors.black), 
                #El tamaño de las letras de cada una de las celdas será de 10
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('FONT', (0, 0), (-1, -1), 'Times-New-Roman'),
            ]
        ))
        #Establecemos el tamaño de la hoja que ocupará la tabla 
        detalle_orden.wrapOn(pdf, 800, 600)
        #Definimos la coordenada donde se dibujará la tabla
        detalle_orden.drawOn(pdf, 50,160)
        pdf.showPage()
        pdf.save()
        return redirect('.\\static\\'+fech_+'.pdf')
      



    return render('movement.html', title="Movimientos de Productos", link=link, trans_message=msg,
                  products=products, locations=locations, days=days, allocated=alloc_json,
                  logs=logistics_data, database=log_summary)


@app.route('/delete')
def delete():
    type_ = request.args.get('type')
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    if type_ == 'location':
        id_ = request.args.get('loc_id')

        cursor.execute("SELECT prod_id, SUM(prod_quantity) FROM logistics WHERE to_loc_id = ? GROUP BY prod_id", (id_,))
        in_place = cursor.fetchall()

        cursor.execute("SELECT prod_id, SUM(prod_quantity) FROM logistics WHERE from_loc_id = ? GROUP BY prod_id", (id_,))
        out_place = cursor.fetchall()

        # converting list of tuples to dict
        in_place = dict(in_place)
        out_place = dict(out_place)

        # print(in_place, out_place)
        all_place = {}
        for x in in_place.keys():
            if x in out_place.keys():
                all_place[x] = in_place[x] - out_place[x]
            else:
                all_place[x] = in_place[x]
        # print(all_place)

        for products_ in all_place.keys():
            cursor.execute("""
            UPDATE products SET unallocated_quantity = unallocated_quantity + ? WHERE prod_id = ?
            """, (all_place[products_], products_))

        cursor.execute("DELETE FROM location WHERE loc_id == ?", (str(id_),))
        db.commit()

        return redirect(url_for('location'))

    elif type_ == 'product':
        id_ = request.args.get('prod_id')
        cursor.execute("DELETE FROM products WHERE prod_id == ?", (str(id_),))
        db.commit()

        return redirect(url_for('product'))
    
    elif type_ == 'user':
        id_ = request.args.get('user_id')
        cursor.execute("DELETE FROM user WHERE idUsuario == ?", (str(id_),))
        db.commit()

        return redirect(url_for('user'))


@app.route('/edit', methods=['POST', 'GET'])
def edit():
    type_ = request.args.get('type')
    db = sqlite3.connect(DATABASE_NAME)
    cursor = db.cursor()

    if type_ == 'location' and request.method == 'POST':
        loc_id = request.form['loc_id']
        loc_name = request.form['loc_name']

        if loc_name:
            cursor.execute("UPDATE location SET loc_name = ? WHERE loc_id == ?", (loc_name, str(loc_id)))
            db.commit()

        return redirect(url_for('location'))

    elif type_ == 'product' and request.method == 'POST':
        prod_id = request.form['prod_id']
        prod_name = request.form['prod_name']
        prod_quantity = request.form['prod_quantity']

        if prod_name:
            cursor.execute("UPDATE products SET prod_name = ? WHERE prod_id == ?", (prod_name, str(prod_id)))
        if prod_quantity:
            cursor.execute("SELECT prod_quantity FROM products WHERE prod_id = ?", (prod_id,))
            old_prod_quantity = cursor.fetchone()[0]
            cursor.execute("UPDATE products SET prod_quantity = ?, unallocated_quantity =  unallocated_quantity + ? - ?"
                           "WHERE prod_id == ?", (prod_quantity, prod_quantity, old_prod_quantity, str(prod_id)))
        db.commit()
        
        return redirect(url_for('product'))

    elif type_ == 'user' and request.method == 'POST':
        user_id = request.form['user_id']
        new_password = request.form['new_password']
        name = request.form['name']
        last_name = request.form['lastname']
        tipe = request.form['tipe']
        print(tipe)
        if new_password:
            cursor.execute("UPDATE user SET contraseña = ? WHERE idUsuario == ?", (new_password, str(user_id)))
        if name:
            cursor.execute("UPDATE user SET nombres = ? WHERE idUsuario == ?", (name, str(user_id)))
        if last_name:
            cursor.execute("UPDATE user SET apellidos = ? WHERE idUsuario == ?", (last_name, str(user_id)))
        if tipe:
            cursor.execute("UPDATE user SET tipo = ? WHERE idUsuario == ?", (tipe, str(user_id)))
        
        db.commit()

        return redirect(url_for('user'))

    return render(url_for(type_))

if __name__ == '__main__':
    app.run(port = 3000 , debug = True)
