import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
STATE = D / "_login_state.json"
PENDING = D / "pending_login.json"
LOG = D / "login_watch.log"

def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")

pend = json.loads(PENDING.read_text())
qr_id, code = pend["qr_id"], pend["code"]
log(f"开始监听扫码，qr_id={qr_id}")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

pw = sync_playwright().start()
b = pw.chromium.launch(headless=True)
ctx = b.new_context(storage_state=str(STATE), user_agent=UA,
                    viewport={"width": 1440, "height": 900},
                    locale="zh-CN", timezone_id="Asia/Shanghai")
page = ctx.new_page()
Stealth().apply_stealth_sync(page)
page.goto("https://www.xiaohongshu.com", timeout=60000, wait_until="domcontentloaded")
page.wait_for_timeout(2500)

def sign(uri, data=None):
    s = page.evaluate("([url,data]) => window._webmsxyw(url,data)", [uri, data])
    return {"X-s": str(s.get("X-s", "")), "X-t": str(s.get("X-t", "")),
            "X-s-common": str(s.get("X-s-common", ""))}

H = {"Content-Type": "application/json",
     "Origin": "https://www.xiaohongshu.com",
     "Referer": "https://www.xiaohongshu.com/"}

uri = "/api/sns/web/v1/login/qrcode/status"
last = None
deadline = time.time() + 300

while time.time() < deadline:
    try:
        sg = sign(uri, {})
        r = ctx.request.get(
            f"https://edith.xiaohongshu.com{uri}?qr_id={qr_id}&code={code}",
            headers={**sg, **H})
        res = r.json()
        d = res.get("data", res)
        st = d.get("code_status", -1)
        if st != last:
            log(f"状态变化 -> code_status={st}")
            last = st
        if st == 2:
            cookies = ctx.cookies()
            (D / "cookies.json").write_text(json.dumps(cookies, ensure_ascii=False))
            page.wait_for_timeout(2000)
            log("✅ 登录成功，cookies 已写入 " + str(D / "cookies.json"))
            break
        if st == -1 or (res.get("code") not in (0, None) and st == -1):
            log(f"二维码可能已失效: {res}")
            break
    except Exception as e:
        log(f"轮询异常: {e}")
    time.sleep(3)
else:
    log("⏱ 超时（5 分钟）未完成扫码，二维码已失效，需要重新生成")

b.close()
pw.stop()
