#!/usr/bin/env python3
"""Match ID-bearing SVG text to actual PDF spans and report bounding-box collisions."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def audit(svg, pdf):
    import fitz
    root=ET.parse(svg).getroot()
    with fitz.open(pdf) as document:
        if len(document)!=1:
            raise ValueError('Text audit expects a one-page diagram')
        page=document[0]
        spans=[s for b in page.get_text('dict')['blocks'] if 'lines' in b for line in b['lines'] for s in line['spans'] if s['text'].strip()]
        labels,unmapped,ambiguous=[],[],[]
        for el in root.iter('{http://www.w3.org/2000/svg}text'):
            if 'id' not in el.attrib:
                continue
            parts=[el.text or '']+[child.text or '' for child in el if child.tag=='{http://www.w3.org/2000/svg}tspan']
            parts=[''.join(p.split()) for p in parts if p.strip()]
            boxes=[]
            for part in parts:
                found=[s['bbox'] for s in spans if ''.join(s['text'].split())==part]
                if not found:
                    unmapped.append(el.attrib['id'])
                elif len(found)!=1:
                    ambiguous.append(el.attrib['id'])
                else:
                    boxes.append(found[0])
            if boxes and len(boxes)==len(parts):
                labels.append({'id':el.attrib['id'],'boxes':boxes})
        collisions=[]
        for i,a in enumerate(labels):
            for b in labels[i+1:]:
                for ra in a['boxes']:
                    for rb in b['boxes']:
                        overlap=fitz.Rect(ra)&fitz.Rect(rb)
                        if overlap.width>0.5 and overlap.height>0.5:
                            collisions.append({'ids':[a['id'],b['id']],'overlap_pdf_points':list(overlap)})
        outside=[label['id'] for label in labels if any(not page.rect.contains(fitz.Rect(box)) for box in label['boxes'])]
        return {'status':'collision_found' if collisions or outside else 'needs_mapping_review' if unmapped or ambiguous else 'no_collisions_among_mapped_labels',
                'mapped_labels':labels,'collisions':collisions,'outside_page':outside,'unmapped_ids':sorted(set(unmapped)),'ambiguous_ids':sorted(set(ambiguous)),
                'scope':'Only SVG text elements carrying IDs, matched to unique exact PDF text spans. Anonymous/ambiguous labels and overlaps with graphics still need visual inspection.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('svg',type=Path); p.add_argument('pdf',type=Path); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); report=audit(a.svg,a.pdf); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':report['status'],'collisions':len(report['collisions'])}))
