"""Incremental, audited official UF faculty discovery. Never claim full coverage."""
import json,re,hashlib,requests,time,os
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup

ROOT='https://gradcatalog.ufl.edu/graduate/colleges-departments/'
ROSTER='https://gradcatalog.ufl.edu/graduate/faculty/'
COLLEGES=['College of Agricultural and Life Sciences','College of the Arts','Warrington College of Business','College of Dentistry','College of Design, Construction and Planning','College of Education','Herbert Wertheim College of Engineering','College of Health and Human Performance','College of Journalism and Communications','Levin College of Law','College of Liberal Arts and Sciences','College of Medicine','College of Nursing','College of Pharmacy','College of Public Health and Health Professions','College of Veterinary Medicine']
SPECIAL={'Soil, Water, and Ecosystem Sciences':['https://soils.ifas.ufl.edu/people/faculty/','https://soils.ifas.ufl.edu/people/faculty/ebrahim-babaeian/'],'Levin College of Law faculty':['https://www.law.ufl.edu/faculty']}
OUT=Path('public/data/faculty.json'); REPORT=Path('public/data/coverage.json'); STATE=Path('data/crawl_state.json')
BUDGET=int(os.getenv('ATLAS_PAGE_BUDGET','125'))
def read(p,default):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return default
def normal(s):return re.sub(r'[^a-z0-9]+',' ',str(s or '').lower().replace('&','and')).strip()
def clean(s):return ' '.join(str(s or '').split())
def good(url):
 p=urlparse(url);return p.scheme=='https' and bool(p.hostname) and (p.hostname=='ufl.edu' or p.hostname.endswith('.ufl.edu'))
def uid(s):return hashlib.sha1(s.encode()).hexdigest()[:12]
S=requests.Session();S.headers['User-Agent']='UF-Faculty-Atlas/1.0 (public academic directory research)'
errors=[]
def fetch(url):
 if not good(url):return None
 try:
  r=S.get(url,timeout=25);r.raise_for_status()
  if 'html' not in r.headers.get('Content-Type','text/html'):return None
  time.sleep(.35)
  return BeautifulSoup(r.text,'lxml')
 except requests.RequestException as e:errors.append({'url':url,'error':str(e)[:200]});return None
def inventory():
 doc=fetch(ROOT)
 if not doc:raise RuntimeError('Official UF unit listing unavailable: preserve existing faculty data')
 body=doc.select_one('#content') or doc.select_one('main') or doc
 college=None;units=[];seen=set()
 for el in body.find_all(['h2','li']):
  if el.name=='h2':
   college=next((c for c in COLLEGES if normal(c)==normal(el.get_text(' ',strip=True))),None)
  elif college:
   a=el.find('a',href=True)
   if not a:continue
   name=clean(a.get_text(' ',strip=True));url=urljoin(ROOT,a['href'])
   if not name or not good(url) or (college,name) in seen:continue
   seen.add((college,name));units.append({'id':uid(college+'|'+name),'college':college,'name':name,'source_url':url})
 units.append({'id':'law-faculty','college':'Levin College of Law','name':'Levin College of Law faculty','source_url':'https://www.law.ufl.edu/faculty'})
 if not any(u['name']=='Soil, Water, and Ecosystem Sciences' for u in units):units.append({'id':'swes','college':COLLEGES[0],'name':'Soil, Water, and Ecosystem Sciences','source_url':SPECIAL['Soil, Water, and Ecosystem Sciences'][0]})
 return units
def links(doc,url):
 body=doc.select_one('main') or doc.select_one('#content') or doc
 found=[]
 for a in body.select('a[href]'):
  dest=urljoin(url,a['href']).split('?')[0].split('#')[0]
  if not good(dest) or dest==url:continue
  if re.search(r'/faculty/|/people/|/directory/|/personnel/|/profiles/',urlparse(dest).path,re.I):found.append(dest)
 return list(dict.fromkeys(found))[:100]
def person(doc,url):
 body=doc.select_one('main') or doc.select_one('#content') or doc
 h=body.find('h1')
 if not h:return None
 name=clean(h.get_text(' ',strip=True))
 if not re.fullmatch(r'[A-Z][A-Za-zÀ-ÿ.\x27 -]+(?:, [A-Za-zÀ-ÿ.\x27 -]+)?',name) or len(name.split())<2 or len(name)>85:return None
 visible=clean(body.get_text(' ',strip=True))[:25000]
 if not re.search(r'\bprofessor\b|\blecturer\b|\bresearch scientist\b|\binstructor\b',visible[:1800],re.I) and not re.search(r'/faculty/[^/]+/',url):return None
 email='';scholar='';lab='';labname=''
 for a in body.select('a[href]'):
  href=urljoin(url,a['href']);label=clean(a.get_text(' ',strip=True))
  if href.startswith('mailto:') and not email:email=href[7:].split('?')[0]
  if 'scholar.google.' in href and not scholar:scholar=href
  if re.search(r'\blab(oratory)?\b',label,re.I) and good(href) and not lab:lab=href;labname=label
 topics=['remote sensing','gis','geospatial','artificial intelligence','machine learning','precision agriculture','soil physics','soil moisture','hydrology','wetland','climate','data science','sustainability']
 return {'name':name,'email':email,'google_scholar':scholar,'lab_url':lab,'lab_name':labname,'research_areas':[t for t in topics if t in visible.lower()],'profile_url':url}
def main():
 existing=read(OUT,{'faculty':[]});faculty=existing.get('faculty',[])
 if len(faculty)<100:raise RuntimeError('Existing graduate roster unavailable, refusing to replace it')
 state=read(STATE,{'visited':[],'pending':{}});visited=set(state['visited']);pending=state['pending']
 units=inventory();mapdept={}
 for u in units:mapdept.setdefault(normal(u['name']),set()).add(u['college'])
 for f in faculty:
  c=mapdept.get(normal(f.get('department','')),set())
  if len(c)==1 and not f.get('college'):f['college']=next(iter(c))
 # Confirmed against the official department profile, not inferred by name similarity.
 for f in faculty:
  if normal(f.get('name'))=='babaeian ebrahim' or normal(f.get('name'))=='ebrahim babaeian':
   f['college']='College of Agricultural and Life Sciences'
   f['department']='Soil, Water, and Ecosystem Sciences'
   f['profile_url']='https://soils.ifas.ufl.edu/people/faculty/ebrahim-babaeian/'
   f['sources']=list(dict.fromkeys(f.get('sources',[])+[f['profile_url']]))
   f['affiliations']=[{'college':f['college'],'department':f['department']}]
 # Remove a demonstrated false-positive entry where the scraper treated a department as a person.
 faculty=[f for f in faculty if not (normal(f.get('name'))=='soil water and ecosystem sciences' and not f.get('profile_url'))]
 byurl={f.get('profile_url'):f for f in faculty if f.get('profile_url')}
 remaining=BUDGET;statuses=[]
 for u in units:
  urls=list(dict.fromkeys(SPECIAL.get(u['name'],[])+pending.get(u['id'],[])+[u['source_url']]))
  found=0;done=0;nextqueue=[];failure=False
  for url in urls[:65]:
   if url in visited:continue
   if remaining<=0:nextqueue.append(url);continue
   remaining-=1;doc=fetch(url)
   if not doc:failure=True;nextqueue.append(url);continue
   visited.add(url)
   new=links(doc,url)
   found+=len(new)
   nextqueue.extend(x for x in new if x not in visited)
   p=person(doc,url)
   if p:
    rec=byurl.get(url)
    if rec is None:
     rec={'id':uid(url),'name':p['name'],'title':'','college':u['college'],'department':u['name'],'research_areas':[],'teaching':[],'current_students':[],'lab_name':'','lab_url':'','email':'','google_scholar':'','profile_url':url,'sources':[]}
     faculty.append(rec);byurl[url]=rec
    rec['college']=rec.get('college') or u['college']
    rec['department']=rec.get('department') or u['name']
    rec.setdefault('affiliations',[])
    affiliation={'college':u['college'],'department':u['name']}
    if affiliation not in rec['affiliations']:rec['affiliations'].append(affiliation)
    for field in ['email','google_scholar','lab_url','lab_name']:
     if p[field] and not rec.get(field):rec[field]=p[field]
    rec['research_areas']=list(dict.fromkeys(rec.get('research_areas',[])+p['research_areas']))
    rec['sources']=list(dict.fromkeys(rec.get('sources',[])+[url]))
    rec['verified_at']=datetime.now(timezone.utc).isoformat();done+=1
  pending[u['id']]=list(dict.fromkeys(nextqueue))[:180]
  statuses.append({**u,'profiles_found_this_run':found,'profiles_enriched_this_run':done,'remaining_urls':len(pending[u['id']]),'status':'not_checked' if remaining==BUDGET else ('partial' if pending[u['id']] or failure else 'visited_not_verified_complete')})
 now=datetime.now(timezone.utc).isoformat()
 colleges=[{'name':c,'departments_identified':sum(u['college']==c for u in units),'departments_with_pending':sum(u['college']==c and len(pending.get(u['id'],[]))>0 for u in units),'faculty_records':sum(f.get('college')==c for f in faculty),'status':'partial_not_verified'} for c in COLLEGES]
 OUT.parent.mkdir(parents=True,exist_ok=True);STATE.parent.mkdir(parents=True,exist_ok=True)
 OUT.write_text(json.dumps({'metadata':{'updated_at':now,'total':len(faculty),'source':ROSTER,'coverage_note':'INCOMPLETE: graduate faculty roster plus incremental official department pages; each faculty and field requires verification.'},'faculty':sorted(faculty,key=lambda f:f.get('name','').lower())},indent=2))
 REPORT.write_text(json.dumps({'updated_at':now,'coverage_status':'incomplete','colleges':colleges,'departments':statuses,'pages_visited':len(visited),'errors':errors[:100]},indent=2))
 STATE.write_text(json.dumps({'visited':sorted(visited),'pending':pending},indent=2))
 print('Indexed faculty:',len(faculty),'Colleges:',len(colleges),'Units:',len(units),'Pages visited total:',len(visited),'Pending:',sum(map(len,pending.values())))
if __name__=='__main__':main()
