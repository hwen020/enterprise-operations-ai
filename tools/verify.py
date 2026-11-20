"""Run isolated regression and publish only sanitized summary evidence."""
from contextlib import redirect_stderr
from datetime import datetime
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
def main():
    private=ROOT/".local";private.mkdir(exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    with (private/"tests.log").open("w",encoding="utf-8") as log,redirect_stderr(log):
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    report=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),successful=result.wasSuccessful(),python=sys.version.split()[0],scope="Temporary SQLite and localhost HTTP only; no secret or external connector",checked_at_utc=datetime.utcnow().isoformat()+"Z")
    docs=ROOT/"docs";docs.mkdir(exist_ok=True)
    (docs/"test-validation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if result.wasSuccessful() else 1
if __name__=="__main__": raise SystemExit(main())
