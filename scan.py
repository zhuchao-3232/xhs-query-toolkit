"""竞品对标扫描：搜索 -> 低粉爆文过滤 -> 输出清单"""
import json, time, sys
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
cookies = json.loads((D / "cookies.json").read_text())
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

KEYWORDS = ["海外社媒变现", "TikTok运营", "跨境独立站"]

pw = sync_playwright().start()
b = pw.chromium.launch(headless=True)
ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                    locale="zh-CN", timezone_id="Asia/Shanghai")
ctx.add_cookies(cookies)
page = ctx.new_page()
Stealth().apply_stealth_sync(page)


def harvest_search(kw, scrolls=3):
    got = []

    def h(r):
        if "/search/notes" in r.url:
            try:
                got.append(r.json())
            except Exception:
                pass

    page.on("response", h)
    page.goto(f"https://www.xiaohongshu.com/search_result?keyword={quote(kw)}&source=web_explore_feed",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(6000)
    for _ in range(scrolls):
        page.mouse.wheel(0, 2200)
        page.wait_for_timeout(3200)
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
            out.append({
                "id": nid,
                "title": (nc.get("display_title") or "").replace("\n", " "),
                "author": u.get("nickname", ""),
                "user_id": u.get("user_id", ""),
                "likes": int(ic.get("liked_count") or 0),
                "collects": int(ic.get("collected_count") or 0),
                "comments": int(ic.get("comment_count") or 0),
                "token": it.get("xsec_token", ""),
            })
    return out


def fans_of(uid):
    try:
        page.goto(f"https://www.xiaohongshu.com/user/profile/{uid}",
                  timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(6500)
        return page.evaluate("""() => {
          const u = (window.__INITIAL_STATE__ || {}).user || {};
          let d = u.userPageData;
          if (d && (d._value || d.value)) d = d._value || d.value;
          if (!d) return null;
          const b = d.basicInfo || {};
          let n = u.notes;
          if (n && (n._value || n.value)) n = n._value || n.value;
          return {fans: (d.interactions||[]).find(i=>i.name==='粉丝')?.count || '0',
                  likes: (d.interactions||[]).find(i=>i.name==='获赞与收藏')?.count || '0',
                  desc: b.desc || '', ip: b.ipLocation || '',
                  note_count: Array.isArray(n) ? n.length : null};
        }""")
    except Exception as e:
        return None


all_notes = {}
for kw in KEYWORDS:
    ns = harvest_search(kw)
    print(f"[{kw}] 抓到 {len(ns)} 条", flush=True)
    for n in ns:
        n["kw"] = kw
        if n["id"] not in all_notes:
            all_notes[n["id"]] = n

pool = list(all_notes.values())
hot = [n for n in pool if n["likes"] >= 500]
hot.sort(key=lambda x: -x["likes"])
print(f"\n总去重笔记 {len(pool)} 条，其中点赞≥500 的 {len(hot)} 条")

# 取点赞最高的若干篇，逐个查作者粉丝数
cand = hot[:10]
results = []
for i, n in enumerate(cand, 1):
    prof = fans_of(n["user_id"]) if n["user_id"] else None
    fan = 0
    if prof:
        try:
            fan = int(prof["fans"])
        except Exception:
            fan = 0
    results.append({**n, "fans": fan, "prof": prof})
    flag = "★低粉爆文" if fan < 10000 and n["likes"] >= 1000 else ""
    print(f"{i:>2}. 赞{n['likes']:<6} 粉{fan:<7} {n['author'][:16]:<18} {n['title'][:26]} {flag}",
          flush=True)

Path("/tmp/xhs_scan.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
print("\n明细已存 /tmp/xhs_scan.json")
b.close()
pw.stop()
