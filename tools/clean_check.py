"""Copy only public files, install offline, test and probe restart/reseed behavior."""
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.public_scan import public_files
def main():
    private=ROOT/".local";private.mkdir(exist_ok=True)
    report=dict(installation=False,initialization=False,automated_tests=False,no_key_start=False,retained_database_restart=False,ephemeral_database_reseed=False,visitor_isolation=False)
    temporary=tempfile.TemporaryDirectory(prefix="clean-release-",dir=str(private))
    target=Path(temporary.name).resolve()
    target.relative_to(private.resolve())  # Cleanup is confined to this newly created directory.
    process=None
    env={k:v for k,v in os.environ.items() if k in ("PATH","SYSTEMROOT","WINDIR","COMSPEC","PATHEXT","TEMP","TMP")}
    env["PYTHONDONTWRITEBYTECODE"]="1"
    try:
        for name in public_files():
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
        def command(arguments):
            result=subprocess.run(arguments,cwd=str(target),env=env,capture_output=True,timeout=120)
            if result.returncode:
                (private/"clean-failure.log").write_bytes(result.stdout+result.stderr)
                raise RuntimeError("Clean-directory command failed; private diagnostic log retained")
            return result
        command([sys.executable,"-m","venv",str(target/".venv")])
        executable=target/".venv"/("Scripts/python.exe" if os.name=="nt" else "bin/python")
        command([str(executable),"-m","pip","install","--no-index","--disable-pip-version-check","-r","requirements.txt"]);report["installation"]=True
        command([str(executable),"-B","tools/seed_demo.py","--db",str(target/"var/inspection.sqlite3")]);report["initialization"]=True
        command([str(executable),"-B","-m","unittest","discover","-s","tests","-v"]);report["automated_tests"]=True
        sys.path.insert(0,str(target))
        from tests.test_app import Client
        def start(database,port=0):
            child=subprocess.Popen([str(executable),"-B","server.py","--port",str(port),"--db",str(database)],cwd=str(target),env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
            first=child.stdout.readline();second=child.stdout.readline().decode()
            if "Open http://127.0.0.1:" not in second: raise RuntimeError("Clean service did not start")
            number=int(second.strip().rsplit(":",1)[1])
            return child,"http://127.0.0.1:"+str(number),number
        database=target/"var/clean.sqlite3"
        process,base,port=start(database)
        with urlopen(base+"/health",timeout=5) as r: report["no_key_start"]=r.status==200
        a=Client(base);a.start();b=Client(base);b.start()
        ac=a.state()["customers"][0];bc=b.state()["customers"][0]
        report["visitor_isolation"]=ac["id"]!=bc["id"] and b.call("/api/customers/"+str(ac["id"])+"/stage",dict(stage="LEAD",expected_stage=ac["stage"]))[0]==404
        process.terminate();process.wait(timeout=10)
        process,base,port=start(database,port)
        report["retained_database_restart"]=a.state()["customers"][0]["id"]==ac["id"]
        process.terminate();process.wait(timeout=10)
        # A fresh path models lost ephemeral storage, without deleting the retained database.
        process,base,port=start(target/"var/ephemeral-new.sqlite3",port)
        expired=a.call("/api/state")[0]==401
        a.start()
        report["ephemeral_database_reseed"]=expired and len(a.state()["products"])==4
        report["successful"]=all(report.values())
        report["checked_at_utc"]=datetime.utcnow().isoformat()+"Z"
        report["scope"]="Offline clean copy + fresh virtual environment + localhost only. Hosting provider not deployed."
    finally:
        if process and process.poll() is None:
            process.terminate();process.wait(timeout=10)
        temporary.cleanup()
        (ROOT/"docs/clean-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(json.dumps(report,indent=2))
    if not report.get("successful"): raise SystemExit(1)
if __name__=="__main__": main()
