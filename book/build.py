import subprocess, re, sys, html, pathlib
from playwright.sync_api import sync_playwright
D=pathlib.Path(__file__).parent
parts=sorted((D/"chapters").glob("*.md"))
md=[(D/"front.md").read_text()]+[p.read_text() for p in parts]+[(D/"back.md").read_text()]
src="\n\n".join(md)
body=subprocess.run(["pandoc","-f","markdown+pipe_tables+fenced_code_blocks-smart","-t","html5","--no-highlight"],input=src,text=True,capture_output=True,check=True).stdout
# ids for h1/h2 so the TOC can link; pandoc adds ids automatically
h1=re.findall(r'<h1[^>]*?id="([^"]+)"[^>]*>(.*?)</h1>',body,re.S)
css=open(D/"book.css").read()
def toc(pages):
    rows=[]
    for i,t in h1:
        txt=re.sub("<.*?>","",t)
        pg=pages.get(i,"")
        rows.append(f'<li><a href="#{i}">{txt}</a><span class="pg">{pg}</span></li>')
    return '<ol class="toc">'+"".join(rows)+'</ol>'
def doc(pages):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>The Practitioner's Library</title><style>{css}</style></head><body>
<section class="cover"><div class="kicker">A GENERAL LEARNING PATH</div><h1 class="ct">The Practitioner&rsquo;s Library</h1><div class="sub">Eleven disciplines from beginner to professional judgement</div><div class="list">Data Analyst &middot; Data Scientist &middot; Machine Learning &middot; Data Engineering &middot; AI Engineering &middot; Project &amp; Product &middot; Systems Analyst &middot; Full Stack Developer &middot; Cybersecurity &middot; Network Engineer &middot; IT Specialist</div><div class="by">Prepared for Lamarcus &middot; October 2026</div></section>
<section class="tocp"><h2 class="tt">Contents</h2>{toc(pages)}</section>
{body}</body></html>'''
def render(pages,out):
    f=D/"_book.html"; f.write_text(doc(pages),encoding="utf-8")
    with sync_playwright() as p:
        b=p.chromium.launch(); pg=b.new_page(); pg.goto(f.as_uri()); pg.wait_for_timeout(500)
        pg.pdf(path=str(out),format="Letter",print_background=True,display_header_footer=True,
               header_template='<span></span>',footer_template='<div style="font-size:8px;width:100%;text-align:center;color:#666;font-family:Georgia,serif"><span class="pageNumber"></span></div>',
               margin={"top":"0.9in","bottom":"0.9in","left":"0.9in","right":"0.9in"})
        b.close()
out=D/"The_Practitioners_Library.pdf"
render({},out)
from pypdf import PdfReader
r=PdfReader(str(out)); pages={}
txt=[ (pg.extract_text() or "") for pg in r.pages]
norm=lambda x:re.sub(r"[^a-z0-9]","",x.lower())
for i,t in h1:
    title=norm(html.unescape(re.sub("<.*?>","",t)))
    for n,tx in enumerate(txt):
        if n>=2 and norm(tx[:200]).startswith(title):
            pages[i]=n+1; break
print("found",len(pages),"of",len(h1))
render(pages,out)
print(len(PdfReader(str(out)).pages),"pages")
