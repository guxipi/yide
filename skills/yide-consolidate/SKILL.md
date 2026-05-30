---
description: 翼德(yide)整理记忆。当用户说"整理记忆/翼德整理一下/yide 整理一下/consolidate/清理大脑",或大脑里 lessons 越积越多、可能有重复或过时,或会话开始时提示"记忆整理到期/自动整理"时使用。合并重复、修正过时、把反复出现的教训升级为红线,冲突攒起来问用户。
---

# 翼德 · 整理记忆(consolidate)

目标:防止"记忆腐烂"。这是大脑长期可用的关键维护步骤(事件驱动:每次开会话若距上次 >24h 会被提醒)。

## 步骤

1. **盘点**:读取 `~/.yide/INDEX.md`、`lessons/` 下所有 `L-*.md`、以及 `.meta/inbox/`(待整理的原始提炼,若有)。

2. **两阶段对账**(借鉴 mem0 的 ADD/UPDATE/DELETE/NOOP)。对每条候选/已有记忆判定:
   - **ADD**:新的、不重复 → 保留/新建。
   - **UPDATE**:与已有同主题但更新更准 → 合并,旧的标 `status: superseded`(软删除,保留历史)。
   - **DELETE/ARCHIVE**:已过时或明确错误 → 标 `status: archived`,从 INDEX 移除。
   - **NOOP**:重复且无新信息 → 丢弃候选。

3. **去重合并**:同一主题的多条 lesson 合并成一条更一般化的规则(Reflexion 式归纳),保留最高 severity。

4. **升级反复犯的**:同类错误出现 ≥2 次 → 提升 severity,必要时并入 `core/hard-rules.md`,能硬拦截的加进 `.meta/hook-rules.json`(保守:正则要能精确命中)。

5. **冲突不自作主张**:新信息与旧记忆矛盾、又拿不准时,**不要擅自改**,写进 `~/.yide/.meta/conflicts.md` 等用户裁决。

6. **修订索引**:更新 `INDEX.md` 使其与现状一致;确认它仍在 ≤200 行的预算内。

7. **归档与重建索引**:把 `status: archived/superseded` 的 lesson 移到 `~/.yide/lessons/archive/`(运行时不再扫,保持活跃集精简);然后运行
   `node "${CLAUDE_PLUGIN_ROOT}/scripts/build-index.js"` 重建编译索引。

8. **打整理时间戳**:用 Bash 工具运行
   `node "${CLAUDE_PLUGIN_ROOT}/scripts/stamp-consolidate.js"`
   (写入 `~/.yide/.meta/last-consolidate.txt`,这样 SessionStart 的"整理到期"会重置 24 小时。)

9. **汇报**:简短列出本次做了什么(合并 N 条、归档 M 条、升级 K 条、待裁决 J 条),并把 conflicts 念给用户。

## 原则
- 软删除优先于硬删(标 status,不物理删除),保留可追溯历史。
- 拿不准就攒着问,绝不替用户做矛盾裁决(对应红线:不编造、不擅自大改)。
- 保持 core 精简,别让红线膨胀到 LLM 服从性下降(≤15 条)。
