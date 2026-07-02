# 翼德 · 体检(doctor)

出问题时别只会"找咕鸡"——先自诊断。一屏 ✅/⚠️/❌ + 每项修复指引。

## 怎么做
1. 用 Bash 跑:`node "${CLAUDE_SKILL_DIR}/scripts/doctor.js"`
2. 把输出**原样念给勾哥**,再对 ❌/⚠️ 项给一句人话解释 + 下一步。

## 检查项(doctor.js 覆盖)
- **大脑指针链**:`~/.yide-location` → 大脑目录存在且含 `INDEX.md` + `core/identity.md`。❌ 常见根因:**指针多写了一层**(如 `…/My Drive/yide/yide-brain`,正确应指到**直接含 INDEX.md** 那层)。修:把 `~/.yide-location` 内容改成正确大脑根目录。
- **hook 活动**:近 7 天有没有 hook 写过状态。久了 → 确认插件已 `/plugin marketplace update guji-tools` + `/reload-plugins`。
- **版本同步**:插件版本 vs 大脑 `plugin-version.txt`。不一致 → 下次开会话自动 migrate;有冲突跑 `翼德 update`。
- **skill 预算**:`SLASH_COMMAND_TOOL_CHAR_BUDGET` 是否 ≥40000。没配 → 长 skill 描述会被**静默截断**(技能不触发)。修:`~/.claude/settings.json` 的 `"env"` 里加 `"SLASH_COMMAND_TOOL_CHAR_BUDGET": "40000"`。
- **本机私有状态**:`~/.yide-local` 目录(会话级易变状态落点)。首次会话自动建,不算错。
- **Unity SmartMerge**:`.gitconfig` 是否配 `unityyamlmerge`。没配 → scene/prefab 冲突只能手撕。修:见 `integrations/unity-smartmerge/SETUP.md`。
- **可选项**:adb / Coplay MCP / STT —— 只报未配置,不算错(按需才配)。

## 铁律
- doctor 只**读**、只诊断,绝不自动改配置/大脑;修复动作交给勾哥或对应 SETUP。
- 每次 integrations 里"连不上/没生效"类问题,**先建议跑一次体检**再深挖。
