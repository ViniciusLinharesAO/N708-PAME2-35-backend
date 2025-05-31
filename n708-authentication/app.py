# auth_service/app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import re
import json
from datetime import timedelta

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuração do JWT
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default-dev-key-auth-service')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)

# Caminho do banco de dados
DB_PATH = os.environ.get('DB_PATH', 'users.db')

# Função para obter conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Inicialização do banco de dados
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Criação da tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        document_type TEXT NOT NULL,
        document TEXT UNIQUE NOT NULL,
        address TEXT,
        role TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Verificar se já existe um usuário admin
    admin = cursor.execute('SELECT * FROM users WHERE role = ?', ('admin',)).fetchone()
    if not admin:
        # Criar usuário admin padrão
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Admin', 'admin@example.com', generate_password_hash('admin123'), 'cpf', '00000000000', 'admin')
        )
    
    # Verificar se já existe um usuário organization
    org = cursor.execute('SELECT * FROM users WHERE role = ?', ('organization',)).fetchone()
    if not org:
        # Criar usuário organization padrão
        cursor.execute(
            'INSERT INTO users (name, email, password, document_type, document, role) VALUES (?, ?, ?, ?, ?, ?)',
            ('Prefeitura', 'prefeitura@example.com', generate_password_hash('org123'), 'cnpj', '00000000000000', 'organization')
        )
    
    conn.commit()
    conn.close()
    
# Inicializar o banco de dados na inicialização da aplicação
init_db()