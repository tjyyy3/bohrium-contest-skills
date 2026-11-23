#!/usr/bin/env python3
"""Audit named SVG ports and directed M/L or polyline connectors against a source table."""
import argparse
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET

NUMBER=r'[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?'


def check(svg, table):
    root=ET.parse(svg).getroot()
    ids={}
    parents={child:parent for parent in root.iter() for child in parent}
    for element in root.iter():
        if 'id' in element.attrib:
            if element.attrib['id'] in ids:
                raise ValueError('Duplicate SVG ID')
            ids[element.attrib['id']]=element
    def translate(element, point):
        point=list(point)
        while element is not None:
            transform=element.attrib.get('transform','').strip()
            if transform:
                match=re.fullmatch(r'translate\(\s*('+NUMBER+r')(?:[\s,]+('+NUMBER+r'))?\s*\)',transform)
                if not match:
                    raise ValueError('Unsupported transform: '+transform)
                point[0]+=float(match[1]); point[1]+=float(match[2] or 0)
            element=parents.get(element)
        return point
    errors, verified=[],[]
    for connection in table['connections']:
        try:
            edge=ids[connection['id']]
            ports=[ids[connection[key]] for key in ['from_svg','to_svg']]
            positions=[]
            for port in ports:
                if port.tag.split('}')[-1]!='circle':
                    raise ValueError('Port must be an explicit circle with cx/cy for this checker')
                positions.append(translate(port,[float(port.attrib['cx']),float(port.attrib['cy'])]))
            if edge.tag.split('}')[-1]=='path':
                value=edge.attrib['d']
                tokens=re.findall(r'[A-Za-z]|'+NUMBER,value)
                if re.sub(r'[\s,]','',value) != ''.join(tokens) or len(tokens)%3 or len(tokens)<6:
                    raise ValueError('Use absolute M/L path syntax for this checker')
                points=[]
                for i in range(0,len(tokens),3):
                    if tokens[i] != ('M' if i==0 else 'L'):
                        raise ValueError('Unsupported path command: '+tokens[i])
                    points.append(translate(edge,[float(tokens[i+1]),float(tokens[i+2])]))
            elif edge.tag.split('}')[-1]=='polyline':
                values=[float(x) for x in re.findall(NUMBER,edge.attrib['points'])]
                if len(values)<4 or len(values)%2:
                    raise ValueError('Bad polyline')
                points=[translate(edge,values[i:i+2]) for i in range(0,len(values),2)]
            else:
                raise ValueError('Unsupported connector geometry')
            for attr,key in [('data-from-port','from_svg'),('data-to-port','to_svg'),('data-type','type')]:
                if attr in edge.attrib and edge.attrib[attr]!=connection[key]:
                    raise ValueError('Semantic mismatch '+attr)
            if math.dist(points[0],positions[0])>0.01 or math.dist(points[-1],positions[1])>0.01:
                raise ValueError('Wrong source/destination port geometry; actual '+str([points[0],points[-1]])+' expected '+str(positions))
            if math.dist(points[-2],points[-1])<0.01:
                raise ValueError('Zero-length destination segment')
            verified.append({'id':connection['id'],'from':connection['from'],'to':connection['to'],'type':connection['type'],'locator':connection['locator'],'from_point':points[0],'to_point':points[-1],'final_direction':[points[-1][i]-points[-2][i] for i in range(2)]})
        except (KeyError,ValueError) as error:
            errors.append({'connection':connection.get('id',''),'error':str(error)})
    return {'status':'failed' if errors else 'passed','errors':errors,'verified':verified,'scope':'Explicit circle ports, absolute M/L or polyline connectors, translation transforms. Arrow glyph shape and all source interpretations still require visual/source review.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('svg',type=Path); p.add_argument('connections',type=Path); p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); report=check(a.svg,json.loads(a.connections.read_text(encoding='utf-8-sig'))); a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'status':report['status'],'connections_checked':len(report['verified']),'errors':len(report['errors'])})); raise SystemExit(1 if report['errors'] else 0)
