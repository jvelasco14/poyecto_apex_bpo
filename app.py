from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Ruta 1: Pantalla de Login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        
        # Simulamos una validación sencilla
        if usuario == 'admin' and password == '1234':
            return redirect(url_for('dashboard'))
        else:
            return "Credenciales incorrectas. Intenta de nuevo."
            
    return render_template('login.html')

# Ruta 2: Dashboard Interno (Por ahora vacío, lo haremos en la siguiente fase)
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    # Ejecutamos el servidor en el puerto 5000
    app.run(debug=True, port=5000)