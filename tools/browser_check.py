"""Real Chrome end-to-end acceptance for desktop and 390px, with synthetic data."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.devtools import DevTools
import server

def browser_path():
    configured=os.getenv("BROWSER_BIN")
    candidates=[configured,shutil.which("google-chrome"),shutil.which("chromium"),shutil.which("chromium-browser")]
    if os.name=="nt":
        candidates += [str(Path(os.getenv("PROGRAMFILES","C:/Program Files"))/"Google/Chrome/Application/chrome.exe")]
    for path in candidates:
        if path and Path(path).is_file(): return str(path)
    raise RuntimeError("Set BROWSER_BIN to Chrome or Chromium")

def run(width):
    shots=ROOT/"assets/screenshots";shots.mkdir(parents=True,exist_ok=True)
    temporary=tempfile.TemporaryDirectory(prefix="enterprise-qa-")
    folder=Path(temporary.name)
    service=server.make_server(folder/"browser.sqlite3",port=0)
    thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
    process=subprocess.Popen([browser_path(),"--headless=new","--disable-gpu","--no-first-run","--remote-debugging-port=0","--remote-allow-origins=*","--user-data-dir="+str(folder/"profile"),"about:blank"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
    checks={};client=None
    try:
        for _ in range(100):
            try:
                debug=int((folder/"profile/DevToolsActivePort").read_text().splitlines()[0])
                with urlopen("http://127.0.0.1:"+str(debug)+"/json/list",timeout=1) as response: tabs=json.load(response)
                if tabs: break
            except (OSError,ValueError): time.sleep(.1)
        client=DevTools(next(t for t in tabs if t["type"]=="page")["webSocketDebuggerUrl"])
        client.call("Page.enable");client.call("Runtime.enable")
        client.call("Emulation.setDeviceMetricsOverride",dict(width=width,height=1000 if width>500 else 844,deviceScaleFactor=1,mobile=False))
        def evaluate(code): return client.evaluate(code)
        def check(name,code):
            for _ in range(40):
                value=evaluate(code)
                if value is True:
                    checks[name]=True;return
                time.sleep(.12)
            raise AssertionError(name+": "+str(value))
        def capture(name):
            evaluate("window.scrollTo(0,0)")
            image=client.call("Page.captureScreenshot",dict(format="png"))["data"]
            (shots/(name+"-"+str(width)+".png")).write_bytes(base64.b64decode(image))
        def click(text,scope="document"):
            evaluate("[..."+scope+".querySelectorAll('button')].find(b=>b.textContent==="+json.dumps(text)+").click()")
        def navigate(page):
            evaluate("closeDialog();location.hash="+json.dumps(page))
            check("navigate-"+page,"document.getElementById('crumb').textContent==="+json.dumps(dict(dashboard="Dashboard",crm="CRM",products="Products & quotations",campaigns="Campaigns",workflows="AI workflow",analytics="Analytics")[page]))
        client.call("Page.navigate",dict(url="http://127.0.0.1:"+str(service.server_port)+"/"))
        check("seeded-dashboard","typeof data!=='undefined'&&data?.products.length===4&&document.querySelectorAll('.metric').length===4")
        check("no-overflow-dashboard","document.documentElement.scrollWidth<=innerWidth")
        capture("dashboard")
        if width==390:
            click("Menu")
            check("mobile-menu-open","document.body.classList.contains('nav-open')")
            capture("navigation")
            evaluate("document.querySelector('a[data-page=crm]').click()")
            check("mobile-menu-closes","!document.body.classList.contains('nav-open')")
        else: navigate("crm")
        check("crm-visible","document.getElementById('crm-search')!==null")
        evaluate("document.getElementById('crm-search').value='no match';document.getElementById('crm-search').dispatchEvent(new Event('input'))")
        check("crm-empty-state","document.querySelector('.empty')?.textContent.includes('No records')")
        evaluate("document.getElementById('crm-search').value='';document.getElementById('crm-search').dispatchEvent(new Event('input'))")
        click("Add fictional customer")
        evaluate("(()=>{const f=document.querySelector('#dialog-content form');const values={company:'Acceptance Fictional Studio',contact:'Demo Visitor',email:'visitor@acceptance.example'};for(const[k,v]of Object.entries(values))f.elements[k].value=v;f.requestSubmit();})()")
        check("crm-create-persisted","data.customers.some(c=>c.company==='Acceptance Fictional Studio')")
        evaluate("customerDetail(data.customers.find(c=>c.company==='Acceptance Fictional Studio').id)")
        evaluate("(()=>{const f=document.querySelector('#dialog-content form');f.elements.stage.value='QUALIFIED';f.requestSubmit();})()")
        check("crm-timeline","data.activities.some(a=>a.message.includes('LEAD -> QUALIFIED'))")
        navigate("crm");capture("crm")
        navigate("products")
        click("Load sample CSV")
        check("csv-preview-loaded","document.getElementById('csv-preview').value.includes('EX-HALO-05')")
        evaluate("document.getElementById('csv-preview').closest('form').requestSubmit()")
        check("import-persisted","data.products.length===6&&data.campaigns.length===4")
        capture("products")
        evaluate("(()=>{const f=[...document.querySelectorAll('main form')].find(f=>f.elements.label);f.elements.label.value='Acceptance quotation';f.elements.product_id.value=data.products.find(p=>p.sku==='EX-HALO-05').id;f.elements.quantity.value='3';f.requestSubmit();})()")
        check("quotation-created","document.getElementById('detail').open&&document.getElementById('dialog-title').textContent==='Acceptance quotation'")
        check("decimal-total-rendered","document.getElementById('dialog-content').textContent.includes('$0.32')")
        evaluate("(()=>{const f=document.getElementById('quote-version-form');f.elements.quantity.value='5';f.elements.unit_price.value='0.20';f.requestSubmit();})()")
        check("new-version","data.quote_versions.filter(v=>v.quote_id===data.quotes.at(-1).id).length===2")
        click("Compare snapshots")
        check("version-comparison","document.getElementById('dialog-content').textContent.includes('unit_price')&&document.getElementById('dialog-content').textContent.includes('1.08')")
        click("Switch to Reviewer")
        check("reviewer-persona","session.role==='Reviewer'")
        click("Approve v2")
        check("quote-approved","data.quote_versions.at(-1).status==='APPROVED'")
        capture("quotation")
        click("Create campaign")
        check("campaign-quote-link","data.campaigns.at(-1).quote_version_id===data.quote_versions.at(-1).id")
        click("Run simulation")
        check("unapproved-blocked","document.getElementById('toast').textContent.includes('requires human approval')")
        click("Approve current revision")
        check("campaign-approved","data.campaigns.at(-1).status==='APPROVED'")
        const_before=evaluate("data.summary.delivered")
        click("Run simulation")
        check("campaign-simulated","data.campaigns.at(-1).status==='SIMULATED'&&data.summary.delivered>"+str(const_before))
        check("recipient-exclusion-evidence","document.getElementById('dialog-content').textContent.includes('UNSUBSCRIBED')&&document.getElementById('dialog-content').textContent.includes('DUPLICATE')")
        capture("campaign")
        click("View agent trace")
        check("workflow-completed","document.getElementById('dialog-content').textContent.includes('COMPLETED')&&document.querySelectorAll('.step').length===7")
        capture("workflow")
        navigate("workflows");check("workflow-table","document.querySelectorAll('main tbody tr').length>=4")
        # Create a failed import and confirm the agent error is a persisted record.
        navigate("products")
        evaluate("(()=>{const t=document.getElementById('csv-preview');t.value='sku,name,category,unit_price,currency\\nEX-INVALID,Invalid,Workspace,-2,USD';t.closest('form').requestSubmit();})()")
        check("error-trace-persisted","data.workflows.some(w=>w.status==='FAILED')")
        navigate("analytics");check("analytics-updated","document.querySelectorAll('.metric').length===4&&document.querySelectorAll('svg.chart').length===4")
        check("no-overflow-analytics","document.documentElement.scrollWidth<=innerWidth")
        capture("analytics")
        # Browser reload must retain data through the HttpOnly visitor cookie.
        client.call("Page.reload")
        check("reload-persistence","typeof data!=='undefined'&&data?.quotes.some(q=>q.label==='Acceptance quotation')")
        # Reset the current visitor and verify starter state returns.
        evaluate("window.confirm=()=>true;document.getElementById('reset').click()")
        check("reset-seeded-again","data.products.length===4&&data.customers.length===7")
        runtime=[e for e in client.events if e.get("method")=="Runtime.exceptionThrown"]
        if runtime: raise AssertionError("Browser runtime errors")
        return dict(viewport=width,passed=len(checks),checks=checks,runtime_errors=0,successful=True)
    finally:
        if client:
            try: client.call("Browser.close")
            except Exception: pass
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.terminate();process.wait(timeout=5)
        service.shutdown();service.server_close();thread.join()
        temporary.cleanup()
def main():
    report=dict(mode="Synthetic local simulation only",browser_checks=[])
    try:
        for width in (1440,390): report["browser_checks"].append(run(width))
        report["successful"]=True
    finally:
        folder=ROOT/"docs";folder.mkdir(exist_ok=True)
        (folder/"browser-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps({k:v for k,v in report.items() if k!="browser_checks"}))
        for item in report["browser_checks"]: print(item["viewport"],item["passed"])
if __name__=="__main__": main()
