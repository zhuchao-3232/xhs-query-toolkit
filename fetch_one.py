"""按笔记 id 抓详情并下载图片。

用法: python fetch_one.py <note_id> [xsec_token] [--outdir DIR]
"""
import json, sys, time
from pathlib import Path
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
          topComments:(U(com.list)||[]).slice(0,15).map(c=>S(U(c).content).replace(/\\n/g,' '))};
}"""


def main():
    nid = sys.argv[1]
    tok = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else ""
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

    url = f"https://www.xiaohongshu.com/explore/{nid}"
    if tok:
        url += f"?xsec_token={tok}&xsec_source=pc_search"
    page.goto(url, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)
    d = page.evaluate(READ)
    if not (d.get("title") or d.get("desc")):
        page.wait_for_timeout(6000)
        d = page.evaluate(READ)

    print("=" * 78)
    print(f"【{d.get('title')}】 作者 {d.get('author')} ({d.get('authorId')})")
    print(f"赞{d.get('likes')} 藏{d.get('collects')} 评{d.get('comments')} 转{d.get('shares')} "
          f"图{len(d.get('imgs') or [])}张")
    print("=" * 78)
    print((d.get("desc") or "(无正文)")[:2500])
    if d.get("tags"):
        print("标签:", " ".join(d["tags"]))
    if d.get("topComments"):
        print("-- 评论 --")
        for c in d["topComments"]:
            print("  ·", c[:90])

    for i, img in enumerate(d.get("imgs") or [], 1):
        if not img:
            continue
        try:
            r = ctx.request.get(img, timeout=30000)
            body = r.body()
            ext = ".jpg" if body[:3] == b"\xff\xd8\xff" else (".png" if body[:8] == b"\x89PNG\r\n\x1a\n" else ".webp")
            fp = outdir / f"{nid}_{i}{ext}"
            fp.write_bytes(body)
            print(f"[图{i}] {len(body)}B -> {fp}", flush=True)
        except Exception as e:
            print(f"[图{i} 失败] {str(e)[:80]}")

    Path("/tmp/fetch_one.json").write_text(json.dumps(d, ensure_ascii=False, indent=2))
    print("明细 -> /tmp/fetch_one.json")
    b.close()
    pw.stop()


if __name__ == "__main__":
    main()
