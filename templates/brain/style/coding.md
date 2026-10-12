# 写代码风格 Coding Style

> 按需读。Unity 手游把关规则见 [[unity]](PostToolUse lint 的依据)。

## 命名与格式
- 跟随周围代码风格,不擅自统一格式(这条优先于下面的直白命名)。

### 直白命名(AI 和人都要秒懂"这是哪个系统、做什么")
- 宁长勿短:`CalculateAsyncPvPDefendPower()` 好过 `GetDefPwr()`。
- 函数 = 动词 + 系统前缀 + 完整名词宾语;变量用完整词,布尔带 `is/has/can/should`。
- 跨系统概念带系统名前缀(`AsyncPvP` / `Trade` / `Clan` / `Economy`),别用裸 `power` / `result` / `data`。
- 禁机械缩写(`Pwr` / `Def` / `Mgr` / `Calc` / `Cfg` / `Tmp`),领域共识缩写除外(`HP` / `UI` / `HQ` / `Id` / `Vfx`)。循环计数器和 lambda 短参豁免。

## 注释、测试、日志
- 注释只在关键 / 非显而易见处写;Extraction 中等密度,其他项目尽量不写。
- 玩法相关以 PlayMode 真跑为准;纯逻辑才用 EditMode。
- 项目有日志封装就用封装,没有就直接 `Debug.Log`,别为此新造一个(Extraction 属于没有的)。
- 不写没必要的 try-catch;边界处(外部 API、用户输入)才校验。

## 偏好
- 讨厌过度工程、为"以后"加抽象、半成品、加没要求的东西;喜欢贴合现有架构、最小改动。
