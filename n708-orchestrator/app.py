# app.py (Aplicação Orquestradora)
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações de conexão com os microserviços
# Em um ambiente de produção, essas URLs viriam de variáveis de ambiente
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')
TICKETS_SERVICE_URL = os.environ.get('TICKETS_SERVICE_URL', 'http://localhost:5002')

# Função para verificar se os serviços estão ativos
def check_services():
    services_status = {
        'auth_service': 'offline',
        'tickets_service': 'offline'
    }
    
    try:
        auth_response = requests.get(f"{AUTH_SERVICE_URL}/health", timeout=2)
        if auth_response.status_code == 200:
            services_status['auth_service'] = 'online'
    except:
        pass
    
    try:
        tickets_response = requests.get(f"{TICKETS_SERVICE_URL}/health", timeout=2)
        if tickets_response.status_code == 200:
            services_status['tickets_service'] = 'online'
    except:
        pass
    
    return services_status

# Rota para verificar a saúde da aplicação orquestradora
@app.route('/health', methods=['GET'])
def health_check():
    services_status = check_services()
    
    return jsonify({
        'status': 'online',
        'services': services_status
    })
