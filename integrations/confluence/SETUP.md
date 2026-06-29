# Confluence 项目文档 · 给勾哥的傻瓜配置

**目的**:让翼德能读你写在 Confluence 的项目文档,蒸成 `CLAUDE.md`,以后做功能自动带项目背景。
**不改你习惯**:你照常在 Confluence 写;翼德只是把它读过来、提炼一份精简版。

---

## 方式一(最省事 · 免 token · 首次推荐)
1. 进你的 space → **空间设置 → 导出(Export)→ 选 HTML(或 XML)→ 导出**。
2. 浏览器会下个 **zip 到「下载」文件夹**。
3. 在终端里跟翼德说 **"翼德 吸收文档"** —— 它会**自动去下载夹找最新那个导出**,解压、读、蒸成 `CLAUDE.md`。
   (找不到就把 zip **拖进终端**,或贴路径。)— 蒸出的精简版落 `CLAUDE.md`(Claude Code 每次会话自动读)。
> 免 token、不撞限流、内容最全。适合第一次"全局理解"。

## 方式二(增量保鲜 · 配一次 token)
想让翼德以后**只拉改动的页、自动保鲜**,配个 API token(免费):
1. 浏览器开 **id.atlassian.com → Security → API tokens → Create API token**,复制下来。
2. 建文件 `~/.yide/.meta/confluence.json`,填:
   ```json
   { "site": "你的站点.atlassian.net", "email": "你的邮箱", "token": "粘贴token", "spaceKey": "你的space缩写" }
   ```
3. 以后说 **"翼德 更新文档"**,它就增量拉最新(平时也会 7 天内自动懒同步)。

---

## 说明
- **免费档够用**:普通 REST API 含在订阅里、不花钱;限流低但我们调用很少,基本撞不到。
- **token 存本地**(`~/.yide/.meta/`),**别提交到 git**;它只读你本就有权限的页。
- **自建版(Server/Data Center)**:接口不同,告诉翼德,会换法。
- 没配 token 也没关系:随时用**方式一**重新导出一次即可。
