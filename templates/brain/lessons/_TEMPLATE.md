---
id: L-0000              # 递增编号
date: 2026-01-01        # 记录日期(绝对日期)
severity: 5             # 1-10。≥8 进 hard-rules 永远带;高的可上 hook 硬拦截
scope: ["*"]            # 何时触发:glob(如 "**/*.cs")或场景描述(如 "写邮件时")
enforce: context        # context(软注入) | hook(Claude Code 硬拦截)
status: active          # active | superseded | archived
---
## 错误
<!-- AI 当时做错了什么 -->

## 规则(正向、具体、可验证)
<!-- 写成"该怎么做",不要写"不要怎样"。配 IMPORTANT 强调。
     反例:不要用 print 调试
     正例:**IMPORTANT** 调试输出一律用 logging(之前因为用了 print 出过错) -->

## 触发那次的原文
<!-- 当时你的原话,保留语气,方便日后回看 -->
