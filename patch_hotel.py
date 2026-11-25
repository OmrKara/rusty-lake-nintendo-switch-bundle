import sys
import importlib.util,hashlib,json,struct,zlib,shutil
from pathlib import Path
spec=importlib.util.spec_from_file_location('p',str(Path(__file__).with_name('patch_paradise.py')));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
src=Path(sys.argv[1]).resolve();raw=src.read_bytes();assert hashlib.sha256(raw).hexdigest()=='018a166d0d7001e696ba49c5e50a0a6f63747f3925c1fac2479f3fdaf3b58074'
head,tags=p.read_swf(raw);out=[];changes=[]
for tag,payload in tags:
 if tag==82:
  off=payload.index(0,4)+1;a=p.ABC(payload[off:])
  for j,e in enumerate(a.multinames[1:],1):
   if e[0]==7 and a.strings[e[2]]=='File' and a.strings[a.namespaces[e[1]][1]]=='flash.filesystem':
    ob=a.qname('','Object');x,y=a.multiname_spans[j];v,w=a.multiname_spans[ob];a.edit(x,y,a.data[v:w],'AIR File type')
  main=next((x for x in a.instances if a.name(x['name'])=='Main'),None)
  if main:
   tr={a.name(t['name']):t for t in main['traits']};q=lambda n:p.u30(a.qname('',n));i=main['init']
   for name,value in [('itch',b'\x0b'),('trackingOn',b'\x0a')]:
    t=tr[name];v=t['value_kind_pos'];a.edit(v,v+1,value,name)
   t=tr['basePath'];a.edit(t['type_start'],t['type_end'],b'\0','basePath wildcard')
   old=b'\x60'+q('SaveGameClass')+b'\x60'+q('SaveGameClass')+b'\x46'+q('getOS')+b'\0\x46'+q('getBaseFile')+b'\1';a.replace_code(i,old,b'\x20','skip AIR file')
   old=b'\xd0\x66'+q('onMobile')+b'\x24\0\x14';new=b'\xd0\x66'+q('onMobile')+b'\x24\xff\x14'
   a.replace_code(i,old,new,'SharedObject load');a.replace_code(tr['saveToDisk']['method'],old,new,'SharedObject save')
  data,labels=a.apply_edits();changes+=labels;payload=payload[:off]+data
 out.append((tag,payload))
body=bytearray(head)
for tag,b in out:body+=struct.pack('<HI',(tag<<6)|63,len(b))+b if len(b)>=63 else struct.pack('<H',(tag<<6)|len(b))+b
patched=b'CWS'+raw[3:4]+struct.pack('<I',len(body)+8)+zlib.compress(body,9);p.read_swf(patched)
root=Path(sys.argv[2]).resolve();root.mkdir(parents=True,exist_ok=True);(root/'RustyLakeHotel.swf').write_bytes(patched);shutil.copy2(src.parent/'hotel-translations.xml',root)
print(json.dumps({'sha256':hashlib.sha256(patched).hexdigest(),'changes':changes},indent=2))
