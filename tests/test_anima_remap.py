"""Offline tests for the Anima remap layer and both nodes.

Run from the node folder (no ComfyUI required):

    py -3 tests/test_anima_remap.py

ComfyUI-only modules (folder_paths, comfy.*) are stubbed so the mapping tables,
key rewriting and node plumbing can all be checked standalone.
"""

import sys
import types
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

# --------------------------------------------------------------------------- #
# Stubs: folder_paths + comfy.*
# --------------------------------------------------------------------------- #
_FAKE_FILES = {}
APPLIED = []

fp = types.ModuleType("folder_paths")
fp.get_filename_list = lambda kind: []
fp.get_full_path = lambda kind, name: f"/fake/{name}"
fp.get_output_directory = lambda: "/fake"
sys.modules["folder_paths"] = fp

_comfy = types.ModuleType("comfy")
_comfy_utils = types.ModuleType("comfy.utils")
_comfy_sd = types.ModuleType("comfy.sd")


def _load_torch_file(path, safe_load=True):
    return _FAKE_FILES[path]


def _load_lora_for_models(model, clip, lora_sd, strength_model, strength_clip):
    APPLIED.append(
        {
            "keys": list(lora_sd.keys()),
            "strength_model": strength_model,
            "strength_clip": strength_clip,
        }
    )
    return (model, clip)


_comfy_utils.load_torch_file = _load_torch_file
_comfy_sd.load_lora_for_models = _load_lora_for_models
_comfy.utils = _comfy_utils
_comfy.sd = _comfy_sd
sys.modules["comfy"] = _comfy
sys.modules["comfy.utils"] = _comfy_utils
sys.modules["comfy.sd"] = _comfy_sd

# --------------------------------------------------------------------------- #
# Imports under test
# --------------------------------------------------------------------------- #
import anima_arch as A            # noqa: E402
import anima_remap as R           # noqa: E402
import oplorast_slots as S        # noqa: E402
import oplorast_node as BASE      # noqa: E402
import oplorast_anima_node as ANI  # noqa: E402

# --------------------------------------------------------------------------- #
# Tiny harness
# --------------------------------------------------------------------------- #
OK = True


def check(label, got, exp):
    global OK
    good = got == exp
    if not good:
        OK = False
    print(("[OK ] " if good else "[FAIL] ") + label)
    if not good:
        print(f"        got = {got!r}")
        print(f"        exp = {exp!r}")


def check_true(label, cond, hint=""):
    global OK
    if not cond:
        OK = False
    print(("[OK ] " if cond else "[FAIL] ") + label + (f"  {hint}" if (not cond and hint) else ""))


# --------------------------------------------------------------------------- #
# 1. Architecture tables
# --------------------------------------------------------------------------- #
print("\n=== 1. anima_arch 映射表 ===")

check("28->40 表长度", len(A.MAP_28_40), 28)
check("28->40 单射", len(set(A.MAP_28_40.values())), 28)
check("28->40 base2 -> 3", A.MAP_28_40[2], 3)
check("28->40 base27 -> 39", A.MAP_28_40[27], 39)

check("40->52 表长度", len(A.MAP_40_52), 40)
check("40->52 单射", len(set(A.MAP_40_52.values())), 40)
check("40->52 base2 -> 2", A.MAP_40_52[2], 2)
check("40->52 base3 -> 4", A.MAP_40_52[3], 4)

check(
    "28->52 == 28->40 再套 40->52",
    A.MAP_28_52,
    {s: A.MAP_40_52[d] for s, d in A.MAP_28_40.items()},
)

# inserted_sources 必须与社区 manifest 的 inserted_to_source 一致
check(
    "28->40 插入块来源（对照社区 manifest）",
    A.inserted_sources(A.MAP_28_40, 40),
    {2: 1, 5: 3, 8: 5, 11: 7, 14: 9, 17: 11, 21: 14, 24: 16, 27: 18, 30: 20, 33: 22, 36: 24},
)
check(
    "40->52 插入块来源（对照社区 manifest）",
    A.inserted_sources(A.MAP_40_52, 52),
    {3: 2, 7: 5, 11: 8, 15: 11, 19: 14, 23: 17, 27: 20, 31: 23, 35: 26, 39: 29, 43: 32, 47: 35},
)
check("28->52 插入块数量", len(A.inserted_sources(A.MAP_28_52, 52)), 24)

check("bucket(28)", A.bucket_block_count(28), 28)
check("bucket(29)", A.bucket_block_count(29), 40)
check("bucket(36)", A.bucket_block_count(36), 40)
check("bucket(40)", A.bucket_block_count(40), 40)
check("bucket(52)", A.bucket_block_count(52), 52)
check("bucket(53)", A.bucket_block_count(53), None)
check("bucket(0)", A.bucket_block_count(0), None)

check("get_mapping(28,40) 存在", A.get_mapping(28, 40) is A.MAP_28_40, True)
check("get_mapping(28,28) 为 None", A.get_mapping(28, 28), None)
check("get_mapping(40,28) 为 None（不支持降级）", A.get_mapping(40, 28), None)

check("下拉解析 Animia(28)", A.resolve_dropdown("Anima (28 layers)"), 28)
check("下拉解析 2.9B(40)", A.resolve_dropdown("Anima 2.9B (40 layers)"), 40)
check("下拉解析 3.8B(52)", A.resolve_dropdown("Anima 3.8B (52 layers)"), 52)
check("下拉解析 Auto", A.resolve_dropdown(A.AUTO_LABEL), None)

# --------------------------------------------------------------------------- #
# 2. Key handling
# --------------------------------------------------------------------------- #
print("\n=== 2. anima_remap 键处理 ===")

# 这两种拼写都在真实 Anima LoRA 里出现过
kohya = "lora_unet_blocks_5_cross_attn_k_proj.lora_down.weight"
peft = "diffusion_model.blocks.5.adaln_modulation_cross_attn.1.lora_A.weight"
net_kohya = "lora_unet_net_blocks_5_x.lora_down.weight"
bare = "blocks.5.thing.lora_down.weight"

check("kohya 块号识别", sorted(R.block_indices([kohya])), [5])
check("peft 块号识别", sorted(R.block_indices([peft])), [5])
check("net_ 变体识别", sorted(R.block_indices([net_kohya])), [5])
check("裸键识别", sorted(R.block_indices([bare])), [5])

llm_ad = "lora_unet_llm_adapter_blocks_3_x.lora_down.weight"
te = "lora_te_text_model_encoder_layers_3_mlp_fc1.lora_down.weight"
check("llm_adapter 必须被排除", sorted(R.block_indices([llm_ad])), [])
check("lora_te 必须被排除", sorted(R.block_indices([te])), [])
check("llm_adapter 键重写后不变", R.remap_key(llm_ad, A.MAP_28_40), llm_ad)
check("lora_te 键重写后不变", R.remap_key(te, A.MAP_28_40), te)

check("重写 kohya 键", R.remap_key(kohya, A.MAP_28_40), kohya.replace("blocks_5_", "blocks_7_"))
check("重写 peft 键", R.remap_key(peft, A.MAP_28_40), peft.replace("blocks.5.", "blocks.7."))
check("无映射项的块返回 None", R.remap_key("lora_unet_blocks_30_x", A.MAP_28_40), None)

# --------------------------------------------------------------------------- #
# 3. state dict 重写
# --------------------------------------------------------------------------- #
print("\n=== 3. state dict 重写 / 扩展 ===")


def make_lora_sd(blocks, extras=True):
    sd = {}
    for b in blocks:
        sd[f"lora_unet_blocks_{b}_cross_attn_k_proj.lora_down.weight"] = 2.0
        sd[f"lora_unet_blocks_{b}_cross_attn_k_proj.lora_up.weight"] = 3.0
        sd[f"lora_unet_blocks_{b}_cross_attn_k_proj.alpha"] = 16.0
    if extras:
        sd[llm_ad] = "llm"
        sd[te] = "te"
    return sd


sd28 = make_lora_sd(range(28))
out, st = R.remap_state_dict(sd28, A.MAP_28_40)

check("重写后块集合 == 40 代里保留的位置", sorted(R.block_indices(out.keys())), sorted(A.MAP_28_40.values()))
check("重写后无丢弃（28->40 全部有落点）", st["dropped"], 0)
check("llm_adapter 权重仍在", llm_ad in out, True)
check("lora_te 权重仍在", te in out, True)
check("张量值原样搬运", out["lora_unet_blocks_3_cross_attn_k_proj.lora_down.weight"], 2.0)

# 扩展模式
out2, st2 = R.extend_state_dict(sd28, A.MAP_28_40, 40, 0.5)
per_block_targets = A.source_to_inserted(A.MAP_28_40, 40)
expected_added = sum(len(v) for v in per_block_targets.values()) * 3  # down/up/alpha
check("扩展新增张量数", st2["added"], expected_added)
check("扩展后包含全部 40 个块", len(R.block_indices(out2.keys())), 40)
# 只有 up 侧按 strength 缩放；down / alpha 原样搬运
check("扩展：up 侧缩放 3.0*0.5", out2["lora_unet_blocks_2_cross_attn_k_proj.lora_up.weight"], 1.5)
check("扩展：down 侧不缩放", out2["lora_unet_blocks_2_cross_attn_k_proj.lora_down.weight"], 2.0)
check("扩展：alpha 不缩放", out2["lora_unet_blocks_2_cross_attn_k_proj.alpha"], 16.0)

# --------------------------------------------------------------------------- #
# 4. 共享槽位逻辑
# --------------------------------------------------------------------------- #
print("\n=== 4. oplorast_slots ===")

S.get_structured_tags = lambda name, force: {  # 避免真实文件/网络访问
    "variants": ["zzz_x, pink hair, black dress, see-through mouth mask", "zzz_alt"],
    "meta": ["pink hair", "mask"],
}

kw = {
    "lora_1": True, "lora_name_1": "a.safetensors", "model_weight_1": 0.8, "clip_weight_1": 0.0,
    "trigger_selector_1": "", "trigger_weight_1": 1.0, "trigger_preview_1": "",
    "lora_2": True, "lora_name_2": "b.safetensors", "model_weight_2": 0.0, "clip_weight_2": 0.0,
    "trigger_selector_2": "", "trigger_weight_2": 1.0, "trigger_preview_2": "",
    "lora_3": False, "lora_name_3": "c.safetensors", "model_weight_3": 1.0, "clip_weight_3": 1.0,
    "trigger_selector_3": "", "trigger_weight_3": 1.0, "trigger_preview_3": "",
    "lora_4": True, "lora_name_4": "None", "model_weight_4": 1.0, "clip_weight_4": 1.0,
    "trigger_selector_4": "", "trigger_weight_4": 1.0, "trigger_preview_4": "",
}

check("启用槽位（1 开且模型非0；2 两个权重都为0；3 未开；4 名称 None）",
      [i for i, *_ in S.iter_enabled_slots(kw)], [1])

check("空选择器 -> 第一条变体",
      S.trigger_segment("a.safetensors", kw, 1, False, True, 0.8),
      "zzz_x, pink hair, black dress, see-through mouth mask")

kw["trigger_selector_1"] = "pink hair, black dress"
check("自由文本原样", S.trigger_segment("a.safetensors", kw, 1, False, True, 0.8), "pink hair, black dress")

kw["trigger_weight_1"] = 1.2
check("权重包装", S.trigger_segment("a.safetensors", kw, 1, False, True, 0.8),
      "(pink hair:1.2), (black dress:1.2)")

S.get_structured_tags = lambda name, force: {"variants": [], "meta": []}
kw["trigger_selector_1"] = ""
kw["trigger_weight_1"] = 1.0
check("无触发词 + 兜底 -> <lora:...>", S.trigger_segment("a.safetensors", kw, 1, False, True, 0.8),
      "<lora:a:0.800>")
check("无触发词 + 不兜底 -> 空串", S.trigger_segment("a.safetensors", kw, 1, False, False, 0.8), "")

# --------------------------------------------------------------------------- #
# 5. 基础节点回归（v1.1.0 行为不变）
# --------------------------------------------------------------------------- #
print("\n=== 5. 基础节点回归 ===")

S.get_structured_tags = lambda name, force: {"variants": ["tagA, tagB"], "meta": []}
node = BASE.LoRAStackAutoTriggers()
stack, prompt, meta = node.lora_stacker(False, False, True, **kw)
check("基础节点 stack", stack, [("a.safetensors", 0.8, 0.0)])
check("基础节点 prompt", prompt, "tagA, tagB")
check("基础节点 meta", meta, "a")

# --------------------------------------------------------------------------- #
# 6. Anima 节点端到端（打桩）
# --------------------------------------------------------------------------- #
print("\n=== 6. Anima 节点端到端 ===")


class FakeModel:
    def __init__(self, n):
        dm = types.SimpleNamespace(blocks=[None] * n)
        self.model = types.SimpleNamespace(diffusion_model=dm)


FAKE_PATH = "/fake/mylora.safetensors"
_FAKE_FILES[FAKE_PATH] = make_lora_sd(range(28))

anima = ANI.LoRAStackAutoTriggersAnimaRemap()
slot_kw = {
    "lora_1": True, "lora_name_1": "mylora.safetensors", "model_weight_1": 0.85, "clip_weight_1": 0.0,
    "trigger_selector_1": "pink hair", "trigger_weight_1": 1.0, "trigger_preview_1": "",
    "lora_2": False, "lora_name_2": "None", "model_weight_2": 1.0, "clip_weight_2": 1.0,
    "trigger_selector_2": "", "trigger_weight_2": 1.0, "trigger_preview_2": "",
    "lora_3": False, "lora_name_3": "None", "model_weight_3": 1.0, "clip_weight_3": 1.0,
    "trigger_selector_3": "", "trigger_weight_3": 1.0, "trigger_preview_3": "",
    "lora_4": False, "lora_name_4": "None", "model_weight_4": 1.0, "clip_weight_4": 1.0,
    "trigger_selector_4": "", "trigger_weight_4": 1.0, "trigger_preview_4": "",
}


def run_anima(model_layers=40, mode=ANI.REMAP_MODE_KEYS, enable=True,
              target_choice=A.AUTO_LABEL, source_choice=A.AUTO_LABEL):
    APPLIED.clear()
    return anima.stack(
        model=FakeModel(model_layers),
        enable_remap=enable,
        target_model=target_choice,
        source_model=source_choice,
        remap_mode=mode,
        extend_strength=0.5,
        save_hash=False,
        force_fetch=False,
        fallback_to_filename=True,
        **slot_kw,
    )


out_model, out_clip, prompt, meta, stack_out, info = run_anima(40)
check("输出端口数", 6, 6)
check("prompt 来自触发词", prompt, "pink hair")
check("meta", meta, "mylora")
check("stack 输出", stack_out, [("mylora.safetensors", 0.85, 0.0)])
check_true("REMAP_INFO 指出 28->40", "28->40" in info, info)
check("应用次数", len(APPLIED), 1)
applied_blocks = sorted(R.block_indices(APPLIED[0]["keys"]))
check("应用到模型的是 40 代块位", applied_blocks, sorted(A.MAP_28_40.values()))
check("clip=None 时 clip 强度归零", APPLIED[0]["strength_clip"], 0.0)

# 同代：模型 28 层，不该 remap
out_model, *_rest, info_same = run_anima(28)
check_true("同代时不重映射", "as-is" in info_same, info_same)
check("同代时块位保持原样", sorted(R.block_indices(APPLIED[0]["keys"])), list(range(28)))

# 关闭重映射
out_model, *_r2, info_off = run_anima(40, enable=False)
check_true("关闭 remap 时提示", "disabled" in info_off, info_off)

# 降级必须报错
try:
    run_anima(28, source_choice="Anima 2.9B (40 layers)")
    check_true("源>目标 应抛错", False, "没有抛错")
except ValueError as e:
    check_true("源>目标 抛 ValueError", "cannot" in str(e).lower() or "not supported" in str(e).lower(), str(e))

# 手动覆盖目标代
out_model, *_r3, info_manual = run_anima(28, target_choice="Anima 3.8B (52 layers)")
check_true("手动指定目标代 52 生效", "28->52" in info_manual, info_manual)
check("28->52 块位", sorted(R.block_indices(APPLIED[0]["keys"])), sorted(A.MAP_28_52.values()))

# 扩展模式
out_model, *_r4, info_ext = run_anima(40, mode=ANI.REMAP_MODE_EXTEND)
check_true("扩展模式提示", "new layers" in info_ext, info_ext)
check("扩展后覆盖 40 个块", len(R.block_indices(APPLIED[0]["keys"])), 40)

# --------------------------------------------------------------------------- #
print()
print("RESULT:", "ALL PASS" if OK else "SOME FAILED")
sys.exit(0 if OK else 1)
