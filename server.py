"""Same-origin REST service for isolated, expiring public demo workspaces."""
import argparse
from contextlib import closing
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit,parse_qs
from operations import storage,domain,seed
from operations.rules import Problem
ROOT=Path(__file__).resolve().parent

def new_visit(db,ttl=14400):
    now=int(time.time())
    db.execute("DELETE FROM visits WHERE expires<=?",(now,))
    if db.execute("SELECT COUNT(*) FROM visits").fetchone()[0]>=200:
        raise Problem("Demo capacity reached. Try again later",503)
    raw=secrets.token_urlsafe(32);tenant=secrets.token_hex(16);csrf=secrets.token_urlsafe(32)
    db.execute("INSERT INTO visits(id,token_hash,csrf,role,expires,created) VALUES(?,?,?,'Operator',?,?)",(tenant,hashlib.sha256(raw.encode()).hexdigest(),csrf,now+ttl,now))
    seed.populate(db,tenant)
    return raw,dict(id=tenant,csrf=csrf,role="Operator",expires=now+ttl)

class Handler(BaseHTTPRequestHandler):
    server_version="OperationsSandbox/1"
    def log_message(self,*args): pass  # Never log cookies or submitted content.
    def setup(self):
        super().setup()
        self.connection.settimeout(15)
        self.cookie=None
    def send(self,status,value,kind="application/json"):
        payload=json.dumps(value).encode() if kind=="application/json" else value
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Referrer-Policy","no-referrer")
        self.send_header("X-Frame-Options","DENY")
        self.send_header("Content-Security-Policy","default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if self.cookie: self.send_header("Set-Cookie",self.cookie)
        self.end_headers()
        self.wfile.write(payload)
    def origin_check(self):
        host=self.headers.get("Host","")
        if not host or not re.fullmatch(r"[a-zA-Z0-9.:-]+",host): raise Problem("Invalid host",403)
        public=self.server.public_origin
        allowed={"127.0.0.1:"+str(self.server.server_port),"localhost:"+str(self.server.server_port)}
        if public: allowed.add(urlsplit(public).netloc)
        if host not in allowed: raise Problem("Host not allowed",403)
        origin=self.headers.get("Origin")
        expected=public or "http://"+host
        if origin and origin!=expected: raise Problem("Cross-origin request blocked",403)
        if self.headers.get("Sec-Fetch-Site")=="cross-site": raise Problem("Cross-site request blocked",403)
    def actor(self,db,write=False,optional=False):
        cookies=SimpleCookie()
        try: cookies.load(self.headers.get("Cookie",""))
        except Exception: raise Problem("Invalid session",401)
        item=cookies.get("eo_visit");raw=item.value if item else ""
        row=db.execute("SELECT * FROM visits WHERE token_hash=? AND expires>?",(hashlib.sha256(raw.encode()).hexdigest(),int(time.time()))).fetchone()
        if not row:
            if optional: return None
            raise Problem("Workspace expired. Reload to start a fresh demo",401)
        if write and not hmac.compare_digest(self.headers.get("X-CSRF-Token",""),row["csrf"]):
            raise Problem("CSRF validation failed",403)
        return dict(row)
    def set_visit_cookie(self,raw):
        secure="; Secure" if self.server.public_origin.startswith("https://") else ""
        self.cookie="eo_visit="+raw+"; HttpOnly; SameSite=Strict; Path=/; Max-Age=14400"+secure
    def handle_error(self,error):
        if isinstance(error,Problem): self.send(error.status,{"error":str(error)})
        elif isinstance(error,sqlite3.IntegrityError): self.send(409,{"error":"Data constraint conflict. Refresh and review."})
        elif isinstance(error,(ValueError,KeyError,TypeError,UnicodeError,csv_error())): self.send(422,{"error":"Invalid input. Review the required fields."})
        else: self.send(500,{"error":"The demo could not complete this operation. Refresh or reset your workspace."})
    def do_GET(self):
        try:
            self.origin_check()
            path=urlsplit(self.path).path
            if path=="/health": return self.send(200,dict(status="ok",mode="simulation"))
            if path.startswith("/api/"):
                with closing(storage.connect(self.server.db_path)) as db:
                    if path=="/api/session":
                        with db:
                            db.execute("BEGIN IMMEDIATE")
                            actor=self.actor(db,optional=True)
                            if not actor:
                                with self.server.gate:
                                    now=time.time()
                                    recent=[t for t in self.server.starts.get(self.client_address[0],[]) if now-t<3600]
                                    if len(recent)>=40: raise Problem("Too many workspaces. Reuse your current demo",429)
                                    self.server.starts[self.client_address[0]]=recent+[now]
                                raw,actor=new_visit(db)
                                self.set_visit_cookie(raw)
                        return self.send(200,{k:actor[k] for k in ("csrf","role","expires")})
                    actor=self.actor(db);tenant=actor["id"]
                    if path=="/api/state": return self.send(200,domain.state(db,tenant))
                    match=re.fullmatch(r"/api/quotes/(\d+)/compare",path)
                    if match:
                        query=parse_qs(urlsplit(self.path).query)
                        return self.send(200,domain.compare(db,tenant,int(match[1]),int(query.get("a",["1"])[0]),int(query.get("b",["2"])[0])))
                    raise Problem("API route not found",404)
            mapping={"/":ROOT/"web/index.html","/app.js":ROOT/"web/app.js","/styles.css":ROOT/"web/styles.css","/sample-products.csv":ROOT/"fixtures/products.csv"}
            file=mapping.get(path)
            if not file and path.startswith("/assets/"):
                candidate=(ROOT/path.lstrip("/")).resolve()
                try: candidate.relative_to((ROOT/"assets").resolve())
                except ValueError: raise Problem("Asset not found",404)
                if candidate.suffix.lower() in (".svg",".png",".pdf"): file=candidate
            if not file or not file.is_file(): raise Problem("Page not found",404)
            kind=mimetypes.guess_type(str(file))[0] or "application/octet-stream"
            if file.suffix==".js": kind="text/javascript"
            if file.suffix in (".html",".css",".js",".csv"): kind+="; charset=utf-8"
            self.send(200,file.read_bytes(),kind)
        except Exception as error: self.handle_error(error)
    def do_POST(self):
        try:
            self.origin_check()
            if self.headers.get_content_type()!="application/json": raise Problem("Send JSON",415)
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=100000: raise Problem("Request body exceeds demo limits",413)
            data=json.loads(self.rfile.read(length),parse_float=str,parse_constant=lambda x: (_ for _ in ()).throw(ValueError()))
            if not isinstance(data,dict): raise Problem("Send a JSON object")
            path=urlsplit(self.path).path
            with closing(storage.connect(self.server.db_path)) as db,db:
                db.execute("BEGIN IMMEDIATE")
                actor=self.actor(db,write=True);tenant=actor["id"]
                if path=="/api/reset":
                    db.execute("DELETE FROM visits WHERE id=?",(tenant,))
                    raw,actor=new_visit(db);self.set_visit_cookie(raw)
                    result={k:actor[k] for k in ("csrf","role","expires")}
                elif path=="/api/persona":
                    if data.get("role") not in ("Operator","Reviewer"): raise Problem("Invalid demo persona")
                    db.execute("UPDATE visits SET role=? WHERE id=?",(data["role"],tenant));result={"role":data["role"]}
                else:
                    if actor["writes"]>=160: raise Problem("Workspace write limit reached; reset this demo",429)
                    db.execute("UPDATE visits SET writes=writes+1 WHERE id=?",(tenant,))
                    result=self.mutate(db,tenant,actor["role"],path,data)
            status=result.pop("_status",422 if result.get("errors") else 200)
            self.send(status,result)
        except Exception as error: self.handle_error(error)
    def mutate(self,db,t,role,path,data):
        def cap(table,max_rows):
            if db.execute("SELECT COUNT(*) FROM "+table+" WHERE tenant=?",(t,)).fetchone()[0]>=max_rows: raise Problem("Demo record limit reached; reset workspace",429)
        if path=="/api/customers":
            cap("customers",50)
            return domain.customer(db,t,data)
        m=re.fullmatch(r"/api/customers/(\d+)/stage",path)
        if m: return domain.transition(db,t,int(m[1]),data)
        m=re.fullmatch(r"/api/contacts/(\d+)/preference",path)
        if m:
            c=domain.own(db,"contacts",t,int(m[1]))
            if data.get("preference") not in ("OK","UNSUBSCRIBED","REJECTED","HARD_BOUNCE","BLOCKED","CONTACTED"): raise Problem("Invalid preference")
            db.execute("UPDATE contacts SET preference=? WHERE tenant=? AND id=?",(data["preference"],t,c["id"]))
            db.execute("INSERT INTO activities(tenant,customer_id,message) VALUES(?,?,?)",(t,c["customer_id"],"Demo contact preference updated"))
            return {"updated":True}
        if path=="/api/imports":
            cap("products",100);cap("workflows",35)
            return domain.import_csv(db,t,data)
        if path=="/api/quotes":
            cap("quotes",40)
            return domain.create_quote(db,t,data)
        m=re.fullmatch(r"/api/quotes/(\d+)/(versions|approve)",path)
        if m:
            cap("quote_versions",120)
            return domain.amend_quote(db,t,int(m[1]),data) if m[2]=="versions" else domain.approve_quote(db,t,int(m[1]),data,role)
        if path=="/api/campaigns":
            cap("campaigns",35)
            v=domain.own(db,"quote_versions",t,data.get("quote_version_id"))
            if v["status"]!="APPROVED": raise Problem("Approve the quotation version first",409)
            p=json.loads(v["snapshot"])
            cid=domain.new_campaign(db,t,[p["name"]],p["category"],v["id"])
            c=domain.own(db,"campaigns",t,cid)
            domain.step(db,t,c["workflow_id"],1,"Quote reader","DONE","Immutable approved quotation snapshot loaded")
            domain.step(db,t,c["workflow_id"],2,"Validator / rule","DONE","Backend verified quotation approval")
            return {"id":cid}
        m=re.fullmatch(r"/api/campaigns/(\d+)/(approve|revise|execute)",path)
        if m:
            cid=int(m[1])
            if m[2]=="approve": return domain.approve_campaign(db,t,cid,data,role)
            if m[2]=="revise": return domain.revise_campaign(db,t,cid,data)
            return domain.execute(db,t,cid,data)
        raise Problem("API route not found",404)

def csv_error():
    import csv
    return csv.Error

class BoundedServer(ThreadingHTTPServer):
    """A small demo must fail closed instead of spawning unbounded threads."""
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(24)
        super().__init__(*args,**kwargs)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            try: request.sendall(b"HTTP/1.1 503 Busy\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            finally: self.shutdown_request(request)
            return
        try: super().process_request(request,address)
        except Exception:
            self.slots.release()
            raise
    def process_request_thread(self,request,address):
        try: super().process_request_thread(request,address)
        finally: self.slots.release()

def make_server(db_path,host="127.0.0.1",port=8790,public_origin=None):
    storage.migrate(db_path)
    server=BoundedServer((host,port),Handler)
    server.db_path=Path(db_path);server.public_origin=(public_origin or "").rstrip("/")
    server.gate=threading.Lock();server.starts={}
    return server

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=int(os.getenv("PORT","8790")))
    parser.add_argument("--host",default=os.getenv("HOST","127.0.0.1"))
    parser.add_argument("--db",default=os.getenv("DATABASE_PATH",str(ROOT/"var/demo.sqlite3")))
    args=parser.parse_args()
    origin=os.getenv("PUBLIC_ORIGIN") or os.getenv("RENDER_EXTERNAL_URL") or ""
    server=make_server(args.db,args.host,args.port,origin)
    print("Enterprise Operations AI - simulation only",flush=True)
    print("Open http://127.0.0.1:"+str(server.server_port),flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=="__main__": main()
