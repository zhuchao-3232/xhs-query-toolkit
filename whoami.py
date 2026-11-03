# -*- coding: utf-8 -*-
# 验证当前登录身份（读首页 SSR 状态，只读操作）
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
ck = D / "cookies.json"
if not ck.exists():
    print("未找到 cookies.json，先跑 login_flow.py 登录")
    raise SystemExit(1)

cookies = json.loads(ck.read_text())
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

pw = sync_playwright().start()
b = pw.chromium.launch(headless=True)
ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                    locale="zh-CN", timezone_id="Asia/Shanghai")
ctx.add_cookies(cookies)
page = ctx.new_page()
Stealth().apply_stealth_sync(page)
page.goto("https://www.xiaohongshu.com", timeout=60000, wait_until="domcontentloaded")
page.wait_for_timeout(4500)

raw = page.evaluate("""() => {
  const s = window.__INITIAL_STATE__;
  if (!s || !s.user) return {err: 'no state'};
  let ui = s.user.userInfo;
  if (ui && ui.__v_isRef) ui = ui._value;
  if (!ui) return {err: 'not logged in'};
  return {nick: ui.nickName || ui.nickname, redId: ui.redId, desc: ui.desc};
}""")

if raw.get("err"):
    print("登录状态失效（%s），重跑 login_flow.py 重新扫码" % raw["err"])
else:
    print("当前登录账号：")
    print("  昵称    :", raw.get("nick"))
    print("  小红书号:", raw.get("redId"))
    print("  简介    :", raw.get("desc") or "（无简介）")

b.close()
pw.stop()
