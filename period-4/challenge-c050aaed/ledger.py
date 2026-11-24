"""Build and query an anchored reading ledger. Python 3.9+, local files only."""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import sys
from pathlib import Path
from datetime import datetime, timezone

from extract import extract, sha

VERSION = "1.0"


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False)


def save(path, obj):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+"\n",encoding="utf-8")
    tmp.replace(path)


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def key(value):
    return hashlib.sha256(dump(value).encode()).hexdigest()[:20]


def filter_date(raw):
    match=re.match(r"(?:D:)?(\d{4})-?(\d{2})-?(\d{2})",raw or "")
    return "-".join(match.groups()) if match else ""


def inspect(root, out):
    files, folders, contents, events = {}, [], {}, []
    def on_error(err):
        events.append({"path":os.path.relpath(err.filename, root),"status":"unreadable_directory",
                       "detail":str(err),"recovery":"request authorized access or an export, then rebuild"})
    for directory, names, entries in os.walk(root,onerror=on_error,followlinks=False):
        d = Path(directory)
        folders.append(d.relative_to(root).as_posix())
        names.sort()
        for name in list(names):
            if (d/name).is_symlink():
                entries.append(name)
                names.remove(name)
        for name in sorted(entries):
            path = d/name
            rel = path.relative_to(root).as_posix()
            row = files[rel] = {"path":rel,"extension":path.suffix.lower(),"parent":path.parent.relative_to(root).as_posix()}
            if path.is_symlink():
                row.update(status="skipped_symlink",target=os.readlink(path))
                events.append({"path":rel,"status":row["status"],"recovery":"verify target and authorization before including it"})
                continue
            try:
                s = path.stat()
                if not stat.S_ISREG(s.st_mode):
                    raise ValueError("not a regular file")
                digest = sha(path)
                row.update(sha256=digest,bytes=s.st_size,mode=stat.filemode(s.st_mode),read="successful",
                           modified_utc=datetime.fromtimestamp(s.st_mtime,timezone.utc).isoformat())
                if digest in contents:
                    row.update(status="identical_bytes",canonical=contents[digest]["source"])
                    events.append({"path":rel,"status":"identical_bytes","canonical":row["canonical"],"effect":"retained both paths"})
                    continue
                content=contents[digest]={"source":rel,"units":[],"annotations":[],"status":"pending"}
                units, annotations, issues=extract(path)
                for n, a in enumerate(annotations):
                    a["id"]="ann-"+key([digest,a["locator"],a["kind"],a["start"],a["end"],n])
                content.update(units=units,annotations=annotations,status="needs_review" if issues else "indexed")
                row["status"]=content["status"]
                if issues:
                    events.extend({"path":rel,"status":"needs_review","detail":i,"recovery":"inspect the cited original and retain a review receipt"} for i in issues)
            except Exception as exc:
                status="unreadable" if isinstance(exc,PermissionError) else "unsupported" if str(exc).startswith("unsupported format") else "extraction_failed"
                row.update(status=status,error=f"{type(exc).__name__}: {exc}")
                if row.get("sha256") in contents:
                    contents[row["sha256"]]["status"]=status
                events.append({"path":rel,"status":status,"detail":row["error"],"recovery":"obtain authorized readable source/export or run an installed reader; keep unresolved until checked"})
    state={"version":VERSION,"adapter_sha256":sha(Path(__file__).with_name("extract.py")),
           "ledger_sha256":sha(Path(__file__)),"directories":folders,"files":files,"contents":contents,"events":events}
    save(out/"sources.json",state)
    return state


class Unresolved(ValueError):
    pass


def anchor(state, ref):
    path, quote = ref.get("source"), ref.get("quote")
    file = state["files"].get(path,{})
    if not file.get("sha256") or not isinstance(quote,str) or not quote.strip():
        raise Unresolved(f"missing readable source or exact quote: {path}")
    digest = file["sha256"]
    if ref.get("sha256",digest)!=digest:
        raise Unresolved(f"source bytes changed: {path}; recheck previous version")
    matches=[]
    for u in state["contents"][digest]["units"]:
        if ref.get("locator",u["locator"])!=u["locator"]:
            continue
        if not ref.get("locator") and "/annotation:" in u["locator"]:
            continue  # native selection duplicates the body text; address it by its own locator
        text=u["text"]
        pos=text.find(quote)
        while pos>=0:
            end=pos+len(quote)
            if (("start" not in ref or ref["start"]==pos) and text[:pos].endswith(ref.get("prefix",""))
                    and text[end:].startswith(ref.get("suffix",""))):
                matches.append({"source":path,"sha256":digest,"locator":u["locator"],"quote":quote,"start":pos,"end":end,
                                **{k:u[k] for k in ("page","bbox","quads","html_id") if k in u}})
            pos=text.find(quote,pos+1)
    if len(matches)!=1:
        raise Unresolved(f"{len(matches)} exact matches for {quote!r} in {path}; inspect source, locator, context or changed wording")
    return matches[0]


def compile_ledger(state, plan):
    notes, edges, versions, issues, transfers = {}, [], {}, [], []
    anns = {}
    for digest, content in state["contents"].items():
        for a in content["annotations"]:
            anns[a["id"]]=(digest,a)
            if not a["quote"]:
                continue
            ev = anchor(state,{"source":content["source"],"quote":a["quote"],"locator":a["locator"],"start":a["start"]})
            notes[a["id"]]={"id":a["id"],"kind":"native:"+a["kind"],"claim":a.get("comment") or a["quote"],
                            "attribution":"reader annotation" if a.get("comment") else "verbatim selection",
                            "evidence":[ev],"annotation_ids":[a["id"]],"tags":[],"entities":[],"date":a.get("date","")}
    def refs(item):
        if not isinstance(item.get("evidence"),list) or not item["evidence"]:
            raise Unresolved("requires at least one source selector")
        return [anchor(state,r) for r in item["evidence"]]
    def exists(path):
        if not state["files"].get(path,{}).get("sha256"):
            raise Unresolved(f"missing readable file {path}")
        return state["files"][path]["sha256"]
    def problem(stage, item, exc):
        issues.append({"stage":stage,"id":item.get("id",""),"status":"unresolved","reason":str(exc),
                       "input":item,"recovery":"inspect evidence, correct plan, rerun build; never transfer an unchecked claim"})
    for item in plan.get("notes",[]):
        try:
            ident=item["id"]
            if not ident or ident in notes or not item.get("claim","").strip() or not item.get("kind"):
                raise Unresolved("duplicate ID or missing note claim/kind")
            evidence=refs(item)
            for aid in item.get("annotation_ids",[]):
                if aid not in anns:
                    raise Unresolved(f"unknown native annotation {aid}")
                digest,a=anns[aid]
                if not any(e["sha256"]==digest and e["locator"]==a["locator"] and
                           (e["start"]<a["end"] and a["start"]<e["end"]) for e in evidence):
                    raise Unresolved(f"no overlapping anchor for {aid}")
            notes[ident]={**item,"evidence":evidence}
        except (Unresolved,KeyError) as exc:
            problem("note",item,exc)
    for item in plan.get("versions",[]):
        try:
            a,b=exists(item["from"]),exists(item["to"])
            if a==b or item["id"] in versions or item.get("kind") not in {"revision","administrative","translation","edition"}:
                raise Unresolved("requires different bytes, unique ID and explicit version relation type")
            versions[item["id"]]={**item,"from_sha256":a,"to_sha256":b,"evidence":refs(item)}
        except (Unresolved,KeyError) as exc:
            problem("version",item,exc)
    for item in plan.get("transfers",[]):
        try:
            v=versions[item["version"]]
            old=anchor(state,item["old"])
            if old["sha256"]!=v["from_sha256"]:
                raise Unresolved("old anchor does not belong to declared predecessor")
            # Original locator/offset/adjacent context may have moved. Re-evaluate uniqueness on target.
            newref={"source":v["to"],"quote":old["quote"],**item.get("new",{})}
            new=anchor(state,newref)
            if new["sha256"]!=v["to_sha256"]:
                raise Unresolved("new anchor does not belong to declared successor")
            status="verbatim_relocated" if old["quote"]==new["quote"] else "wording_changed"
            transfers.append({"id":item["id"],"version":v["id"],"status":status,"old":old,"new":new,
                              "meaning_review":item.get("meaning_review","pending; reread both contexts")})
        except (Unresolved,KeyError) as exc:
            problem("transfer",item,exc)
    for item in plan.get("links",[]):
        try:
            x,y=item["from"],item["to"]
            if x==y or any(z not in notes for z in (x,y)) or not item.get("reason","").strip() or not item.get("kind"):
                raise Unresolved("requires two accepted notes, a relation and a specific explanation")
            evidence=refs(item)
            for endpoint in (x,y):
                if not any(a["sha256"]==b["sha256"] and a["locator"]==b["locator"] and a["start"]<b["end"] and b["start"]<a["end"]
                           for a in notes[endpoint]["evidence"] for b in evidence):
                    raise Unresolved(f"link evidence does not overlap the supporting passages of {endpoint}")
            edges.append({**item,"evidence":evidence})
        except (Unresolved,KeyError) as exc:
            problem("link",item,exc)
    return {"notes":list(notes.values()),"versions":list(versions.values()),"transfers":transfers,"links":edges,"issues":issues}


def database(out,state,compiled):
    tmp=out/"index.building.sqlite"
    with sqlite3.connect(tmp) as db:
        db.execute("DROP TABLE IF EXISTS entries")
        db.execute("CREATE TABLE entries(id,kind,source,digest,locator,body,tags,entities,date,evidence)")
        for digest,c in state["contents"].items():
            for u in c["units"]:
                e={"source":c["source"],"sha256":digest,**{k:v for k,v in u.items() if k!="text"}}
                if u["text"].strip():
                    db.execute("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (f"pass-{key([digest,u['locator']])}","passage",c["source"],digest,u["locator"],u["text"],"[]","[]","",dump([e])))
        for n in compiled["notes"]:
            e=n["evidence"][0]
            db.execute("INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (n["id"],n["kind"],e["source"],e["sha256"],e["locator"],n["claim"],dump(n.get("tags",[])),
                     dump(n.get("entities",[])),n.get("date",""),dump(n["evidence"])))
        db.execute("CREATE INDEX entry_source ON entries(digest,kind)")
    db.close()
    tmp.replace(out/"index.sqlite")


def search(args):
    state=load(args.out/"sources.json")
    source=state["files"].get(args.source,{}) if args.source else {}
    terms=[s.casefold() for s in args.terms]
    hits=[]
    with sqlite3.connect((args.out/"index.sqlite").resolve().as_uri()+"?mode=ro",uri=True) as db:
        db.row_factory=sqlite3.Row
        for row in db.execute("SELECT * FROM entries"):
            e,tags,entities=map(json.loads,(row["evidence"],row["tags"],row["entities"]))
            if args.source and not any(x["sha256"]==source.get("sha256") for x in e):
                continue
            if args.notes_only and row["kind"]=="passage" or args.tag and args.tag not in tags or args.entity and args.entity not in entities:
                continue
            date=filter_date(row["date"])
            if (args.since and (not date or date<args.since)) or (args.until and (not date or date>args.until)):
                continue
            text=" ".join([row["body"],*tags,*entities,*[x.get("quote","") for x in e]]).casefold()
            if not all(t in text for t in terms):
                continue
            score=(row["kind"]!="passage",sum(t in row["body"].casefold() for t in terms))
            snippet=row["body"]
            if len(snippet)>480:
                pos=max(0,snippet.casefold().find(terms[0])-70) if terms else 0
                snippet=snippet[pos:pos+480]
            hits.append((score,{"id":row["id"],"kind":row["kind"],"text":snippet,"tags":tags,"entities":entities,"evidence":e}))
    hits.sort(key=lambda hit:(-int(hit[0][0]),-hit[0][1],hit[1]["id"]))
    return {"terms":args.terms,"source":args.source,"tag":args.tag,"entity":args.entity,"since":args.since,"until":args.until,
            "notes_only":args.notes_only,"total":len(hits),"hits":[h for _,h in hits[:args.limit]]}


def restore(args):
    root,dest=args.input.resolve(),args.dest.resolve()
    if root==dest or root in dest.parents or dest in root.parents:
        raise ValueError("use a separate, disjoint recovery directory")
    state=load(args.out/"sources.json")
    rows=[]
    for item in load(args.plan).get("copies",[]):
        row={"request":item}
        try:
            path=item["source"]
            digest=state["files"][path]["sha256"]
            if item["sha256"]!=digest or not item.get("reason") or not item.get("evidence"):
                raise Unresolved("requires correct inventoried digest, authorization reason and cited evidence")
            row["evidence"]=[anchor(state,r) for r in item["evidence"]]
            for e in row["evidence"]:
                authority=(root/e["source"]).resolve()
                if root not in authority.parents or sha(authority)!=e["sha256"]:
                    raise Unresolved("authorization evidence changed; rebuild and review")
            src=(root/path).resolve()
            dst=(dest/item["destination"]).resolve()
            if root not in src.parents or dest not in dst.parents or sha(src)!=digest:
                raise Unresolved("path escapes selected directory or source content changed")
            row.update(source_sha256=digest,destination=item["destination"])
            if dst.exists():
                old=sha(dst)
                row["before_sha256"]=old
                if old!=digest:
                    raise Unresolved("destination contains different bytes; select permitted alternative or resolve conflict")
                row["status"]="already_verified"
            else:
                dst.parent.mkdir(parents=True,exist_ok=True)
                with src.open("rb") as r,dst.open("xb") as w:
                    shutil.copyfileobj(r,w)
                row["status"]="copied"
            row["after_sha256"]=sha(dst)
            if row["after_sha256"]!=digest:
                raise Unresolved("copy integrity failed; inspect source and destination")
        except (KeyError,ValueError,OSError,TypeError) as exc:
            row.update(status="unresolved",reason=str(exc),recovery="verify source, authority, destination and read/write access; preserve existing bytes")
        rows.append(row)
    save(args.receipt,{"operations":rows})
    return {"operations":len(rows),"resolved":sum(r["status"] in {"copied","already_verified"} for r in rows)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    build=sub.add_parser("build")
    build.add_argument("--input",required=True,type=Path)
    build.add_argument("--out",required=True,type=Path)
    build.add_argument("--plan",type=Path)
    recovery=sub.add_parser("restore")
    for opt in ("input","out","dest","plan","receipt"):
        recovery.add_argument("--"+opt,required=True,type=Path)
    query=sub.add_parser("find")
    query.add_argument("--out",required=True,type=Path)
    query.add_argument("terms",nargs="*")
    for option in ("source","tag","entity","since","until"):
        query.add_argument("--"+option,default="")
    query.add_argument("--notes-only",action="store_true")
    query.add_argument("--limit",type=int,default=12)
    query.add_argument("--receipt",type=Path)
    args=ap.parse_args()
    if args.command=="restore":
        print(dump(restore(args)))
        return
    if args.command=="find":
        if args.limit<1:
            ap.error("limit must be positive")
        result=search(args)
        if args.receipt:
            save(args.receipt,result)
        print(dump(result))
        return
    root,out=args.input.resolve(),args.out.resolve()
    if not root.is_dir() or out==root or root in out.parents:
        ap.error("input must be an existing directory and output must be outside that tree")
    out.mkdir(parents=True,exist_ok=True)
    state=inspect(root,out)
    plan=load(args.plan) if args.plan else {}
    compiled=compile_ledger(state,plan)
    save(out/"knowledge.json",compiled)
    database(out,state,compiled)
    counts={"paths":len(state["files"]),"distinct_bytes":len(state["contents"]),
            "native_annotations":sum(len(c["annotations"]) for c in state["contents"].values()),
            **{k:len(v) for k,v in compiled.items()}}
    receipt={"tool_version":VERSION,"counts":counts,"plan_sha256":sha(args.plan) if args.plan else None,
             "source_events":len(state["events"]),"outputs":{n:sha(out/n) for n in ("sources.json","knowledge.json","index.sqlite")}}
    save(out/"build.json",receipt)
    print(dump(receipt))


if __name__=="__main__":
    main()
