# 随手记 · Telegram bot 安装(给勾哥)

效果:用手机 Telegram 给自己的 bot 发消息 → 自动落进 Drive 的 **`yide-inbox`** 文件夹 → `翼德 笔记 整理` 时搬进大脑并归档。
**bot 跑在 Google 云端(Apps Script),电脑关机也能记。** 一次性设置,约 10 分钟。

> 前提:大脑迁 git 后**不在同步盘**了,所以 inbox 用一个**独立 Drive 文件夹** `yide-inbox`(唯一保留的 Drive 依赖)。本机把它的路径写进指针 `~/.yide-inbox-location`,`note` 整理时据此搬文件进大脑。
> (大脑还在同步盘、没迁 git 的旧机器,FOLDER_ID 仍可指大脑的 `notes/inbox`——两种都行,重点是 note 整理能读到。)

## 步骤
1. **建 bot**:Telegram 里找 `@BotFather` → `/newbot` → 取名 → 拿到 **bot token**。
2. **拿 inbox 文件夹 ID**:在 Google Drive 网页打开 **`yide-inbox`** 文件夹(迁移时建的,如 `H:\My Drive\yide-inbox`),地址栏 `folders/` 后面那串就是 **FOLDER_ID**。
3. **建脚本**:打开 https://script.google.com → 新建项目 → 把本目录 `Code.gs` 全部贴进去 → 填好顶部 `BOT_TOKEN` 和 `INBOX_FOLDER_ID`(填 `yide-inbox` 的 ID)。
4. **部署**:右上"部署 → 新建部署 → 类型选 Web 应用 → 执行身份=我 → 谁可访问=任何人" → 部署 → 复制 **Web App URL**。
5. **注册 webhook**:把 `setWebhook()` 里的 `WEBAPP_URL` 填成上一步的 URL → 运行一次 `setWebhook` 函数(首次会要授权,点允许)。日志显示 `{"ok":true}` 即成功。
6. **测试**:给 bot 发一句话,它回"已记下";过会儿在 Drive `yide-inbox` 看到 `telegram-YYYY-MM.md`。

## 之后怎么用
- 手机随时发消息记想法;电脑这边 `翼德 笔记 整理` 把 `yide-inbox` 的新文件**搬进 git 大脑**并按时间/主题/项目归档(收尾自动 commit+push),`翼德 笔记 <关键词>` 查询。

## 说明
- 免费额度对个人远够用;消息只进你自己的 Drive,不经第三方。
- 微信不做:无官方 API、封号风险、聊天记录不可导出(已评估)。

> **连不上 / 没生效?** 先跑一次 **翼德 体检**(`node scripts/doctor.js`)自查,再深挖。
