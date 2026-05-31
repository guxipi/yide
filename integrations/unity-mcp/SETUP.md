# Unity MCP 接入(让翼德"看见"Editor)

默认翼德只能读 `.cs`/`.unity`/`.prefab` 文本。接上 Unity MCP 后,它能**看实时场景/Inspector、按 Play、跑测试读结果、读 Console 报错、查贴图导入设置**——把"盲改文件"升级成"在引擎里验证再改"。

> **opt-in,不随插件自动启用**(避免 Unity 没开时每次会话都报错、拖累 Claude)。想用再按下面接。

## 选型
用 **CoplayDev/unity-mcp**(MIT,最活跃,~40 工具含 `run_tests`/`read_console`/`manage_scene`)。无 Python 洁癖可换 IvanMurzak/Unity-MCP(.NET,带 win-x64 exe)。

## 安装(Windows)
1. **装 uv**(管 MCP server):管理员 PowerShell `irm https://astral.sh/uv/install.ps1 | iex`,重开终端。
2. **Unity 侧**:Package Manager → Add package from git URL:
   `https://github.com/CoplayDev/unity-mcp.git?path=/MCPForUnity#main`
   然后菜单 **Window → MCP for Unity → Configure All Detected Clients**(自动写 Claude Code 配置)。
3. **若没自动配上**,手动:
   ```
   claude mcp add --scope user --transport stdio coplay-mcp \
     --env MCP_TOOL_TIMEOUT=720000 -- uvx --python ">=3.11" coplay-mcp-server@latest
   ```
   (超时设长,因为跑测试/重编译慢。)
- WSL 跑 Claude、Unity 在 Windows:改用 HTTP transport + 端口转发(见 CoplayDev wiki)。

## 接上之后翼德能做(QA/把关升级)
- **编译门**:改完脚本 → 重编译 → `read_console`,有报错就拦。
- **测试门**:`run_tests`(EditMode/PlayMode)→ 读 pass/fail,红了不放行。
- **移动端审计**:查贴图压缩/Read-Write/包体/内存快照。
- **场景体检**:查丢失引用(MissingReferenceException 文本审查抓不到)。

## 风险(务必知道)
- **Unity 编辑器必须开着**,否则所有工具调用失败。
- 这些 server 能在编辑器里执行代码/改项目 → 视为完全信任;只对版本控制下的项目用,提交前看 diff。
- pre-1.0,版本会变;`@latest` 可能与 Unity 包版本漂移,上生产前 pin 版本。
