# Unity SmartMerge(UnityYAMLMerge)一次性配置

Git 管 Unity 的头号日常痛 = scene/prefab 合并冲突。Unity 自带 **UnityYAMLMerge**(SmartMerge)能按 YAML 语义自动合大部分,剩下的才丢给你手动。配一次,永久生效。

## 前提
- Unity 项目已用 **Force Text** 序列化(Edit → Project Settings → Editor → Asset Serialization = Force Text)。Unity 6 默认就是。

## 1. 找到 UnityYAMLMerge.exe
随 Unity 编辑器安装,通常在:
```
<Unity 安装目录>\Editor\Data\Tools\UnityYAMLMerge.exe
```
Hub 装的典型路径(版本号按实际):
```
C:\Program Files\Unity\Hub\Editor\6000.3.5f2\Editor\Data\Tools\UnityYAMLMerge.exe
```

## 2. 写进全局 .gitconfig(把下面的路径换成你机器上的真路径)
在 `~/.gitconfig` 追加(注意 Windows 路径用正斜杠或双反斜杠):
```ini
[merge]
    tool = unityyamlmerge
[mergetool "unityyamlmerge"]
    trustExitCode = false
    keepBackup = false
    cmd = "'C:/Program Files/Unity/Hub/Editor/6000.3.5f2/Editor/Data/Tools/UnityYAMLMerge.exe' merge -p \"$BASE\" \"$REMOTE\" \"$LOCAL\" \"$MERGED\""
```
或命令行等价(免手写):
```powershell
git config --global merge.tool unityyamlmerge
git config --global mergetool.unityyamlmerge.trustExitCode false
git config --global mergetool.unityyamlmerge.keepBackup false
git config --global mergetool.unityyamlmerge.cmd "'C:/Program Files/Unity/Hub/Editor/6000.3.5f2/Editor/Data/Tools/UnityYAMLMerge.exe' merge -p \"`$BASE\" \"`$REMOTE\" \"`$LOCAL\" \"`$MERGED\""
```

## 3. 让 .unity/.prefab/.asset 走这个 merge(项目 .gitattributes)
项目根 `.gitattributes` 加(没有就建):
```
*.unity  merge=unityyamlmerge
*.prefab merge=unityyamlmerge
*.asset  merge=unityyamlmerge
```

## 4. 冲突时怎么用
```
git merge <branch>        # 撞了 .unity/.prefab 冲突
git mergetool             # UnityYAMLMerge 自动合大部分,合不了的留标记
```
剩余冲突按 YAML 语义手动裁决(见 `templates/brain/style/unity.md` 的「scene/prefab 冲突处置」)。

## 验证
`node scripts/doctor.js` 的「Unity SmartMerge」项应变 ✅(它查 `.gitconfig` 里有没有 `unityyamlmerge`)。

## 排错
先跑一次 **翼德 体检**(`node scripts/doctor.js`)——它会告诉你 .gitconfig 配没配、路径对不对。
