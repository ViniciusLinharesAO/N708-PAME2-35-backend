# tickets_service/app.py
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import os
import uuid
import json
import requests
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configurações
DB_PATH = os.environ.get('DB_PATH', 'tickets.db')
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads')
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://localhost:5001')

# Garantir que o diretório de uploads existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Extensões permitidas para imagens
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Função para obter conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Inicialização do banco de dados
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Criação da tabela de tickets
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        image_url TEXT,
        address TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()

# Inicializar o banco de dados na inicialização da aplicação
init_db()

# Função para verificar extensão de arquivo permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Função para verificar token JWT com o serviço de autenticação
def verify_token(token):
    try:
        # Primeiro, verificar se o token é válido
        response = requests.post(
            f"{AUTH_SERVICE_URL}/verify-token",
            json={"token": token},
            timeout=5
        )
        if response.status_code == 200:
            user_id = response.json()['user']
            
            # Agora, buscar os dados completos do usuário no serviço de auth
            # Fazer uma chamada para obter o perfil completo
            profile_response = requests.get(
                f"{AUTH_SERVICE_URL}/profile",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            
            if profile_response.status_code == 200:
                # Se conseguir pegar o perfil, usar os dados completos
                user_data = profile_response.json().get('user', {})
                return {
                    'id': int(user_id),
                    'role': user_data.get('role', 'user'),
                    'name': user_data.get('name', ''),
                    'email': user_data.get('email', '')
                }, None
            else:
                # Fallback: buscar dados básicos do banco local de auth
                return get_user_from_auth_db(int(user_id)), None
        else:
            return None, response.json().get('error', 'Token inválido')
    except requests.RequestException as e:
        return None, f"Erro ao verificar token: {str(e)}"

# NOVA FUNÇÃO: Buscar dados do usuário diretamente no banco do serviço de auth
def get_user_from_auth_db(user_id):
    """
    Função alternativa para buscar dados do usuário.
    Em produção, isso seria feito via API do serviço de auth.
    """
    try:
        # Lista de possíveis caminhos para o banco do serviço de auth
        possible_paths = [
            '../n708-authentication/users.db',
            './users.db',
            'users.db',
            os.path.join(os.path.dirname(__file__), '../n708-authentication/users.db')
        ]
        
        auth_db_path = None
        for path in possible_paths:
            if os.path.exists(path):
                auth_db_path = path
                break
        
        if auth_db_path:
            conn = sqlite3.connect(auth_db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            user = cursor.execute(
                'SELECT id, name, email, role FROM users WHERE id = ?', 
                (user_id,)
            ).fetchone()
            
            conn.close()
            
            if user:
                return {
                    'id': user['id'],
                    'role': user['role'],
                    'name': user['name'],
                    'email': user['email']
                }
        
        # Fallback se não conseguir acessar o banco
        print(f"WARNING: Não foi possível acessar o banco de auth. User ID: {user_id}")
        return {
            'id': user_id,
            'role': 'user',  # Assume user por segurança
            'name': 'Usuário',
            'email': ''
        }
    except Exception as e:
        print(f"ERROR ao buscar usuário: {e}")
        return {
            'id': user_id,
            'role': 'user',
            'name': 'Usuário',
            'email': ''
        }

# Middleware para extrair e verificar token
def auth_required():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, "Token não fornecido"

    token = auth_header.split(' ')[1]
    return verify_token(token)

# Rota para verificação de saúde
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'online',
        'service': 'tickets_service'
    })

# Rota para servir imagens de uploads
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# Rota para obter todos os tickets (com filtros opcionais)
@app.route('/tickets', methods=['GET'])
def get_tickets():
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    # Parâmetros de filtro
    status = request.args.get('status')
    location = request.args.get('location')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = 'SELECT * FROM tickets'
        params = []

        # Adicionar filtros conforme necessário
        conditions = []

        # Se o usuário não for admin ou organização, mostrar apenas seus tickets
        if user['role'] == 'user':
            conditions.append('user_id = ?')
            params.append(user['id'])

        if status:
            conditions.append('status = ?')
            params.append(status)

        if location:
            conditions.append('address LIKE ?')
            params.append(f'%{location}%')

        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)

        # Ordenar por data de criação (mais recentes primeiro)
        query += ' ORDER BY created_at DESC'

        tickets = cursor.execute(query, params).fetchall()

        # Converter para lista de dicionários
        result = []
        for ticket in tickets:
            result.append(dict(ticket))

        conn.close()
        return jsonify({"tickets": result}), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para criar um novo ticket
@app.route('/tickets', methods=['POST'])
def create_ticket():
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    # Verificar se é multipart form data ou json
    if request.content_type and 'multipart/form-data' in request.content_type:
        # Formulário com possível upload de imagem
        if 'title' not in request.form or 'description' not in request.form or 'address' not in request.form:
            return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

        title = request.form['title']
        description = request.form['description']
        address = request.form['address']

        # Processar a imagem (se existir)
        image_url = None
        if 'image' in request.files:
            image = request.files['image']
            if image and allowed_file(image.filename):
                # Gerar nome único para o arquivo
                filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(image.filename)[1])
                image_path = os.path.join(UPLOAD_FOLDER, filename)
                image.save(image_path)
                image_url = f'/uploads/{filename}'
    else:
        # Requisição JSON
        data = request.get_json()

        if 'title' not in data or 'description' not in data or 'address' not in data:
            return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

        title = data['title']
        description = data['description']
        address = data['address']
        image_url = data.get('image_url')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Inserir o ticket no banco de dados
        cursor.execute(
            '''
            INSERT INTO tickets (title, description, user_id, image_url, address, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (title, description, user['id'], image_url, address, 'aberto')
        )
        conn.commit()

        # Obter o ID do ticket recém-criado
        ticket_id = cursor.lastrowid

        conn.close()
        return jsonify({
            "message": "Ticket criado com sucesso",
            "id": ticket_id
        }), 201

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para obter um ticket específico
@app.route('/tickets/<int:ticket_id>', methods=['GET'])
def get_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Buscar o ticket
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        # Verificar permissão para visualizar o ticket
        if user['role'] == 'user' and ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403

        # Adicionar informações do usuário que criou o ticket
        try:
            # Buscar usuário do serviço de autenticação (implementação simulada)
            # Em um cenário real, você faria uma chamada ao serviço de autenticação
            user_info = {
                "id": ticket['user_id'],
                "name": "Nome do Usuário",  # Placeholder
                "email": "email@example.com"  # Placeholder
            }
        except:
            user_info = {
                "id": ticket['user_id'],
                "name": "Usuário desconhecido",
                "email": ""
            }

        # Converter o objeto Row para dicionário
        ticket_dict = dict(ticket)

        # Adicionar informações do usuário
        ticket_dict['user'] = user_info

        conn.close()
        return jsonify({"ticket": ticket_dict}), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para atualizar o status de um ticket
@app.route('/tickets/<int:ticket_id>/status', methods=['PATCH'])
def update_ticket_status(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    # Verificar permissão para atualizar o status
    if user['role'] not in ['admin', 'organization']:
        return jsonify({"error": "Não autorizado"}), 403

    data = request.get_json()

    if 'status' not in data or data['status'] not in ['aberto', 'em andamento', 'resolvido']:
        return jsonify({"error": "Status inválido"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o ticket existe
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        # Atualizar o status do ticket
        cursor.execute(
            'UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (data['status'], ticket_id)
        )
        conn.commit()

        conn.close()
        return jsonify({
            "message": "Status atualizado com sucesso",
            "ticket_id": ticket_id,
            "new_status": data['status']
        }), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para assumir um ticket (para organizações)
@app.route('/tickets/<int:ticket_id>/assign', methods=['PATCH'])
def assign_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    # Debug: verificar dados do usuário
    print(f"DEBUG - User data: {user}")
    print(f"DEBUG - User role: {user.get('role', 'NO_ROLE')}")

    # Verificar permissão para assumir o ticket (apenas organizações)
    if user.get('role') not in ['organization', 'empresa']:
        return jsonify({"error": f"Apenas organizações podem assumir tickets. Role atual: {user.get('role', 'undefined')}"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o ticket existe
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        # Verificar se o ticket ainda está aberto
        if ticket['status'] != 'aberto':
            conn.close()
            return jsonify({"error": "Ticket já foi assumido ou resolvido"}), 400

        # Atualizar o status do ticket para 'em andamento'
        cursor.execute(
            'UPDATE tickets SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            ('em andamento', ticket_id)
        )
        conn.commit()

        conn.close()
        return jsonify({
            "message": "Ticket assumido com sucesso",
            "ticket_id": ticket_id,
            "status": "em andamento",
            "assigned_to": user.get('name', 'Organização')
        }), 200

    except Exception as e:
        if 'conn' in locals():
            conn.close()
        print(f"DEBUG - Error in assign_ticket: {str(e)}")
        return jsonify({"error": str(e)}), 500

# Rota para atualizar um ticket existente
@app.route('/tickets/<int:ticket_id>', methods=['PUT'])
def update_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o ticket existe
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        # Verificar permissão para editar o ticket
        if user['role'] == 'user' and ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403

        # Verificar se é multipart form data ou json
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Formulário com possível upload de imagem
            if 'title' not in request.form or 'description' not in request.form or 'address' not in request.form:
                conn.close()
                return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

            title = request.form['title']
            description = request.form['description']
            address = request.form['address']

            # Processar a imagem (se existir)
            image_url = ticket['image_url']  # Manter a URL atual por padrão
            if 'image' in request.files:
                image = request.files['image']
                if image and allowed_file(image.filename):
                    # Gerar nome único para o arquivo
                    filename = secure_filename(str(uuid.uuid4()) + os.path.splitext(image.filename)[1])
                    image_path = os.path.join(UPLOAD_FOLDER, filename)
                    image.save(image_path)

                    # Se havia uma imagem anterior, pode excluí-la para economizar espaço
                    if ticket['image_url']:
                        try:
                            old_image_path = os.path.join(UPLOAD_FOLDER, os.path.basename(ticket['image_url']))
                            if os.path.exists(old_image_path):
                                os.remove(old_image_path)
                        except:
                            pass

                    image_url = f'/uploads/{filename}'
        else:
            # Requisição JSON
            data = request.get_json()

            if 'title' not in data or 'description' not in data or 'address' not in data:
                conn.close()
                return jsonify({"error": "Título, descrição e endereço são obrigatórios"}), 400

            title = data['title']
            description = data['description']
            address = data['address']
            image_url = data.get('image_url', ticket['image_url'])

        # Atualizar o ticket no banco de dados
        cursor.execute(
            '''
            UPDATE tickets
            SET title = ?, description = ?, image_url = ?, address = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (title, description, image_url, address, ticket_id)
        )
        conn.commit()

        conn.close()
        return jsonify({
            "message": "Ticket atualizado com sucesso",
            "id": ticket_id
        }), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para excluir um ticket
@app.route('/tickets/<int:ticket_id>', methods=['DELETE'])
def delete_ticket(ticket_id):
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar se o ticket existe
        ticket = cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,)).fetchone()

        if not ticket:
            conn.close()
            return jsonify({"error": "Ticket não encontrado"}), 404

        # Verificar permissão para excluir o ticket
        if user['role'] == 'user' and ticket['user_id'] != user['id']:
            conn.close()
            return jsonify({"error": "Não autorizado"}), 403

        # Excluir o ticket
        cursor.execute('DELETE FROM tickets WHERE id = ?', (ticket_id,))
        conn.commit()

        # Se havia uma imagem, excluí-la
        if ticket['image_url']:
            try:
                image_path = os.path.join(UPLOAD_FOLDER, os.path.basename(ticket['image_url']))
                if os.path.exists(image_path):
                    os.remove(image_path)
            except:
                pass

        conn.close()
        return jsonify({
            "message": "Ticket excluído com sucesso",
            "id": ticket_id
        }), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Rota para obter estatísticas dos tickets
@app.route('/tickets/stats', methods=['GET'])
def get_ticket_stats():
    # Verificar autenticação
    user, error = auth_required()
    if error:
        return jsonify({"error": error}), 401

    # Verificar permissão para acessar estatísticas
    if user['role'] not in ['admin', 'organization']:
        return jsonify({"error": "Não autorizado"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Estatísticas por status
        status_stats = []
        for status in ['aberto', 'em andamento', 'resolvido']:
            count = cursor.execute('SELECT COUNT(*) FROM tickets WHERE status = ?', (status,)).fetchone()[0]
            status_stats.append({
                "status": status,
                "count": count
            })

        # Total de tickets
        total = cursor.execute('SELECT COUNT(*) FROM tickets').fetchone()[0]

        # Tickets criados nos últimos 7 dias
        recent = cursor.execute(
            "SELECT COUNT(*) FROM tickets WHERE created_at >= datetime('now', '-7 days')"
        ).fetchone()[0]

        conn.close()
        return jsonify({
            "total": total,
            "recent_7_days": recent,
            "by_status": status_stats
        }), 200

    except sqlite3.Error as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

# Tratamento de erros
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint não encontrado'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'error': 'Erro interno do servidor'}), 500

if __name__ == '__main__':
    # Obter porta do ambiente ou usar 5002 por padrão
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port)