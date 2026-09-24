import redis, time, json, pathlib, os
from filelock import FileLock
r = redis.Redis.from_url(os.getenv("REDIS_URL","redis://localhost:6379/0"), decode_responses=True)

def rate_limit_real(ip, genoma):
    key=f"rl:{ip}"; now=time.time()
    r.zadd(key,{str(now):now}); r.zremrangebyscore(key,0,now-genoma["rate_limit_ventana"])
    r.expire(key, genoma["rate_limit_ventana"])
    return r.zcard(key) >= genoma["rate_limit_umbral"]

def guardar_memoria_threadsafe(path, mem):
    with FileLock(f"{path}.lock"):
        pathlib.Path(path).write_text(json.dumps(mem))
