"""Audit exact XML text edits, nested chart workbooks and unchanged slide objects."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys
import zipfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
from pptx_guard import NS, digest, inspect, read_package

NS = dict(NS, c='http://schemas.openxmlformats.org/drawingml/2006/chart',
          s='http://schemas.openxmlformats.org/spreadsheetml/2006/main')
SHAPE_TAGS = {NS['p']+'}'+name for name in ['sp', 'grpSp', 'graphicFrame', 'pic', 'cxnSp']}


def structure(node):
    return (node.tag, sorted(node.attrib.items()),
            node.text if node.text and (node.text.strip() or node.tag in {'{'+NS['a']+'}t','{'+NS['s']+'}t'}) else '',
            [structure(child) for child in node])


def shapes(root):
    return {props.get('id'): node for node in root.iter()
            if node.tag.lstrip('{') in SHAPE_TAGS
            and (props := node.find('.//p:cNvPr', NS)) is not None}


def inventory(path):
    result = inspect(path)
    parts = read_package(path)
    result['object_inventory'], result['chart_bindings'] = {}, []
    for slide in result['slide_order']:
        if not slide['part'] or slide['part'] not in parts:
            continue
        try:
            root = ET.fromstring(parts[slide['part']])
        except ET.ParseError:
            continue
        objects = []
        for shape_id, shape in shapes(root).items():
            props = shape.find('.//p:cNvPr', NS)
            objects.append({'shape_id': shape_id, 'name': props.get('name'),
                            'type': shape.tag.split('}')[-1],
                            'text_nodes': [node.text or '' for node in shape.findall('.//a:t', NS)],
                            'structure_sha256': digest(json.dumps(structure(shape), ensure_ascii=False).encode('utf-8'))})
            if shape.tag == '{'+NS['p']+'}graphicFrame':
                for chart in shape.findall('.//c:chart', NS):
                    rid = chart.get('{'+NS['r']+'}id')
                    matches = [r for r in result['relationships'] if r['owner'] == slide['part'] and r['id'] == rid]
                    binding = {'slide_id': slide['slide_id'], 'slide_part': slide['part'], 'shape_id': shape_id, 'relationship_id': rid}
                    if len(matches) != 1 or matches[0]['external'] or matches[0]['type'] != NS['r']+'/chart':
                        result['issues'].append(dict(binding, error='invalid_chart_binding'))
                    else:
                        binding['chart_part'] = matches[0]['target']
                        result['chart_bindings'].append(binding)
        result['object_inventory'][slide['part']] = objects
    return result


def verify(baseline, edited, plan):
    before, after = read_package(baseline), read_package(edited)
    original, final = inventory(baseline), inventory(edited)
    issues = list(final['issues'])
    if original['issues']:
        issues.append({'error': 'invalid_baseline', 'details': original['issues']})
    if original['sha256'] != plan.get('baseline_sha256'):
        issues.append({'error': 'baseline_hash_mismatch'})
    allowed = plan.get('allowed_parts')
    atoms = plan.get('xml_edits')
    if not isinstance(allowed, list) or any(not isinstance(p, dict) or not all(isinstance(p.get(k), str) and p[k].strip() for k in ['part','source','reason']) for p in allowed):
        raise ValueError('allowed_parts requires part, source and reason strings')
    if not isinstance(atoms, list) or not atoms:
        raise ValueError('xml_edits requires a nonempty list of exact text-node changes')
    groups = {}
    for atom in atoms:
        if not isinstance(atom, dict) or not all(isinstance(atom.get(k), str) for k in ['part','selector','old','new','source']) or not atom['source'].strip():
            raise ValueError('Each xml_edits entry requires string part, selector, old, new and nonempty source')
        if atom['old'] == atom['new']:
            raise ValueError('Each declared edit must change the old text to a different new text')
        if 'shape_id' in atom and not isinstance(atom['shape_id'], str):
            raise ValueError('shape_id must be the string ID from the inventory')
        if 'member' in atom and not isinstance(atom['member'], str):
            raise ValueError('member must name a nested XML member')
        if 'node_index' in atom and (type(atom['node_index']) is not int or atom['node_index'] < 0):
            raise ValueError('node_index must be a nonnegative integer')
        groups.setdefault((atom['part'], atom.get('member')), []).append(atom)
    changed = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    unexpected = sorted(set(changed) - {p['part'] for p in allowed})
    if unexpected:
        issues.append({'error': 'unapproved_parts', 'parts': unexpected})
    if original['slide_order'] != final['slide_order']:
        issues.append({'error': 'slide_order_or_identity_changed'})
    if original['chart_bindings'] != final['chart_bindings']:
        issues.append({'error': 'chart_bindings_changed', 'before': original['chart_bindings'], 'after': final['chart_bindings']})
    checked = []
    for part in sorted(set(changed) | {part for part, member in groups}):
        if part not in before or part not in after:
            issues.append({'part': part, 'error': 'added_or_removed_part_unsupported'})
            continue
        if part.endswith('.xlsx'):
            with zipfile.ZipFile(BytesIO(before[part])) as z:
                old_members = {n:z.read(n) for n in z.namelist()}
            with zipfile.ZipFile(BytesIO(after[part])) as z:
                new_members = {n:z.read(n) for n in z.namelist()}
        else:
            old_members, new_members = {None: before[part]}, {None: after[part]}
        for member in sorted(old_members.keys() | new_members.keys(), key=str):
            edits = groups.get((part, member), [])
            if old_members.get(member) == new_members.get(member) and not edits:
                continue
            location = {'part': part, 'member': member}
            if member not in old_members or member not in new_members:
                issues.append(dict(location, error='added_or_removed_nested_member'))
                continue
            if not edits:
                issues.append(dict(location, error='changed_without_xml_scope'))
                continue
            try:
                expected = ET.fromstring(old_members[member])
                actual = ET.fromstring(new_members[member])
            except ET.ParseError as error:
                issues.append(dict(location, error='invalid_scoped_xml', detail=str(error)))
                continue
            seen = set()
            for edit in edits:
                target = expected
                if 'shape_id' in edit:
                    target = shapes(expected).get(edit['shape_id'])
                    if target is None:
                        issues.append(dict(location, shape_id=edit['shape_id'], error='shape_not_found'))
                        continue
                nodes = target.findall(edit['selector'], NS)
                index = edit.get('node_index', 0)
                if ('node_index' not in edit and len(nodes) != 1) or index >= len(nodes):
                    issues.append(dict(location, shape_id=edit.get('shape_id'), error='ambiguous_or_missing_node', selector=edit['selector'], matches=len(nodes)))
                    continue
                node = nodes[index]
                if id(node) in seen:
                    issues.append(dict(location, error='duplicate_edit_target', selector=edit['selector']))
                    continue
                seen.add(id(node))
                if (node.text or '') != edit['old']:
                    issues.append(dict(location, shape_id=edit.get('shape_id'), error='old_text_mismatch', actual=node.text, expected=edit['old']))
                    continue
                node.text = edit['new']
            if structure(expected) != structure(actual):
                expected_shapes, actual_shapes = shapes(expected), shapes(actual)
                drift = [sid for sid in expected_shapes.keys() | actual_shapes.keys()
                         if sid not in expected_shapes or sid not in actual_shapes or structure(expected_shapes[sid]) != structure(actual_shapes[sid])]
                issues.append(dict(location, error='out_of_scope_or_missing_edit', shape_ids=sorted(drift)))
            checked.append(dict(location, exact_text_edits=len(edits)))
        absent = [member for p, member in groups if p == part and member not in old_members]
        if absent:
            issues.append({'part':part,'error':'scoped_member_not_found','members':absent})
    return {'passed': not issues, 'baseline_sha256': original['sha256'], 'edited_sha256': final['sha256'],
            'changed_parts': changed, 'checked_xml': checked, 'issues': issues,
            'chart_bindings_before': original['chart_bindings'], 'chart_bindings_after': final['chart_bindings'],
            'scope': 'Exact planned XML text changes, all remaining XML structure, chart binding identity and package bytes. Source truth, chart/workbook numerical agreement and visual quality require separate checks.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('inspect')
    p.add_argument('deck')
    p.add_argument('--out')
    p = subs.add_parser('verify')
    p.add_argument('baseline')
    p.add_argument('edited')
    p.add_argument('plan')
    p.add_argument('--out')
    args = parser.parse_args()
    try:
        result = inventory(args.deck) if args.command == 'inspect' else verify(args.baseline, args.edited, json.loads(Path(args.plan).read_text(encoding='utf-8-sig')))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile, SyntaxError) as error:
        result = {'passed':False, 'issues':[{'error':'invalid_input', 'detail':str(error)}]}
    if args.out:
        Path(args.out).write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    else:
        print(json.dumps(result,indent=2,ensure_ascii=True))
    return 1 if result.get('issues') else 0


if __name__ == '__main__':
    sys.exit(main())
