#!/usr/bin/env python3
"""Inspect and narrowly patch UTF-8 SVG without reserializing unrelated XML."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from xml.parsers import expat
from xml.sax.saxutils import escape

SVG = 'http://www.w3.org/2000/svg'
ATTRS = {'x','y','dx','dy','x1','y1','x2','y2','cx','cy','r','rx','ry',
         'width','height','d','points','transform','fill','stroke','stroke-width',
         'font-size','font-weight','text-anchor','opacity'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def index_svg(raw):
    raw.decode('utf-8-sig')
    parser = expat.ParserCreate(namespace_separator='|')
    stack, indexed, all_nodes = [], {}, []
    def start(name, attrs):
        offset = parser.CurrentByteIndex
        match = re.match(rb'<(?:[^>\'"]|"[^"]*"|\'[^\']*\')*>', raw[offset:])
        if match is None:
            raise ValueError('Cannot locate XML opening tag')
        if not stack and name != SVG+'|svg':
            raise ValueError('Expected a namespaced SVG root')
        node = {'name':name, 'attrs':attrs, 'start':offset,
                'open_end':offset+match.end(), 'children':0, 'text':''}
        if stack:
            stack[-1]['children'] += 1
        if 'id' in attrs:
            if attrs['id'] in indexed:
                raise ValueError('Duplicate SVG ID: '+attrs['id'])
            indexed[attrs['id']] = node
        stack.append(node)
        all_nodes.append(node)
    def end(name):
        node = stack.pop()
        node['content_end'] = parser.CurrentByteIndex
        if raw[node['open_end']-2:node['open_end']] == b'/>':
            node['end'] = node['open_end']
        else:
            node['end'] = raw.index(b'>', parser.CurrentByteIndex)+1
    def text(value):
        if stack:
            stack[-1]['text'] += value
    def reject_doctype(*args):
        raise ValueError('DTD is unsupported; retain source and use a trusted native editor')
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = reject_doctype
    parser.Parse(raw, True)
    return indexed, all_nodes


def apply(source, patch_path, output):
    if source.resolve() == output.resolve():
        raise ValueError('Write a new SVG; the original must remain available')
    if output.exists() or output.with_suffix('.edit.json').exists():
        raise ValueError('Output already exists; choose a fresh version name')
    raw, patch = source.read_bytes(), read_json(patch_path)
    if patch['source_sha256'] != digest(raw):
        raise ValueError('Source SHA256 does not match this patch')
    request = patch['request']
    request_path = (patch_path.parent/request['path']).resolve()
    request_raw = request_path.read_bytes()
    if request['sha256'] != digest(request_raw) or not request['locator'] or not request['quote'] or request['quote'] not in request_raw.decode('utf-8-sig'):
        raise ValueError('Edit request hash or quote does not resolve')
    indexed, nodes = index_svg(raw)
    replacements, touched = [], set()
    for change in patch['changes']:
        key = (change['id'], change['field'])
        if key in touched:
            raise ValueError('Repeated patch field: '+str(key))
        touched.add(key)
        node = indexed[change['id']]
        if not node['name'].startswith(SVG+'|') or node['name'].split('|')[-1] in {'metadata','desc','title','script','style','defs'}:
            raise ValueError('Target is not an editable diagram element: '+change['id'])
        if not isinstance(change['after'], str):
            raise ValueError('All replacement values must be strings')
        if change['field'] == 'text':
            if node['name'].split('|')[-1] not in {'text','tspan'} or node['children'] or b'<' in raw[node['open_end']:node['content_end']]:
                raise ValueError('Text edits require a plain leaf text/tspan; select the individual span')
            before, start, end = node['text'], node['open_end'], node['content_end']
            replacement = escape(change['after']).encode('utf-8')
        else:
            attr = change['field']
            if attr not in ATTRS:
                raise ValueError('Not an allowed presentation attribute: '+attr)
            before = node['attrs'][attr]
            match = re.search(rb'(?<![\w:.-])'+re.escape(attr.encode())+rb'\s*=\s*([\'"])(.*?)\1', raw[node['start']:node['open_end']], re.S)
            if match is None:
                raise ValueError('Attribute has no direct editable lexical value: '+attr)
            start, end = node['start']+match.start(2), node['start']+match.end(2)
            replacement = escape(change['after'], {'"':'&quot;', "'":'&apos;'}).encode('utf-8')
        if before != change['before']:
            raise ValueError('Before-value mismatch: '+str(key))
        if before == change['after']:
            raise ValueError('No-op edit: '+str(key))
        replacements.append({'start':start,'end':end,'old':raw[start:end].decode('utf-8'),
                             'new':replacement.decode('utf-8'), **change})
    if not replacements:
        raise ValueError('No edits requested')
    replacements.sort(key=lambda c:c['start'])
    if any(a['end'] > b['start'] for a,b in zip(replacements,replacements[1:])):
        raise ValueError('Overlapping edits')
    revised, cursor, delta = bytearray(), 0, 0
    for edit in replacements:
        revised.extend(raw[cursor:edit['start']])
        revised.extend(edit['new'].encode('utf-8'))
        edit['output_start'] = edit['start']+delta
        edit['output_end'] = edit['output_start']+len(edit['new'].encode('utf-8'))
        delta += len(edit['new'].encode('utf-8'))-(edit['end']-edit['start'])
        cursor = edit['end']
    revised.extend(raw[cursor:])
    revised = bytes(revised)
    after_ids, after_nodes = index_svg(revised)
    if list(indexed) != list(after_ids) or len(nodes) != len(after_nodes):
        raise ValueError('Element identities or structure changed')
    before_semantics = [(n['name'], n['attrs'], n['text']) for n in nodes]
    expected_semantics = [(name, dict(attrs), text) for name,attrs,text in before_semantics]
    positions = {id(n):i for i,n in enumerate(nodes)}
    for change in patch['changes']:
        i = positions[id(indexed[change['id']])]
        name, attrs, text = expected_semantics[i]
        if change['field']=='text':
            text=change['after']
        else:
            attrs[change['field']]=change['after']
        expected_semantics[i]=(name,attrs,text)
    if expected_semantics != [(n['name'], n['attrs'], n['text']) for n in after_nodes]:
        raise ValueError('Unexpected XML semantic change')
    evidence = []
    for item in patch.get('evidence_files', []):
        path = (patch_path.parent/item['path']).resolve()
        if digest(path.read_bytes()) != item['sha256']:
            raise ValueError('Evidence file changed: '+item['path'])
        evidence.append(item)
    protected = [key for key,node in indexed.items() if not any(node['start'] <= e['start'] < node['end'] for e in replacements)]
    for key in protected:
        a,b=indexed[key],after_ids[key]
        if raw[a['start']:a['end']] != revised[b['start']:b['end']]:
            raise ValueError('Untargeted subtree changed: '+key)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(revised)
    receipt={'status':'edited_needs_render_and_review','source_path':str(source),'source_sha256':digest(raw),
             'output_path':str(output),'output_sha256':digest(revised),'patch_sha256':digest(patch_path.read_bytes()),
             'request':request,'evidence_files':evidence,'changes':replacements,'protected_subtree_ids':protected,
             'untargeted_bytes':'Identical outside the listed replacement spans','id_count':len(indexed),
             'limits':'Preservation proves edit scope, not scientific validity or geometry/port alignment.'}
    save_json(output.with_suffix('.edit.json'),receipt)
    print(json.dumps({'status':receipt['status'],'changed_fields':len(replacements),'protected_subtrees':len(protected)}))


def verify(source, revised, receipt_path):
    raw, after, receipt=source.read_bytes(),revised.read_bytes(),read_json(receipt_path)
    if digest(raw)!=receipt['source_sha256'] or digest(after)!=receipt['output_sha256']:
        raise ValueError('Source or revision does not match the edit receipt')
    restored=after
    for edit in reversed(receipt['changes']):
        start,end=edit['output_start'],edit['output_end']
        if restored[start:end] != edit['new'].encode('utf-8'):
            raise ValueError('Changed span mismatch')
        restored=restored[:start]+edit['old'].encode('utf-8')+restored[end:]
    if restored != raw:
        raise ValueError('Changes extend beyond the authorized replacement spans')
    print(json.dumps({'status':'verified_exact_inverse','source_sha256':digest(raw),'output_sha256':digest(after)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    inspect=sub.add_parser('inspect'); inspect.add_argument('source',type=Path); inspect.add_argument('--out',type=Path,required=True)
    edit=sub.add_parser('apply'); edit.add_argument('source',type=Path); edit.add_argument('patch',type=Path); edit.add_argument('--out',type=Path,required=True)
    check=sub.add_parser('verify'); check.add_argument('source',type=Path); check.add_argument('revised',type=Path); check.add_argument('receipt',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='inspect':
            raw=args.source.read_bytes(); indexed,_=index_svg(raw)
            args.out.parent.mkdir(parents=True,exist_ok=True)
            save_json(args.out,{'source_sha256':digest(raw),'elements':[{k:v for k,v in node.items() if k in {'name','attrs','children','text'}} for node in indexed.values()]})
            print(json.dumps({'status':'indexed','ids':len(indexed)}))
        elif args.command=='apply':
            apply(args.source,args.patch,args.out)
        else:
            verify(args.source,args.revised,args.receipt)
    except (OSError,ValueError,KeyError,TypeError,expat.ExpatError) as error:
        print(json.dumps({'status':'failed','error':str(error)},ensure_ascii=False),file=sys.stderr)
        sys.exit(1)
