#!/usr/bin/env python3
"""Render the actual SVG using an available browser, then rasterize its PDF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def export(source, output, browser, dpi):
    import fitz
    raw=source.read_bytes()
    root=ET.fromstring(raw)
    if output.with_suffix('.pdf').exists() or output.with_suffix('.png').exists():
        raise ValueError('Choose a fresh export prefix; existing files are not overwritten')
    for element in root.iter():
        if element.tag.split('}')[-1] in {'script','foreignObject'}:
            raise ValueError('Active/foreign content is unsupported by this export path')
        for name,value in element.attrib.items():
            if name.split('}')[-1]=='href' and not value.startswith(('#','data:')):
                raise ValueError('Resolve external assets before export: '+value)
    css=raw.decode('utf-8-sig')
    if re.search(r'@import',css,re.I) or any(not value.strip().strip('\'"').startswith(('#','data:')) for value in re.findall(r'url\(([^)]*)\)',css,re.I)):
        raise ValueError('External CSS resources need a separate verified asset workflow')
    viewbox=[float(x) for x in root.attrib.get('viewBox','').replace(',',' ').split()]
    dimensions=[]
    for i,key in enumerate(['width','height']):
        value=root.attrib.get(key,'')
        match=re.fullmatch(r'([0-9.]+)(px|pt|mm|cm|in)?',value)
        if match:
            dimensions.append(float(match[1])*{None:1,'px':1,'pt':96/72,'mm':96/25.4,'cm':96/2.54,'in':96}[match[2]])
        elif len(viewbox)==4:
            dimensions.append(viewbox[i+2])
        else:
            raise ValueError('Explicit dimensions or a viewBox are required')
    if not all(1 <= n <= 20000 for n in dimensions):
        raise ValueError('Unsupported SVG dimensions')
    candidates=[browser] if browser else [shutil.which(name) for name in ['chromium','chromium-browser','google-chrome','msedge','chrome']]
    if os.name=='nt' and not browser:
        candidates += [r'C:\Program Files\Google\Chrome\Application\chrome.exe',r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe']
    executable=next((str(Path(p).resolve()) for p in candidates if p and Path(p).is_file()),None)
    if not executable:
        raise ValueError('No existing Chromium browser found. Use an available trusted SVG renderer; do not install silently.')
    output.parent.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix=output.name+'-render-',dir=output.parent))
    width,height=dimensions
    content=re.sub(r'^\s*<\?xml[^?]*\?>','',raw.decode('utf-8-sig'),count=1)
    html='<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; img-src data:; font-src data:">' + f'<style>@page{{size:{width}px {height}px;margin:0}}html,body{{margin:0;padding:0;width:{width}px;height:{height}px}}svg{{display:block;width:{width}px;height:{height}px}}*{{print-color-adjust:exact;-webkit-print-color-adjust:exact}}</style>'+content
    (work/'render.html').write_text(html,encoding='utf-8')
    command=[executable,'--headless','--disable-gpu','--disable-background-networking','--no-first-run','--no-default-browser-check','--disable-extensions','--no-pdf-header-footer','--user-data-dir='+str((work/'profile').resolve()),'--print-to-pdf='+str(output.with_suffix('.pdf').resolve()),(work/'render.html').resolve().as_uri()]
    warning=''
    with (work/'renderer.log').open('w',encoding='utf-8') as log:
        try:
            run=subprocess.run(command,stdout=log,stderr=log,timeout=45,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if run.returncode:
                warning='Browser exit code '+str(run.returncode)
        except subprocess.TimeoutExpired:
            warning='Browser process timed out after PDF request; exported file must pass reopen and visual checks'
    if not output.with_suffix('.pdf').is_file():
        raise ValueError('Browser export failed; inspect '+str(work/'renderer.log'))
    with fitz.open(output.with_suffix('.pdf')) as pdf:
        if len(pdf)!=1:
            raise ValueError('Expected one SVG page; got '+str(len(pdf)))
        page=pdf[0]
        page.get_pixmap(dpi=dpi,alpha=False).save(output.with_suffix('.png'))
        text=''.join(page.get_text().split())
        missing=[]
        for el in root.iter():
            if el.tag.split('}')[-1]=='text':
                label=''.join(''.join(el.itertext()).split())
                if label and label not in text:
                    missing.append({'id':el.attrib.get('id',''),'text':label})
        receipt={'status':'partial_export' if missing else 'rendered_needs_visual_review','runtime_warning':warning,'source_sha256':hashlib.sha256(raw).hexdigest(),'renderer':executable,'pymupdf_version':fitz.VersionBind,'dpi':dpi,'page_points':list(page.rect),'missing_pdf_text':missing,'pdf_fonts':page.get_fonts(),'work_directory':str(work),'artifacts':{ext:{'path':str(output.with_suffix('.'+ext)),'sha256':hashlib.sha256(output.with_suffix('.'+ext).read_bytes()).hexdigest()} for ext in ['pdf','png']}}
    output.with_suffix('.export.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'pdf':str(output.with_suffix('.pdf')),'png':str(output.with_suffix('.png'))}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('source',type=Path); p.add_argument('--out',type=Path,required=True); p.add_argument('--browser'); p.add_argument('--dpi',type=int,default=180)
    a=p.parse_args()
    try:
        if not 72<=a.dpi<=600:
            raise ValueError('dpi must be 72..600')
        export(a.source,a.out,a.browser,a.dpi)
    except (OSError,ValueError,ImportError,ET.ParseError,subprocess.TimeoutExpired) as error:
        print(json.dumps({'status':'failed','error':str(error)},ensure_ascii=False),file=sys.stderr); sys.exit(1)
