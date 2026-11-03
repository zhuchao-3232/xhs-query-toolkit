"""抓取某个 user_id 主页下所有笔记的正文与互动数据。

用法: python fetch_notes.py <user_id> [--limit N]
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

D = Path.home() / ".xhs-mcp"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36")

READ = """() => {
  const U=(v,d=0)=>{ if(d>5) return v;
    if(v && typeof v==='object' && '__v_isRef' in v) return U(v._value,d+1); return v; };
  const S=x=>(x===undefined||x===null)?'':String(x);
  const s = window.__INITIAL_STATE__||{};
  const nd=U(s.note)||{}; const dm=U(nd.noteDetailMap)||{};
  const k=Object.keys(dm)[0]; const f=U(dm[k])||{}; const n=U(f.note)||{};
  const ii=U(n.interactInfo)||{};
  const com=U(f.comments)||{};
  return {title:S(n.title), desc:S(n.desc), likes:S(ii.likedCount),
          collects:S(ii.collectedCount), comments:S(ii.commentCount),
          shares:S(ii.shareCount), imgs:(U(n.imageList)||[]).length,
          tags:(U(n.tagList)||[]).map(t=>S(U(t).name)),
          topComments:(U(com.list)||[]).slice(0,10).map(c=>S(U(c).content).replace(/\\n/g,' '))};
}"""


def main():
    uid = sys.argv[1]
    limit = 20
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                        locale="zh-CN", timezone_id="Asia/Shanghai")
    ctx.add_cookies(json.loads((D / "cookies.json").read_text()))
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    page.goto(f"https://www.xiaohongshu.com/user/profile/{uid}",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(8000)
    for _ in range(3):
        page.mouse.wheel(0, 2400)
        page.wait_for_timeout(2800)

    hrefs = page.evaluate("""(uid) => Array.from(document.querySelectorAll('a[href]'))
        .map(a => a.href)
        .filter(h => h.includes('/user/profile/' + uid + '/'))""", uid)

    items = []
    seen = set()
    for h in hrefs:
        m = re.search(r"/user/profile/[^/]+/([0-9a-f]{24})", h)
        if not m:
            continue
        nid = m.group(1)
        if nid in seen:
            continue
        seen.add(nid)
        q = urlsplit(h).query
        tok = ""
        for kv in q.split("&"):
            if kv.startswith("xsec_token="):
                tok = kv.split("=", 1)[1]
        items.append((nid, tok))

    print(f"主页链接去重后笔记数: {len(items)}")
    results = {}
    for nid, tok in items[:limit]:
        url = f"https://www.xiaohongshu.com/explore/{nid}"
        if tok:
            url += f"?xsec_token={tok}&xsec_source=pc_user"
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(7000)
            d = page.evaluate(READ)
            if not d.get("title") and not d.get("desc"):
                page.wait_for_timeout(4000)
                d = page.evaluate(READ)
            results[nid] = d
            print("\n" + "=" * 78)
            print(f"【{d.get('title')}】 赞{d.get('likes')} 藏{d.get('collects')} "
                  f"评{d.get('comments')} 图{d.get('imgs')}张")
            print("=" * 78)
            print((d.get("desc") or "(无正文)")[:1100])
            if d.get("topComments"):
                print("  -- 评论 --")
                for c in d["topComments"]:
                    print("   ·", c[:72])
        except Exception as e:
            print(f"[失败 {nid}] {str(e)[:110]}")
        time.sleep(1)

    p = Path("/tmp") / f"notes_{uid}.json"
    p.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n已保存 {len(results)} 条 -> {p}")
    b.close()
    pw.stop()


if __name__ == "__main__":
    main()
