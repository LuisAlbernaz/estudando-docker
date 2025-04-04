import os
import time
import json
import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError

# Carrega variáveis de ambiente
load_dotenv()

# Configurações do Postgres via .env
POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")

# Configura Redis via .env
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Conexão com o banco e redis
DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# Modelo ORM do usuário
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

# Aguarda o banco de dados ficar pronto
def wait_for_db():
    retries = 5
    while retries > 0:
        try:
            with engine.connect() as connection:
                print("🎯 Banco de dados conectado com sucesso!")
                return
        except OperationalError:
            print("⏳ Aguardando o banco de dados...")
            time.sleep(5)
            retries -= 1
    print("❌ Banco de dados não respondeu a tempo.")
    raise Exception("Banco de dados não está disponível.")

wait_for_db()
Base.metadata.create_all(bind=engine)

# Schemas Pydantic
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

# Dependência para obter sessão do banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Rota de registro
@app.post("/register")
def register_user(request: RegisterRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if user:
        raise HTTPException(status_code=400, detail="Usuário já existe")

    new_user = User(username=request.username, password=request.password)
    db.add(new_user)
    db.commit()
    return {"message": "Usuário registrado com sucesso"}

# Rota de login
@app.post("/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or user.password != request.password:
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    return {"message": f"Bem-vindo, {request.username}!"}

# Rota para listar usuários com cache
@app.get("/users")
def get_users(db: Session = Depends(get_db)):
    cache_key = "users_cache"
    cached_users = redis_client.get(cache_key)

    if cached_users:
        print("✅ Retornando do cache...")
        return json.loads(cached_users)

    users = db.query(User).all()
    result = [UserResponse.from_orm(user).dict() for user in users]

    redis_client.setex(cache_key, 30, json.dumps(result))
    print("📦 Dados salvos no cache!")
    return result
