# gen_sheet.py — 打磨一屏的「一份数据 → 表格 payload + 知识库 md/manifest」生成器(翼德 polish 动作)
# 用法:
#   同目录放 meta.json {"date":"2026-10-02","screen":"简报页","sheet":"<url>","hint":"表格第 2 行用法说明"} 与 block_<id>.json(调研代理产出)
#   set POLISH_DIR=D:\screenshots\ER_<屏>_<日期>   (现状裁图 now_<id>.png 在此;产物 stage\payload<TAG>.json 与压缩后的图也落此)
#   set GEN_BLOCKS=P1,P2,P3,P4  GEN_START=4(表头在第 3 行)  GEN_TAG=   → python gen_sheet.py --kb
#   第二批:GEN_BLOCKS=B1,...  GEN_START=<空行后的行号>  GEN_TAG=_B2
# 然后在 Chrome MCP 里:file_upload payload 到页内 input → JS 读 JSON → __paste 各块 → file_upload 图 → __putImg 逐张(见 sheet_helpers.js)
# data.json -> (1) staged images (2) payload.json for the Sheets page JS (3) KB markdown + manifest
import json, os, html, sys
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.path.join(os.environ["POLISH_DIR"], "stage")      # POLISH_DIR = D:\screenshots\ER_<屏>_<日期>
NOW_DIR = os.environ["POLISH_DIR"]                         # now_<id>.png 现状裁图放这里
KB = os.environ.get("POLISH_KB", r"C:\DuckGames\Extraction\Claude Feature Docs\Competitive Research")
START_ROW = int(os.environ.get("GEN_START", "4"))          # row 3 = header
BLOCK_IDS = os.environ.get("GEN_BLOCKS", "P1,P2,P3,P4").split(",")
TAG = os.environ.get("GEN_TAG", "")
COLS = ["#", "现状图", "方向", "参考游戏", "对照图", "他们怎么做", "Action 候选(我们做什么)", "成本", "翼德建议", "勾哥拍板", "讨论备注", "来源"]

data = json.load(open(os.path.join(HERE, "meta.json"), encoding="utf-8"))
data["blocks"] = [json.load(open(os.path.join(HERE, f"block_{p}.json"), encoding="utf-8"))
                  for p in BLOCK_IDS if os.path.exists(os.path.join(HERE, f"block_{p}.json"))]
IMG = KB + "\\images\\"
for b in data["blocks"]:
    for i, r in enumerate(b["rows"]):
        r["id"] = f'{b["id"]}-{i+1}'
        if r.get("img") and not os.path.isabs(r["img"]):
            r["img"] = IMG + r["img"].replace("/", "\\")
os.makedirs(STAGE, exist_ok=True)

def stage(src, name):
    im = Image.open(src).convert("RGB")
    im.thumbnail((1100, 1100))
    out = os.path.join(STAGE, name + ".jpg")
    im.save(out, quality=86)
    return out

def td(s, style=""):
    base = "vertical-align:middle;white-space:normal;"
    return f'<td style="{base}{style}">{s}</td>'

REC_BG = {"★": "#fff2cc"}
pastes, images, heights, uploads = [], [], [], []
row = START_ROW
for b in data["blocks"]:
    # band row
    band = f'<td colspan="{len(COLS)}" style="font-weight:bold;background-color:#d9e8fb;color:#0b2545;vertical-align:middle;white-space:normal;font-size:12pt">{html.escape(b["id"])}  {html.escape(b["title"])}<br><span style="font-weight:normal;font-size:10pt">目标:{html.escape(b["goal"])}　|　现状根因:{html.escape(b.get("cause",""))}</span></td>'
    trs = [f"<tr>{band}</tr>"]
    band_row = row
    row += 1
    refs = [r for r in b["rows"] if r.get("img")]
    extras = [r for r in b["rows"] if not r.get("img")]
    first_ref = row
    for i, r in enumerate(refs + extras):
        is_ref = bool(r.get("img"))
        cells = [td(html.escape(r["id"]), "text-align:center;font-weight:bold;")]
        if i == 0:
            cells.append(f'<td rowspan="{len(refs)+len(extras)}" style="vertical-align:top;background-color:#f3f6fa"></td>')
        bg = "background-color:#fff9e6;" if r.get("rec", "").startswith("★") else ""
        cells.append(td(html.escape(r.get("dir", "")), "font-weight:bold;" + bg))
        cells.append(td(html.escape(r.get("game", "")), bg))
        cells.append(td("", bg))
        cells.append(td(html.escape(r.get("how", "")), bg))
        cells.append(td(html.escape(r.get("action", "")), bg))
        cells.append(td(html.escape(r.get("cost", "")), "text-align:center;" + bg))
        cells.append(td(html.escape(r.get("rec", "")), bg))
        cells.append(td("", bg))
        cells.append(td("", bg))
        src = r.get("src", "")
        cells.append(td(f'<a href="{html.escape(src)}">{html.escape(r.get("srcname","link"))}</a>' if src.startswith("http") else html.escape(src), bg))
        trs.append("<tr>" + "".join(cells) + "</tr>")
        if is_ref:
            name = r["id"].replace("-", "_")
            stage(r["img"], name)
            images.append({"range": f"E{row}", "file": name + ".jpg"})
            uploads.append(os.path.join(STAGE, name + ".jpg"))
        row += 1
    # current-state image goes in merged B cell
    nowname = "now_" + b["id"]
    stage(os.path.join(NOW_DIR, b["now_img"]), nowname)
    images.append({"range": f"B{first_ref}", "file": nowname + ".jpg"})
    uploads.append(os.path.join(STAGE, nowname + ".jpg"))
    if refs:
        heights.append({"from": first_ref, "to": first_ref + len(refs) - 1, "px": 190})
    pastes.append({"range": f"A{band_row}", "html": "<table>" + "".join(trs) + "</table>", "rows": [band_row, row - 1]})
    row += 1  # spacer

hdr = "".join(f'<td style="font-weight:bold;background-color:#1f3a5f;color:#ffffff;vertical-align:middle;text-align:center;white-space:normal">{c}</td>' for c in COLS)
payload = {"header": {"range": "A3", "html": f"<table><tr>{hdr}<td></td></tr></table>"},
           "hint": {"range": "A2", "html": f'<table><tr><td colspan="{len(COLS)}" style="color:#555555;white-space:normal">{html.escape(data["hint"])}</td></tr></table>'},
           "pastes": pastes, "images": images, "heights": heights,
           "widths": {"A": 55, "B": 300, "C": 110, "D": 120, "E": 330, "F": 220, "G": 330, "H": 50, "I": 170, "J": 90, "K": 200, "L": 80}}
json.dump(payload, open(os.path.join(STAGE, f"payload{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(uploads, open(os.path.join(HERE, f"uploads{TAG}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("rows used through", row - 1, "| images", len(images), "| payload bytes", os.path.getsize(os.path.join(STAGE, f"payload{TAG}.json")))
tot = sum(os.path.getsize(u) for u in uploads); print("upload total MB", round(tot / 1e6, 2))

# ---- KB markdown ----
if "--kb" in sys.argv:
    L = [f"# {data.get('screen','屏')}打磨:逐问题竞品对照 + Action 候选 — {data['date']}", "",
         f"> 表格本体(带左右对照图,勾哥拍板列):{data['sheet']}", f"> 现状截图:`{NOW_DIR}`。状态:**待勾哥讨论取舍,未施工**。", ""]
    M = [f"# Manifest — {data.get('screen','屏')}打磨对照图({data['date']})", "", "| 行 | 游戏 | 文件 | 展示内容 | 来源 |", "|---|---|---|---|---|"]
    for b in data["blocks"]:
        L += [f"## {b['id']} {b['title']}", "", f"- 目标:{b['goal']}", f"- 现状根因:{b.get('cause','')}", "",
              "| # | 方向 | 参考 | 他们怎么做 | Action 候选 | 成本 | 翼德建议 | 图 |", "|---|---|---|---|---|---|---|---|"]
        for r in b["rows"]:
            img = (os.path.relpath(r["img"], KB).replace("\\", "/") if r["img"].lower().startswith("c:") else r["img"]) if r.get("img") else ""
            L.append(f"| {r['id']} | {r.get('dir','')} | {r.get('game','')} | {r.get('how','')} | {r.get('action','')} | {r.get('cost','')} | {r.get('rec','')} | {('`'+img+'`') if img else ''} |")
            if img:
                M.append(f"| {r['id']} | {r.get('game','')} | `{img}` | {r.get('how','')} | {r.get('src','')} |")
        L.append("")
    open(os.path.join(KB, f"{data.get('screen','屏')}打磨对照_{data['date']}{TAG}.md"), "w", encoding="utf-8").write("\n".join(L))
    open(os.path.join(KB, f"_manifest_{data['date'][:7]}_{data.get('screen','屏')}打磨{TAG}.md"), "w", encoding="utf-8").write("\n".join(M) + "\n")
    print("KB written")
