"""Workspace-scoped business operations and transparent workflow traces."""
import csv
import hashlib
import io
import json
import re
from .rules import Problem,SEGMENTS,amount,calculate,decimal,digest,message,outcome,text

def rows(db,sql,args=()): return [dict(r) for r in db.execute(sql,args)]

def own(db,table,tenant,key):
    row=db.execute("SELECT * FROM "+table+" WHERE tenant=? AND id=?",(tenant,key)).fetchone()
    if row is None: raise Problem("Record not found in this workspace",404)
    return dict(row)

def reviewer(role):
    if role!="Reviewer": raise Problem("Switch to the simulated Reviewer persona to approve",403)

def step(db,tenant,wid,position,agent,status,detail):
    db.execute("INSERT INTO workflow_steps(tenant,workflow_id,position,agent,status,detail) VALUES(?,?,?,?,?,?) ON CONFLICT(tenant,workflow_id,position) DO UPDATE SET status=excluded.status,detail=excluded.detail,at=CURRENT_TIMESTAMP",(tenant,wid,position,agent,status,detail))

def trace(db,tenant,name,source=None):
    return db.execute("INSERT INTO workflows(tenant,name,status,source_hash) VALUES(?,?,'WAITING',?)",(tenant,name,source)).lastrowid

def customer(db,tenant,data):
    company=text(data.get("company"),"Fictional company",80)
    name=text(data.get("contact"),"Contact name",80)
    email=text(data.get("email"),"Synthetic email",160).lower()
    if not re.fullmatch(r"[a-z0-9._+-]+@[a-z0-9.-]+\.(?:example|invalid)",email):
        raise Problem("Use a fictional address ending in .example or .invalid")
    segment=data.get("segment")
    if segment not in ("Business","Industrial","Retail"): raise Problem("Choose a supported segment")
    cid=db.execute("INSERT INTO customers(tenant,company,segment,stage) VALUES(?,?,?,'LEAD')",(tenant,company,segment)).lastrowid
    db.execute("INSERT INTO contacts(tenant,customer_id,name,email,preference) VALUES(?,?,?,?,'OK')",(tenant,cid,name,email))
    db.execute("INSERT INTO activities(tenant,customer_id,message) VALUES(?,?,?)",(tenant,cid,"Fictional lead created in the demo"))
    return {"id":cid}

def transition(db,tenant,cid,data):
    current=own(db,"customers",tenant,cid)
    stage=data.get("stage")
    if stage not in ("LEAD","QUALIFIED","CUSTOMER"): raise Problem("Invalid lead stage")
    if data.get("expected_stage")!=current["stage"]: raise Problem("Lead changed; refresh first",409)
    if stage!=current["stage"]:
        db.execute("UPDATE customers SET stage=? WHERE tenant=? AND id=?",(stage,tenant,cid))
        db.execute("INSERT INTO activities(tenant,customer_id,message) VALUES(?,?,?)",(tenant,cid,"Demo stage: "+current["stage"]+" -> "+stage))
    return {"id":cid}

def recipients(db,tenant,cid,revision,segment):
    seen=set()
    for c in rows(db,"SELECT c.*,a.segment FROM contacts c JOIN customers a ON a.id=c.customer_id AND a.tenant=c.tenant WHERE c.tenant=? ORDER BY c.id",(tenant,)):
        email=c["email"].strip().lower()
        bad=db.execute("SELECT preference FROM contacts WHERE tenant=? AND lower(email)=? AND preference<>'OK' ORDER BY id LIMIT 1",(tenant,email)).fetchone()
        included,reason=1,"Segment matched"
        if bad: included,reason=0,bad[0]
        elif c["segment"]!=segment: included,reason=0,"SEGMENT_MISMATCH"
        elif email in seen: included,reason=0,"DUPLICATE"
        seen.add(email)
        db.execute("INSERT INTO recipients(tenant,campaign_id,revision,contact_id,included,reason) VALUES(?,?,?,?,?,?)",(tenant,cid,revision,c["id"],included,reason))

def new_campaign(db,tenant,names,category,quote_version=None,workflow=None):
    segment=SEGMENTS.get(category)
    if not segment: raise Problem("Unsupported category")
    wid=workflow or trace(db,tenant,"Quotation to campaign")
    subject,body=message(names,segment)
    cid=db.execute("INSERT INTO campaigns(tenant,name,segment,subject,body,status,quote_version_id,workflow_id) VALUES(?,?,?,?,?,'DRAFT',?,?)",(tenant,names[0]+" launch",segment,subject,body,quote_version,wid)).lastrowid
    recipients(db,tenant,cid,1,segment)
    count=db.execute("SELECT COUNT(*) FROM recipients WHERE tenant=? AND campaign_id=? AND included=1",(tenant,cid)).fetchone()[0]
    step(db,tenant,wid,3,"Segment matcher / rule","DONE",str(count)+" eligible contacts; exclusions retained")
    step(db,tenant,wid,4,"Draft composer / rule","DONE","Local template generated. No LLM inference")
    step(db,tenant,wid,5,"Human approval","WAITING","Reviewer must approve the current revision")
    step(db,tenant,wid,6,"Simulated execution","WAITING","Manual simulation. No SMTP or email provider")
    step(db,tenant,wid,7,"Analytics aggregator","WAITING","Waiting for synthetic results")
    return cid

def import_csv(db,tenant,data):
    filename=text(data.get("filename"),"CSV filename",100)
    content=text(data.get("csv"),"CSV content",60000)
    sha=hashlib.sha256(content.encode()).hexdigest()
    prior=db.execute("SELECT * FROM imports WHERE tenant=? AND digest=?",(tenant,sha)).fetchone()
    if prior: return {"id":prior["id"],"workflow_id":prior["workflow_id"],"reused":True,"errors":json.loads(prior["errors"])}
    wid=trace(db,tenant,"Product import: "+filename,sha)
    step(db,tenant,wid,1,"Import reader","DONE","Synthetic CSV retained with SHA-256")
    reader=csv.DictReader(io.StringIO(content));errors=[];parsed=[];seen=set()
    if not reader.fieldnames or not {"sku","name","category","unit_price","currency"}.issubset(reader.fieldnames):
        errors.append("Required headers: sku,name,category,unit_price,currency")
    else:
        for number,row in enumerate(reader,2):
            if number>51:
                errors.append("Maximum 50 rows per import")
                break
            try:
                sku=text(row.get("sku"),"SKU",40).upper();name=text(row.get("name"),"Name",100)
                category=row.get("category")
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{1,39}",sku): raise Problem("Invalid SKU characters")
                if sku in seen: raise Problem("Duplicate SKU in file")
                seen.add(sku)
                if category not in SEGMENTS or row.get("currency")!="USD": raise Problem("Use Workspace/Industrial/Outdoor and USD")
                price=decimal(row.get("unit_price"),"Unit price")
                old=db.execute("SELECT * FROM products WHERE tenant=? AND sku=?",(tenant,sku)).fetchone()
                if old and (old["name"]!=name or old["category"]!=category): raise Problem("Master data conflict; no values overwritten")
                parsed.append((sku,name,category,format(price,"f")))
            except Problem as e: errors.append("Row "+str(number)+": "+str(e))
    if not parsed and not errors: errors.append("CSV has no product rows")
    if errors:
        step(db,tenant,wid,2,"Validator / rule","ERROR","; ".join(errors))
        db.execute("UPDATE workflows SET status='FAILED' WHERE tenant=? AND id=?",(tenant,wid))
        status="FAILED"
    else:
        step(db,tenant,wid,2,"Validator / rule","DONE",str(len(parsed))+" rows validated. Decimal prices, USD only")
        for sku,name,category,price in parsed:
            db.execute("INSERT OR IGNORE INTO products(tenant,sku,name,category,description) VALUES(?,?,?,?,?)",(tenant,sku,name,category,"Fictional catalog specification"))
            pid=db.execute("SELECT id FROM products WHERE tenant=? AND sku=?",(tenant,sku)).fetchone()[0]
            current=db.execute("SELECT * FROM prices WHERE tenant=? AND product_id=? ORDER BY version DESC LIMIT 1",(tenant,pid)).fetchone()
            if not current or decimal(current["unit_price"],"Price")!=decimal(price,"Price"):
                db.execute("INSERT INTO prices(tenant,product_id,version,unit_price,currency,source) VALUES(?,?,?,?,?,?)",(tenant,pid,current["version"]+1 if current else 1,price,"USD",filename+" / "+sha[:10]))
        new_campaign(db,tenant,[p[1] for p in parsed],parsed[0][2],workflow=wid)
        status="VALIDATED"
    iid=db.execute("INSERT INTO imports(tenant,digest,filename,csv_text,status,errors,workflow_id) VALUES(?,?,?,?,?,?,?)",(tenant,sha,filename,content,status,json.dumps(errors),wid)).lastrowid
    return {"id":iid,"workflow_id":wid,"errors":errors,"rows":len(parsed)}

def quote_version(db,tenant,qid,product,price,qty,unit):
    last=db.execute("SELECT COALESCE(MAX(version),0) FROM quote_versions WHERE tenant=? AND quote_id=?",(tenant,qid)).fetchone()[0]
    v=calculate(qty,unit)
    snap=json.dumps({k:product[k] for k in ("sku","name","category","description")},sort_keys=True)
    vid=db.execute("INSERT INTO quote_versions(tenant,quote_id,version,product_id,price_id,snapshot,quantity,unit_price,subtotal,tax,total,currency,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,'USD','DRAFT')",(tenant,qid,last+1,product["id"],price["id"],snap,v["quantity"],v["unit_price"],v["subtotal"],v["tax"],v["total"])).lastrowid
    return {"id":qid,"version_id":vid,"version":last+1}

def create_quote(db,tenant,data):
    c=own(db,"customers",tenant,data.get("customer_id"));p=own(db,"products",tenant,data.get("product_id"))
    price=db.execute("SELECT * FROM prices WHERE tenant=? AND product_id=? ORDER BY version DESC LIMIT 1",(tenant,p["id"])).fetchone()
    if not price: raise Problem("Product needs a price")
    qid=db.execute("INSERT INTO quotes(tenant,customer_id,label) VALUES(?,?,?)",(tenant,c["id"],text(data.get("label"),"Quotation label",80))).lastrowid
    return quote_version(db,tenant,qid,p,dict(price),data.get("quantity"),price["unit_price"])

def amend_quote(db,tenant,qid,data):
    own(db,"quotes",tenant,qid)
    last=db.execute("SELECT * FROM quote_versions WHERE tenant=? AND quote_id=? ORDER BY version DESC LIMIT 1",(tenant,qid)).fetchone()
    if not last or data.get("expected_version")!=last["version"]: raise Problem("Quotation changed; refresh first",409)
    return quote_version(db,tenant,qid,own(db,"products",tenant,last["product_id"]),own(db,"prices",tenant,last["price_id"]),data.get("quantity"),data.get("unit_price"))

def approve_quote(db,tenant,qid,data,role):
    reviewer(role);own(db,"quotes",tenant,qid)
    row=db.execute("SELECT * FROM quote_versions WHERE tenant=? AND quote_id=? AND version=?",(tenant,qid,data.get("version"))).fetchone()
    if not row: raise Problem("Version not found",404)
    if row["status"]=="APPROVED": return {"reused":True}
    payload={k:row[k] for k in ("snapshot","quantity","unit_price","total","currency")}
    db.execute("UPDATE quote_versions SET status='APPROVED' WHERE tenant=? AND id=?",(tenant,row["id"]))
    db.execute("INSERT INTO approvals(tenant,kind,object_id,version,content_hash,actor,result) VALUES(?,'QUOTE',?,?,?,'Demo Reviewer','APPROVED')",(tenant,qid,row["version"],digest(payload)))
    return {"approved":row["id"]}

def campaign_hash(db,tenant,c):
    eligible=rows(db,"SELECT contact_id,included,reason FROM recipients WHERE tenant=? AND campaign_id=? AND revision=? ORDER BY id",(tenant,c["id"],c["revision"]))
    return digest(dict(subject=c["subject"],body=c["body"],segment=c["segment"],recipients=eligible,quote_version=c["quote_version_id"]))

def approve_campaign(db,tenant,cid,data,role):
    reviewer(role);c=own(db,"campaigns",tenant,cid)
    if data.get("revision")!=c["revision"]: raise Problem("Campaign changed; review current revision",409)
    if c["status"] in ("APPROVED","SIMULATED"): return {"reused":True}
    if not db.execute("SELECT 1 FROM recipients WHERE tenant=? AND campaign_id=? AND revision=? AND included=1",(tenant,cid,c["revision"])).fetchone(): raise Problem("No eligible recipients",409)
    db.execute("INSERT INTO approvals(tenant,kind,object_id,version,content_hash,actor,result) VALUES(?,'CAMPAIGN',?,?,?,'Demo Reviewer','APPROVED')",(tenant,cid,c["revision"],campaign_hash(db,tenant,c)))
    db.execute("UPDATE campaigns SET status='APPROVED' WHERE tenant=? AND id=?",(tenant,cid))
    step(db,tenant,c["workflow_id"],5,"Human approval","DONE","Demo Reviewer approved revision "+str(c["revision"]))
    db.execute("UPDATE workflows SET status='WAITING' WHERE tenant=? AND id=?",(tenant,c["workflow_id"]))
    step(db,tenant,c["workflow_id"],6,"Simulated execution","WAITING","Ready for manual simulation")
    return {"approved":cid}

def revise_campaign(db,tenant,cid,data):
    c=own(db,"campaigns",tenant,cid)
    if data.get("revision")!=c["revision"]: raise Problem("Campaign changed; reload first",409)
    subject,body=text(data.get("subject"),"Subject",160),text(data.get("body"),"Body",3000)
    if subject==c["subject"] and body==c["body"]: return {"reused":True}
    db.execute("UPDATE campaigns SET subject=?,body=?,revision=revision+1,status='DRAFT' WHERE tenant=? AND id=?",(subject,body,tenant,cid))
    recipients(db,tenant,cid,c["revision"]+1,c["segment"])
    db.execute("UPDATE workflows SET status='WAITING' WHERE tenant=? AND id=?",(tenant,c["workflow_id"]))
    step(db,tenant,c["workflow_id"],5,"Human approval","WAITING","Content changed; a new approval is required")
    step(db,tenant,c["workflow_id"],6,"Simulated execution","WAITING","Current revision has not been simulated")
    step(db,tenant,c["workflow_id"],7,"Analytics aggregator","WAITING","Previous results remain historical")
    return {"revision":c["revision"]+1}

def blocked_execution(db,tenant,c,message_text):
    step(db,tenant,c["workflow_id"],6,"Simulated execution","ERROR",message_text)
    db.execute("UPDATE workflows SET status='BLOCKED' WHERE tenant=? AND id=?",(tenant,c["workflow_id"]))
    return {"error":message_text,"_status":409}

def execute(db,tenant,cid,data):
    c=own(db,"campaigns",tenant,cid)
    if data.get("revision")!=c["revision"]: raise Problem("Campaign changed; reload first",409)
    old=db.execute("SELECT id FROM executions WHERE tenant=? AND campaign_id=? AND revision=?",(tenant,cid,c["revision"])).fetchone()
    if old: return {"execution_id":old[0],"reused":True}
    approval=db.execute("SELECT * FROM approvals WHERE tenant=? AND kind='CAMPAIGN' AND object_id=? AND version=? ORDER BY id DESC LIMIT 1",(tenant,cid,c["revision"])).fetchone()
    if c["status"]!="APPROVED" or not approval or approval["content_hash"]!=campaign_hash(db,tenant,c): return blocked_execution(db,tenant,c,"Current revision requires human approval")
    selected=rows(db,"SELECT c.* FROM recipients r JOIN contacts c ON c.tenant=r.tenant AND c.id=r.contact_id WHERE r.tenant=? AND r.campaign_id=? AND r.revision=? AND r.included=1",(tenant,cid,c["revision"]))
    for ctc in selected:
        if db.execute("SELECT 1 FROM contacts WHERE tenant=? AND lower(email)=? AND preference<>'OK'",(tenant,ctc["email"].lower())).fetchone(): return blocked_execution(db,tenant,c,"Recipient preferences changed. Prepare a new campaign")
    eid=db.execute("INSERT INTO executions(tenant,campaign_id,revision,status) VALUES(?,?,?,'SIMULATED')",(tenant,cid,c["revision"])).lastrowid
    for ctc in selected:
        delivered,opened,clicked=outcome(ctc["email"])
        db.execute("INSERT INTO results(tenant,execution_id,contact_id,delivered,opened,clicked) VALUES(?,?,?,?,?,?)",(tenant,eid,ctc["id"],delivered,opened,clicked))
        db.execute("INSERT INTO activities(tenant,customer_id,message) VALUES(?,?,?)",(tenant,ctc["customer_id"],"SIMULATED campaign result recorded; no email sent"))
    db.execute("UPDATE campaigns SET status='SIMULATED' WHERE tenant=? AND id=?",(tenant,cid))
    step(db,tenant,c["workflow_id"],6,"Simulated execution","DONE","Deterministic outcomes; zero external messages")
    step(db,tenant,c["workflow_id"],7,"Analytics aggregator","DONE",str(len(selected))+" synthetic results aggregated")
    db.execute("UPDATE workflows SET status='COMPLETED' WHERE tenant=? AND id=?",(tenant,c["workflow_id"]))
    return {"execution_id":eid,"simulated_contacts":len(selected)}

def compare(db,tenant,qid,a,b):
    own(db,"quotes",tenant,qid);versions=[]
    for version in (a,b):
        row=db.execute("SELECT * FROM quote_versions WHERE tenant=? AND quote_id=? AND version=?",(tenant,qid,version)).fetchone()
        if not row: raise Problem("Select two existing versions",404)
        versions.append(dict(row))
    keys=("snapshot","quantity","unit_price","subtotal","tax","total","currency","status")
    return [dict(field=k,before=versions[0][k],after=versions[1][k]) for k in keys if versions[0][k]!=versions[1][k]]

def state(db,tenant):
    data={}
    for table in ("customers","contacts","activities","products","prices","quotes","quote_versions","campaigns","recipients","approvals","executions","results","workflows","workflow_steps"):
        data[table]=[{k:v for k,v in r.items() if k!="tenant"} for r in rows(db,"SELECT * FROM "+table+" WHERE tenant=? ORDER BY id",(tenant,))]
    data["imports"]=rows(db,"SELECT id,filename,status,errors,workflow_id,at FROM imports WHERE tenant=? ORDER BY id",(tenant,))
    data["summary"]=dict(customers=len(data["customers"]),products=len(data["products"]),quotes=len(data["quotes"]),pending=sum(c["status"]=="DRAFT" for c in data["campaigns"]),campaigns=len(data["campaigns"]),simulated=len(data["executions"]),delivered=sum(r["delivered"] for r in data["results"]),opened=sum(r["opened"] for r in data["results"]),clicked=sum(r["clicked"] for r in data["results"]),quote_value=amount(sum((decimal(q["total"],"Total") for q in data["quote_versions"] if q["status"]=="APPROVED"),decimal("0","Zero"))))
    return data
