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

### 2. 实时预览（无需点"运行"）
- 选择 LoRA 后，预览框自动拉取并显示触发词，带索引与来源：
  ```
  [trigger words] civitai:3 meta:2
  0: tag_a (civitai)
  1: tag_b (civitai)
  2: tag_c (meta)
  [selected] tag_a, tag_c
  ```
- 修改 `trigger_selector` 时，`[selected]` 行即时刷新（前端 JS 本地计算）。

### 3. 切片选择器（沿用 Auto-Trigger-Words 语法）
- 默认 `:` = 选择全部触发词。
- 支持离散索引、范围、负索引、开放端：`0, 3, 5:8, -8:, :`。

### 4. 触发词权重
- 每槽位 `trigger_weight`，≠1.0 时把选中词包装为 `(tag:权重)`。

### 5. LoRA 堆叠（保留 JK 全部能力）
- 每节点 4 个 LoRA 槽位；多余通过 `lora_stack` 输入口串联下一节点。
- 每槽：开关 / 名称 / 模型强度 / CLIP强度 / 触发词选择器 / 触发词权重 / 触发词预览。
- **模型与 CLIP 权重独立控制**：CLIP 调 0 = 不影响 CLIP（模型照常生效），不再因 CLIP=0 整个禁用。

### 6. 合并输出
- `LORA_PROMPT`：有触发词输出触发词；无触发词输出 `<lora:名:权重>` 兜底（`fallback_to_filename` 控制）。
- `LORA_MetaData`：LoRA 名 + 可选 SHA256 哈希。
- `LORA_STACK`：标准三元组，供 Apply 节点加载。

---

## 节点：LoRA Stack Auto Triggers

### 输入
**每槽位（1..4）**：`开关` / `名称` / `模型强度` / `CLIP强度` / `触发词选择器(:)` / `触发词权重` / `触发词预览`

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
2. 选择 LoRA -> 预览框自动拉取并显示触发词
3. `trigger_selector` 填切片表达式（默认 `:` 全选），预览底部 `[selected]` 实时刷新
4. 可选 `trigger_weight` 包装为 `(tag:权重)`
5. 运行 -> 检查 `LORA_PROMPT` / `LORA_MetaData` / `LORA_STACK` 输出

## 切片语法

| 表达式 | 含义 |
|---|---|
| `0, 2, 5` | 离散索引 |
| `2:5` | 范围 [2,5) |
| `:5` | 从头到 5 |
| `5:` | 从 5 到末尾 |
| `-1` | 最后一个 |
| `:` | 全选 |

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
- 预览框触发词很多时节点会变高，可后续加折叠/截断。
