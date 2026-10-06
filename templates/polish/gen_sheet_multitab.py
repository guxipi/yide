# gen_main.py — ER 主玩法打磨:block_G*.json → 每个分页一份 payload(HTML 表+图片放置+行高)+ 总览 payload + 知识库 md/manifest
# 基于 yide templates/polish/gen_sheet.py,改成多分页 + 现状图拼版 + 缺图容错。
# 用法: python gen_main.py [--kb]
import json, os, html, sys, glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
STAGE = os.path.join(ROOT, "stage")
BASE = os.path.join(ROOT, "baseline")
IMG = r"C:\DuckGames\Extraction\Claude Feature Docs\Competitive Research\images" + "\\"
KB = r"C:\DuckGames\Extraction-w2\Claude Feature Docs\Competitive Research"
SHEET = "https://docs.google.com/spreadsheets/d/16OUTwM1m0_Bs_3C73P8nubIxl3wV5EpOFi62NOWOtHU"
DATE = "2026-10-06"
START_ROW = 4
COLS = ["#", "现状图", "方向", "参考游戏", "对照图", "他们怎么做", "Action 候选(我们做什么)", "成本", "翼德建议", "勾哥拍板", "讨论备注", "来源"]
TABS = [
    ("1 战斗手感", ["G01", "G03", "G05", "G06", "G07"]),
    ("2 角色·敌人·Boss", ["G02", "G04", "G18"]),
    ("3 场景", ["G13", "G14", "G15", "G16", "G17", "G24"]),
    ("4 UI·物品·指引", ["G10", "G08", "G09", "G11", "G12"]),
    ("5 节奏·数值·演出·联动", ["G19", "G20", "G25", "G21", "G22", "G23"]),
]
HINT = "用法:每个色带=一个问题(目标|现状根因)。带图行=竞品做法+我们可抄的 action;无图行=额外 action(冗余,供取舍)。黄底=翼德首选。你在「勾哥拍板」列写 ✓/✗/改,备注列写想法;定案后表尾出施工单。成本 S≈半天 M≈1–2天 L≈3天+。"
now_map = {}
p = os.path.join(HERE, "now_map.json")
if os.path.exists(p):
    now_map = json.load(open(p, encoding="utf-8"))
os.makedirs(STAGE, exist_ok=True)


def stage(src, name, box=(1100, 1100)):
    im = Image.open(src).convert("RGB")
    im.thumbnail(box)
    out = os.path.join(STAGE, name + ".jpg")
    im.save(out, quality=85)
    return out


def stage_now(bid, files):
    """1–3 张现状图横向拼成一张(竖屏截图并排)。"""
    ims = []
    for f in files[:3]:
        fp = f if os.path.isabs(f) else os.path.join(BASE, f)
        if os.path.exists(fp):
            im = Image.open(fp).convert("RGB")
            im.thumbnail((700, 1500))
            ims.append(im)
    if not ims:
        return None
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims) + 14 * (len(ims) - 1)
    sheet = Image.new("RGB", (w, h), "white")
    y = 0
    for im in ims:
        sheet.paste(im, ((w - im.width) // 2, y))
        y += im.height + 14
    out = os.path.join(STAGE, f"now_{bid}.jpg")
    sheet.save(out, quality=85)
    return out


def td(s, style=""):
    return f'<td style="vertical-align:middle;white-space:normal;{style}">{s}</td>'


def load(bid):
    fp = os.path.join(HERE, f"block_{bid}.json")
    if not os.path.exists(fp):
        return None
    b = json.load(open(fp, encoding="utf-8"))
    b["id"] = bid
    rows = []
    for r in b["rows"]:
        if r.get("img"):
            ip = r["img"] if os.path.isabs(r["img"]) else IMG + r["img"].replace("/", "\\")
            if os.path.exists(ip):
                r["img"] = ip
            else:
                print("MISSING IMG", bid, r["img"])
                r.pop("img")
        rows.append(r)
    refs = [r for r in rows if r.get("img")]
    extras = [r for r in rows if not r.get("img")]
    b["rows"] = refs + extras
    for i, r in enumerate(b["rows"]):
        r["id"] = f"{bid}-{i+1}"
    b["nrefs"] = len(refs)
    return b


all_blocks, summary = [], []
for ti, (tab, ids) in enumerate(TABS, 1):
    pastes, images, heights = [], [], []
    row = START_ROW
    for bid in ids:
        b = load(bid)
        if not b:
            print("NO BLOCK", bid)
            continue
        all_blocks.append(b)
        n = len(b["rows"])
        band = (f'<td colspan="{len(COLS)}" style="font-weight:bold;background-color:#d9e8fb;color:#0b2545;vertical-align:middle;white-space:normal;font-size:12pt">'
                f'{html.escape(bid)}  {html.escape(b["title"])}<br><span style="font-weight:normal;font-size:10pt">目标:{html.escape(b.get("goal",""))}　|　现状根因:{html.escape(b.get("cause",""))}</span></td>')
        trs = [f"<tr>{band}</tr>"]
        band_row = row
        row += 1
        first = row
        for i, r in enumerate(b["rows"]):
            star = r.get("rec", "").startswith("★")
            bg = "background-color:#fff2cc;" if star else ""
            cells = [td(html.escape(r["id"]), "text-align:center;font-weight:bold;")]
            if i == 0:
                cells.append(f'<td rowspan="{n}" style="vertical-align:top;background-color:#f3f6fa">&nbsp;</td>')
            cells.append(td(html.escape(r.get("dir", "")), "font-weight:bold;" + bg))
            cells.append(td(html.escape(r.get("game", "")), bg))
            cells.append(td("&nbsp;" if r.get("img") else "", bg))
            cells.append(td(html.escape(r.get("how", "")), bg))
            cells.append(td(html.escape(r.get("action", "")), bg))
            cells.append(td(html.escape(r.get("cost", "")), "text-align:center;" + bg))
            cells.append(td(html.escape(r.get("rec", "")), bg))
            cells.append(td("", bg))
            cells.append(td("", bg))
            src = r.get("src", "")
            cells.append(td(f'<a href="{html.escape(src)}">{html.escape(r.get("srcname","link"))}</a>' if src.startswith("http") else html.escape(src), bg))
            trs.append("<tr>" + "".join(cells) + "</tr>")
            if r.get("img"):
                name = r["id"].replace("-", "_")
                try:
                    stage(r["img"], name)
                    images.append({"range": f"E{row}", "file": name + ".jpg"})
                except Exception as e:
                    print("STAGE FAIL", r["img"], e)
            row += 1
        nf = now_map.get(bid) or ([b["now_img"]] if b.get("now_img") else [])
        if stage_now(bid, nf):
            images.append({"range": f"B{first}", "file": f"now_{bid}.jpg"})
        else:
            print("NO NOW IMG", bid)
        if b["nrefs"]:
            heights.append({"from": first, "to": first + b["nrefs"] - 1, "px": 190})
        pastes.append({"id": bid, "range": f"A{band_row}", "html": "<table>" + "".join(trs) + "</table>", "rows": [band_row, row - 1]})
        stars = [r for r in b["rows"] if r.get("rec", "").startswith("★")]
        summary.append({"id": bid, "tab": tab, "title": b["title"], "goal": b.get("goal", ""), "cause": b.get("cause", ""),
                        "nref": b["nrefs"], "nact": n, "row": band_row, "stars": stars})
        row += 1
    hdr = "".join(f'<td style="font-weight:bold;background-color:#1f3a5f;color:#ffffff;vertical-align:middle;text-align:center;white-space:normal">{c}</td>' for c in COLS)
    payload = {"tab": tab,
               "title": {"range": "A1", "html": f'<table><tr><td colspan="{len(COLS)}" style="font-weight:bold;font-size:14pt;color:#0b2545">ER 主玩法打磨 · {html.escape(tab)}({DATE})</td></tr></table>'},
               "hint": {"range": "A2", "html": f'<table><tr><td colspan="{len(COLS)}" style="color:#555555;white-space:normal">{html.escape(HINT)}</td></tr></table>'},
               "header": {"range": "A3", "html": f"<table><tr>{hdr}</tr></table>"},
               "pastes": pastes, "images": images, "heights": heights, "last_row": row - 1}
    json.dump(payload, open(os.path.join(STAGE, f"payload_T{ti}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"T{ti} {tab}: rows through {row-1} | blocks {len(pastes)} | images {len(images)} | bytes {os.path.getsize(os.path.join(STAGE, f'payload_T{ti}.json'))}")

# ---- 总览 payload ----
OC = ["#", "分页", "问题", "目标", "现状根因", "参考图", "Action 数", "翼德首选(前 4 条)", "勾哥优先级", "备注"]
oh = "".join(f'<td style="font-weight:bold;background-color:#1f3a5f;color:#ffffff;text-align:center;vertical-align:middle">{c}</td>' for c in OC)
otr = [f"<tr>{oh}</tr>"]
for s in summary:
    st = "<br>".join("★ " + html.escape(r.get("action", "")) + f"({r.get('cost','')})" for r in s["stars"][:4])
    otr.append("<tr>" + td(s["id"], "font-weight:bold;text-align:center;") + td(html.escape(s["tab"])) + td(html.escape(s["title"]), "font-weight:bold;")
               + td(html.escape(s["goal"])) + td(html.escape(s["cause"])) + td(str(s["nref"]), "text-align:center;") + td(str(s["nact"]), "text-align:center;")
               + td(st) + td("") + td("") + "</tr>")
tot_a = sum(s["nact"] for s in summary); tot_r = sum(s["nref"] for s in summary)
ov = {"title": {"range": "A1", "html": f'<table><tr><td colspan="{len(OC)}" style="font-weight:bold;font-size:14pt;color:#0b2545">ER 主玩法(Expedition 远征)打磨 · 总览({DATE})— {len(summary)} 个问题 / {tot_r} 张对照图 / {tot_a} 条 action</td></tr></table>'},
      "hint": {"range": "A2", "html": f'<table><tr><td colspan="{len(OC)}" style="color:#555555;white-space:normal">每个问题的竞品对照与全部 action 在对应分页(下方 tab)。先在本页「勾哥优先级」列标 P0/P1/P2/不做,我按优先级排施工批次;细项在各分页「勾哥拍板」列勾。</td></tr></table>'},
      "table": {"range": "A3", "html": "<table>" + "".join(otr) + "</table>"}, "rows": len(summary)}
BATCHES = [('B1 参数级快赢(约 1–2 天,立刻脱离「开发版」观感)', '镜头俯角 70°→55–60°+角色放大(G06/G02);地面降饱和+阴影冷紫+描边 2.5(G14/G24);hitstop/屏震下放小怪+伤害数字分级(G01);EffectsConfig 空槽、命中音、BGM/环境音填槽(G07/G22);截图/release 隐藏 Cheats·DBG(G10)'), ('B2 丛林竖切片(T0→T2 一条主路做成标杆)', '地面重做+主题道具族+地标+风摆/水沫/浮尘(G13/G14/G15);POI 营地 kit+敌人主题绑定(G17);遮挡与碰撞审计(G16);Boss 接入远征+登场演出(G18)'), ('B3 局内 UI 全套换皮(设计稿源头改 SuperCasual+Cairo)', 'HUD 重做;小地图/撤离读条/结算 prefab 化;背包与搜刮面板;contract 追踪条;死亡三段演出;图标集自产(G10/G09/G08/G11/G23)'), ('B4 战斗演出与音乐', '五类枪演出语言+握持点节点化(G03);敌人前摇/受击/体型分档(G04/G05);VFX flipbook 自产(G07);统一事件横幅+撤离舱+落地演出(G21);BGM 探索/战斗/撤离三态(G22)'), ('B5 节奏·数值·玩法 option', '风险圈数值缩放旋钮进 ConfigHub、可见威胁条(G19);推荐战力+携带价值(G20);副目标+定时事件(G25);首次交互引导+地标光柱(G12)')]
btr = ['<tr><td colspan="3" style="font-weight:bold;background-color:#1f3a5f;color:#ffffff">翼德建议的施工批次(先后顺序,供讨论)</td><td colspan="5" style="font-weight:bold;background-color:#1f3a5f;color:#ffffff">内容(对应问题)</td><td style="font-weight:bold;background-color:#1f3a5f;color:#ffffff;text-align:center">勾哥拍板</td><td style="font-weight:bold;background-color:#1f3a5f;color:#ffffff">备注</td></tr>']
for n, c in BATCHES:
    btr.append('<tr><td colspan="3" style="font-weight:bold;vertical-align:middle;white-space:normal;background-color:#fff2cc">' + html.escape(n) + '</td><td colspan="5" style="vertical-align:middle;white-space:normal">' + html.escape(c) + '</td><td></td><td></td></tr>')
ov["batches"] = {"range": "A%d" % (3 + len(summary) + 3), "html": "<table>" + "".join(btr) + "</table>"}
json.dump(ov, open(os.path.join(STAGE, "payload_T0.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("overview:", len(summary), "topics |", tot_r, "refs |", tot_a, "actions")

# ---- KB markdown ----
if "--kb" in sys.argv:
    L = [f"# 主玩法(Expedition)打磨:逐问题竞品对照 + Action 候选 — {DATE}", "",
         f"> 表格本体(带左右对照图,勾哥拍板列):{SHEET}", f"> 现状截图:`{BASE}`;代码现状:`{ROOT}\\RECON_A/B/C.md`。状态:**待勾哥讨论取舍,未施工**。", ""]
    M = [f"# Manifest — 主玩法打磨对照图({DATE})", "", "| 行 | 游戏 | 文件 | 展示内容 | 来源 |", "|---|---|---|---|---|"]
    for b in all_blocks:
        L += [f"## {b['id']} {b['title']}", "", f"- 目标:{b.get('goal','')}", f"- 现状根因:{b.get('cause','')}", "",
              "| # | 方向 | 参考 | 他们怎么做 | Action 候选 | 成本 | 翼德建议 | 图 |", "|---|---|---|---|---|---|---|---|"]
        for r in b["rows"]:
            img = r["img"][len(IMG):].replace("\\", "/") if r.get("img") else ""
            L.append(f"| {r['id']} | {r.get('dir','')} | {r.get('game','')} | {r.get('how','')} | {r.get('action','')} | {r.get('cost','')} | {r.get('rec','')} | {('`images/'+img+'`') if img else ''} |")
            if img:
                M.append(f"| {r['id']} | {r.get('game','')} | `images/{img}` | {r.get('how','')} | {r.get('src','')} |")
        L.append("")
    open(os.path.join(KB, f"主玩法打磨对照_{DATE}.md"), "w", encoding="utf-8").write("\n".join(L))
    open(os.path.join(KB, f"_manifest_2026-10_主玩法打磨.md"), "w", encoding="utf-8").write("\n".join(M) + "\n")
    print("KB written")
