"""API and domain regressions: only fresh temporary SQLite databases."""
from contextlib import closing
from http.cookiejar import CookieJar
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener,HTTPCookieProcessor,Request
import server
from operations import storage,domain
from operations.rules import calculate,Problem
ROOT=Path(__file__).resolve().parents[1]
class Client:
    def __init__(self,base):
        self.base=base;self.opener=build_opener(HTTPCookieProcessor(CookieJar()));self.csrf=""
    def call(self,path,data=None,csrf=True,origin=None):
        headers={"Content-Type":"application/json"}
        if csrf: headers["X-CSRF-Token"]=self.csrf
        if origin: headers["Origin"]=origin
        request=Request(self.base+path,data=None if data is None else json.dumps(data).encode(),headers=headers)
        try:
            with self.opener.open(request,timeout=15) as response:
                kind=response.headers.get_content_type()
                value=json.loads(response.read()) if kind=="application/json" else response.read().decode()
                return response.status,value
        except HTTPError as e: return e.code,json.load(e)
    def start(self):
        code,body=self.call("/api/session")
        if code!=200: raise AssertionError(body)
        self.csrf=body["csrf"];return body
    def state(self): return self.call("/api/state")[1]
    def role(self,role="Reviewer"): return self.call("/api/persona",{"role":role})
class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/"test.sqlite3"
        self.http=server.make_server(self.path,port=0)
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.base="http://127.0.0.1:"+str(self.http.server_port)
        self.a=Client(self.base);self.a.start()
    def tearDown(self):
        self.http.shutdown();self.http.server_close();self.thread.join();self.tmp.cleanup()
    def import_file(self,content=None):
        return self.a.call("/api/imports",dict(filename="fictional.csv",csv=content or (ROOT/"fixtures/products.csv").read_text()))
    def test_seeded_without_secrets(self):
        s=self.a.state();self.assertEqual(len(s["customers"]),7);self.assertEqual(len(s["products"]),4);self.assertTrue(s["results"]);self.assertNotIn("tenant",str(s["customers"]))
    def test_auth_csrf_and_origin(self):
        self.assertEqual(Client(self.base).call("/api/state")[0],401)
        self.assertEqual(self.a.call("/api/reset",{},csrf=False)[0],403)
        self.assertEqual(self.a.call("/api/persona",{"role":"Reviewer"},origin="https://attacker.example")[0],403)
    def test_persona_gate(self):
        c=next(c for c in self.a.state()["campaigns"] if c["status"]=="DRAFT")
        self.assertEqual(self.a.call("/api/campaigns/"+str(c["id"])+"/approve",dict(revision=1))[0],403)
        self.a.role();self.assertEqual(self.a.call("/api/campaigns/"+str(c["id"])+"/approve",dict(revision=1))[0],200)
    def test_workspace_isolation_and_cross_id(self):
        b=Client(self.base);b.start();ac=self.a.state()["customers"][0];bc=b.state()["customers"][0]
        self.assertNotEqual(ac["id"],bc["id"])
        self.assertEqual(b.call("/api/customers/"+str(ac["id"])+"/stage",dict(stage="LEAD",expected_stage=ac["stage"]))[0],404)
        quote=self.a.state()["quotes"][0]
        self.assertEqual(b.call("/api/quotes/"+str(quote["id"])+"/compare?a=1&b=2")[0],404)
        p=self.a.state()["products"][0]
        self.assertEqual(b.call("/api/quotes",dict(customer_id=bc["id"],product_id=p["id"],quantity="3",label="Bad cross reference"))[0],404)
    def test_reset_only_own_data_and_rotates_session(self):
        b=Client(self.base);b.start();old=self.a.state()["customers"][0]["id"];other=b.state()
        code,result=self.a.call("/api/reset",{});self.assertEqual(code,200);self.assertNotEqual(self.a.csrf,result["csrf"]);self.a.csrf=result["csrf"]
        self.assertNotEqual(old,self.a.state()["customers"][0]["id"]);self.assertEqual(other,b.state())
    def test_valid_import_and_idempotency(self):
        before=self.a.state();code,result=self.import_file();self.assertEqual(code,200)
        self.assertEqual(len(self.a.state()["products"]),len(before["products"])+2)
        after=self.a.state();self.assertTrue(self.import_file()[1]["reused"]);self.assertEqual(after,self.a.state())
        self.assertEqual(len([s for s in after["workflow_steps"] if s["workflow_id"]==result["workflow_id"]]),7)
    def test_invalid_import_atomic_and_error_trace(self):
        before=len(self.a.state()["products"])
        code,r=self.import_file("sku,name,category,unit_price,currency\nEX-OK,Valid,Workspace,0.10,USD\nEX-BAD,Invalid,Workspace,NaN,USD")
        self.assertEqual(code,422);self.assertTrue(r["errors"]);s=self.a.state()
        self.assertEqual(len(s["products"]),before);self.assertTrue(any(x["status"]=="ERROR" for x in s["workflow_steps"]))
    def test_master_conflict_is_not_overwritten(self):
        p=self.a.state()["products"][0]
        code,r=self.import_file("sku,name,category,unit_price,currency\n"+p["sku"]+",Conflicting name,Outdoor,2.00,USD")
        self.assertEqual(code,422);self.assertEqual(self.a.state()["products"][0],p)
    def test_price_versions_do_not_mutate_quotes(self):
        s=self.a.state();p=s["products"][0];old=s["quote_versions"]
        content="sku,name,category,unit_price,currency\n"+p["sku"]+","+p["name"]+","+p["category"]+",60.00,USD"
        self.assertEqual(self.import_file(content)[0],200);new=self.a.state();self.assertEqual(old,new["quote_versions"])
        self.assertEqual(len([x for x in new["prices"] if x["product_id"]==p["id"]]),2)
    def test_quote_versions_compare_and_stale_guard(self):
        s=self.a.state();code,q=self.a.call("/api/quotes",dict(customer_id=s["customers"][0]["id"],product_id=s["products"][0]["id"],quantity="3",label="Fresh fictional quote"));self.assertEqual(code,200)
        route="/api/quotes/"+str(q["id"])
        self.assertEqual(self.a.call(route+"/versions",dict(expected_version=1,quantity="3",unit_price="0.10"))[0],200)
        self.assertEqual(self.a.call(route+"/versions",dict(expected_version=1,quantity="3",unit_price="0.20"))[0],409)
        code,diff=self.a.call(route+"/compare?a=1&b=2");self.assertEqual(code,200);self.assertTrue(any(x["field"]=="unit_price" for x in diff))
        self.a.role();self.assertEqual(self.a.call(route+"/approve",dict(version=2))[0],200)
    def test_campaign_current_revision_and_repeat_execution(self):
        self.import_file();c=self.a.state()["campaigns"][-1];route="/api/campaigns/"+str(c["id"])
        self.assertEqual(self.a.call(route+"/execute",dict(revision=1))[0],409)
        self.a.role();self.assertEqual(self.a.call(route+"/approve",dict(revision=1))[0],200)
        self.assertEqual(self.a.call(route+"/revise",dict(revision=1,subject="An updated fictional subject",body=c["body"]))[0],200)
        self.assertEqual(self.a.call(route+"/execute",dict(revision=2))[0],409)
        self.assertEqual(self.a.call(route+"/approve",dict(revision=1))[0],409)
        self.assertEqual(self.a.call(route+"/approve",dict(revision=2))[0],200)
        self.assertEqual(self.a.call(route+"/execute",dict(revision=2))[0],200)
        s=self.a.state();self.assertTrue(self.a.call(route+"/execute",dict(revision=2))[1]["reused"]);self.assertEqual(s,self.a.state())
    def test_recipient_dedup_exclusion_and_preferences_recheck(self):
        c=next(c for c in self.a.state()["campaigns"] if c["status"]=="DRAFT")
        recipients=[r for r in self.a.state()["recipients"] if r["campaign_id"]==c["id"]]
        for reason in ("DUPLICATE","UNSUBSCRIBED","REJECTED","BLOCKED","HARD_BOUNCE","CONTACTED"):
            self.assertTrue(any(r["reason"]==reason for r in recipients),reason)
        self.a.role();self.a.call("/api/campaigns/"+str(c["id"])+"/approve",dict(revision=1))
        chosen=next(r for r in recipients if r["included"])
        self.assertEqual(self.a.call("/api/contacts/"+str(chosen["contact_id"])+"/preference",dict(preference="UNSUBSCRIBED"))[0],200)
        self.assertEqual(self.a.call("/api/campaigns/"+str(c["id"])+"/execute",dict(revision=1))[0],409)
    def test_quote_link_requires_approval(self):
        v=next(v for v in self.a.state()["quote_versions"] if v["status"]=="DRAFT")
        self.assertEqual(self.a.call("/api/campaigns",dict(quote_version_id=v["id"]))[0],409)
        self.a.role();self.a.call("/api/quotes/"+str(v["quote_id"])+"/approve",dict(version=v["version"]))
        code,result=self.a.call("/api/campaigns",dict(quote_version_id=v["id"]));self.assertEqual(code,200)
        c=self.a.state()["campaigns"][-1];self.assertEqual(c["quote_version_id"],v["id"])
    def test_crm_stages_timeline_and_reserved_addresses(self):
        self.assertEqual(self.a.call("/api/customers",dict(company="Fictional",segment="Retail",contact="Test",email="person@blocked.test"))[0],422)
        code,c=self.a.call("/api/customers",dict(company="Fictional New Studio",segment="Retail",contact="Test Visitor",email="visitor@newstudio.example"));self.assertEqual(code,200)
        self.assertEqual(self.a.call("/api/customers/"+str(c["id"])+"/stage",dict(stage="QUALIFIED",expected_stage="LEAD"))[0],200)
        self.assertTrue(any("QUALIFIED" in a["message"] for a in self.a.state()["activities"]))
    def test_static_security_headers(self):
        with self.a.opener.open(self.base+"/") as response:
            self.assertIn("default-src 'self'",response.headers["Content-Security-Policy"])
            self.assertEqual(response.headers["X-Content-Type-Options"],"nosniff")
        self.assertEqual(self.a.call("/assets/../../server.py")[0],404)
    def test_expired_session_is_inaccessible(self):
        with closing(storage.connect(self.path)) as db,db: db.execute("UPDATE visits SET expires=0")
        self.assertEqual(self.a.call("/api/state")[0],401)
        self.a.start();self.assertEqual(len(self.a.state()["products"]),4)
    def test_tenant_composite_foreign_keys(self):
        b=Client(self.base);b.start()
        with closing(storage.connect(self.path)) as db:
            visits=db.execute("SELECT id FROM visits ORDER BY created,id").fetchall();t1,t2=visits[0][0],visits[1][0]
            foreign=db.execute("SELECT id FROM customers WHERE tenant=?",(t2,)).fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError): db.execute("INSERT INTO contacts(tenant,customer_id,name,email,preference) VALUES(?,?,?,?,'OK')",(t1,foreign,"Fictional","x@foreign.example"))
            db.rollback()
    def test_money_snapshots_enforced_by_database(self):
        with closing(storage.connect(self.path)) as db:
            for sql in ("UPDATE prices SET unit_price='0'","UPDATE quote_versions SET total='0'","UPDATE approvals SET actor='Unknown'"):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(sql)
                db.rollback()
class MoneyTests(unittest.TestCase):
    def test_decimal_precision(self):
        self.assertEqual(calculate("3","0.10"),dict(quantity="3",unit_price="0.10",subtotal="0.30",tax="0.02",total="0.32"))
    def test_invalid_values(self):
        for qty,price in (("0","1"),("3","NaN"),("3","Infinity"),("3","-1"),("3",0.1),("1","0.12345")):
            with self.assertRaises(Problem): calculate(qty,price)
class MigrationTests(unittest.TestCase):
    def test_repeat_checksums_and_foreign_keys(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"db.sqlite3";storage.migrate(path);storage.migrate(path)
            with closing(storage.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok");self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(),[])
                db.execute("UPDATE migrations SET digest='invalid'");db.commit()
            with self.assertRaises(RuntimeError): storage.migrate(path)
if __name__=="__main__": unittest.main()
