"""Conservative source/history release scan. Findings never echo private phrases."""
import argparse
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
IGNORED={".git",".local","var",".venv","venv","__pycache__","node_modules"}
EXTENSIONS={".py",".md",".html",".css",".js",".sql",".json",".yaml",".yml",".csv",".txt",".svg",".png",".pdf"}
EXACT={"LICENSE","Dockerfile",".gitignore",".gitattributes",".dockerignore",".env.example"}
PATTERNS=[
    ("private-key",re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("provider-token",re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{25,}|sk-[A-Za-z0-9]{25,}|AKIA[0-9A-Z]{16})")),
    ("credential-assignment",re.compile(r"""(?i)(?:api[_-]?key|password|access_token|refresh_token|client_secret)\s*[:=]\s*["']([A-Za-z0-9_./+=-]{16,})["']""")),
    ("local-user-path",re.compile(r"(?:[A-Za-z]:[\\/])(?:Users|home)[\\/][^\\/\s]+")),
]
def public_files(root=ROOT):
    root=Path(root)
    if (root/".git").is_dir():
        result=subprocess.run(["git","ls-files","-z"],cwd=str(root),capture_output=True)
        if result.returncode: raise RuntimeError("Cannot read repository file inventory")
        return sorted(n for n in result.stdout.decode().split("\0") if n)
    found=[]
    for folder,dirs,names in os.walk(root):
        dirs[:]=[d for d in dirs if d not in IGNORED]
        for name in names:
            p=Path(folder)/name
            if p.name in EXACT or p.suffix in EXTENSIONS:
                found.append(p.relative_to(root).as_posix())
    return sorted(found)
def textual(name,raw):
    if name.lower().endswith(".png"):
        if not raw.startswith(b"\x89PNG\r\n\x1a\n"): raise ValueError("Invalid PNG")
        position=8;parts=[]
        while position+12<=len(raw):
            size=struct.unpack(">I",raw[position:position+4])[0];kind=raw[position+4:position+8]
            if kind in (b"tEXt",b"iTXt",b"zTXt"): parts.append(raw[position+8:position+8+size])
            position+=12+size
        return b" ".join(parts).decode("utf-8",errors="replace")
    return raw.decode("utf-8",errors="replace")
def inspect(name,raw,denied):
    issues=[]
    p=Path(name)
    if any(part in IGNORED for part in p.parts) or p.name==".env" or p.suffix in (".db",".sqlite3",".pem",".key",".p12") or p.name.startswith("credentials"):
        issues.append(dict(file=name,rule="private-runtime-file"))
    if p.suffix not in EXTENSIONS and p.name not in EXACT:
        issues.append(dict(file=name,rule="unreviewed-file-type"))
    content=textual(name,raw)
    for label,pattern in PATTERNS:
        if pattern.search(content): issues.append(dict(file=name,rule=label))
    for phrase in denied:
        # Short organization abbreviations use word boundaries to avoid random substrings.
        matched=re.search(r"\b"+re.escape(phrase)+r"\b",content,re.I) if len(phrase)<5 else phrase.casefold() in content.casefold()
        if matched:
            issues.append(dict(file=name,rule="restricted-phrase"))
            break
    return issues
def license_inventory(files):
    unknown=set()
    for name in files:
        if not name.endswith(".py"): continue
        tree=ast.parse((ROOT/name).read_text(encoding="utf-8"))
        imports=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import): imports.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n,ast.ImportFrom) and n.level==0 and n.module: imports.add(n.module.split(".")[0])
        for module in imports:
            if module in {"operations","server","tools","tests"}: continue
            spec=importlib.util.find_spec(module)
            origin=spec.origin if spec else None
            if not spec or (origin and ("site-packages" in origin or "dist-packages" in origin)):
                unknown.add(module)
    requirements=(ROOT/"requirements.txt").read_text().splitlines()
    packages=[line for line in requirements if line.strip() and not line.lstrip().startswith("#")]
    return dict(third_party_application_dependencies=packages,unreviewed_imports=sorted(unknown),repository_license="MIT",runtime="Python license stack / SQLite public domain; external runtimes not vendored")
def scan(denied,history=False):
    files=public_files();findings=[]
    for name in files: findings.extend(inspect(name,(ROOT/name).read_bytes(),denied))
    inventory=license_inventory(files)
    if inventory["third_party_application_dependencies"] or inventory["unreviewed_imports"]:
        findings.append(dict(file="requirements.txt",rule="dependency-review-required"))
    commits=0;blobs=0
    if history:
        result=subprocess.run(["git","rev-list","--all"],cwd=str(ROOT),capture_output=True,text=True)
        if result.returncode: raise RuntimeError("Initialize and commit before scanning history")
        for commit in result.stdout.splitlines():
            commits+=1
            metadata=subprocess.check_output(["git","show","-s","--format=fuller",commit],cwd=str(ROOT))
            # Metadata has no file type; inspect text-only patterns.
            text=metadata.decode()
            if any(pattern.search(text) for _,pattern in PATTERNS) or any(p.casefold() in text.casefold() for p in denied):
                findings.append(dict(file="commit-metadata",rule="restricted-history-content"))
            entries=subprocess.check_output(["git","ls-tree","-r","--name-only",commit],cwd=str(ROOT),text=True).splitlines()
            for name in entries:
                raw=subprocess.check_output(["git","show",commit+":"+name],cwd=str(ROOT));blobs+=1
                findings.extend(inspect(name,raw,denied))
    return dict(successful=not findings,public_files=len(files),findings=findings,restricted_phrase_count=len(denied),history_checked=history,reachable_commits=commits,history_blob_checks=blobs,license_inventory=inventory,images="PNG text metadata scanned; original screenshots require visual review",scope="Content patterns and reachable Git history, not a guarantee of exhaustive secret or ownership detection")
def main():
    p=argparse.ArgumentParser();p.add_argument("--deny-file");p.add_argument("--history",action="store_true");p.add_argument("--output")
    args=p.parse_args()
    denied=Path(args.deny_file).read_text(encoding="utf-8").splitlines() if args.deny_file else []
    denied=[s.strip() for s in denied if s.strip()]
    report=scan(denied,args.history)
    default=ROOT/(".local/history-scan.json" if args.history else "docs/security-validation.json")
    output=Path(args.output) if args.output else default
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps(report,indent=2))
    return 0 if report["successful"] else 1
if __name__=="__main__": raise SystemExit(main())
