# 随手记 · Telegram bot 安装(给勾哥)

效果:用手机 Telegram 给自己的 bot 发消息 → 自动落进翼德的 `notes/inbox` → 翼德整理。
**bot 跑在 Google 云端(Apps Script),电脑关机也能记。** 一次性设置,约 10 分钟。

> 前提:翼德大脑放在 **Google Drive 同步盘**(onboard 时选的),这样 inbox 文件夹有 Drive ID。

## 步骤
1. **建 bot**:Telegram 里找 `@BotFather` → `/newbot` → 取名 → 拿到 **bot token**。
2. **拿 inbox 文件夹 ID**:在 Google Drive 网页打开你大脑的 `notes/inbox` 文件夹,地址栏 `folders/` 后面那串就是 **FOLDER_ID**。
3. **建脚本**:打开 https://script.google.com → 新建项目 → 把本目录 `Code.gs` 全部贴进去 → 填好顶部 `BOT_TOKEN` 和 `INBOX_FOLDER_ID`。
4. **部署**:右上"部署 → 新建部署 → 类型选 Web 应用 → 执行身份=我 → 谁可访问=任何人" → 部署 → 复制 **Web App URL**。
5. **注册 webhook**:把 `setWebhook()` 里的 `WEBAPP_URL` 填成上一步的 URL → 运行一次 `setWebhook` 函数(首次会要授权,点允许)。日志显示 `{"ok":true}` 即成功。
6. **测试**:给 bot 发一句话,它回"已记下";过会儿在 Drive `notes/inbox` 看到 `telegram-YYYY-MM.md`。

## 之后怎么用
- 手机随时发消息记想法;电脑这边 `/yide 笔记 整理` 把它们按时间/主题/项目归档,`/yide 笔记 <关键词>` 查询。

## 说明
- 免费额度对个人远够用;消息只进你自己的 Drive,不经第三方。
- 微信不做:无官方 API、封号风险、聊天记录不可导出(已评估)。
