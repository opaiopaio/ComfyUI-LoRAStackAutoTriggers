# ComfyUI-LoRAStackAutoTriggers

[English](README.md) | **中文**

堆 LoRA、可视化挑触发词、再应用——并且带**自动 block 重映射**，让训练在 **Anima** 上的
LoRA 也能在 **Anima 2.9B / 3.8B** 上正常生效。

---

## 包含哪些节点

| 节点 | 作用 | 输出 |
|---|---|---|
| **LoRA 堆 · 自动触发词** | 最多 4 个 LoRA 槽位，用可视化选择器挑触发词。触发词自动从 Civitai **和** 模型文件内的训练元数据读取 | `LORA_STACK`、`LORA_PROMPT`、`LORA_MetaData` |
| **应用 LoRA 堆** | 普通应用器：吃任意 `LORA_STACK`，应用到模型 | `MODEL`、`CLIP`、`INFO` |
| **应用 LoRA 堆（Anima 跨代）** | 同上，额外做 Anima 跨代 block 重映射 | `MODEL`、`CLIP`、`REMAP_INFO` |

为什么给两个应用器？一是**不装第三方「应用LoRA堆」也能用本包**；二是 Anima 用户只在需要时换成带
remap 的那个，普通模型保持干净。

---

## 安装

**通过 ComfyUI Manager / Registry** —— 搜索 `LoRA Stack Auto Triggers`。

**手动**

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/opaiopaio/ComfyUI-LoRAStackAutoTriggers.git
```

重启 ComfyUI。**无需额外 Python 依赖**（`requests` 是 ComfyUI 自带的）。

---

## 快速上手（5 步）

1. 添加节点 **LoRA 堆 · 自动触发词**。
2. 打开 `lora_1`，在 `lora_name_1` 选一个 LoRA。
   摘要行会变成类似 `28层 · 变体 4 / 训练标签 1749`。
3. 点 **⚙ 触发词 1**，在弹窗里：
   - **变体** —— Civitai 通常发布的是**整句触发词**（每套服装一句），点一条即载入。
   - **片段 chip** —— 载入后按逗号切成词片，点一下**剔除**（比如 `see-through mouth mask`），
     再点恢复。
   - **训练标签** —— 训练集标签全量，可搜索，点一下追加。
   - **自由编辑** —— 直接改文本；或用鼠标划选其中一段，点 **应用选区** 只保留那一段。
4. 点 **应用全部**（或 **应用选区**）。
5. `LORA_PROMPT` 接进提示词编码，堆接进应用器（**应用 LoRA 堆** / **（Anima 跨代）**，
   或任何接受 `LORA_STACK` 的节点）。

---

## 选词器

| 页签 | 用途 |
|---|---|
| **变体** | 从 Civitai 的整句触发词里挑一条 |
| **片段 chip** | 不用重新打字就能剔除变体里的可选部分 |
| **训练标签** | 从训练集里挑单个词（可搜索） |
| **自由编辑** | 手改最终文本，或只保留鼠标划选的那一段 |

**`LORA_PROMPT` 最后会是什么**

- 有触发词：**只输出触发词**（不带 `<lora:...>` 标签）。
- 取不到词且 `fallback_to_filename` 开着：输出 `<lora:名:权重>` 兜底。
- `fallback_to_filename` 关掉：这颗 LoRA **不进提示词**（但仍然会应用到模型）。

选中的文本存在 `trigger_selector_*` 字段里（界面上被收纳起来，不占地方），所以**旧工作流和
旧切片语法（`0, 3, 5:8`、`:`）都仍然有效**。

---

## 节点说明

### LoRA 堆 · 自动触发词

4 个完全相同的槽位。每个槽位：

| 字段 | 含义 |
|---|---|
| `lora_N` | 启用该槽位 |
| `lora_name_N` | 选哪个 LoRA |
| `model_weight_N` | LoRA 对**模型**的强度；`0` = 不影响模型 |
| `clip_weight_N` | LoRA 对**文本编码器**的强度；`0` = 不影响 CLIP（模型照常生效） |
| **`⚙ 触发词 N`** | 打开选词器 |
| `trigger_weight_N` | 把每个词片包成 `(词:权重)`；`1.0` = 不加括号 |
| `trigger_preview_N` | 只读的一行摘要 |

槽位生效条件：**已启用** 且 **选了 LoRA** 且 **两个强度至少一个非 0**。
模型强度与 CLIP 强度是**独立**的——把 CLIP 设 0 是"只作用于模型"，不是禁用这颗 LoRA。

底部设置：

| 设置 | 含义 |
|---|---|
| `save_hash` | 在 `LORA_MetaData` 里附上文件 SHA256 前 12 位 |
| `force_fetch` | 无视本地缓存，重新去 Civitai 拉取（会把 4 个槽位全部刷新） |
| `fallback_to_filename` | 没有触发词时输出 `<lora:名:权重>` |
| `lora_prompt` / `lora_metadata` | 给输出加前缀，用于串联节点 |

可选输入 `lora_stack` / `lora_prompt` / `lora_metadata` 可以把多个堆节点串起来。

### 应用 LoRA 堆

| 输入 | 说明 |
|---|---|
| `model` | 要应用到的模型 |
| `clip`（可选） | 不接则忽略 CLIP 权重 |
| `lora_stack`（可选） | 来自本包或任何产出 `LORA_STACK` 的节点 |
| `bypass` | 原样透传，不应用任何 LoRA |
| `weight_multiplier` | 整条堆的权重统一倍率 |
| `apply_clip` | 关掉 = 完全不碰文本编码器 |

输出 `MODEL`、`CLIP`、`INFO`（逐条记录应用了哪些、跳过了哪些）。

### 应用 LoRA 堆（Anima 跨代）

在上面基础上多加：

| 输入 | 说明 |
|---|---|
| `enable_remap` | 关掉 = 普通应用器（不重映射） |
| `target_model` | `Auto (detect)` / `Anima (28 layers)` / `Anima 2.9B (40 layers)` / `Anima 3.8B (52 layers)` |
| `source_model` | 这颗 LoRA 本身是哪一代 |
| `remap_mode` | `Keys only (recommended)` / `Extend to new layers (experimental)` |
| `extend_strength` | 仅 Extend 模式使用；`1.0` = 原样复制源块 delta |

输出 `MODEL`、`CLIP`、`REMAP_INFO`，例如：

```
target: Anima 2.9B (40 layers)
applied: 1 lora(s)
zzz_remielle_anima_v2-rift1000: 28->40 remapped (840 moved, 0 dropped)  [w=0.85, clip=0]
```

---

## Anima 跨代兼容

Anima 各代是**插入式加深**（不是重训）：往上一代的中间**插入 12 个新 block**。

```
28 层（Anima 原版）:  0  1  2  3  4  5 ...
40 层（Anima 2.9B）:  0  1 [2] 3  4 [5] 6  7 [8] ...   [n] = 新插入
                      ↑  ↑     ↑  ↑     ↑  ↑
                      0  1     2  3     4  5            ← 原有块被挤到后面的索引
```

LoRA 的键写的是 `blocks.2`。在 40 层模型上 `blocks.2` **确实存在**（它是插入块），
所以**不会报错**——但 delta 全落在错的层上。本节点会在应用之前改写 LoRA 的块索引。

**为什么有两个下拉。** `target_model` 通常能从所接模型正确探测；但 `source_model`
是靠 LoRA 自身最高块号推断的，对"只改早期层"的 LoRA 会误判。**拿不准就手动指定。**

**两种重映射模式**

| 模式 | 效果 |
|---|---|
| `Keys only` | 只搬索引；新插入的 12 层拿不到这颗 LoRA 的 delta，所以效果比在原版模型上**弱** |
| `Extend` | 额外把每个源块的 delta 复制到"由它插入出来的"新层（按倍率缩放）。属于尽力而为——那些层在训练时还不存在 |

**只支持单向。** 老 → 新（`28→40`、`28→52`、`40→52`）。若 LoRA 需要的层数**多于**模型，
会直接报错，而不是静默只装一半。

**与其它插件共存。** 社区有两个插件（`ComfyUI-Anima-2.9B-loraPatch`、
`ComfyUI-Anima-LoRA-ControlNet-Patch`）会全局 patch `comfy.lora.load_lora`。本节点**不打任何全局补丁**，
只改自己加载的那份 state dict，所以可以和它们共存、不会双重 remap。当然装一个就够。

---

## 语言

节点**标题、分类、说明、tooltip** 跟随**系统语言**（中文或英文）；
选词弹窗跟随**浏览器语言**。

想强制指定，在启动 ComfyUI 前设环境变量：

```bash
OPNODES_LANG=zh    # 或 en
```

下拉菜单的**取值**（`Auto (detect)`、`Anima 2.9B (40 layers)` 等）故意**不翻译**：
ComfyUI 会把选中的取值存进工作流，翻译后换语言打开会变成未知值。

---

## 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 没有 `⚙ 触发词` 按钮、`trigger_selector_*` 全部露出来 | 前端扩展没加载。按 Ctrl+Shift+R 硬刷新；仍然不行就看浏览器控制台里 `[LoRAStackAutoTriggers]` 开头的日志 |
| 触发词是空的 | 这颗 LoRA 在 Civitai 没条目、也没有 `ss_tag_frequency` 元数据。勾一次 `force_fetch`，或在选词器里手打 |
| 换了 LoRA 文件后词不对 | 缓存按 LoRA 名索引。开一次 `force_fetch` 刷新，或删掉 `loras_tags.json` |
| 出图全灰/全黑且不报错 | 有 NaN 权重传到了应用器。当前版本会把 NaN 当 0 并跳过该条——旧版本请更新 |
| Anima LoRA 在 2.9B / 3.8B 上效果偏弱 | `Keys only` 模式的正常现象（12 个新层没效果）。试试 `Extend`，强度 `0.3`–`0.8` |

---

## 致谢

- 触发词提取移植自 [idrirap/ComfyUI-Lora-Auto-Trigger-Words](https://github.com/idrirap/ComfyUI-Lora-Auto-Trigger-Words)
  （MIT，© konohana）——它本身 fork 自
  [Extraltodeus/LoadLoraWithTags](https://github.com/Extraltodeus/LoadLoraWithTags)。
- 堆叠加载器的形态参考 [jakechai/ComfyUI-JakeUpgrade](https://github.com/jakechai/ComfyUI-JakeUpgrade)。
- Anima 的 block 映射表采用社区验证过的版本：
  [sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch](https://github.com/sparklingcoffee777/ComfyUI-Anima-2.9B-loraPatch)
  与 [INuBq8/ComfyUI-Anima-LoRA-ControlNet-Patch](https://github.com/INuBq8/ComfyUI-Anima-LoRA-ControlNet-Patch)
  （穷举 `torch.equal` 验证）。**未使用这两个 GPL 项目的代码。**

## 许可

本包为 MIT。注意 **Anima 模型本身是非商用许可**，由它产出的重映射 LoRA 文件属于衍生作品，
继承非商用限制；但你生成的图片仍可商用。
