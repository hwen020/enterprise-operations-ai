"""Fictional records built independently for every new visitor."""
from . import domain
CATALOG = """sku,name,category,unit_price,currency
EX-ARC-01,Arc task luminaire,Workspace,49.90,USD
EX-FLOW-02,Flow acoustic panel,Workspace,34.25,USD
EX-GRID-03,Grid inspection light,Industrial,86.40,USD
EX-PATH-04,Path garden marker,Outdoor,28.75,USD
"""
def populate(db,tenant):
    companies=[
        ("Cedar Sketch Studio","Business","Maya Reed","maya@cedarsketch.example"),
        ("Paper Kite Atelier","Business","Alex Park","alex@paperkite.example"),
        ("Moss Workshop","Industrial","Robin Vale","robin@mossworks.example"),
        ("Orbit Makers","Industrial","Jules Lane","jules@orbitmakers.example"),
        ("Pebble Market","Retail","Ari Quinn","ari@pebblemarket.example"),
        ("Fern Corner","Retail","Sam Avery","sam@ferncorner.example"),
        ("Bramble Lab","Business","Lee Rowan","lee@bramblelab.example")]
    ids=[]
    for company,segment,name,email in companies:
        ids.append(domain.customer(db,tenant,dict(company=company,segment=segment,contact=name,email=email))["id"])
    for i,cid in enumerate(ids):
        db.execute("UPDATE customers SET stage=? WHERE tenant=? AND id=?",("CUSTOMER" if i<2 else "QUALIFIED" if i<5 else "LEAD",tenant,cid))
    extra=[(ids[0],"Maya duplicate","maya@cedarsketch.example","OK"),(ids[1],"Opted out","optout@paperkite.example","UNSUBSCRIBED"),(ids[2],"Bounce example","bounce@mossworks.example","HARD_BOUNCE"),(ids[4],"Blocked example","blocked@pebblemarket.example","BLOCKED"),(ids[0],"Declined example","declined@cedarsketch.example","REJECTED"),(ids[6],"Contacted example","past@bramblelab.example","CONTACTED")]
    for cid,name,email,preference in extra:
        db.execute("INSERT INTO contacts(tenant,customer_id,name,email,preference) VALUES(?,?,?,?,?)",(tenant,cid,name,email,preference))
    domain.import_csv(db,tenant,dict(filename="fictional-starter.csv",csv=CATALOG))
    pid=db.execute("SELECT id FROM products WHERE tenant=? ORDER BY id LIMIT 1",(tenant,)).fetchone()[0]
    q=domain.create_quote(db,tenant,dict(customer_id=ids[0],product_id=pid,quantity="8",label="Studio refresh / fictional"))
    domain.approve_quote(db,tenant,q["id"],dict(version=1),"Reviewer")
    domain.amend_quote(db,tenant,q["id"],dict(expected_version=1,quantity="10",unit_price="47.50"))
    q2=domain.create_quote(db,tenant,dict(customer_id=ids[2],product_id=pid,quantity="4",label="Sample kit / fictional"))
    domain.approve_quote(db,tenant,q2["id"],dict(version=1),"Reviewer")
    for name,category,simulate in (("Workshop collection","Industrial",True),("Garden collection","Outdoor",False)):
        cid=domain.new_campaign(db,tenant,[name],category)
        domain.approve_campaign(db,tenant,cid,dict(revision=1),"Reviewer")
        if simulate: domain.execute(db,tenant,cid,dict(revision=1))
    for wid, in db.execute("SELECT id FROM workflows WHERE tenant=? AND source_hash IS NULL",(tenant,)).fetchall():
        domain.step(db,tenant,wid,1,"Demo starter","DONE","Independently generated fictional catalog")
        domain.step(db,tenant,wid,2,"Validator / rule","DONE","Synthetic records validated locally")
