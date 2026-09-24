from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class Acceso(Base):
    __tablename__ = "accesos"
    id = Column(Integer, primary_key=True)
    usuario = Column(String, index=True)
    rol = Column(String)
    recurso = Column(String)
    ip = Column(String, index=True)
    hora = Column(String)
    fecha = Column(DateTime, default=datetime.utcnow)
    tenant_id = Column(String, index=True, default="default") # multi-tenancy
    motivos = Column(JSON)

class Blacklist(Base):
    __tablename__ = "blacklist"
    ip = Column(String, primary_key=True)
    count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow)
