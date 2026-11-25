import sys
import importlib.util,hashlib,json,struct,zlib,shutil
from pathlib import Path
spec=importlib.util.spec_from_file_location('paradise',str(Path(__file__).with_name('patch_paradise.py')));p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
source=Path(sys.argv[1]).resolve();raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()=='0e988df0375a5ec39a65056d89cca404c9412c0727dca018ef19d8c52353f13e'
header,tags=p.read_swf(raw);new=[];changes=[]
for tag,payload in tags:
 if tag==82:
  off=payload.index(0,4)+1;a=p.ABC(payload[off:])
  for i,e in enumerate(a.multinames[1:],1):
   if e[0]==7 and a.strings[e[2]]=='File' and a.strings[a.namespaces[e[1]][1]]=='flash.filesystem':
    ob=a.qname('','Object');x,y=a.multiname_spans[i];v,w=a.multiname_spans[ob];a.edit(x,y,a.data[v:w],'AIR File type')
  main=next((x for x in a.instances if a.name(x['name'])=='Main'),None)
  if main:
   tr={a.name(t['name']):t for t in main['traits']};q=lambda n:p.u30(a.qname('',n));i=main['init']
   v=tr['steamOn']['value_kind_pos'];a.edit(v,v+1,b'\x0a','disable Steam')
   t=tr['basePath'];a.edit(t['type_start'],t['type_end'],b'\0','basePath wildcard')
   old=b'\x60'+q('SaveGameClass')+b'\x60'+q('SaveGameClass')+b'\x46'+q('getOS')+b'\0\x46'+q('getBaseFile')+b'\1'
   a.replace_code(i,old,b'\x20','skip AIR file')
   old=b'\xd0\x66'+q('onMobile')+b'\x24\0\x14'
   newcode=b'\xd0\x66'+q('onMobile')+b'\x24\xff\x14'
   a.replace_code(i,old,newcode,'use SharedObject load',branch_tail=b'\xf0'+p.u30(240)+b'\xd0\x60'+q('SaveGameClass'))
  data,labels=a.apply_edits();changes+=labels
  if main:
   # Extend the string pool with Flash's rightClick event name.
   cursor=4
   def num():
    global cursor
    v=0
    for shift in range(0,35,7):
     b=data[cursor];cursor+=1;v|=(b&127)<<shift
     if not b&128:return v
    raise ValueError('bad U30')
   for _ in range(2):
    count=num()
    for _ in range(max(0,count-1)):num()
   count=num();cursor+=max(0,count-1)*8
   countpos=cursor;count=num();endcount=cursor
   for _ in range(max(0,count-1)):
    n=num();cursor+=n
   right_index=count
   data=data[:countpos]+p.u30(count+1)+data[endcount:cursor]+p.u30(10)+b'rightClick'+data[cursor:]
   a=p.ABC(data);main=next(x for x in a.instances if a.name(x['name'])=='Main');i=main['init'];handler=a.methods.index('Main/$construct/onKeyDown');q=lambda n:p.u30(a.qname('',n))
   old=b'\xd0\x66'+q('onMobile')+b'\x24\x01\x14';newcode=b'\xd0\x66'+q('onMobile')+b'\x24\x00\x14'
   a.replace_code(i,old,newcode,'create Back handler',branch_tail=b'\xf0'+p.u30(273)+b'\x65\x01\x40'+p.u30(handler))
   start,end,typ=a.method_params[handler][0];assert a.name(typ)=='KeyboardEvent';a.edit(start,end,p.u30(a.qname('flash.events','MouseEvent')),'Back MouseEvent')
   old=b'\xd1\x66'+q('keyCode')+b'\x60'+p.u30(a.qname('flash.ui','Keyboard'))+b'\x66'+q('BACK');a.replace_code(handler,old,b'\x26\x26','Back right click')
   tr={a.name(t['name']):t for t in main['traits']};talk=a.methods.index('Main/talk_up')
   old=b'\xf0'+p.u30(649)+b'\xd0\x66'+p.u30(tr['runningLevel']['name'])+b'\x76'
   newguard=b'\xd0\x66'+p.u30(tr['screenNum']['name'])+b'\x24\x02\xab'
   a.replace_code(talk,old,newguard,'only inspect mouseDown in playable scene')
   data,labels2=a.apply_edits();changes+=labels2;a=p.ABC(data);i=next(x['init'] for x in a.instances if a.name(x['name'])=='Main');start,size=a.bodies[i];code=data[start:start+size];assert code[-1]==0x47 and data[start+size]==0
   listener=b'\x60'+p.u30(a.qname('','stage'))+b'\x2c'+p.u30(right_index)+b'\x65\x01\x6c\x09\x4f'+p.u30(a.qname('','addEventListener'))+b'\x02'
   lenstart=start-len(p.u30(size));assert data[lenstart:start]==p.u30(size)
   data=data[:lenstart]+p.u30(size+len(listener))+code[:-1]+listener+b'\x47'+data[start+size:];p.ABC(data);changes.append('register right click Back listener')
  payload=payload[:off]+data
 new.append((tag,payload))
new=p.preload_fonts(new);changes.append('preload embedded fonts')
out=bytearray(header)
for tag,payload in new:
 out+=struct.pack('<HI',(tag<<6)|63,len(payload))+payload if len(payload)>=63 else struct.pack('<H',(tag<<6)|len(payload))+payload
patched=b'CWS'+raw[3:4]+struct.pack('<I',len(out)+8)+zlib.compress(out,9)
h,t=p.read_swf(patched);assert h==header and len(t)>1000
root=Path(sys.argv[2]).resolve();root.mkdir(parents=True,exist_ok=True);(root/'RustyLakeRoots.swf').write_bytes(patched);shutil.copy2(source.parent/'roots-translations2.xml',root)
print(json.dumps({'sha256':hashlib.sha256(patched).hexdigest(),'changes':changes,'tags':len(t)},indent=2))
