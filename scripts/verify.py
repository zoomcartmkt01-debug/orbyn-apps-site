"""Validate policy wording and site requirements with Python standard library."""
import argparse, json, re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://apps.lchnetmarketing.com'
POLICIES = {
 'watt-to-amp/terms/index.html': ('watt-to-amp/TERMS-EN.md', '[DATE OF PUBLICATION]', '21 October 2026'),
 'site-measure-check/terms/index.html': ('app-003/TERMS-EN.md', '[DATE OF PUBLICATION]', '21 October 2026'),
 'steel-weight/terms/index.html': ('steel-weight/TERMS-EN.md', '[DATE OF PUBLICATION]', '21 October 2026'),
 'watt-to-amp/privacy/index.html': ('watt-to-amp/PRIVACY-POLICY-EN.md', '[DATE OF PUBLICATION]', '21 October 2026'),
 'stcw-tracker/privacy/index.html': ('stcw-tracker/PRIVACY-POLICY-EN.md', '[DATE OF PUBLICATION]', '20 October 2026'),
 'stcw-tracker/terms/index.html': ('stcw-tracker/TERMS-EN.md', '[DATE OF PUBLICATION]', '20 October 2026'),
 'site-measure-check/privacy/index.html': ('app-003/APP-003-Privacy-Policy-EN-Draft.md', '[DD Month YYYY]', '19 October 2026'),
}
PAGES = ['index.html', 'stcw-tracker/index.html', 'watt-to-amp/index.html', *POLICIES, '404.html']
def norm(s): return ' '.join(s.split())
def plain_markdown(s):
 s = re.sub(r'^\s*(?:[-*]|\d+\.)\s+', '', s, flags=re.M)
 s = re.sub(r'^#{1,6}\s+', '', s, flags=re.M)
 return norm(s.replace('**', ''))
class Page(HTMLParser):
 def __init__(self, html):
  super().__init__(convert_charrefs=True)
  self.policy=False; self.text=[]; self.links=[]; self.scripts=[]; self.meta={}; self.lang=None; self.in_title=False; self.title=''
  self.feed(html)
 def handle_starttag(self, tag, attrs):
  a=dict(attrs)
  if tag=='html': self.lang=a.get('lang')
  if tag=='title': self.in_title=True
  if tag=='article' and a.get('id')=='policy-body': self.policy=True
  if tag=='meta': self.meta[a.get('name')]=a.get('content')
  if tag in ('a','link','img'): self.links.append(a.get('href') or a.get('src') or '')
  if tag=='script': self.scripts.append(a)
  if self.policy: self.text.append(' ')
 def handle_endtag(self,tag):
  if tag=='article': self.policy=False
  if tag=='title': self.in_title=False
  if self.policy: self.text.append(' ')
 def handle_data(self,s):
  if self.policy: self.text.append(s)
  if self.in_title: self.title+=s

def verify(source_root=None):
 for name in PAGES:
  path=ROOT/name
  assert path.is_file(), f'Missing page: {name}'
  html=path.read_text(encoding='utf-8'); p=Page(html)
  assert p.lang=='en' and p.title.strip() and p.meta.get('description') and p.meta.get('viewport'), name
  assert 'ORBYN TECH · LCH NETWORK MARKETING · admin@lchnetmarketing.com' in html, name
  assert not re.search(r'\bon\w+\s*=',html,re.I), name
  assert all(s.get('type')=='application/ld+json' and 'src' not in s for s in p.scripts), name
  for link in p.links:
   u=urlsplit(link)
   if u.scheme or u.netloc or not u.path: continue
   dest=ROOT/u.path.lstrip('/') if u.path.startswith('/') else path.parent/u.path
   if dest.is_dir(): dest/='index.html'
   assert dest.is_file(), f'Broken local link: {name}: {link}'
  if name in POLICIES:
   source,placeholder,date=POLICIES[name]
   snapshot=(ROOT/'policy-sources'/source).read_text(encoding='utf-8')
   if source_root: assert snapshot==(source_root/source).read_text(encoding='utf-8'), source
   expected_text=plain_markdown(snapshot.replace(placeholder,date))
   if source.startswith('watt-to-amp/'):
    expected_text=norm(re.sub(r'^#{1,6}\s+', '', snapshot, flags=re.M))
   assert norm(''.join(p.text))==expected_text, f'Policy wording differs: {name}'
   assert date in ''.join(p.text) and placeholder not in html, name
   data=re.search(r'<script type="application/ld\+json">(.*?)</script>',html,re.S)
   assert data, name
   schema=json.loads(data[1])
   assert schema['@type']=='WebPage' and schema['url']==BASE+'/'+name.removesuffix('index.html'), name
   print(f'PASS exact policy wording: {name}')
 assert (ROOT/'CNAME').read_text().strip()=='apps.lchnetmarketing.com'
 assert (ROOT/'.nojekyll').is_file()
 assert 'Sitemap: '+BASE+'/sitemap.xml' in (ROOT/'robots.txt').read_text()
 urls={e.text for e in ET.parse(ROOT/'sitemap.xml').findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
 expected={BASE+'/'+n.removesuffix('index.html') for n in PAGES if n!='404.html'}
 assert urls==expected, 'Sitemap URLs differ'
 llms=(ROOT/'llms.txt').read_text(encoding='utf-8')
 assert not any(w in llms.lower() for w in ['draft','/apps/','pending'])
 assert all(url in llms for url in expected)
 verify_watt()
 print(f'PASS {len(PAGES)} pages: metadata, footer, links, no executable scripts; CNAME, sitemap, robots, llms.txt')
def verify_watt():
 from html import escape
 from math import sqrt
 html=(ROOT/'watt-to-amp/index.html').read_text(encoding='utf-8')
 schemas=[json.loads(s) for s in re.findall(r'<script type="application/ld\+json">(.*?)</script>',html,re.S)]
 assert len(schemas)==2, 'Expected SoftwareApplication and FAQPage'
 app,faq=schemas
 assert app['@type']=='SoftwareApplication' and app['applicationCategory']=='UtilitiesApplication'
 assert app['operatingSystem']=='Android' and float(app['offers']['price'])==0
 assert app['url']==BASE+'/watt-to-amp/'
 assert faq['@type']=='FAQPage' and len(faq['mainEntity'])>=6
 for item in faq['mainEntity']:
  assert item['@type']=='Question' and item['acceptedAnswer']['@type']=='Answer'
  assert '<h3>'+escape(item['name'])+'</h3>' in html, 'FAQ question not visible'
  assert '<p>'+escape(item['acceptedAnswer']['text'])+'</p>' in html, 'FAQ answer differs from visible text'
 answers=' '.join(i['acceptedAnswer']['text'] for i in faq['mainEntity'])
 for value in ['120 W', '12 V', '10 A', '15 kW', '400 V', '0.85', '25.47 A', '2,200', '1,000', '700 W', '230 V', '16.96 A', '20 A', '84.8%']:
  assert value in answers, f'Missing approved example: {value}'
 assert round(120/12,2)==10 and round(15000/(sqrt(3)*400*.85),2)==25.47
 assert round((2200+1000+700)/230,2)==16.96 and round((2200+1000+700)/230/20*100,1)==84.8
 assert 'href="/watt-to-amp/"' in (ROOT/'index.html').read_text(encoding='utf-8')
 print('PASS Watt to Amp: free Android app schema, visible matching FAQ, approved calculations, homepage link')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--source-root',type=Path)
 verify(parser.parse_args().source_root)
