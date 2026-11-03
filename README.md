# 小红书查询工具包 · 部署说明

> 用途：在任意一台电脑上部署「小红书只读查询能力」——扫码登录后可搜索笔记、看对标主页、抓笔记正文和图片。
> **只有查询，没有发布**。发布是账号主人自己在手机上做的事。

---

## 一、登录方式是什么（一句话讲清）

**网页版扫码登录**：

1. 电脑上用「带反检测的无头浏览器」打开小红书网页版
2. 脚本调平台接口生成一个登录二维码（`login_qr.png`）
3. 用**手机上已登录目标账号的小红书 App** 扫这个码 → 手机上点「确认登录」
4. 登录凭证（cookies）自动存到本地 `~/.xhs-mcp/cookies.json`
5. 以后这台电脑每次查询都自动带这个凭证，不用再扫

平台视角里，这就是一台正常的电脑在浏览网页。反检测层（stealth + 真实 UA + 拟人操作）负责让它不被一眼识别成脚本。

## 二、新电脑部署步骤（5 步）

### 1. 装 Python 3.10+

Windows：python.org 下载安装，勾选「Add to PATH」。
Mac：自带或 `brew install python`。

### 2. 装依赖

```bash
pip install playwright playwright-stealth qrcode pillow
```

国内网络慢就加镜像：

```bash
pip install playwright playwright-stealth qrcode pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 装浏览器内核

```bash
playwright install chromium
```

下载慢用镜像：

```bash
# Mac/Linux
PLAYWRIGHT_DOWNLOAD_HOST=https://cdn.npmmirror.com/binaries/playwright playwright install chromium
# Windows PowerShell
$env:PLAYWRIGHT_DOWNLOAD_HOST="https://cdn.npmmirror.com/binaries/playwright"; playwright install chromium
```

### 4. 登录

把这个文件夹整个拷到新电脑，然后：

```bash
python login_flow.py
```

跑起来后等几秒，`~/.xhs-mcp/login_qr.png` 会生成二维码——**用手机上已登录目标账号的小红书 App 扫它**（App 右上角扫一扫），手机上点确认。脚本自动检测登录成功并存好 cookies。

二维码几分钟过期，过期脚本会自动刷新一张。

### 5. 验证

```bash
python whoami.py
```

显示出账号昵称和小红书号就是通了。然后就能用 `scan.py`（关键词搜索）、`fetch_one.py`（单条笔记详情）、`list_notes.py`（主页笔记列表）这些脚本查资料了。

---

## 三、红线（每台电脑都要守，出事都是这里出的）

1. **绝对不要把 `cookies.json` 从一台电脑拷到另一台**。每台电脑自己扫码登录。拷凭证等于把同一个登录态铺到多台机器，平台侧立刻异常。
2. **一个账号只登一台电脑**。同一个号在多台电脑登录 = 多设备频繁登录记录，风控直接往上叠。想多台机器查询，就每台配一个不同的号。
3. **用可牺牲的小号登录，不要用主号、不要用养着的号**。自动化会话长期看总会被识别，别把值钱的号押上去。
4. **查询节奏放低**：一次会话抓十几条、隔几秒一条没问题；连续高速抓几百条，号和 IP 一起出事。
5. 这个包里**没有任何发布脚本，也请不要往里加**。发布一律手机端手动。
6. 登录遇到「IP 存在风险」提示：换网络（手机热点）再试，或等几小时。别反复重试。

## 四、常见问题

| 现象 | 处理 |
|---|---|
| `whoami.py` 显示未登录 | cookies 过期了，重跑 `login_flow.py` 重新扫码 |
| 二维码一直生成失败 | 网络出口被风控，换热点/换网络再跑 |
| 打开笔记页内容是空的 | 详情页要带 `xsec_token` 参数，从主页笔记列表里取（参考 `find_note.py`） |
| 想换号 | 删掉 `~/.xhs-mcp/cookies.json` 后重新跑登录脚本 |

## 五、文件说明

| 文件 | 作用 |
|---|---|
| `login_flow.py` | 生成二维码 + 监听扫码 + 存 cookies（登录入口） |
| `watch_login.py` | 单独监听扫码状态 |
| `whoami.py` | 验证当前登录的是哪个号 |
| `scan.py` | 关键词搜索，单次约抓 80–100 条 |
| `fetch_one.py` / `find_note.py` | 抓单条笔记的正文、话题、互动数据 |
| `list_notes.py` / `fetch_notes.py` | 抓某个账号主页的笔记列表 |
