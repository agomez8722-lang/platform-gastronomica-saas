import sqlite3, json, glob, os
DB_PATH="accesos.db"
class AccessRepository:
    def __init__(self, db_path=DB_PATH):
        self.db_path=db_path; self._init_db()
    def _init_db(self):
        conn=sqlite3.connect(self.db_path)
        conn.execute("CREATE TABLE IF NOT EXISTS accesos (id INTEGER PRIMARY KEY, usuario TEXT, rol TEXT, fecha TEXT, hora TEXT, recurso TEXT, raw TEXT)")
        conn.commit(); conn.close()
    def guardar(self, lista):
        if not lista: return 0
        conn=sqlite3.connect(self.db_path); conn.execute("DELETE FROM accesos")
        for r in lista:
            conn.execute("INSERT INTO accesos (usuario,rol,fecha,hora,recurso,raw) VALUES (?,?,?,?,?,?)",
                         (r.get("usuario"),r.get("rol"),r.get("fecha"),r.get("hora"),r.get("recurso"),json.dumps(r)))
        conn.commit(); conn.close(); return len(lista)
    def listar(self):
        conn=sqlite3.connect(self.db_path)
        cur=conn.execute("SELECT raw FROM accesos ORDER BY fecha,hora")
        rows=[json.loads(x[0]) for x in cur.fetchall()]; conn.close(); return rows
    def migrar_desde_json(self):
        for p in glob.glob("historico*.json"):
            try:
                with open(p,"r",encoding="utf-8") as f:
                    d=json.load(f)
                    if isinstance(d,dict) and "registros" in d: d=d["registros"]
                    if isinstance(d,list) and d: self.guardar(d); return True
            except: pass
        return False
