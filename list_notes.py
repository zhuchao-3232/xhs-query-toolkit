"""列出关键词搜索结果全量清单（含 id/作者/标题/token），并高亮目标作者。"""
import json, sys
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

KWS = sys.argv[1:] or ["云梦泽服务表", "红薯卖情感资料"]


def harvest(page, kw, scrolls=3):
    got = []

    def h(r):
        if "/search/notes" in r.url:
            try:
                got.append(r.json())
            except Exception:
                pass

    page.on("response", h)
    page.goto("https://www.xiaohongshu.com/search_result?keyword="
              + quote(kw) + "&source=web_explore_feed",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(6500)
    for _ in range(scrolls):
        page.mouse.wheel(0, 2000)
        page.wait_for_timeout(2800)
    page.remove_listener("response", h)
    out, seen = [], set()
    for j in got:
        for it in (j.get("data") or {}).get("items", []):
            nc = it.get("note_card") or {}
            nid = it.get("id")
            if not nid or nid in seen:
                continue
            seen.add(nid)
            u = nc.get("user") or {}
            ic = nc.get("interact_info") or {}
            out.append({"id": nid, "title": (nc.get("display_title") or "").replace("\n", " "),
                        "author": u.get("nickname", ""), "user_id": u.get("user_id", ""),
                        "likes": int(ic.get("liked_count") or 0),
                        "token": it.get("xsec_token", ""), "kw": kw})
    return out


pw = sync_playwright().start()
b = pw.chromium.launch(headless=True)
ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                    locale="zh-CN", timezone_id="Asia/Shanghai")
ctx.add_cookies(json.loads((D / "cookies.json").read_text()))
page = ctx.new_page()
Stealth().apply_stealth_sync(page)

alln, seen = [], set()
for kw in KWS:
    ns = harvest(page, kw)
    print(f"\n[{kw}] {len(ns)} 条", flush=True)
    for n in ns:
        mark = "  ★★★" if ("云梦泽" in n["author"] or "服务表" in n["title"]) else ""
        print(f"  {n['likes']:>5} {n['author'][:16]:<18} {n['title'][:44]}  {n['id']}{mark}", flush=True)
        if n["id"] not in seen:
            seen.add(n["id"])
            alln.append(n)

Path("/tmp/list_notes.json").write_text(json.dumps(alln, ensure_ascii=False, indent=2))
print(f"\n合计 {len(alln)} 条 -> /tmp/list_notes.json")
b.close()
pw.stop()
