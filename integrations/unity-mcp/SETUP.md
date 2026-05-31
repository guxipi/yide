# 给勾哥:接 Unity MCP(让翼德"看见"你的 Unity)

接之前,翼德只能读 `.cs` 文本、凭经验猜;接上后它能**真跑测试、读真实报错、看场景、查贴图/内存**——从"看不见屏幕的顾问"变成"在引擎里验证再说话"。

> 这是**可选**的。不接,翼德照常用(只是把关靠静态规则)。**接了之后,Unity 编辑器必须开着**才有效。
> 约 10 分钟,一次性。下面按 Windows 写。

---

## 前提
- 已装 Claude Code、能跑 `/yide`。
- 你的 Unity 工程能正常打开。

## 第 1 步 · 装 uv(MCP server 的运行时)
**管理员** PowerShell 跑:
```powershell
irm https://astral.sh/uv/install.ps1 | iex
```
**关掉终端重开**,输入 `uv --version`,能打印版本号就对了 ✅(打不出来=没进 PATH,重启电脑再试)。

## 第 2 步 · Unity 工程里装桥接包
1. 打开你的 Unity 工程 → 菜单 **Window → Package Manager**。
2. 左上 **＋ → Add package from git URL…**,粘贴:
   ```
   https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main
   ```
   回车,等它装好(出现 "MCP for Unity" 包即成 ✅)。
3. 菜单出现 **Window → MCP for Unity** → 打开 → 点 **Configure All Detected Clients**。
   - 它会自动找到 Claude Code 并写好连接配置(看到 Claude Code 那行变绿/✓ 即成 ✅)。

## 第 3 步 · 让 Editor 开着
保持这个 Unity 工程**开着不关**。翼德要"看引擎"时,靠的就是这个在跑的 Editor。

## 第 4 步 · 在 Claude Code 里验证
1. **重启 Claude Code**(让它加载新 MCP)。
2. 输入 `/mcp` —— 列表里能看到 Unity 的 server(如 `coplay-mcp` / `MCP for Unity`)就连上了 ✅。
3. 试一句:`翼德，读一下 Unity Console 有没有报错` —— 它能真去读 Console,就成功了 🎉
   (没装包/Editor 没开时它会说"没接 MCP、没在引擎验证过"——这是诚实,不是 bug。)

---

## 如果第 2 步没自动配上 Claude Code(手动兜底)
在系统终端跑一次:
```
claude mcp add --scope user --transport stdio coplay-mcp --env MCP_TOOL_TIMEOUT=720000 -- uvx --python ">=3.11" coplay-mcp-server@latest
```
(超时设长,因为跑测试/重编译慢。)

## 接上之后翼德多了什么
- **编译门**:改完脚本→读 Console,有报错先拦;
- **测试门**:真跑 EditMode/PlayMode,红了不放行;
- **手游审计**:看贴图压缩/包体/内存快照;
- **场景体检**:揪丢失引用(`MissingReferenceException` 文本审查抓不到)。

## 排错 / 注意
- **`/mcp` 里没有它** → 八成 Editor 没开,或 `uv` 没进 PATH(回第 1 步),或没重启 Claude Code。
- **工具调用一直失败** → Editor 是不是关了?MCP 要 Editor 在跑。
- **安全**:这套能在编辑器里执行代码/改工程 → 只对**版本控制下**的工程用,提交前看 diff。
- **版本**:CoplayDev 还在快速迭代,`@latest` 可能和 Unity 包版本漂移;真出问题就在 Package Manager 里更新包、或 pin 一个版本。
- 不想用了:`/mcp` 里禁用,或 `claude mcp remove coplay-mcp`。翼德自动退回静态把关。
