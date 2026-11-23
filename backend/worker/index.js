// Avsar Worker: Telegram webhook + dashboard API + calendar feed + poster reading.
const CORS={"access-control-allow-origin":"*","access-control-allow-headers":"authorization,content-type","access-control-allow-methods":"GET,POST,OPTIONS"};
const J=(o,s=200)=>new Response(JSON.stringify(o),{status:s,headers:{"content-type":"application/json",...CORS}});
const tg=(e,m,b)=>fetch(`https://api.telegram.org/bot${e.TELEGRAM_TOKEN}/${m}`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify(b)});
const sb=(e,p,o={})=>fetch(`${e.SUPABASE_URL}/rest/v1/${p}`,{...o,headers:{apikey:e.SUPABASE_SERVICE_KEY,Authorization:"Bearer "+e.SUPABASE_SERVICE_KEY,"content-type":"application/json",...(o.headers||{})}});
const say=(e,id,text)=>tg(e,"sendMessage",{chat_id:id,text:text.slice(0,4000),disable_web_page_preview:true});
const ID=/^[0-9a-f]{8}$/, ST=["new","tracking","applied","skipped"];
// ---- signed login tokens (30 days) ----
const b64u=b=>btoa(String.fromCharCode(...new Uint8Array(b))).replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
async function sign(e,s){const k=await crypto.subtle.importKey("raw",new TextEncoder().encode(e.SESSION_SECRET),{name:"HMAC",hash:"SHA-256"},false,["sign"]);return b64u(await crypto.subtle.sign("HMAC",k,new TextEncoder().encode(s)));}
async function mk(e,c){const p=btoa(JSON.stringify({c,x:Date.now()+30*864e5})).replace(/=+$/,"");return p+"."+await sign(e,p);}
async function ver(e,t){const[p,s]=(t||"").split(".");if(!p||!s||await sign(e,p)!==s)return null;try{const d=JSON.parse(atob(p));return d.x>Date.now()?d.c:null}catch{return null}}
const PRIV=/^(localhost|.*\.local|.*\.internal|\d+\.\d+\.\d+\.\d+|\[.*\])$/i;
const okUrl=u=>{try{const x=new URL(u);return x.protocol==="https:"&&!PRIV.test(x.hostname)&&x.hostname.includes(".")}catch{return false}};
async function addInst(e,chat,o){
  const name=String(o.name||"").trim().slice(0,100),web=String(o.website||"").trim();
  const pages=(Array.isArray(o.pages)?o.pages:String(o.pages||"").split(",")).map(s=>String(s).trim()).filter(Boolean).slice(0,5);
  if(name.length<2||!okUrl(web)||!pages.every(okUrl))return "Invalid: need a name, an https website, and optional https page links (max 5).";
  const cnt=await (await sb(e,`institutes?submitted_by=eq.${chat}&status=eq.pending&select=id`)).json();
  if(cnt.length>=3)return "You already have 3 pending submissions. Please wait for approval.";
  const r=await sb(e,"institutes",{method:"POST",headers:{Prefer:"return=representation"},body:JSON.stringify({name,website:web,pages,contact:String(o.contact||"").slice(0,120),info:String(o.info||"").slice(0,500),submitted_by:chat})});
  const row=(await r.json())[0]; if(!row)return "Could not save. Try again later.";
  const off=/\.(ac\.in|edu\.in|edu|gov\.in)$/i.test(new URL(web).hostname);
  if(e.ADMIN_CHAT_ID)await say(e,e.ADMIN_CHAT_ID,`🏛 New institute #${row.id}: ${name}\n${web}\n${pages.join("\n")}\nContact: ${o.contact||"–"}\n${off?"✅ official-looking domain":"⚠️ not an .ac.in/.edu domain: verify"}\n/approve ${row.id}  ·  /reject ${row.id}`);
  return `Submitted (#${row.id}). It goes live after admin approval and I'll tell you.`;
}
const HELP=`Avsar finds contests + internships from IITs, IIMs, NITs, IIITs, COEP, VJTI, VIT and more, and checks if they look legit.
/interests hackathon, internship, ai → what you want
/login → your web dashboard + calendar link
/list → applied vs remaining
/github username → profile tips
/addinstitute Name | https://site | https://page1,https://page2 | contact | info
/institutes → registered institutes
Send a poster photo → I read and add it
/stop · /resume · /delete`;
async function msg(m,e){
  const id=m.chat.id;
  if(m.photo)return photo(m,e);
  const [c,...r]=(m.text||"").trim().split(/\s+/),arg=r.join(" "),cmd=c.split("@")[0].toLowerCase();
  if(cmd==="/start"){
    await sb(e,"users?on_conflict=chat_id",{method:"POST",headers:{Prefer:"resolution=merge-duplicates"},body:JSON.stringify({chat_id:id,name:m.from?.first_name||"",active:true})});
    return say(e,id,"Welcome to Avsar 🎯\nSet your interests, e.g.\n/interests hackathon, internship, ai, finance\n\n"+HELP);
  }
  if(cmd==="/interests"){
    const a=arg.toLowerCase().split(",").map(s=>s.trim()).filter(Boolean).slice(0,10);
    await sb(e,`users?chat_id=eq.${id}`,{method:"PATCH",body:JSON.stringify({interests:a})});
    return say(e,id,a.length?"Saved: "+a.join(", "):"Cleared. You will get everything.");
  }
  if(cmd==="/stop"||cmd==="/resume"){
    await sb(e,`users?chat_id=eq.${id}`,{method:"PATCH",body:JSON.stringify({active:cmd==="/resume"})});
    return say(e,id,cmd==="/stop"?"Alerts paused.":"Alerts resumed.");
  }
  if(cmd==="/delete"){await sb(e,`users?chat_id=eq.${id}`,{method:"DELETE"});return say(e,id,"All your data was deleted.");}
  if(cmd==="/login"){
    const t=await mk(e,id);
    return say(e,id,`🔐 Dashboard (private link, don't share):\n${e.DASHBOARD_URL}#t=${t}&api=${encodeURIComponent(e.WORKER_URL)}\n\n📅 Calendar feed (add via "subscribe by URL" in Google Calendar):\n${e.WORKER_URL}/cal/${t}.ics`);
  }
  if(cmd==="/list"){
    const rows=await (await sb(e,`user_items?chat_id=eq.${id}&status=in.(tracking,applied)&select=status,items(name,inst,deadline,link)`)).json();
    const t=new Date().toISOString().slice(0,10),L=rows.filter(x=>x.items&&x.items.deadline>=t).sort((a,b)=>a.items.deadline<b.items.deadline?-1:1);
    const f=s=>L.filter(x=>x.status===s).map(x=>`• ${x.items.deadline} ${x.items.name} (${x.items.inst})\n  ${x.items.link||""}`).join("\n")||"  none";
    return say(e,id,`⏳ REMAINING (tracking, not applied)\n${f("tracking")}\n\n✅ APPLIED\n${f("applied")}`);
  }
  if(cmd==="/addinstitute"){const [name,web,pages,contact,...info]=arg.split("|").map(s=>s.trim());return say(e,id,await addInst(e,id,{name,website:web,pages,contact,info:info.join(" | ")}));}
  if(cmd==="/institutes"){
    const L=await (await sb(e,"institutes?status=eq.approved&select=name,website&order=name&limit=80")).json();
    return say(e,id,L.length?L.map(x=>`• ${x.name} – ${x.website}`).join("\n"):"No registered institutes yet.");
  }
  if((cmd==="/approve"||cmd==="/reject")&&String(id)===String(e.ADMIN_CHAT_ID)){
    const n=parseInt(arg); if(!Number.isInteger(n))return say(e,id,"Usage: "+cmd+" <id>");
    const row=(await (await sb(e,`institutes?id=eq.${n}`,{method:"PATCH",headers:{Prefer:"return=representation"},body:JSON.stringify({status:cmd==="/approve"?"approved":"rejected"})})).json())[0];
    if(!row)return say(e,id,"Not found.");
    if(row.submitted_by)await say(e,row.submitted_by,cmd==="/approve"?`✅ ${row.name} is approved. Avsar will now scan its pages.`:`❌ ${row.name} was not approved.`);
    return say(e,id,`Done: #${n} ${cmd.slice(1)}d`);
  }
  if(cmd==="/github"&&/^[A-Za-z0-9-]{1,39}$/.test(arg))return gh(arg,e,id);
  if(cmd==="/stats"&&String(id)===String(e.ADMIN_CHAT_ID)){
    const [u,i]=await Promise.all([sb(e,"users?select=chat_id"),sb(e,"items?select=id")].map(async p=>(await p).json()));
    return say(e,id,`Users: ${u.length}\nContests/internships: ${i.length}`);
  }
  return say(e,id,HELP);
}
async function gh(user,e,id){
  const r=await fetch(`https://api.github.com/users/${user}/repos?per_page=100&sort=pushed`,{headers:{"User-Agent":"avsar"}});
  if(!r.ok)return say(e,id,"GitHub user not found (or rate-limited, try later).");
  const R=await r.json(),own=R.filter(x=>!x.fork),now=Date.now(),tips=[];
  if(own.length<4)tips.push(`Only ${own.length} original repos: ship 1–2 substantial projects`);
  if(own.filter(x=>x.description).length<own.length/2)tips.push("Add descriptions + READMEs to your repos");
  if(!own.some(x=>now-new Date(x.pushed_at)<60*864e5))tips.push("No pushes in 60 days: commit something this week");
  if(!R.some(x=>x.name.toLowerCase()===user.toLowerCase()))tips.push(`Create a profile README (a repo named ${user})`);
  return say(e,id,tips.length?`GitHub tips for ${user}:\n• `+tips.join("\n• "):"GitHub looks solid. Keep it active and pin your best 3 repos.");
}
async function photo(m,e){
  const id=m.chat.id,fid=m.photo[m.photo.length-1].file_id;
  try{
    const info=await (await tg(e,"getFile",{file_id:fid})).json();
    const buf=new Uint8Array(await (await fetch(`https://api.telegram.org/file/bot${e.TELEGRAM_TOKEN}/${info.result.file_path}`)).arrayBuffer());
    let s="";for(let i=0;i<buf.length;i+=8192)s+=String.fromCharCode(...buf.subarray(i,i+8192));
    const P=`Today is ${new Date().toISOString().slice(0,10)}. Read this contest/internship poster. Reply ONLY a JSON object: name, inst, type (Hackathon|Case comp|Coding|Business plan|Quiz|Internship|Other), deadline (YYYY-MM-DD, only if printed, else ""), eligibility, details, fee, prize, link (only if printed), brochure "", tags (3-6 lowercase words). Never guess.`;
    const r=await fetch(e.LLM_BASE_URL.replace(/\/$/,"")+"/chat/completions",{method:"POST",headers:{"content-type":"application/json",Authorization:"Bearer "+e.LLM_API_KEY},body:JSON.stringify({model:e.LLM_MODEL,temperature:0,messages:[{role:"user",content:[{type:"text",text:P},{type:"image_url",image_url:{url:"data:image/jpeg;base64,"+btoa(s)}}]}]})});
    const t=(await r.json()).choices[0].message.content,j=t.match(/\{[\s\S]*\}/),o=j&&JSON.parse(j[0]);
    if(!o||!o.name||!o.deadline)return say(e,id,"I couldn't read a name + deadline from that image. Try a clearer screenshot.");
    await sb(e,"inbox",{method:"POST",body:JSON.stringify({chat_id:id,payload:o})});
    return say(e,id,`Read: ${o.name} (${o.inst||"?"}) · deadline ${o.deadline}.\nAvsar will verify the link/organiser and add it to your tracked list within a few hours.`);
  }catch(x){return say(e,id,"Couldn't process that image (your LLM must support images).");}
}
async function cb(q,e){
  const [a,i]=(q.data||"").split(":"),S={t:"tracking",a:"applied",x:"skipped"}[a];
  if(S&&ID.test(i))await sb(e,`user_items?chat_id=eq.${q.from.id}&item_id=eq.${i}`,{method:"PATCH",body:JSON.stringify({status:S})});
  return tg(e,"answerCallbackQuery",{callback_query_id:q.id,text:{tracking:"⭐ Tracking",applied:"✅ Marked applied",skipped:"Skipped"}[S]||"?"});
}
const auth=(req,e)=>ver(e,(req.headers.get("Authorization")||"").slice(7));
async function items(req,e){
  const c=await auth(req,e); if(!c)return J({error:"auth"},401);
  const t=new Date().toISOString().slice(0,10);
  const r=await Promise.all([sb(e,`items?deadline=gte.${t}&trust=gte.25&select=*&order=deadline&limit=500`),sb(e,`user_items?chat_id=eq.${c}&select=item_id,status`),sb(e,`users?chat_id=eq.${c}&select=name,interests`)]);
  const [I,UI,U]=await Promise.all(r.map(x=>x.json())),M={};UI.forEach(x=>M[x.item_id]=x.status);
  return J({user:U[0]||{},items:I.map(x=>({...x,status:M[x.id]||"none"}))});
}
async function status(req,e){
  const c=await auth(req,e); if(!c)return J({error:"auth"},401);
  const b=await req.json(); if(!ID.test(b.id)||!ST.includes(b.status))return J({error:"bad"},400);
  await sb(e,"user_items?on_conflict=chat_id,item_id",{method:"POST",headers:{Prefer:"resolution=merge-duplicates"},body:JSON.stringify({chat_id:c,item_id:b.id,status:b.status})});
  return J({ok:1});
}
async function cal(url,e){
  const c=await ver(e,url.pathname.slice(5).replace(/\.ics$/,"")); if(!c)return new Response("forbidden",{status:403});
  const rows=await (await sb(e,`user_items?chat_id=eq.${c}&status=in.(tracking,applied)&select=status,items(id,name,deadline,link)`)).json();
  const x=s=>String(s||"").replace(/[\\;,]/g,m=>"\\"+m).replace(/\n/g," "),st=new Date().toISOString().replace(/[-:]|\.\d+/g,"");
  const ev=rows.filter(r=>r.items).map(r=>`BEGIN:VEVENT\r\nUID:${r.items.id}@avsar\r\nDTSTAMP:${st}\r\nDTSTART;VALUE=DATE:${r.items.deadline.replace(/-/g,"")}\r\nSUMMARY:${x((r.status==="applied"?"[Applied] ":"Deadline: ")+r.items.name)}\r\nDESCRIPTION:${x(r.items.link)}\r\nEND:VEVENT\r\n`).join("");
  return new Response(`BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Avsar//EN\r\n${ev}END:VCALENDAR\r\n`,{headers:{"content-type":"text/calendar"}});
}
export default{async fetch(req,e){
  const u=new URL(req.url);
  if(req.method==="OPTIONS")return new Response(null,{headers:CORS});
  if(u.pathname==="/api/items"&&req.method==="GET")return items(req,e);
  if(u.pathname==="/api/institutes"&&req.method==="GET"){const c=await auth(req,e);if(!c)return J({error:"auth"},401);return J(await (await sb(e,"institutes?status=eq.approved&select=name,website,info&order=name&limit=200")).json());}
  if(u.pathname==="/api/institute"&&req.method==="POST"){const c=await auth(req,e);if(!c)return J({error:"auth"},401);return J({message:await addInst(e,c,await req.json())});}
  if(u.pathname==="/api/status"&&req.method==="POST")return status(req,e);
  if(u.pathname.startsWith("/cal/"))return cal(u,e);
  if(req.method!=="POST")return new Response("Avsar running");
  if(req.headers.get("X-Telegram-Bot-Api-Secret-Token")!==e.WEBHOOK_SECRET)return new Response("forbidden",{status:403});
  const b=await req.json();
  try{if(b.message)await msg(b.message,e);else if(b.callback_query)await cb(b.callback_query,e);}catch(x){console.log(String(x));}
  return new Response("ok");
}};
