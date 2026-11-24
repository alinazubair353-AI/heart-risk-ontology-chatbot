"""Web UI for the ontology chatbot. Standard library only, nothing to install.

    py app.py

Opens http://127.0.0.1:8000 in your browser. Stop it with Ctrl+C in the terminal.
Put this file in the same folder as chatbot.py and heart_risk.owl.
"""
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from chatbot import HeartRiskBot

BOT = HeartRiskBot()
LOCK = threading.Lock()

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>CardioCheck | Heart-Risk Ontology Chatbot</title>
<style>
:root{color-scheme:light;--bg:#eef4f7;--card:#fff;--ink:#12283a;--mute:#5c7080;--line:#d8e4eb;
--teal:#0b7a8a;--navy:#123f6d;--red:#d6334a;--soft:#e8f4f6;--high:#e0701a;--mod:#c99a06;--info:#5b7c99}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Segoe UI",system-ui,-apple-system,Arial,sans-serif}
.top{background:linear-gradient(110deg,#0a5870 0%,#123f6d 100%);color:#fff;position:relative;overflow:hidden}
.top .in{max-width:1120px;margin:0 auto;padding:18px 20px 16px;display:flex;align-items:center;gap:14px;position:relative;z-index:1}
.logo{width:50px;height:50px;border-radius:14px;background:#ffffff1f;display:grid;place-items:center;flex:none}
.logo svg{width:30px;height:30px;animation:beat 1.6s ease-in-out infinite}
@keyframes beat{0%,100%{transform:scale(1)}14%{transform:scale(1.14)}28%{transform:scale(1)}42%{transform:scale(1.1)}}
.top h1{margin:0;font-size:23px;letter-spacing:.2px}.top .sub{font-size:14px;color:#cfe6ee}
.ecg{position:absolute;right:0;top:0;height:100%;width:60%;opacity:.28}
.notice{background:#fff7e0;border-bottom:1px solid #f1e2ad;color:#6a5410;font-size:13.5px;text-align:center;padding:7px 12px}
.app{max-width:1120px;margin:0 auto;padding:18px 20px 24px;display:grid;grid-template-columns:1fr 300px;gap:18px}
@media (max-width:860px){.app{grid-template-columns:1fr}.side{order:-1}}
.chat{background:var(--card);border:1px solid var(--line);border-radius:16px;display:flex;flex-direction:column;
height:calc(100vh - 190px);min-height:460px;box-shadow:0 6px 22px #123f6d12}
@media (max-width:860px){.chat{height:68vh}}
.chat-h{padding:12px 16px;border-bottom:1px solid var(--line);display:flex;align-items:center;gap:10px;font-weight:600}
.dot{width:9px;height:9px;border-radius:50%;background:#2bb673;box-shadow:0 0 0 4px #2bb67326}
.chat-h small{color:var(--mute);font-weight:400;margin-left:auto}
#log{flex:1;overflow:auto;padding:18px 16px;display:flex;flex-direction:column;gap:14px;background:linear-gradient(#fbfdfe,#f6fafc)}
.row{display:flex;gap:10px;align-items:flex-start}.row.u{justify-content:flex-end}
.av{width:34px;height:34px;border-radius:50%;background:var(--soft);display:grid;place-items:center;flex:none;border:1px solid var(--line)}
.av svg{width:18px;height:18px}
.msg{max-width:88%;padding:11px 15px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word}
.user{background:linear-gradient(120deg,#0b7a8a,#0e5f8f);color:#fff;border-bottom-right-radius:4px}
.bot{background:#fff;border:1px solid var(--line);border-bottom-left-radius:4px;box-shadow:0 1px 3px #123f6d0d}
.bot.urgentbox{background:#fff5f6;border:1px solid #f1b4bc;border-left:5px solid var(--red)}
.tag{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.4px;padding:1px 9px;border-radius:999px;color:#fff;margin-right:6px;vertical-align:1px}
.t-URGENT{background:var(--red)}.t-HIGH{background:var(--high)}.t-MODERATE{background:var(--mod)}.t-INFO{background:var(--info)}
.src{color:var(--teal);font-weight:600}
.warn{color:var(--red);font-weight:800;font-size:17px}
.disc{color:var(--mute);font-size:13px}
.typing{color:var(--mute);font-size:14px}
form{display:flex;gap:8px;padding:12px;border-top:1px solid var(--line);background:#fff;border-radius:0 0 16px 16px}
input[type=text]{flex:1;padding:12px 14px;border-radius:10px;border:1px solid #c8d8e2;background:#f8fbfd;color:var(--ink);font:inherit}
input[type=text]:focus{outline:2px solid #0b7a8a55;border-color:var(--teal)}
button{padding:10px 18px;border-radius:10px;border:0;background:var(--teal);color:#fff;font:inherit;font-weight:600;cursor:pointer}
button:hover{background:#09697a}
button.ghost{background:#fff;color:var(--navy);border:1px solid #c8d8e2}button.ghost:hover{background:var(--soft)}
.side{display:flex;flex-direction:column;gap:14px}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 14px 12px;box-shadow:0 6px 22px #123f6d12}
.panel h2{font-size:12.5px;text-transform:uppercase;letter-spacing:.09em;color:var(--teal);margin:0 0 10px;display:flex;align-items:center;gap:7px}
.chips{display:flex;flex-direction:column;gap:7px}
.chip{text-align:left;font-weight:500;font-size:14px;padding:9px 11px;background:#f7fbfc;color:var(--ink);border:1px solid var(--line);border-radius:10px}
.chip:hover{border-color:var(--teal);background:var(--soft)}
#vals div{display:flex;justify-content:space-between;gap:10px;font-size:14px;padding:6px 0;border-bottom:1px dashed var(--line)}
#vals div:last-child{border-bottom:0}#vals span:last-child{font-weight:700;color:var(--navy);text-align:right}
.empty{color:var(--mute);font-size:14px}
.foot{max-width:1120px;margin:0 auto;padding:0 20px 20px;color:var(--mute);font-size:12.5px;text-align:center}
</style></head><body>
<div class="top">
<svg class="ecg" viewBox="0 0 600 100" preserveAspectRatio="none"><path d="M0,55 L120,55 L145,55 L160,20 L180,92 L200,40 L215,55 L330,55 L350,55 L365,25 L385,88 L405,45 L420,55 L600,55" fill="none" stroke="#fff" stroke-width="2.2"/></svg>
<div class="in"><div class="logo"><svg viewBox="0 0 24 24"><path fill="#ff6b81" d="M12 21.2l-1.4-1.27C5.4 15.2 2 12.1 2 8.3 2 5.2 4.4 3 7.4 3c1.7 0 3.4.8 4.6 2.1C13.2 3.8 14.9 3 16.6 3 19.6 3 22 5.2 22 8.3c0 3.8-3.4 6.9-8.6 11.63L12 21.2z"/></svg></div>
<div><h1>CardioCheck</h1><div class="sub">Heart-risk ontology chatbot: every answer comes from a rule and a source. No LLM.</div></div></div></div>
<div class="notice">Educational project for a course. Not a medical device, not clinically validated. For emergencies call your local emergency number.</div>
<div class="app">
<div class="chat"><div class="chat-h"><span class="dot"></span>Ontology assistant<small>OWL + reasoning</small></div>
<div id="log"></div>
<form id="f"><input id="q" type="text" autocomplete="off" placeholder="Type lab values or a question..." autofocus>
<button type="submit">Send</button><button type="button" class="ghost" id="reset">New patient</button></form></div>
<aside class="side">
<div class="panel"><h2>Patient values</h2><div id="vals"><div class="empty">No values yet.</div></div></div>
<div class="panel"><h2>Try an example</h2><div class="chips" id="chips"></div></div>
</aside></div>
<div class="foot">Thresholds follow published guidelines (ACC/AHA, ADA, WHO). Always consult a doctor.</div>
<script>
const log=document.getElementById('log'),q=document.getElementById('q');
const HEART='<svg viewBox="0 0 24 24"><path fill="#d6334a" d="M12 21.2l-1.4-1.27C5.4 15.2 2 12.1 2 8.3 2 5.2 4.4 3 7.4 3c1.7 0 3.4.8 4.6 2.1C13.2 3.8 14.9 3 16.6 3 19.6 3 22 5.2 22 8.3c0 3.8-3.4 6.9-8.6 11.63L12 21.2z"/></svg>';
const EX=["My LDL is 175, HDL 38, BP 150/95, fasting glucose 132, age 58 male, I am a smoker","why am I flagged?","what should I do?",
"what is a normal HDL for women?","My LDL is 120, BP 118/76, age 30 female","I have chest pain","tell me a joke","help"];
const esc=s=>s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
function fmt(t){let h=esc(t);
 h=h.replace(/\[(URGENT|HIGH|MODERATE|INFO)\]/g,'<span class="tag t-$1">$1</span>');
 h=h.replace(/^(!!! URGENT !!!)/m,'<span class="warn">&#9888; URGENT</span>');
 h=h.replace(/^(\s*Source: .*)$/gm,'<span class="src">$1</span>');
 h=h.replace(/^(This is an educational tool.*)$/gm,'<span class="disc">$1</span>');return h}
function add(text,who,html){const r=document.createElement('div');r.className='row'+(who==='user'?' u':'');
 const d=document.createElement('div');d.className='msg '+who;
 if(who==='bot'){r.innerHTML='<div class="av">'+HEART+'</div>';d.innerHTML=html||fmt(text);if(text.includes('!!! URGENT !!!'))d.classList.add('urgentbox')}else d.textContent=text;
 r.appendChild(d);log.appendChild(r);log.scrollTop=log.scrollHeight;return r}
function vals(v){const el=document.getElementById('vals');if(!v.length){el.innerHTML='<div class="empty">No values yet.</div>';return}
 el.innerHTML=v.map(x=>`<div><span>${esc(x[0])}</span><span>${esc(x[1])}</span></div>`).join('')}
async function send(text){if(!text.trim())return;add(text,'user');q.value='';
 const t=add('','bot','<span class="typing">Reasoning over the ontology...</span>');
 try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
  const j=await r.json();t.remove();add(j.reply,'bot');vals(j.values)}catch(e){t.remove();add('Could not reach the chatbot server. Is the terminal still running?','bot')}}
document.getElementById('f').addEventListener('submit',e=>{e.preventDefault();send(q.value)});
document.getElementById('reset').addEventListener('click',()=>send('reset'));
const chips=document.getElementById('chips');
EX.forEach(t=>{const b=document.createElement('button');b.type='button';b.className='chip';b.textContent=t;b.onclick=()=>send(t);chips.appendChild(b)});
add("Hello! I can check your lab values against published cardiology cut-offs and explain every finding with its source. Type your values (for example LDL, HDL, BP like 150/95, glucose, age, sex, smoker) or pick an example on the right.",'bot');
</script></body></html>"""


def values_for_ui():
    onto = BOT.onto
    out = []
    for prop in onto.properties:
        if prop in BOT.patient:
            label, _, rest = onto.fmt_prop(prop, BOT.patient[prop]).partition(": ")
            out.append([label, rest])
    return out


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        else:
            self._send(404, "Not found", "text/plain")

    def do_POST(self):
        if self.path != "/api/chat":
            return self._send(404, "Not found", "text/plain")
        try:
            n = int(self.headers.get("Content-Length", 0))
            msg = json.loads(self.rfile.read(n).decode("utf-8")).get("message", "")
            with LOCK:
                reply = BOT.handle(msg)
                values = values_for_ui()
            self._send(200, json.dumps({"reply": reply, "values": values}), "application/json")
        except Exception as e:  # keep the demo alive and show the problem
            self._send(500, json.dumps({"reply": f"Internal error: {e}", "values": []}), "application/json")

    def log_message(self, *args):
        pass


def main():
    server = None
    for port in range(8000, 8010):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("Could not find a free port between 8000 and 8009.")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print(f"Chatbot is running at {url}")
    print("Close it with Ctrl+C in this terminal.")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
