# 翼德 · Playtest 冻帧标注反馈(playtest)

解决:试玩时手感/UI 的问题,事后靠记忆口述,丢三落四、定位不准。
做法:**Unity 里按一个键冻帧标注(语音为主、可打字)→ 工具自动抓"命中的 UI/物体 + 场景 + 上下文"→ 翼德本地转写 + 读截图 → 出带定位的问题清单 → 联合优化回流**。

> 比整段录屏强在:① 翼德拿到的是**游戏内部状态**(哪个 GameObject/Prefab/场景),能直通代码;② 一条标注 = 一个干净问题包,噪音低;③ 打字时**完全不用转写**,语音也走**本地 SenseVoice 离线转**,不上云、不跨境(适配你们在海外)。

## 铁律(勾哥只做这几件,其余全自动)
**① F8 开始录音 → ② 测/说出问题(中文) → ③ F8 停录(屏上自动出字,看一眼对不对、不对就改)→ ④ F8 保存 → 继续玩。** 不想说话就直接在框里打字。测完回 Claude Code 说"翼德 playtest",其余翼德全包。**别让勾哥做任何额外手动操作。**

## 首次:确认配好(没配先 guide,别假装能转写)
见 `integrations/playtest-capture/SETUP.md`(一次性):
1. 把 `templates/qa/PlaytestMarker.cs` 放进项目 Scripts 目录;`templates/qa/Editor/PlaytestMarkerWindow.cs` 和 `templates/qa/Editor/PlaytestAsrServer.cs` 放进任意 `Editor/` 文件夹。(自动在 Play 时生成,不用手挂;`#if UNITY_EDITOR(||DEVELOPMENT_BUILD)` 包住,不进正式包。)
2. 本地中文转写:装 Python + `pip install funasr`(首次拉 ~900MB 模型,纯 CPU 可跑)。**想要"停录即出字"**还要在标注窗口「⚙ 转写设置」里把 `asr_server.py` 路径指一次(见 SETUP 2.1)。**没装/没配也能用**,降级成"只用打字 + 上下文",事后 `翼德 playtest` 仍会批量补转。
3. 隐私:录的是麦克风,**全程本地处理、不外传**;不想录就只打字。

## 正常流程
1. 勾哥进 Playmode 玩,遇到问题按 **F8** → 画面冻住、自动截图(窗口里**大图、可点开放大**)+ 抓上下文 + 开始录音;**「翼德 标注」编辑器窗口**自动弹出(停靠在 Game 视图旁,**不挡游戏**),能看到命中元素。
2. 说完按 **F8 停录** → 几秒后**本地转写的中文自动填进打字框**,勾哥**当场确认/修改**(没配转写/没说话就直接打字)。再按 **F8**(或点绿钮)保存成一个 marker,解冻继续玩。`Esc` 取消当前这条。
3. 测完,回 Claude Code 说"**翼德 playtest**"。
4. 翼德跑(写文件,过一次审批):
   ```
   node ${CLAUDE_SKILL_DIR}/scripts/playtest.js
   ```
   (不带参=自动取 `QA/playtest` 最新一场;`--no-asr` 跳过转写。)它会:**补转**那些录制时没当场确认过文字的语音(已在 Unity 里确认的直接用 `note.txt`,不重转)+ 合并 + 读 `context.json` → 写 `manifest.json` + 打印速览。
5. 翼德**逐条 Read `shot.png`** 看画面,结合"勾哥说的(语音转写+打字)+ 命中元素路径"→ 出**带定位问题清单**:`[marker-03] 现象 → BattleHUD/TopBar/PauseBtn ← PauseButton.prefab(场景 Battle)→ 类型(UI/手感/逻辑/性能)`。
6. 接 **联合优化回流**(同 `qa.md` F.7):art-director(数值)+ ui-ux(设计)联合建议、PM challenge → 最佳方案供勾哥定夺 → 执行;能进 bug 的按 SOP 立项。

## 产物结构
```
项目/QA/playtest/session-<时间戳>/
├── marker-01/{shot.png, context.json, voice.wav?, note.txt?}
├── marker-02/...
└── manifest.json          # playtest.js 生成:每条 = 截图 + 命中元素 + 勾哥说的
```
`context.json` 关键字段:`scene / hitPath / hitSource(含 Prefab)/ resolution / fps / version / timeInGame / typedNote`。

## 降级(诚实,别硬编)
- **没装 Python/funasr 或转写失败**:用打字 + 上下文,明说"这次没转语音,要更准就装下本地转写或补一句"。
- **没麦克风**:只存截图 + 上下文 + 打字。
- **指针下没命中对象**:`hitPath` 标"(无命中)",翼德靠截图判断,别脑补路径。
- 拿不准的列进"待勾哥确认"。

## 文件去哪
- 标注产物 → **项目** `QA/playtest/`;**截图/录音不进 git**(让勾哥把 `QA/playtest/` 加进 `.gitignore`)。
- 产物是项目证据,**不进 ~/.yide**;可复用经验(教训)才进大脑。

## 范围(v1)
- **做**:F8 冻帧标注(截图+抓状态+语音+打字)· 本地 SenseVoice 转写 · 翼德出带定位问题清单 · 接回流。
- **暂不做**:整段屏幕录屏(老代码 `playtest-rec.bat` 留作可选,见 SETUP「可选」段)· 真机非 Editor 下的标注 UI(v1 以 Editor 为主)· 逐词时间戳。
- ⚠️ **整条链路(Unity 工具 / 录音 / 本地转写)需在勾哥真 Unity + 真环境端到端验**,翼德跑时如实报,别冒充已验证。
