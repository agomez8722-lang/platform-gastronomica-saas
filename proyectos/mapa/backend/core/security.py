from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os, re
from urllib.parse import unquote_plus

SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esto-en-prod-muy-largo")
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def normalize(s: str) -> str:
    cur = s.lower()
    for _ in range(3):
        cur = unquote_plus(cur)
    return cur

SQLI_RE = re.compile(r"('|\"|%27).*?(or|union|select|drop).*?(=|1=1)", re.I)
TRAVERSAL_RE = re.compile(r"(\.\./|etc/passwd|etc/shadow)", re.I)

def detectar_sqli_real(r: dict) -> bool:
    recurso = normalize(r.get("recurso",""))
    return bool(SQLI_RE.search(recurso))

def verificar_rol(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("rol")!= "admin":
            raise HTTPException(status_code=403, detail="No admin")
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalido")
