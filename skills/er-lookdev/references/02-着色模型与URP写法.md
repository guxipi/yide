# 02 风格化着色模型和 URP 手写 shader

来源标记:〔读〕〔测〕〔推〕同 01。主要来源:Valve TF2 论文和 GDC 2008 幻灯、Riot VALORANT shader 文章、Cyanilux URP shader 教程和 CustomLighting.hlsl、Unity 6 文档和 Graphics 仓库源码、Unity 的 Survival Kids 文章、Catlike Coding、Roystan。工程是 Unity 6000.3 / URP 17.3,下面的关键字按这个版本写;换版本先核包里的源码。

记号:N 法线,L 指向光,V 指向相机,H = normalize(L+V)。

## 一、着色项目录

### 漫反射

- Lambert:`saturate(dot(N,L))`。背光半球全是零,背面只剩环境光,发平。
- Half-Lambert(Valve):`pow(0.5*dot(N,L)+0.5, γ)`,点积不截断,整个球面都有形体变化。Half-Life 用 γ=2,TF2 用 γ=1 再交给 ramp。VALORANT 也用它让暗部不死黑。〔读〕
- 包裹光:`saturate((dot(N,L)+w)/(1+w))`,w=1 就是 Half-Lambert。〔推,通用写法〕
- ramp 贴图(TF2、VALORANT 的 Gradient Lambert):把 N·L 映射到 0..1 去采一张一维渐变图。TF2 的 ramp 分三段:受光段灰渐变、交界处一小段偏红、阴影段偏冷;采出来再乘 2,所以图的右端是中灰。美术能控制交界位置、软硬和交界色。代价是每盏灯多一次采样。〔读〕
- smoothstep 分带:`smoothstep(阈值-软, 阈值+软, halfLambert)`,不采贴图,边缘自带抗锯齿。VALORANT 的武器选了它。手机上默认用这个,要交界色时再加一项。〔读;后半句推〕

### 阴影上色(保饱和、转色相)

- 不要 `col *= 灰`。写成两个颜色之间插值:`lit = albedo * lightColor`;`shade = albedo * _ShadeTint`(tint 是有饱和度、带色相偏移的颜色);`col = lerp(shade, lit, t)`,`t = 分带(N·L) * shadowAtten`。固有色乘一个有饱和度的颜色,彩度保住或上升;乘灰只降明度。〔推〕
- 投影衰减在分带之前或和分带相乘进同一个 t,投影和背光面就共用一条边、一个颜色。〔读 Roystan〕
- 交界色(可选):`col += _TermColor * albedo * 4*t*(1-t)`。〔推〕
- 逐像素 RGB 转 HSV 再转回在手机上贵(TF2 当年因为这个放弃了按色相索引的 ramp)。色相偏移烘进 tint 里。〔读〕
- Survival Kids 的做法:一个 renderer feature 出四分之一分辨率的屏幕贴图,沿光的方向往前看采阴影图得到一个混合值,着色时在三种阴影色之间混,影子边缘有渐变色。同一个阴影色也喂给它的遮蔽。〔读〕
- URP 自带的 Subtractive 模式有 `_SubtractiveShadowColor`,是一个带色的阴影下限。〔读〕

### 环境光

- 单色:没有形体。
- 三色渐变(天 / 赤道 / 地):`lerp(地, 赤道, saturate(N.y+1))` 再 `lerp(…, 天, saturate(N.y))`。Unity 的 Gradient 环境光模式就是它,会烘进 SH。地面色那一档就是最便宜的地面反弹。〔推〕
- SH:`SampleSH(normalWS)`。裸调它不认光照图和 APV;要认就走 `SAMPLE_GI` 那条路(见下)。〔读 Cyanilux〕
- TF2 用六色方向环境光让角色「落在环境里」;VALORANT 取最近的间接光缓存样本,漫反射和高光分别缩放,并按地图区域钳制最暗和最亮值保可读性。〔读〕

### Rim

- TF2:`fr = (1 - N·V)^4`,再乘 `N·U`(U 是世界向上)截正,所以 rim 只出现在朝上的法线上,颜色取沿视线方向的环境光。粗网格上菲涅尔 rim 会过宽。〔读〕
- Roystan:`rim = smoothstep(_RimAmount-0.01, _RimAmount+0.01, (1-dot(V,N)) * NdotL)`,乘 NdotL 让 rim 只在受光侧。〔读〕

### 高光和玻璃

- 卡通高光:`smoothstep(0.005, 0.01, pow(NdotH * lit, gloss²))`。乘 lit 让影子里没有高光。〔读〕
- VALORANT:高光主要来自美术画的静态 HDR 全景图(粗糙度放在 mip 里),只有接近镜面的玻璃才用真实场景反射。〔读〕
- matcap:`uv = normalize(mul((float3x3)UNITY_MATRIX_V, N)).xy*0.5+0.5`,约 10 条指令。平的面整面一个颜色,窗玻璃这类平面要用按视线对齐的版本(约 17 条)或用反射向量去查。〔读 bgolus;后半句推〕

### 遮蔽和投影怎么进公式

见 03 第四节。要点:URP 自己的规则是烘焙遮蔽只乘间接光,屏幕空间遮蔽对直接光按 Direct Lighting Strength 部分作用,两者用 `min()` 合并,不相乘。

## 二、URP 手写 shader 要点

### 必须有的 pass

| LightMode | 干什么 | 不写会怎样 |
|---|---|---|
| UniversalForward | 主着色 | — |
| ShadowCaster | 投影 | 不投影 |
| DepthOnly | 深度图 | 深度预通道里没有它 |
| DepthNormals | 法线图 | 屏幕空间遮蔽(用 Depth Normals 源时)没有它 |
| Meta | 给烘焙器固有色和自发光 | 烘光照图时它不贡献反弹色和自发光 |

`UsePass` 借 URP Lit 的 pass 可能破坏 SRP Batcher 兼容(借来的 pass 用的是 Lit 自己的材质常量块,和本 shader 的不一致),资料建议每个 pass 自己写,公共声明放 `HLSLINCLUDE`。借了之后在材质或 shader 的 Inspector 上看「SRP Batcher」那一行是否 compatible,再决定留不留。〔读 Cyanilux;核法推〕

写自己的 ShadowCaster / DepthOnly 时包含 `Shaders/ShadowCasterPass.hlsl`、`DepthOnlyPass.hlsl`,前面要先包含 `CommonMaterial.hlsl` 和 `SurfaceInput.hlsl`;不要包含 `LitInput.hlsl`(它会重定义常量块)。有顶点位移时两个 pass 的顶点函数也要带位移。〔读〕

### SRP Batcher 规矩

- 每个 pass 声明完全相同的 `CBUFFER_START(UnityPerMaterial)`,里面放所有暴露的非贴图属性和 `_ST`、`_TexelSize`。
- 全局量(全局影色这类)放在常量块外,用 `Shader.SetGlobal*` 设。
- MaterialPropertyBlock 会破坏合批。
- 材质开关用 `shader_feature_local`,运行时或管线切换的用 `multi_compile`。运行时才打开的 `shader_feature` 变体可能在打包时被剥掉。〔读〕

### 关键字(Unity 6000.1 起)

```
#pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
#pragma multi_compile _ _ADDITIONAL_LIGHTS_VERTEX _ADDITIONAL_LIGHTS
#pragma multi_compile_fragment _ _ADDITIONAL_LIGHT_SHADOWS
#pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
#pragma multi_compile _ _CLUSTER_LIGHT_LOOP
#pragma multi_compile_fragment _ _SCREEN_SPACE_OCCLUSION
#pragma multi_compile_fragment _ _LIGHT_COOKIES
#pragma multi_compile _ LIGHTMAP_ON
#pragma multi_compile _ DIRLIGHTMAP_COMBINED
#pragma multi_compile _ LIGHTMAP_SHADOW_MIXING
#pragma multi_compile _ SHADOWS_SHADOWMASK
#pragma multi_compile _ EVALUATE_SH_MIXED EVALUATE_SH_VERTEX
#include_with_pragmas "Packages/com.unity.render-pipelines.universal/ShaderLibrary/ProbeVolumeVariants.hlsl"
#pragma multi_compile_fog
#pragma multi_compile_instancing
```

- Forward+ 的关键字在 6000.0 及更早叫 `_FORWARD_PLUS`,6000.1 起改名 `_CLUSTER_LIGHT_LOOP`。〔读〕
- 只加用得上的:每多一行变体数翻倍。不烘光照图就不加 `LIGHTMAP_ON` 那几行;但只要开始烘,少了 `LIGHTMAP_ON` 采样会悄悄返回零。〔读〕

### 主光和投影

```
#include ".../universal/ShaderLibrary/Core.hlsl"
#include ".../universal/ShaderLibrary/Lighting.hlsl"
float4 sc = TransformWorldToShadowCoord(positionWS);   // 在片元里算;在顶点里算,多于一级级联时会坏
Light key = GetMainLight(sc);    // .direction .color .shadowAttenuation .distanceAttenuation .layerMask
```

### 点光源(Forward 和 Forward+ 通用写法)

```
InputData inputData = (InputData)0;      // 变量必须叫 inputData,必须清零
inputData.positionWS = positionWS;
inputData.normalizedScreenSpaceUV = GetNormalizedScreenSpaceUV(positionCS);
uint count = GetAdditionalLightsCount();   // Forward+ 下恒为 0,靠下面的宏循环
LIGHT_LOOP_BEGIN(count)
    Light l = GetAdditionalLight(lightIndex, positionWS, shadowMask);
    half3 c = l.color * (l.distanceAttenuation * l.shadowAttenuation);
    // 着色
LIGHT_LOOP_END
```

- `GetAdditionalLight(i, posWS)` 两个参数的版本不带阴影;要点光投影用三个参数的版本并开 `_ADDITIONAL_LIGHT_SHADOWS`。
- Forward+ 下额外的方向光要单独一段循环(`URP_FP_DIRECTIONAL_LIGHTS_COUNT`)。
- 最便宜的档:`_ADDITIONAL_LIGHTS_VERTEX` + `VertexLighting(positionWS, normalWS)`,只在 Forward 下有。
- 卡通化的点光:衰减过一道 `step` 或分带;Cyanilux 给点光的卡通高光留零。〔读〕

### 烘焙光、探针、APV

```
// 顶点
OUTPUT_LIGHTMAP_UV(IN.lightmapUV, unity_LightmapST, OUT.lightmapUV);
OUTPUT_SH4(positionWS, normalWS, GetWorldSpaceNormalizeViewDir(positionWS), OUT.vertexSH, OUT.probeOcclusion);
// 片元
half3 bakedGI = SAMPLE_GI(IN.lightmapUV, IN.vertexSH, normalWS);   // APV 开着时参数表不同,照包里 Lit 的写法
MixRealtimeAndBakedGI(key, normalWS, bakedGI);
```

宏的参数表各版本改过,动手前打开工程里 `Packages/com.unity.render-pipelines.universal/Shaders/LitForwardPass.hlsl` 照抄。Meta pass 用 `UniversalVertexMeta` / `UniversalFragmentMeta`;烘焙器写死认 `_MainTex`、`_Color`、`_Cutoff` 这几个名字,自发光要清掉 `EmissiveIsBlack` 标志才会被烘。〔读 Catlike〕

### 屏幕空间遮蔽

```
#if defined(_SCREEN_SPACE_OCCLUSION)
AmbientOcclusionFactor aoF = GetScreenSpaceAmbientOcclusion(normalizedScreenSpaceUV);
// aoF.indirectAmbientOcclusion 乘环境光;aoF.directAmbientOcclusion 乘主光色
#endif
```

SSAO 的 After Opaque 模式不需要 shader 支持,它是事后整屏盖一层,所有东西(包括受光面)一起压暗。〔读文档;后半句推〕

### 雾

`#pragma multi_compile_fog`;顶点 `ComputeFogFactor(positionCS.z)`,片元 `MixFog(color, fogFactor)`。

## 三、资料点名的坑

- 插值后的法线要重新归一化。
- `ComputeScreenPos` 在 URP 11 起弃用。
- Survival Kids 量过:URP 自带 SSAO 在他们要的大半径下约 4 ms,所以换成了改过的 MSVAO;后处理只留色调映射、bloom、调色。
- VALORANT:光照图只存漫反射;场景只用静态光照;角色不投影。
- 没有 `fixed` 类型,用 `half`。

## 没读到、待补

NedMakesGames「Writing Unity URP Shaders with Code」系列(403);带色阴影和色相偏移没找到专门的一手资料,上面的插值写法是推断加 TF2、Survival Kids 的做法归纳;VALORANT 文章里的公式是图片,没提取到数字。
