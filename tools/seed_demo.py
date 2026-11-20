"""Initialize a disposable fictional workspace, without disclosing its token."""
import argparse
from contextlib import closing
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from operations import storage
from server import new_visit
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--db",default=str(ROOT/"var/seed-inspection.sqlite3"))
    args=parser.parse_args();storage.migrate(args.db)
    with closing(storage.connect(args.db)) as db,db:
        raw,actor=new_visit(db)
        count=db.execute("SELECT COUNT(*) FROM products WHERE tenant=?",(actor["id"],)).fetchone()[0]
        print("Fictional workspace initialized; products="+str(count)+". Visitor secret not printed.")
if __name__=="__main__": main()
