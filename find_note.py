"""按关键词搜笔记 -> 命中目标标题 -> 下载笔记图片与正文。

用法: python find_note.py "云梦泽服务表" [--outdir DIR] [--max N]
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

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
  const ii=U(n.interactInfo)||{}; const u=U(n.user)||{};
  const com=U(f.comments)||{};
  return {noteId:S(n.noteId), title:S(n.title), desc:S(n.desc),
          author:S(u.nickname), authorId:S(u.userId),
          likes:S(ii.likedCount), collects:S(ii.collectedCount),
          comments:S(ii.commentCount), shares:S(ii.shareCount),
          imgs:(U(n.imageList)||[]).map(i=>S(U(i).urlDefault||U(i).url)),
          tags:(U(n.tagList)||[]).map(t=>S(U(t).name)),
          topComments:(U(com.list)||[]).slice(0,12).map(c=>S(U(c).content).replace(/\\n/g,' '))};
}"""


def harvest_search(page, kw, scrolls=3):
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
        page.wait_for_timeout(3000)
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
                        "token": it.get("xsec_token", "")})
    return out


def main():
    kw = sys.argv[1] if len(sys.argv) > 1 else "云梦泽服务表"
    outdir = Path("/Users/chaoren/WorkBuddy/2026-10-08-21-52-58/xhs_refs")
    if "--outdir" in sys.argv:
        outdir = Path(sys.argv[sys.argv.index("--outdir") + 1])
    outdir.mkdir(parents=True, exist_ok=True)

    pw = sync_playwright().start()
    b = pw.chromium.launch(headless=True)
    ctx = b.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                        locale="zh-CN", timezone_id="Asia/Shanghai")
    ctx.add_cookies(json.loads((D / "cookies.json").read_text()))
    page = ctx.new_page()
    Stealth().apply_stealth_sync(page)

    print(f"搜索关键词: {kw}", flush=True)
    notes = harvest_search(page, kw)
    print(f"命中 {len(notes)} 条：", flush=True)
    for i, n in enumerate(notes[:25], 1):
        print(f"  {i:>2}. 赞{n['likes']:<6} {n['author'][:14]:<16} {n['title'][:40]}", flush=True)

    # 命中目标
    key = re.sub(r"服务表|新版|红薯|❤️|\(|\)", "", kw).strip() or kw
    hits = [n for n in notes if key and key in n["title"]] or \
           [n for n in notes if "服务表" in n["title"]] or notes[:3]
    print(f"\n锁定候选 {len(hits)} 条", flush=True)

    results = {}
    for n in hits[:3]:
        url = f"https://www.xiaohongshu.com/explore/{n['id']}"
        if n["token"]:
            url += f"?xsec_token={n['token']}&xsec_source=pc_search"
        try:
            page.goto(url, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            d = page.evaluate(READ)
            if not (d.get("title") or d.get("desc")):
                page.wait_for_timeout(5000)
                d = page.evaluate(READ)
            results[n["id"]] = d
            print("\n" + "=" * 78)
            print(f"【{d.get('title')}】 作者 {d.get('author')} 赞{d.get('likes')} "
                  f"藏{d.get('collects')} 评{d.get('comments')} 图{len(d.get('imgs') or [])}张")
            print("=" * 78)
            print((d.get("desc") or "(无正文)")[:1500])
            if d.get("topComments"):
                print("  -- 评论 --")
                for c in d["topComments"]:
                    print("   ·", c[:80])
            # 下载图片
            for i, img in enumerate(d.get("imgs") or [], 1):
                if not img:
                    continue
                ext = ".webp"
                try:
                    r = ctx.request.get(img, timeout=30000)
                    body = r.body()
                    if body[:3] == b"\xff\xd8\xff":
                        ext = ".jpg"
                    elif body[:8] == b"\x89PNG\r\n\x1a\n":
                        ext = ".png"
                    fp = outdir / f"{n['id']}_{i}{ext}"
                    fp.write_bytes(body)
                    print(f"   [图{i}] {len(body)}B -> {fp}", flush=True)
                except Exception as e:
                    print(f"   [图{i} 失败] {str(e)[:80]}")
        except Exception as e:
            print(f"[失败 {n['id']}] {str(e)[:120]}")
        time.sleep(1)

    p = Path("/tmp") / "find_note.json"
    p.write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n明细 -> {p}")
    b.close()
    pw.stop()


if __name__ == "__main__":
    main()
