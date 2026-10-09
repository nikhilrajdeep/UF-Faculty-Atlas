"""UF graduate faculty catalog ingestion; only verified fields, no guesses."""
import json,re,hashlib
from pathlib import Path
from datetime import datetime,timezone
import requests
from bs4 import BeautifulSoup

SOURCE='https://gradcatalog.ufl.edu/graduate/faculty/'
OUTPUT=Path('public/data/faculty.json')

ORG_SOURCE='https://gradcatalog.ufl.edu/graduate/colleges-departments/'
def normal_unit(value):
 value=clean(value).lower().replace('&','and')
 value=re.sub(r'^(department of|school of)\s+','',value)
 value=re.sub(r'\s+(department|dept\.?|school)\Z','',value)
 return clean(re.sub(r'[^a-z0-9]+',' ',value))

def get_college_map(session):
 """Parse each h2 college heading and its following academic-unit list."""
 response=session.get(ORG_SOURCE,timeout=60)
 response.raise_for_status()
 soup=BeautifulSoup(response.text,'lxml')
 root=soup.select_one('#content') or soup.select_one('main') or soup
 mapping={}
 for h in root.find_all('h2'):
  heading=clean(h.get_text(' ',strip=True))
  if not (heading.startswith('College of ') or heading.startswith('Warrington College ') or heading.startswith('Herbert Wertheim College ')):
   continue
  for elem in h.next_elements:
   if getattr(elem,'name',None)=='h2':break
   if getattr(elem,'name',None)!='li':continue
   a=elem.find('a')
   if not a:continue
   key=normal_unit(a.get_text(' ',strip=True))
   if key:mapping.setdefault(key,set()).add(heading)
 return {k:next(iter(v)) for k,v in mapping.items() if len(v)==1}

SWES_DIRECTORY='https://soils.ifas.ufl.edu/people/faculty/'
SWES_COLLEGE='College of Agricultural and Life Sciences'
SWES_DEPARTMENT='Soil, Water, and Ecosystem Sciences'
def merge_swes_profiles(session,records):
 """Official department pages supplement the graduate roster, not replace it."""
 from urllib.parse import urljoin,urlparse
 from time import sleep
 try:
  r=session.get(SWES_DIRECTORY,timeout=30);r.raise_for_status()
  soup=BeautifulSoup(r.text,'lxml')
 except requests.RequestException as e:
  print('SWES directory unavailable; retaining existing data:',e)
  return
 links=set()
 for a in soup.select('a[href]'):
  url=urljoin(SWES_DIRECTORY,a['href']).split('#')[0].split('?')[0]
  parsed=urlparse(url)
  if parsed.netloc=='soils.ifas.ufl.edu' and re.fullmatch(r'/people/faculty/[^/]+/',parsed.path):
   links.add(url)
 # Known official SWES profile guarantees this important directory has a seed entry.
 links.add('https://soils.ifas.ufl.edu/people/faculty/ebrahim-babaeian/')
 def by_name(name):
  n=normal_unit(name)
  tokens=n.split()
  if len(tokens)>1 and ',' in name:
   left,right=name.split(',',1);n=normal_unit(right+' '+left)
  return n
 lookup={by_name(f['name']):f for f in records}
 for url in sorted(links):
  try:
   response=session.get(url,timeout=25);response.raise_for_status()
   doc=BeautifulSoup(response.text,'lxml')
   header=doc.find('h1')
   if not header:continue
   name=clean(header.get_text(' ',strip=True))
   key=by_name(name)
   if not key or len(key.split())<2:continue
   record=lookup.get(key)
   if record is None:
    ident=hashlib.sha1(normal_unit(name).encode()).hexdigest()[:12]
    record={'id':ident,'name':name,'title':'','department':SWES_DEPARTMENT,'college':SWES_COLLEGE,'research_areas':[],'teaching':[],'lab_name':'','lab_url':'','current_students':[],'email':'','google_scholar':'','profile_url':'','tags':[],'sources':[]}
    records.append(record)
    lookup[key]=record
   record['department']=SWES_DEPARTMENT
   record['college']=SWES_COLLEGE
   record['profile_url']=url
   record['sources']=list(dict.fromkeys(record.get('sources',[])+[url]))
   mail=doc.select_one('a[href^="mailto:"]')
   if mail and not record.get('email'):
    address=mail.get('href','')[7:].split('?')[0]
    if '@' in address:record['email']=address
   sleep(0.15)
  except requests.RequestException as e:
   print('Skipping SWES profile',url, str(e)[:100])
 print('SWES profiles checked:',len(links))

def clean(s):return re.sub(r'\s+',' ',s or '').strip()
def parse(html):
 soup=BeautifulSoup(html,'lxml')
 main=soup.select_one('#content') or soup.select_one('main') or soup
 for t in main.select('script,style,nav,footer,aside'):t.decompose()
 lines=[clean(s) for s in main.get_text('\n',strip=True).splitlines()]
 lines=[s for s in lines if s]
 rank=re.compile(r'^(?:(?:Distinguished|Assistant|Associate|Research|Clinical|Courtesy|Adjunct|Affiliate|Emeritus|Visiting|Full|Senior|Master)\s+)*(?:Professor|Lecturer|Scientist|Instructor|Curator|Scholar|Researcher|Engineer|Librarian)(?:\b.*)?$',re.I)
 records={}
 for i,name in enumerate(lines[:-2]):
  if ',' not in name or not 4<=len(name)<=100 or re.search(r'\d|https?://',name):continue
  candidates=lines[i+1:i+5]
  pos=next((j for j,t in enumerate(candidates) if len(t)<80 and rank.match(t)),None)
  if pos is None:continue
  title=candidates[pos]
  dept=''
  if pos+1<len(candidates):
   possible=candidates[pos+1]
   if len(possible)<120 and not rank.match(possible) and ',' not in possible:dept=possible
  key=re.sub('[^a-z0-9]','',name.lower())
  id=hashlib.sha1(key.encode()).hexdigest()[:12]
  records[id]={'id':id,'name':name,'title':title,'department':dept,'college':'','research_areas':[],'teaching':[],'lab_name':'','lab_url':'','current_students':[],'email':'','google_scholar':'','profile_url':'','tags':[],'sources':[SOURCE]}
 return list(records.values())
def main():
 r=requests.get(SOURCE,timeout=60,headers={'User-Agent':'UF-Faculty-Atlas/0.1 (public graduate faculty indexing)'})
 r.raise_for_status()
 result=parse(r.text)
 session=requests.Session()
 college_map=get_college_map(session)
 if len(result)<100:raise RuntimeError('Only '+str(len(result))+' faculty parsed. Catalog may have changed. Refusing to overwrite database.')
 old={}
 if OUTPUT.exists():
  try:old={f['id']:f for f in json.loads(OUTPUT.read_text())['faculty']}
  except (KeyError,ValueError):pass
 for f in result:
  f['college']=college_map.get(normal_unit(f.get('department','')),'')
  earlier=old.get(f['id'],{})
  for k in ['college','research_areas','teaching','lab_name','lab_url','current_students','email','google_scholar','profile_url','tags']:
   if earlier.get(k):f[k]=earlier[k]
  if earlier.get('sources'):f['sources']=list(dict.fromkeys(f['sources']+earlier['sources']))
 merge_swes_profiles(session,result)
 result.sort(key=lambda f:f['name'].casefold())
 OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 OUTPUT.write_text(json.dumps({'metadata':{'updated_at':datetime.now(timezone.utc).isoformat(),'total':len(result),'source':SOURCE,'coverage_note':'Graduate faculty catalog, not all UF faculty. Enrichment fields require separate verification.'},'faculty':result},indent=2,ensure_ascii=False)+'\n')
 print('Imported',len(result),'graduate faculty candidates; college mapped:',sum(bool(f['college']) for f in result))
if __name__=='__main__':main()
