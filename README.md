# ComfyUI-LoRAStackAutoTriggers

一个 ComfyUI 自定义节点，把 **LoRA 堆叠管理** 与 **自动触发词提取** 整合进单个节点：选 LoRA 即自动拉取触发词，界面实时预览，切片选择，一个节点搞定"自动拉取提示词 + LoRA 堆 + 开关 + 模型/CLIP 分强度控制"。

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

## 文件结构

```
ComfyUI-LoRAStackAutoTriggers/
├── __init__.py                  # 插件入口（注册节点 + 路由 + web 目录）
├── oplorast_utils.py            # 触发词逻辑（移植自 ATW）+ 后端路由
├── oplorast_node.py             # 节点类 LoRAStackAutoTriggers
├── web/js/oplorast_lora_triggers.js  # 前端实时预览
├── requirements.txt             # requests
├── README.md
└── loras_tags.json              # 运行后生成的缓存
```

## 已知限制
- Civitai 查询用整文件 SHA256（沿用 ATW），部分模型可能查不到。
- 首次获取某 LoRA 触发词时需联网（走缓存后不再联网）。
- 该 LoRA 若在 civitai 没有任何变体，只能靠"训练标签"页或"自由编辑"手动组织。
