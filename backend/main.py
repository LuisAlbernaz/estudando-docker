import time
import json
import redis
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import OperationalError

# Configuração do banco (conectando ao serviço `db` do Docker Compose)
DATABASE_URL = "postgresql://user:password@db:5432/mydb"
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI()

# Modelo de usuário no banco
table_name = "users"
class User(Base):
    __tablename__ = table_name
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)

# Esperar o banco estar pronto
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

# Dependência do banco
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

    # Cache por 30 segundos
    redis_client.setex(cache_key, 30, json.dumps(result))

    print("📦 Dados salvos no cache!")
    return result
