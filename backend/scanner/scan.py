import os,json,re,hashlib,time,datetime as dt,urllib.request as U
from urllib.parse import urlparse
import socket,ipaddress
R=os.path.dirname(os.path.abspath(__file__)); cfg=json.load(open(os.path.join(R,"config.json")))
TG=os.environ["TELEGRAM_TOKEN"]; SB=os.environ["SUPABASE_URL"].rstrip("/")+"/rest/v1"; SK=os.environ["SUPABASE_SERVICE_KEY"]
KEY=os.environ.get("ANTHROPIC_API_KEY",""); today=dt.date.today(); ADMIN=os.environ.get("ADMIN_CHAT_ID")
def http(url,body=None,h=None,method=None,t=300):
    r=U.Request(url,json.dumps(body).encode() if body is not None else None,h or {"content-type":"application/json"},method=method)
    with U.urlopen(r,timeout=t) as f:
        x=f.read(); return json.loads(x) if x else None
def sb(path,body=None,method=None,prefer=None):
    h={"apikey":SK,"Authorization":"Bearer "+SK,"content-type":"application/json"}
    if prefer: h["Prefer"]=prefer
    return http(f"{SB}/{path}",body,h,method)
def say(c,t,btn=None):
    k={"chat_id":c,"text":t[:4000],"disable_web_page_preview":True}
    if btn: k["reply_markup"]={"inline_keyboard":[btn]}
    try: http(f"https://api.telegram.org/bot{TG}/sendMessage",k); time.sleep(.06); return True
    except U.HTTPError as e:
        if e.code==403: sb(f"users?chat_id=eq.{c}",{"active":False},"PATCH")
        return False
days=lambda d:(dt.date.fromisoformat(d)-today).days
PREP={"Hackathon":["Pin 3 best repos on GitHub with clear READMEs","Have a deployed demo link","List projects + stack on LinkedIn"],
"Case comp":["1-page CV with measurable impact","Practise 2 mock cases","Prepare a 2-slide team intro"],
"Coding":["Keep Codeforces/LeetCode profile public","Keep GitHub active this month"],
"Business plan":["Draft a 10-slide pitch deck","Write a one-line problem statement"],
"Internship":["Tailor a 1-page CV to the role","Link 2 relevant projects on GitHub","Polish LinkedIn headline + about"],"Quiz":["Revise current affairs + domain topics"],"Other":["Update CV and LinkedIn headline"]}

def ask(batch):
    p=f"""Today is {today}. Search official websites, fest/club pages and public Instagram posts of: {', '.join(batch)}.
Find competitions, hackathons, case competitions, quizzes, coding or business-plan contests AND internships/research fellowships (type Internship) published by the institute, open for registration now, deadline on or after today, posted in roughly the last 30 days. Prefer ones open to students from other colleges.
Never invent facts; skip anything whose deadline you cannot confirm.
Reply with ONLY a JSON array. Each item: name, inst, type (Hackathon|Case comp|Coding|Business plan|Quiz|Internship|Other), deadline (YYYY-MM-DD), eligibility, details, fee, prize, past_winners, link, brochure (URL or ""), tags (3-6 lowercase topic words e.g. ai, finance, web, cybersecurity, design)."""
    r=http("https://api.anthropic.com/v1/messages",{"model":cfg["model"],"max_tokens":4000,
      "tools":[{"type":"web_search_20250305","name":"web_search","max_uses":cfg.get("searches",4)}],
      "messages":[{"role":"user","content":p}]},{"content-type":"application/json","x-api-key":KEY,"anthropic-version":"2023-06-01"})
    t="".join(b.get("text","") for b in r["content"] if b["type"]=="text"); m=re.search(r"\[.*\]",t,re.S)
    return json.loads(m.group(0)) if m else []

SYN={"ai":["machine learning","ml","deep learning","llm"],"web":["frontend","backend","full stack","react","node"],"finance":["investment","trading","equity","banking"],"case":["case study","consulting","strategy"],"internship":["intern","summer research","fellowship"],"coding":["competitive programming","dsa","algorithm"],"cybersecurity":["security","ctf","hacking"],"startup":["entrepreneurship","pitch","business plan"],"design":["ui","ux","product design"]}
def score(u,it):
    I=[x.strip().lower() for x in (u.get("interests") or []) if x.strip()]
    if not I: return 40
    blob=" ".join([it["type"]," ".join(it["tags"]),it["name"],it["details"]]).lower()
    return min(100,40*sum(any(k in blob for k in [x]+SYN.get(x,[])) for x in I))

# ---- reliability / phishing heuristics (a risk signal, not a guarantee) ----
REG=set(); REGINST=[]
def load_reg():  # approved, self-registered institutes
    for i in sb("institutes?status=eq.approved&select=*") or []:
        urls=[i["website"]]+list(i.get("pages") or [])
        for u in urls:
            h=(urlparse(u).hostname or "").lower()
            REG.add(h[4:] if h.startswith("www.") else h)
        REGINST.append({"name":i["name"],"urls":urls})
def safe_url(u):  # SSRF guard: public http(s) hosts only
    p=urlparse(u)
    if p.scheme not in("http","https") or not p.hostname: return False
    try:
        for a in socket.getaddrinfo(p.hostname,None):
            ip=ipaddress.ip_address(a[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved: return False
    except Exception: return False
    return True
SHORT={"bit.ly","tinyurl.com","t.co","goo.gl","cutt.ly","rb.gy","is.gd","shorturl.at","wa.me","t.me"}
PLAT=("unstop.com","devfolio.co","hackerearth.com","linkedin.com","instagram.com","github.com","kaggle.com","forms.gle","docs.google.com","internshala.com")
BADTLD=(".xyz",".top",".click",".shop",".work",".loan",".icu",".buzz",".rest",".gq",".tk",".ml",".cf",".site",".online")
SCAM=re.compile(r"pay (now|to|via)|processing fee|guaranteed (job|selection|prize)|send money|upi id|whatsapp only|dm (us )?to register|crypto|lottery|refundable deposit|security deposit",re.I)
def age_days(h):
    p=h.split("."); d=".".join(p[-3:] if ".".join(p[-2:]) in ("co.in","org.in","net.in","ac.in","edu.in") else p[-2:])
    for ev in http("https://rdap.org/domain/"+d,t=8).get("events",[]):
        if ev.get("eventAction")=="registration": return (today-dt.date.fromisoformat(ev["eventDate"][:10])).days
def trust(it):
    sc,n=60,[]
    try: h=(urlparse(it["link"]).hostname or "").lower(); sch=urlparse(it["link"]).scheme
    except Exception: h,sch="",""
    off=h.endswith((".ac.in",".edu.in",".edu",".gov.in",".nic.in")); plat=h.endswith(PLAT)
    if not h: sc-=20; n.append("no link")
    if off: sc+=30; n.append("institute domain")
    elif plat: sc+=10; n.append("known platform: confirm organiser")
    if h and any(h==d or h.endswith("."+d) for d in REG): sc+=25; n.append("registered institute site")
    if h in SHORT: sc-=25; n.append("shortened link")
    if re.fullmatch(r"[\d.]+",h): sc-=35; n.append("IP address link")
    if "xn--" in h: sc-=30; n.append("lookalike characters")
    if h.endswith(BADTLD): sc-=20; n.append("risky domain ending")
    if h and sch=="http": sc-=10; n.append("not https")
    if h.count("-")>=3: sc-=10; n.append("odd domain")
    if h and not off and not plat and re.search(r"iit|iim|nit|iiit|bits|xlri|isb|vit|coep|vjti",h): sc-=35; n.append("imitates an institute name")
    if SCAM.search(" ".join([it["name"],it["details"],it["fee"],it["eligibility"]])): sc-=30; n.append("asks for payment/deposit or off-platform signup")
    try:
        if h and not off and not plat:
            a=age_days(h)
            if a is not None: sc+= -20 if a<180 else 5; n.append(f"domain {a}d old")
    except Exception: pass
    return max(0,min(100,sc)),"; ".join(n)[:200]
TL=lambda x:"✅ Looks official" if x>=70 else "⚠️ Verify before applying" if x>=40 else "🚩 Suspicious"

def dispatch(it,users,force=False):
    if it["trust"]<25 and not force: return
    g=lambda x:it.get(x) or "–"
    for u in users:
        s=score(u,it)
        if s<40 and not force: continue
        st="tracking" if (s>=80 or force) and it["trust"]>=40 else "new"
        sb("user_items",{"chat_id":u["chat_id"],"item_id":it["id"],"status":st,"rem":[]},"POST","resolution=ignore-duplicates")
        todo="; ".join(PREP.get(it["type"],PREP["Other"]))
        say(u["chat_id"],("⭐ Auto-tracking (strong match)\n" if st=="tracking" else "🆕 ")+f"{g('name')}\n🏛 {g('inst')} · {g('type')}\n📅 Deadline: {it['deadline']} ({days(it['deadline'])} days)\n🔒 {TL(it['trust'])} ({it['trust']}/100) {it.get('trust_note') or ''}\n👥 {g('eligibility')}\n💰 Fee: {g('fee')} · Prize: {g('prize')}\n📝 {g('details')}\n🏆 Past winners: {g('past_winners')}\n🔗 {g('link')}\n📄 Brochure: {it.get('brochure') or 'not found'}\n🛠 To qualify: {todo}",
          [{"text":"⭐ Track","callback_data":"t:"+it["id"]},{"text":"✅ Applied","callback_data":"a:"+it["id"]},{"text":"🚫 Skip","callback_data":"x:"+it["id"]}])

def health(url,ok):
    k="f"+hashlib.md5(url.encode()).hexdigest()[:12]; m=sb(f"meta?key=eq.{k}")
    n=0 if ok else int(m[0]["value"] if m else 0)+1
    sb("meta?on_conflict=key",{"key":k,"value":str(n)},"POST","resolution=merge-duplicates")
    if n==3 and ADMIN: say(ADMIN,"⚠️ Source failing 3 runs in a row: "+url)

from html.parser import HTMLParser
class TX(HTMLParser):
    def __init__(s): super().__init__(); s.o=[]; s.k=0
    def handle_starttag(s,t,a):
        if t in("script","style","noscript"): s.k+=1
        if t=="a":
            for n,v in a:
                if n=="href" and v and v.startswith("http"): s.o.append(f"[{v}]")
    def handle_endtag(s,t):
        if t in("script","style","noscript") and s.k: s.k-=1
    def handle_data(s,d):
        if not s.k and d.strip(): s.o.append(d.strip())
def page(u):
    if not safe_url(u): raise Exception("blocked url")
    r=U.Request(u,headers={"User-Agent":"Mozilla/5.0 Avsar"})
    with U.urlopen(r,timeout=60) as f: h=f.read(600000).decode("utf-8","ignore")
    p=TX(); p.feed(h); return " ".join(p.o)[:cfg.get("page_chars",9000)]
def llm(p):  # any OpenAI-compatible endpoint (Gemini, Groq, OpenRouter, Cloudflare, Ollama...)
    r=http(os.environ["LLM_BASE_URL"].rstrip("/")+"/chat/completions",{"model":os.environ["LLM_MODEL"],"temperature":0,
      "messages":[{"role":"user","content":p}]},{"content-type":"application/json","Authorization":"Bearer "+os.environ["LLM_API_KEY"]})
    return r["choices"][0]["message"]["content"]
FIELDS="name, inst, type (Hackathon|Case comp|Coding|Business plan|Quiz|Internship|Other), deadline (YYYY-MM-DD), eligibility, details, fee, prize, past_winners, link (absolute URL), brochure (absolute URL or \"\"), tags (3-6 lowercase topic words)"
def ask_free(src):
    k="h"+hashlib.md5(src["url"].encode()).hexdigest()[:12]
    try: txt=page(src["url"])
    except Exception as e: print("fetch failed",src["url"],e); health(src["url"],False); return []
    h=hashlib.md5(txt.encode()).hexdigest()
    m=sb(f"meta?key=eq.{k}")
    if m and m[0]["value"]==h: health(src["url"],True); return []  # unchanged -> zero LLM calls
    out=[]
    if re.search(r"hackathon|competition|contest|case|quiz|register|deadline",txt,re.I):
        t=llm(f"""Today is {today}. Below is text scraped from {src['url']} ({src.get('inst','')}); [urls] are link targets.
Extract competitions/hackathons/case competitions/quizzes/internships/fellowships currently open for registration. Use ONLY what the text states; never invent. Skip any whose deadline is missing or before today.
Reply with ONLY a JSON array; each item has: {FIELDS}.
TEXT: {txt}""")
        m2=re.search(r"\[.*\]",t,re.S)
        out=json.loads(m2.group(0)) if m2 else []
        for it in out: it.setdefault("inst",src.get("inst",""))
    sb("meta?on_conflict=key",{"key":k,"value":h},"POST","resolution=merge-duplicates")
    health(src["url"],True)
    return out

def ingest(found,users,force=False):
    rows={}
    for it in found:
        try:
            s=lambda x:str(it.get(x) or "")
            d=s("deadline")[:10]
            if days(d)<0: continue
            i=hashlib.md5((re.sub(r"[^a-z0-9]","",s("name").lower())+d).encode()).hexdigest()[:8]
            r={"id":i,"name":s("name"),"inst":s("inst"),"type":s("type") or "Other","deadline":d,"eligibility":s("eligibility"),"details":s("details"),"fee":s("fee"),"prize":s("prize"),"past_winners":s("past_winners"),"link":s("link"),"brochure":s("brochure"),"tags":[str(t).lower() for t in (it.get("tags") or [])][:6]}
            r["trust"],r["trust_note"]=trust(r)
            rows[i]=r
        except Exception: continue
    if not rows: return 0
    new=sb("items?on_conflict=id",list(rows.values()),"POST","resolution=ignore-duplicates,return=representation") or []
    for it in new: dispatch(it,users,force)
    return len(new)

def inbox():  # posters sent to the bot as photos
    for r in sb("inbox?done=eq.false&select=*") or []:
        c=r["chat_id"]; u=sb(f"users?chat_id=eq.{c}&select=*") or []
        try: n=ingest([r["payload"] or {}],u,True)
        except Exception as e: print("inbox failed",e); n=0
        if not n and u: say(c,"That one was already in Avsar (or its deadline was invalid/expired).")
        sb(f"inbox?id=eq.{r['id']}",{"done":True},"PATCH")

def scan():
    users=sb("users?active=eq.true&select=*") or []
    if not users: return
    if os.environ.get("PROVIDER","free")=="free":
        for src in list(cfg.get("sources",[]))+[{"inst":i["name"],"url":u} for i in REGINST for u in i["urls"]]:
            try: ingest(ask_free(src),users)
            except Exception as e: print("source failed",src.get("url"),e)
        return
    ins=cfg["institutes"]+[i["name"] for i in REGINST]; n=cfg.get("batch",6)
    for k in range(0,len(ins),n):
        try: ingest(ask(ins[k:k+n]),users)
        except Exception as e: print("batch failed",e)

def remind():
    for r in sb("user_items?status=eq.tracking&select=chat_id,item_id,rem,items(*)") or []:
        it=r["items"]
        if not it: continue
        d=days(it["deadline"])
        if d<0: continue
        due=[t for t in (7,3,1,0) if d<=t and t not in r["rem"]]
        if due and say(r["chat_id"],f"⏰ {'LAST DAY' if d==0 else str(d)+' day(s) left'}: {it['name']} ({it['inst']})\nDeadline {it['deadline']}\n🔗 {it['link']}\n📄 {it['brochure'] or ''}"):
            sb(f"user_items?chat_id=eq.{r['chat_id']}&item_id=eq.{r['item_id']}",{"rem":r["rem"]+due},"PATCH")

def digest():
    if today.weekday()!=6: return
    m=sb("meta?key=eq.digest")
    if m and m[0]["value"]==str(today): return
    G={}
    for r in sb("user_items?status=eq.tracking&select=chat_id,items(name,inst,deadline)") or []:
        if r["items"] and days(r["items"]["deadline"])>=0: G.setdefault(r["chat_id"],[]).append(r["items"])
    for c,L in G.items():
        L.sort(key=lambda x:x["deadline"]); say(c,"📋 Weekly digest\n"+"\n".join(f"• {x['deadline']} – {x['name']} ({x['inst']})" for x in L))
    sb("meta?on_conflict=key",{"key":"digest","value":str(today)},"POST","resolution=merge-duplicates")

load_reg()
if os.environ.get("MODE","scan")=="scan": scan(); digest()
inbox()
remind()
