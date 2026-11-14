# ER 地面 / 地形套件索引(每种一个目录;Unity 资产真源在项目仓,这里放可重建描述;C1 起连生成器源码一起放)

| id | 套件 | 版本 | 批准 | 唯一参考 | 项目资产 | 重建 | 说明 |
|---|---|---|---|---|---|---|---|
| A1 | 联邦主干道人行道地砖 + 地缘砖 | v4f | 2026-11-02 勾哥过 | moco_street_crosswalk.png 裁 480,0,641,300 | Assets/Art/Lab/J01v7/A1 | A1KitGen.Build() | [A1/README.md](A1/README.md) |
| B1 | 沙滩海岸(楔形沙滩 + 草平压沙 + 浅水透沙 / 5 段色阶 / 软浪边的海面;沙上杂物和土边都否决) | v1 | 2026-11-14 勾哥过 | Boom Beach 整岛图 refs_bb/gou_1113_6.png(颜色、沙滩占比);mo.co 只学交界画法 | Assets/Shaders/Lab/LabBaseWater.shader + BaseV3EnvStep4Builder.cs(岸线 / 沙 / 水段) | BaseV3EnvStep4Builder.Build();src/ 有原样拷贝 | [SeaBeach/README.md](SeaBeach/README.md) |
| C1 | 草顶崖壁(阶梯岩体 + 每级一块圆肩垂边草盖;叶片和横向岩层都否决,不在库里) | v1.1 | 2026-11-14 勾哥过 | mo.co cl_1-28 裁 1250,410,2050,1000(只学形,颜色传场景自己的) | Assets/Scripts/Editor/Lab/Kits/GrassTopCliffKit.cs | GrassTopCliffKit.Make(tiers, params) | [GrassTopCliff/README.md](GrassTopCliff/README.md) |
