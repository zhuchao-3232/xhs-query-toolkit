import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
D.mkdir(parents=True, exist_ok=True)
LOG = D / "login_watch.log"

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")
H = {"Content-Type": "application/json",
     "Origin": "https://www.xiaohongshu.com",
     "Referer": "https://www.xiaohongshu.com/"}

pw = sync_playwright().start()
b = pw.chromium.launch(headless=True)
ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                    locale="zh-CN", timezone_id="Asia/Shanghai")
page = ctx.new_page()
Stealth().apply_stealth_sync(page)
page.goto("https://www.xiaohongshu.com", timeout=60000, wait_until="domcontentloaded")
page.wait_for_timeout(2000)
page.mouse.move(700, 400); page.wait_for_timeout(500)
page.mouse.wheel(0, 800); page.wait_for_timeout(1200)

def sign(uri, data=None):
    s = page.evaluate("([url,data]) => window._webmsxyw(url,data)", [uri, data])
    return {"X-s": str(s.get("X-s", "")), "X-t": str(s.get("X-t", "")),
            "X-s-common": str(s.get("X-s-common", ""))}

def new_qr():
    uri = "/api/sns/web/v1/login/qrcode/create"
    sg = sign(uri, {})
    r = ctx.request.post(f"https://edith.xiaohongshu.com{uri}",
                         headers={**sg, **H}, data="{}")
    res = r.json()
    if res.get("code") != 0:
        log(f"生成二维码失败: {res}")
        return None
    d = res["data"]
    import qrcode, os
    ts = time.strftime("%H%M%S")
    qr_path = D / f"login_qr_{ts}.png"
    try:
        qrcode.make(d["url"]).save(str(qr_path))
    except OSError:
        qr_path = D.parent / f"xhs_login_qr_{ts}.png"
        qrcode.make(d["url"]).save(str(qr_path))
    (D / "pending_login.json").write_text(json.dumps({"qr_id": d["qr_id"], "code": d["code"]}))
    log(f"新二维码已生成 qr_id={d['qr_id']}")
    log(f"二维码文件: {qr_path}")
    log(f"在 PowerShell 执行这个命令打开它: start \"{qr_path}\"")
    return d["qr_id"], d["code"]

cur = new_qr()
if not cur:
    raise SystemExit(1)
qr_id, code = cur

rounds = 0
max_rounds = 4 * 60 // 3  # 约 4 分钟
while rounds < max_rounds:
    rounds += 1
    time.sleep(3)
    full = f"/api/sns/web/v1/login/qrcode/status?qr_id={qr_id}&code={code}"
    try:
        sg = sign(full, None)
        r = ctx.request.get(f"https://edith.xiaohongshu.com{full}", headers={**sg, **H})
        res = r.json()
    except Exception as e:
        log(f"轮询异常: {e}")
        continue
    d = res.get("data", res)
    st = d.get("code_status", d.get("status", -1)) if isinstance(d, dict) else -1
    if rounds % 10 == 0:
        log(f"心跳 code={res.get('code')} status={st}")
    if st == 0:
        pass                     # 待扫码
    elif st == 1:
        log("👀 已扫码，等待手机端确认…")
    elif st == 2:
        cookies = ctx.cookies()
        (D / "cookies.json").write_text(json.dumps(cookies, ensure_ascii=False))
        page.wait_for_timeout(2000)
        log(f"✅ 登录成功，cookies 已写入 {D/'cookies.json'}")
        break
    elif st in (3, -1) or res.get("code") == -1:
        log(f"二维码失效(status={st})，自动重新生成…")
        nc = new_qr()
        if nc:
            qr_id, code = nc
            rounds = 0
        else:
            time.sleep(10)
else:
    log("⏱ 超时未完成扫码，需要重新生成二维码")

b.close()
pw.stop()
