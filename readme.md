# 📓 Descrição

Projeto da disciplina de "Projeto Aplicado de Multiplataformas etapa 2"

---

# 👥 Membros da equipe 18

- 2314031 - Andrew Ribeiro Pires
- 1610329 - Artur Vinicius Araujo Vieira de Sousa
- 2313394 - Kawhan Santos
- 2226022 - Maurício Conde Ramon Oliveira
- 2323748 - Vinícius Linhares Alves de Oliveira

---

# 📦 Tecnologias

- Python 3.11
- Flask
- SQLite
- JWT (access & refresh tokens)
- Docker e Docker Compose

---

# 1. Rodar usando docker

---

## 1.1. Dependências

- Docker
- Docker Compose

---

## 1.2. Rodar a aplicação com docker
```bash
docker compose up -d
```
---

# 2. Rodar sem docker

---

## 2.1. Dependências

- python

---

## 2.2. Criar ambiente virtual ativar e instalar as dependências
é necessário criar ambiente virtual individual de cada app

```bash
cd n708-authentication
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

cd n708-orchestrator
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

cd n708-ticket
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..
```

## 2.3. Rodar a aplicação
é necessário rodar individualmente cada app

```bash
python n708-authentication/app.py
python n708-orchestrator/app.py
python n708-ticket/app.py
```
