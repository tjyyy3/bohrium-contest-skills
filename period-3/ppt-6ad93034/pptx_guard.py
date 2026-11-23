"""Inspect and bound changes to editable PPTX packages. Python 3.10+ stdlib."""
import argparse
import hashlib
import json
import posixpath
from pathlib import Path
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_package(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP member names are ambiguous')
        return {name: archive.read(name) for name in names if not name.endswith('/')}


def inspect(path):
    parts = read_package(path)
    relations, issues, roots = [], [], {}
    for name, data in parts.items():
        if name.endswith(('.xml', '.rels')):
            try:
                root = ET.fromstring(data)
            except ET.ParseError as error:
                issues.append({'part': name, 'invalid_xml': str(error)})
                continue
            roots[name] = root
            shape_ids = [node.get('id') for node in root.iter('{'+NS['p']+'}cNvPr')]
            duplicates = sorted({value for value in shape_ids if shape_ids.count(value) > 1})
            if duplicates:
                issues.append({'part': name, 'duplicate_shape_ids': duplicates})
            if name.endswith('.rels'):
                owner = '' if name == '_rels/.rels' else posixpath.join(posixpath.dirname(posixpath.dirname(name)), posixpath.basename(name)[:-5])
                for rel in root:
                    external = rel.get('TargetMode') == 'External'
                    target = rel.get('Target', '')
                    resolved = target if external else posixpath.normpath(posixpath.join(posixpath.dirname(owner), target)).lstrip('/')
                    relations.append({'owner': owner, 'id': rel.get('Id'), 'type': rel.get('Type'), 'target': resolved, 'external': external})
                    if not external and resolved not in parts:
                        issues.append({'part': name, 'missing_target': resolved})
    relationship_ids = {(r['owner'], r['id']) for r in relations}
    reference_attributes = {'{'+NS['r']+'}'+key for key in ['id', 'embed', 'link']}
    for name, root in roots.items():
        for node in root.iter():
            for attribute, value in node.attrib.items():
                if attribute in reference_attributes and (name, value) not in relationship_ids:
                    issues.append({'part': name, 'unresolved_relationship_id': value})
    slides = []
    if 'ppt/presentation.xml' in roots:
        tree = roots['ppt/presentation.xml']
        for node in tree.findall('p:sldIdLst/p:sldId', NS):
            rid = node.get('{'+NS['r']+'}id')
            targets = [r['target'] for r in relations if r['owner'] == 'ppt/presentation.xml' and r['id'] == rid and not r['external'] and r['type'] == NS['r']+'/slide' and r['target'] in parts]
            if len(targets) != 1:
                issues.append({'part': 'ppt/presentation.xml', 'invalid_slide_relationship_id': rid})
            slides.append({'slide_id': node.get('id'), 'part': targets[0] if targets else '', 'relationship_id': rid})
    slide_shapes = {}
    for slide in slides:
        if slide['part'] not in roots:
            continue
        tree = roots[slide['part']]
        shape_rows = []
        for shape in tree.findall('.//p:spTree/*', NS):
            props = shape.find('.//p:cNvPr', NS)
            if props is not None:
                shape_rows.append({'id': props.get('id'), 'name': props.get('name'),
                                   'text_runs': [t.text or '' for t in shape.findall('.//a:t', NS)]})
        slide_shapes[slide['part']] = shape_rows
    return {'file': str(path), 'sha256': digest(Path(path).read_bytes()),
            'parts': {name: {'sha256': digest(data), 'bytes': len(data),
                             'referenced_by': [r['owner'] for r in relations if not r['external'] and r['target'] == name]}
                      for name, data in sorted(parts.items())},
            'slide_order': slides, 'slide_shapes': slide_shapes,
            'relationships': relations, 'issues': issues}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('inspect')
    command.add_argument('deck')
    command.add_argument('--out')
    for mode in ['diff', 'splice']:
        command = commands.add_parser(mode)
        command.add_argument('baseline')
        command.add_argument('edited')
        command.add_argument('plan')
        if mode == 'splice':
            command.add_argument('output')
        else:
            command.add_argument('--out')
    command = commands.add_parser('restore')
    command.add_argument('saved')
    command.add_argument('output')
    command.add_argument('expected_sha256')
    args = parser.parse_args()
    if args.command == 'inspect':
        result = inspect(args.deck)
        code = 1 if result['issues'] else 0
    elif args.command == 'restore':
        if Path(args.output).exists():
            parser.error('Rollback destination exists; choose a new path')
        if digest(Path(args.saved).read_bytes()) != args.expected_sha256:
            parser.error('Saved version does not match expected SHA256')
        shutil.copyfile(args.saved, args.output)
        result = {'restored': args.output, 'sha256': digest(Path(args.output).read_bytes())}
        code = 0 if result['sha256'] == args.expected_sha256 else 1
    else:
        plan = json.loads(Path(args.plan).read_text(encoding='utf-8-sig'))
        if digest(Path(args.baseline).read_bytes()) != plan['baseline_sha256']:
            parser.error('Baseline SHA256 differs from edit plan')
        entries = plan['allowed_parts']
        if not isinstance(entries, list) or any(not isinstance(x, dict) or not all(isinstance(x.get(k), str) and x[k].strip() for k in ['part', 'reason', 'source']) for x in entries):
            parser.error('Each allowed_parts item requires nonempty part, reason and source strings')
        allowed = {x['part'] for x in entries}
        before, after = read_package(args.baseline), read_package(args.edited)
        if args.command == 'splice':
            if Path(args.output).exists():
                parser.error('Output exists; choose a new version path')
            if before.keys() != after.keys() or not allowed <= before.keys():
                parser.error('Splice supports existing identical part inventories only; use a structural editor for added/deleted parts')
            candidate = {name: after[name] if name in allowed else data for name, data in before.items()}
            with zipfile.ZipFile(args.output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
                for name, data in candidate.items():
                    archive.writestr(name, data)
            result = inspect(args.output)
            code = 1 if result['issues'] else 0
        else:
            changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
            unexpected = sorted(set(changed) - allowed)
            final = inspect(args.edited)
            result = {'baseline_sha256': plan['baseline_sha256'], 'edited_sha256': final['sha256'],
                      'changed_parts': changed, 'unexpected_changes': unexpected,
                      'unused_allowances': sorted(allowed - set(changed)),
                      'added_parts': sorted(after.keys() - before.keys()), 'removed_parts': sorted(before.keys() - after.keys()),
                      'issues': final['issues'], 'passed': not unexpected and not final['issues'],
                      'scope': 'Package bytes and relationship existence only. Check source truth, edited shapes, workbook data and rendered pages separately.'}
            code = 0 if result['passed'] else 1
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if getattr(args, 'out', None):
        Path(args.out).write_text(output+'\n', encoding='utf-8')
    else:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    return code


if __name__ == '__main__':
    sys.exit(main())
