// 翼德 · Telegram 随手记 bot(跑在 Google Apps Script,serverless,电脑关机也能记)。
// 收到的每条消息 → 追加到 Google Drive 里翼德的 notes/inbox(随后 Drive 同步到电脑,翼德整理)。
// 配置见同目录 SETUP.md。把下面两个常量填好后,部署为 Web App 并 setWebhook。

const BOT_TOKEN = 'PUT-YOUR-BOTFATHER-TOKEN-HERE';
const INBOX_FOLDER_ID = 'PUT-YOUR-DRIVE-INBOX-FOLDER-ID-HERE'; // 翼德 notes/inbox 文件夹的 Drive ID

function doPost(e) {
  try {
    const update = JSON.parse(e.postData.contents);
    const msg = update.message || update.edited_message;
    if (!msg || !msg.text) return ok();

    const now = new Date();
    const stamp = Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm');
    const line = `\n## ${stamp}\n${msg.text}\n`;

    // 每月一个文件:telegram-YYYY-MM.md,追加写入
    const fname = 'telegram-' + Utilities.formatDate(now, Session.getScriptTimeZone(), 'yyyy-MM') + '.md';
    const folder = DriveApp.getFolderById(INBOX_FOLDER_ID);
    const it = folder.getFilesByName(fname);
    if (it.hasNext()) {
      const f = it.next();
      f.setContent(f.getBlob().getDataAsString() + line);
    } else {
      folder.createFile(fname, `---\nsource: telegram\n---\n${line}`, MimeType.PLAIN_TEXT);
    }

    reply(msg.chat.id, '🗡️ 已记下,翼德下次开工会归类整理。');
    return ok();
  } catch (err) {
    return ok(); // 永不抛错给 Telegram,避免它重试风暴
  }
}

function reply(chatId, text) {
  UrlFetchApp.fetch(`https://api.telegram.org/bot${BOT_TOKEN}/sendMessage`, {
    method: 'post',
    payload: { chat_id: String(chatId), text: text },
    muteHttpExceptions: true,
  });
}
function ok() { return ContentService.createTextOutput('ok'); }

// 部署成 Web App 后,运行一次这个函数注册 webhook(把 URL 换成你的 Web App URL)
function setWebhook() {
  const WEBAPP_URL = 'PUT-YOUR-DEPLOYED-WEBAPP-URL-HERE';
  const res = UrlFetchApp.fetch(
    `https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${encodeURIComponent(WEBAPP_URL)}`,
    { muteHttpExceptions: true });
  Logger.log(res.getContentText());
}
