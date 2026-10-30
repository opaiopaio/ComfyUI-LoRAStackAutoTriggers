"""Bilingual strings (English / Chinese) for this node pack.

Language is chosen from the system, not the browser:

    1. OPNODES_LANG env var ("zh" / "en")      -- explicit override
    2. Windows UI language (GetUserDefaultUILanguage)
    3. LC_ALL / LC_MESSAGES / LANG
    4. Python's locale
    5. English

Deliberately NOT localised: the dropdown *values* ("Auto (detect)",
"Anima 2.9B (40 layers)", ...) and the remap mode values. ComfyUI stores a
combo's value string inside the workflow, so translating those would make a
workflow saved under one language read as an unknown value under another.
Only node titles, categories, descriptions and tooltips are translated.
"""

from __future__ import annotations

import os
import sys


def _detect_language() -> str:
    forced = (os.environ.get("OPNODES_LANG") or "").strip().lower()
    if forced:
        return "zh" if forced.startswith("zh") else "en"

    if sys.platform == "win32":
        try:
            import ctypes

            langid = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            primary = langid & 0x3FF
            return "zh" if primary == 0x04 else "en"  # LANG_CHINESE
        except Exception:
            pass

    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = (os.environ.get(var) or "").strip().lower()
        if value:
            return "zh" if value.startswith("zh") else "en"

    try:
        import locale

        name = (locale.getlocale()[0] or "").lower()
        if name:
            return "zh" if name.startswith("zh") else "en"
    except Exception:
        pass

    return "en"


LANG = _detect_language()

LANGUAGE_NAMES = {"en": "English", "zh": "中文"}


def language_name() -> str:
    return LANGUAGE_NAMES.get(LANG, LANG)


_STRINGS = {
    # ------------------------------------------------------------------ en --
    "en": {
        "category": "LoRA Stack",
        "node.stack": "LoRA Stack Auto Triggers",
        "node.apply": "LoRA Stack Apply",
        "node.apply_anima": "LoRA Stack Apply (Anima Remap)",
        "desc.stack": (
            "Stack LoRAs with automatic trigger-word extraction (civitai + "
            "safetensors metadata) and a visual trigger picker."
        ),
        "desc.apply": "Apply a LORA_STACK to MODEL/CLIP.",
        "desc.apply_anima": (
            "Apply a LORA_STACK to MODEL/CLIP with Anima cross-generation block "
            "remapping (28 / 40 / 52 layers)."
        ),
        # stack node -------------------------------------------------------
        "tip.lora_on": "Enable/disable LoRA {i}",
        "tip.lora_name": "Select LoRA model {i}",
        "tip.model_weight": "Model (U-Net) weight for LoRA {i}; 0 = no model effect",
        "tip.clip_weight": (
            "CLIP (text encoder) weight for LoRA {i}; 0 = no CLIP effect "
            "(model still applies)"
        ),
        "tip.selector": (
            "Trigger text for LoRA {i}. Leave empty to use the first civitai "
            "variant. Use the \u2699 picker to choose/modify. Free text is "
            "injected verbatim; legacy slice syntax (0, 3, 5:8, :) still works."
        ),
        "tip.trigger_weight": (
            "Wraps every selected segment as (seg:weight) for LoRA {i}; "
            "1.0 = no wrapping"
        ),
        "tip.preview": "One-line summary for LoRA {i} (filled by the UI)",
        "tip.lora_stack_in": "Existing LoRA stack to extend (chain more nodes here)",
        "tip.lora_prompt": "Existing LoRA prompt to extend",
        "tip.lora_metadata": "Existing LoRA metadata to extend",
        "tip.save_hash": "Include SHA256[:12] in metadata",
        "tip.force_fetch": "Force re-fetch from civitai",
        "tip.fallback": (
            "No trigger words found -> output <lora:name:weight> as fallback; "
            "OFF -> skip that lora from the prompt"
        ),
        # apply nodes ------------------------------------------------------
        "tip.model": (
            "Model to apply the stack to. Its layer count is used to detect the "
            "target Anima generation."
        ),
        "tip.lora_stack_apply": (
            "Stack to apply (from LoRA Stack Auto Triggers or any other node that "
            "produces LORA_STACK)."
        ),
        "tip.bypass": "Pass MODEL/CLIP through untouched (quick A/B toggle)",
        "tip.enable_remap": (
            "Anima only. Turn off to apply LoRAs untouched. For models that are "
            "not Anima this is a no-op either way."
        ),
        "tip.target_model": (
            "Generation of the connected model. Auto detects it from the layer "
            "count; override if Auto gets it wrong."
        ),
        "tip.source_model": (
            "Generation the LoRA was trained on. Auto infers it from the LoRA's "
            "highest block index -- which mis-reads adapters that only touch early "
            "layers, so override when in doubt."
        ),
        "tip.remap_mode": (
            "Keys only: rewrite indices (new layers get no delta). Extend: also "
            "project each source delta onto the layers inserted from it "
            "(experimental)."
        ),
        "tip.extend_strength": (
            "Only used by Extend mode. 1.0 copies the source delta as-is; scales "
            "linearly."
        ),
        "tip.weight_multiplier": (
            "Multiplies every weight in the stack. 1.0 = unchanged; use it to dial "
            "the whole stack up or down at once."
        ),
        "tip.apply_clip": (
            "OFF = never touch the text encoder: all CLIP weights are forced to 0 "
            "(model-only application)."
        ),
        "tip.clip_optional": "Optional. Without it, CLIP weights are ignored.",
    },
    # ------------------------------------------------------------------ zh --
    "zh": {
        "category": "LoRA 堆",
        "node.stack": "LoRA 堆 · 自动触发词",
        "node.apply": "应用 LoRA 堆",
        "node.apply_anima": "应用 LoRA 堆（Anima 跨代）",
        "desc.stack": (
            "堆叠 LoRA，并自动拉取触发词（civitai + safetensors 元数据），"
            "配合可视化选词器使用。"
        ),
        "desc.apply": "把 LORA_STACK 应用到 MODEL/CLIP。",
        "desc.apply_anima": (
            "把 LORA_STACK 应用到 MODEL/CLIP，并做 Anima 跨代 block 重映射"
            "（28 / 40 / 52 层）。"
        ),
        # stack node -------------------------------------------------------
        "tip.lora_on": "启用/停用第 {i} 个 LoRA",
        "tip.lora_name": "选择第 {i} 个 LoRA",
        "tip.model_weight": "第 {i} 个 LoRA 的模型(U-Net)强度；0 = 不影响模型",
        "tip.clip_weight": (
            "第 {i} 个 LoRA 的 CLIP(文本编码器)强度；0 = 不影响 CLIP（模型照常生效）"
        ),
        "tip.selector": (
            "第 {i} 个 LoRA 的触发词文本。留空 = 用 civitai 第一条变体；"
            "点 \u2699 打开选词器。自由文本原样注入，旧的切片语法"
            "（0, 3, 5:8, :）仍然有效。"
        ),
        "tip.trigger_weight": (
            "把第 {i} 个 LoRA 的每个词片包成 (词:权重)；1.0 = 不加括号"
        ),
        "tip.preview": "第 {i} 个 LoRA 的一行摘要（由界面自动填写）",
        "tip.lora_stack_in": "已有的 LoRA 堆，用于串联更多节点",
        "tip.lora_prompt": "已有的 LoRA 提示词，作为前缀续接",
        "tip.lora_metadata": "已有的 LoRA 元数据，作为前缀续接",
        "tip.save_hash": "在元数据里附上 SHA256 前 12 位",
        "tip.force_fetch": "强制从 civitai 重新拉取（无视本地缓存）",
        "tip.fallback": (
            "取不到触发词时输出 <lora:名:权重> 兜底；关掉则该 LoRA 不进提示词"
        ),
        # apply nodes ------------------------------------------------------
        "tip.model": "要应用到的模型；Auto 探测目标代时用它数层数",
        "tip.lora_stack_apply": "要应用的 LoRA 堆（来自本包或任何产出 LORA_STACK 的节点）",
        "tip.bypass": "直接透传 MODEL/CLIP，不应用任何 LoRA（快速 A/B）",
        "tip.enable_remap": (
            "仅 Anima 相关。关掉就是不改键、原样应用；非 Anima 模型开不开都一样"
        ),
        "tip.target_model": "所接模型是哪一代；Auto 按层数判断，判错时手动指定",
        "tip.source_model": (
            "这个 LoRA 是哪一代；Auto 按 LoRA 最高块号推断，"
            "对「只改早期层」的 LoRA 会误判，拿不准就手动指定"
        ),
        "tip.remap_mode": (
            "Keys only：只搬块索引（新增层拿不到 delta）；"
            "Extend：额外把 delta 投影到由它插入出来的新层（实验）"
        ),
        "tip.extend_strength": "仅 Extend 模式使用；1.0 = 原样复制源块 delta，线性缩放",
        "tip.weight_multiplier": (
            "整条 stack 的权重统一倍率；1.0 = 不变，可一次性放大/缩小全部 LoRA"
        ),
        "tip.apply_clip": "关掉 = 完全不碰文本编码器（所有 CLIP 权重强制为 0，仅作用于模型）",
        "tip.clip_optional": "可选；不接则忽略 CLIP 权重",
    },
}


def t(key: str, **fmt) -> str:
    """Translation for `key`, falling back to English then to the key itself."""
    table = _STRINGS.get(LANG) or _STRINGS["en"]
    text = table.get(key) or _STRINGS["en"].get(key) or key
    if fmt:
        try:
            text = text.format(**fmt)
        except Exception:
            pass
    return text
