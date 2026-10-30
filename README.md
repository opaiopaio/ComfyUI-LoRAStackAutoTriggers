# ComfyUI-LoRAStackAutoTriggers

一个 ComfyUI 节点包，含**两个**节点，共用同一套「LoRA 堆叠 + 自动触发词提取 + 可视化选词」：

| 节点 | 作用 |
|---|---|
| **LoRA Stack Auto Triggers** | 产出 `LORA_STACK` + 提示词/元数据，交给任意 Apply 节点 |
| **LoRA Stack Apply** | 普通应用器：`LORA_STACK` + `MODEL`（+可选 `CLIP`）→ `MODEL/CLIP`。**没装 easy-use 也能直接用** |
| **LoRA Stack Apply (Anima Remap)** | 同上，额外做 Anima 跨代（28 / 40 / 52 层）block 重映射 → 多一个 `REMAP_INFO` |

---

## 声明

本项目是一个**整合型二次开发作品**，并非从零原创。它将两个开源 ComfyUI 项目的核心能力融合到一个节点中：

- 以 [jakechai/ComfyUI-JakeUpgrade](https://github.com/jakechai/ComfyUI-JakeUpgrade) 的 `CR_LoRAStack_JK`（LoRA 堆叠节点）的**功能形态为蓝本**，保留其堆叠/开关/分强度/链式串联/提示词与元数据输出等完整能力。
- 将 [idrirap/ComfyUI-Lora-Auto-Trigger-Words](https://github.com/idrirap/ComfyUI-Lora-Auto-Trigger-Words) 的**触发词自动提取逻辑**（Civitai API 查询 + safetensors 训练元数据解析 + 切片选择器）移植进来，并为每个 LoRA 槽位增加了实时预览。

本项目代码独立编写、独立维护，与上述两个上游项目无附属关系。

## 借用 / 致谢

本项目站在以下项目的肩膀上，在此致谢：

| 借用内容 | 来源项目 | 说明 |
|---|---|---|
| 触发词提取核心逻辑 | [idrirap/ComfyUI-Lora-Auto-Trigger-Words](https://github.com/idrirap/ComfyUI-Lora-Auto-Trigger-Words) | `load_and_save_tags` / `get_metadata` / `sort_tags_by_frequency` / `parse_selector` 等函数的移植与改进 |
| LoRA 堆叠节点形态 | [jakechai/ComfyUI-JakeUpgrade](https://github.com/jakechai/ComfyUI-JakeUpgrade) | `CR_LoRAStack_JK` 的输入/输出设计与堆叠机制 |
| 上游上游 | [Extraltodeus/LoadLoraWithTags](https://github.com/Extraltodeus/LoadLoraWithTags) | Auto-Trigger-Words 项目本身 fork 自此项目 |

> 移植自 Auto-Trigger-Words 的逻辑在本项目中做了若干改进：`requests` 请求增加超时、缓存文件原子写入、异常时返回空列表而非崩溃、`save_hash` 处理 `None` 不报错。

## 功能特性

### 1. 自动触发词提取（每个 LoRA 独立）
- **双来源**：
  - **Civitai API**：通过 LoRA 文件的 SHA256 哈希查询 `model-versions/by-hash`，获取 `trainedWords`。
  - **训练元数据**：读取 safetensors 文件头的 `__metadata__`，解析 `ss_tag_frequency`，按训练频次降序排序。
- 两来源**合并去重**（Civitai 在前，元数据在后），预览中标注每个词的来源。
- 本地缓存（`loras_tags.json`），命中缓存不联网；`force_fetch` 可强制刷新。

### 2. 可视化选词（v1.1.0）
- 每槽位一个 **`⚙ 触发词 i`** 按钮，打开选择器弹窗：变体预设 / 片段剔除 / 训练标签搜索 / 自由编辑 + **鼠标划选**。
- 节点上只显示一行摘要（`已选 N 段 / M 字：…`），不再因长触发词把节点撑高。

### 3. 变体与片段
- civitai 的一条 `trainedWords` 通常是**一整句**触发词（Default、各服装…），选择器按"变体"整句列出。
- 载入变体后按逗号切成**片段 chip**，点一下剔除（如 `see-through mouth mask`）、再点恢复。

### 4. 触发词权重
- 每槽位 `trigger_weight`，≠1.0 时把每个片段包装为 `(片段:权重)`。

### 5. LoRA 堆叠（保留 JK 全部能力）
- 每节点 4 个 LoRA 槽位；多余通过 `lora_stack` 输入口串联下一节点。
- 每槽：开关 / 名称 / 模型强度 / CLIP强度 / `⚙ 触发词` 按钮 / 触发词权重 / 触发词摘要。
- **模型与 CLIP 权重独立控制**：CLIP 调 0 = 不影响 CLIP（模型照常生效），不再因 CLIP=0 整个禁用。

### 6. 合并输出
- `LORA_PROMPT`：有触发词输出触发词；无触发词输出 `<lora:名:权重>` 兜底（`fallback_to_filename` 控制）。
- `LORA_MetaData`：LoRA 名 + 可选 SHA256 哈希。
- `LORA_STACK`：标准三元组，供 Apply 节点加载。

---

## 节点：LoRA Stack Auto Triggers

### 输入
**每槽位（1..4）**：`开关` / `名称` / `模型强度` / `CLIP强度` / **`⚙ 触发词` 按钮** / `触发词权重` / `触发词摘要`（单行）

> `trigger_selector` 在界面上隐藏，由 `⚙ 触发词` 弹窗写入；存的是**文本**而非索引，换 LoRA 或重新拉取后不会错位。

**节点级**：
- `save_hash` - 元数据是否含 SHA256[:12]
- `force_fetch` - 强制从 Civitai 重新拉取
- `fallback_to_filename` - 无触发词时输出 `<lora:名:权重>` 兜底（ON，默认）；OFF 则该 LoRA 不进 prompt

**可选输入**：`lora_stack` / `lora_prompt` / `lora_metadata`（用于链式续接）

### 输出
| 输出 | 内容 |
|---|---|
| `LORA_STACK` | LoRA 堆栈三元组 `(name, model_weight, clip_weight)`，供 Apply 节点加载 |
| `LORA_PROMPT` | 有词出词；无词兜底 `<lora:名:权重>` |
| `LORA_MetaData` | LoRA 名（+ 可选哈希） |

### 权重行为
| model_weight | clip_weight | 结果 |
|---|---|---|
| ≠0 | 0 | 仅模型 |
| 0 | ≠0 | 仅 CLIP |
| ≠0 | ≠0 | 模型 + CLIP |
| 0 | 0 | 跳过（无意义）|

---

## 安装

把 `ComfyUI-LoRAStackAutoTriggers` 文件夹放入 ComfyUI 的 `custom_nodes` 目录，重启 ComfyUI。

依赖：`requests`（ComfyUI 通常已自带）。

## 用法

1. 节点搜索 `LoRA Stack Auto Triggers` 添加
2. 选中 LoRA，摘要行显示 `已选 N 段 / M 字：…`
3. 点 **`⚙ 触发词 i`** 打开选择器：

| 页签 | 用途 |
|---|---|
| **变体 N** | civitai 的整句触发词（Default / 各服装…）逐条列出，**点一条即载入** |
| **片段 chip** | 载入变体后按逗号切成词片，**点一下剔除**（如 `see-through mouth mask`），再点恢复 |
| **训练标签 N** | safetensors 训练集标签全量，带搜索，点一下追加（多数与角色无关，仅作补充） |
| **自由编辑** | 直接改文本；**鼠标划选一段后点「应用选区」**，只注入这一段 |

4. `[应用全部]` / `[应用选区]` 写回该槽位
5. 可选 `trigger_weight` 把每段包成 `(段:权重)`
6. 运行 -> 检查 `LORA_PROMPT` / `LORA_MetaData` / `LORA_STACK`

## 触发词取值方式

`trigger_selector_i` 支持四种写法（按优先级）：

| 写法 | 行为 |
|---|---|
| **空**（默认） | 使用**第一条** civitai 变体（不再全选） |
| 自由文本 | 原样注入（选择器写回的就是这种） |
| `["a","b"]` | JSON 数组，逗号连接 |
| `0, 3, 5:8` / `:` | 旧切片语法，兼容 1.0.0 工作流；`:` 仍是"全部变体 + 训练标签" |

> 从 1.0.0 升级：旧工作流里存的 `:` 依旧按全选执行（行为不变）；新节点默认空值，只取第一条变体。

## 节点二 & 三：应用器

本包提供两个应用器，都是 easy-use「应用LoRA堆」的**替代品**（顺带解决"没装 easy-use 就没法用本包"的问题）：

| 节点 | 选项 | 适用 |
|---|---|---|
| **LoRA Stack Apply** | 只有 `bypass` / `weight_multiplier` / `apply_clip` | 普通模型，干净 |
| **LoRA Stack Apply (Anima Remap)** | 上面三个 + `enable_remap` / `target_model` / `source_model` / `remap_mode` / `extend_strength` | Anima 跨代 |

两者的端口顺序都是 **model → clip（可选）→ lora_stack（可选）**。ComfyUI 总是把必接端口画在可选端口之前，所以 `lora_stack` 放在 optional 里才能排在 `clip` 之后。

### 为什么它必须站在"应用节点"的位置上

`comfy.sd.load_lora_for_models()` 是**当场**把 LoRA delta 按当前索引写进 ModelPatcher 的。也就是说经过「应用LoRA堆」之后，权重已经按**错误的层号**算好并挂上去了——**下游节点无法反悔**。

所以 remap 只能在"加载 LoRA 之后、应用之前"发生：

```
❌ stack → 应用LoRA堆 → [remap 节点]            ← 无效（水已经倒进杯子）
✅ stack → [LoRA Stack Apply (Anima Remap)]    ← 替代掉应用节点
```

### 接线

```
Checkpoint ─模型─┐
           ─CLIP─┤
LoRA Stack Auto Triggers ─LORA_STACK─→ [LoRA Stack Apply (Anima Remap)] ─模型/CLIP→ 采样器
```

### 输入

| 输入 | 说明 |
|---|---|
| `model` | **必接**。目标模型；Auto 探测目标代就靠它的层数 |
| `lora_stack` | **必接**。来自任意产出 `LORA_STACK` 的节点（不限于本包） |
| `clip`（可选） | 不接则所有 CLIP 权重被忽略 |
| `bypass` | 透传（不应用任何 LoRA），做 A/B 对比用 |
| `enable_remap` | 关掉 = 纯应用器（不改键）。非 Anima 模型开不开都一样 |
| `target_model` | Auto / Anima (28 layers) / Anima 2.9B (40 layers) / Anima 3.8B (52 layers) |
| `source_model` | 同上 —— **LoRA 是哪一代**；Auto 会误判"只改早期层的 LoRA"，拿不准就手选 |
| `remap_mode` | `Keys only (recommended)` / `Extend to new layers (experimental)` |
| `extend_strength` | 仅 Extend 模式用；1.0 = 原样复制源块 delta，线性缩放 |
| `weight_multiplier` | 全局倍率，把 stack 里所有权重统一放大/缩小（1.0 = 不变） |
| `apply_clip` | OFF = 完全不碰文本编码器（所有 CLIP 权重强制 0，仅作用于模型） |

### 输出

`MODEL` / `CLIP` / `REMAP_INFO`

`REMAP_INFO` 逐条写明做了什么：

```
target: Anima 2.9B (40 layers)
applied: 1 lora(s)
zzz_remielle_anima_v2-rift1000: 28->40 remapped (840 moved, 0 dropped)  [w=0.85, clip=0]
```

### 两种 remap 模式

| 模式 | 做法 | 效果 |
|---|---|---|
| **Keys only**（推荐先用） | 只把块索引搬到正确位置 | 新增的 12 层拿不到该 LoRA 的 delta，**效果比在原版模型上弱** |
| **Extend** | 额外把每个源块的 delta 复制到"由它插入出来的"新层，×`extend_strength` | 更接近原版强度，但是 best-effort 猜的（那些层训练时还不存在） |

### 与其它 Anima 补丁插件共存

社区有两个"全局 patch"实现（`ComfyUI-Anima-2.9B-loraPatch`、`ComfyUI-Anima-LoRA-ControlNet-Patch`），它们 monkeypatch 全局 `comfy.lora.load_lora`。本节点**不 monkeypatch**，只改自己加载的那份 state dict；改完后在它们眼里已是"新代原生 LoRA"，因此**不会双重重映射**。装一个就够。

### 方向限制

只支持"老的 → 新的"（28→40、28→52、40→52）。反过来（52 层 LoRA 用在 28 层模型上）**直接报错**：那些层在模型上根本不存在。

### 健壮性

- `NaN` / `Inf` 权重一律按 **0** 处理（条目跳过）。否则 `NaN != 0` 会被判成"启用"，把 NaN 强度灌进模型 → 全灰/全黑图且不报错
- SDXL 风格的 `input_blocks` / `output_blocks` **不会**被误认成 Anima 块
- 权重为 0 的条目、`"None"` 条目、空 stack 都会被安全跳过

## 语言 / Language

节点**标题、分类、说明与 tooltip** 按**系统语言**自动切换中文/英文；选词弹窗按**浏览器语言**切换。

| 判定 | 结果 |
|---|---|
| Windows 系统 UI 语言为中文，或 `LANG`/`LC_ALL`/`LC_MESSAGES` 以 `zh` 开头 | 中文 |
| 其他 | English |

强制指定：设环境变量 `OPNODES_LANG=zh`（或 `en`）后重启 ComfyUI。启动日志会打印当前语言。

> 下拉菜单的**取值**（Auto (detect) / Anima 2.9B (40 layers) / Keys only (recommended) 等）故意**不翻译**：ComfyUI 会把下拉取值存进工作流，翻译后换语言打开会变成未知值。只翻译标题、分类与提示文字。
## 文件结构

```
ComfyUI-LoRAStackAutoTriggers/
├── __init__.py                  # 入口（注册三个节点 + 路由 + web）
├── oplorast_slots.py            # 两个节点共用的槽位/触发词逻辑
├── oplorast_node.py             # 节点一：LoRAStackAutoTriggers（stack 构建）
├── oplorast_apply.py            # 节点二/三：两个应用器（普通 / Anima remap）
├── i18n.py                      # 中英双语（按系统语言自动切换）
├── anima_arch.py                # Anima 层数映射表（纯数据，可单测）
├── anima_remap.py               # 键名识别 / 层数探测 / state dict 重写
├── oplorast_utils.py            # 触发词逻辑（移植自 ATW）+ 后端路由
├── web/js/oplorast_lora_triggers.js  # 前端选择器（两个节点共用）
├── tests/test_anima_remap.py    # 离线单测：py -3 tests/test_anima_remap.py
├── requirements.txt
├── README.md
└── loras_tags.json              # 运行后生成的缓存
```

## 已知限制
- Civitai 查询用整文件 SHA256（沿用 ATW），部分模型可能查不到。
- 首次获取某 LoRA 触发词时需联网（走缓存后不再联网）。
- 该 LoRA 若在 civitai 没有任何变体，只能靠"训练标签"页或"自由编辑"手动组织。
- **Anima 3.8B（52 层）的映射表由社区验证**（穷举 `torch.equal` 全配对，非官方发布），本机也没有 52 层模型可实测。
- **Extend 模式是近似**：新增的 12 层训练时不存在，复制源块 delta 只是 best-effort。
- **自动代际判定会误判**"只改早期层的 LoRA"——用手动 `source_model` 覆盖。
- 重映射**不碰文本编码器**：换用 Qwen3.5 4B 之类的编码器会独立改变出图效果，与块数无关。
