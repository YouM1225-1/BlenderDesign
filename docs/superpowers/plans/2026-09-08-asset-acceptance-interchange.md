# 静态 GLB 投影闭环（M3）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 M0/M1 可信核心及 M2 原生证据之上，让限定静态 GLB 完成全部 34 个现有适用检查、独立技术门禁与真实交付封装，允许合法拆点和未使用数据裁剪，拒绝实际表面、UV、材质、身份及变换损失。

**Architecture:** 原生 inspector 与完整 source 视觉实验复用 M2；导出副本产生唯一 D，Node 包适配器真实调用 Khronos Validator，controller 复核完整报告和资源证据。独立进程导入同一 D，按显式表面投影匹配；源投影与导入投影使用相同受控相机和解码器。worker 只提交测量，核心 decide 归约全部检查及 gates，Q/T 沿用无环证据链。

**Tech Stack:** CPython 3.13.13；Blender 5.2.0 LTS / `fbe6228777e7`；Node.js v20.20.2；`gltf-validator@2.0.0-dev.3.10`；标准库；pytest。只为 interchange 安装 Node 验证器包，原生路径不依赖它。

## Global Constraints

- 「所有必需检查均须真实执行；不能通过减少 required 集合、合成 Pass 或放宽阈值制造成功。」
- 「M3 先支持锁定导出 preset 的静态三角表面、简单 PBR 和已明确用途的纹理。」
- 「对 source 使用冻结的 export projection，import 使用对应投影及同一相机；全源诊断单独保留。」
- 「Blender→GLB→Blender 已完成轴转换时，不再额外换轴。」
- 「数值条件统一为 `abs(a-b) <= abs_tolerance + rel_tolerance * reference_scale`」；位置以冻结源 reference_scale 计量，单位法线/UV/PBR 的 reference_scale 固定为 1。
- 「issues.truncated=false」是完成条件；格式、保真与实际消费者是不同门禁。
- 「未用层是否可丢由合同声明，需新增真实正向夹具后才开放该能力」；本包不开放 UV 层裁剪。
- 「文件 SHA-256 证明证据字节身份」；PNG 像素比较及纹理解码身份单独记录。
- 「批准本设计本身不构成未来某个资产的签收。」测试 reviewer 仅限测试。
- 「不得将 `bpy` 引入 `bridge/core` 或 `protocol`。不为本设计把 `acceptance/` 提前加入 wheel/sdist。」
- 「每个实施包提交前运行一次 `bash scripts/checks.sh` 并确认 `ALL CHECKS PASSED`；最后修改后执行 `graft build .`，交付前 `graft check .` 退出 0。」

---

## 前置、文件边界与完成口径

先完成 [M0/M1](2026-09-08-asset-acceptance-core-v2.md) 与 [M2](2026-09-08-asset-acceptance-native.md)。本计划复用它们的 v2 Contract、文件/作业注册、worker/result 接收、进程与 RSS 预算、真实 R5、技术 gates 及审阅封装。不得把本包的辅助 parser 作为另一套放行算法。

| 文件 | 职责 |
|---|---|
| `acceptance/interchange_policy.py` | 纯 Python 封闭政策、固定导出 preset 与有限能力声明 |
| `acceptance/projection.py` | 深结构校验与有界三角角点匹配；保留逐对匹配和差异 |
| `acceptance/blender_scripts/projection_capture.py` | Blender 表面、使用材质、解码纹理及身份采集 |
| `acceptance/glb_budget.py` | 有界 GLB chunk 读取、唯一资源与逐 node 绘制预算 |
| `acceptance/node_scripts/validator_worker.mjs` | 调用真正的 npm 库并保存完整原始报告与资源读取记录 |
| `acceptance/glb_budget_worker.py`、`acceptance/projection_worker.py` | M1 协议适配；不自授最终 Pass |
| `acceptance/blender_scripts/glb_worker.py` | 副本导出、新进程导入、投影视觉及差异图 |
| `acceptance/interchange_plan.py`、`acceptance/interchange_results.py` | 单一文件展开、检查/报告/进程/消费者门禁接线 |
| `tests/unit/interchange_support.py` 与下列测试 | 纯 Python 正反行为回归；不启动 Blender |
| `tests/fixtures/asset_interchange.py`、`tests/integration/test_asset_interchange.py` | 独立 Blender 与 Node 的真实正反证据 |
| `acceptance/contract.py`、`scripts/asset_accept.py` | 启用封闭政策和 CLI kind 分支 |
| `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`、`docs/validation.md` | V5 接线状态与 M3 专用门禁 |

本包支持普通非镜像静态 MESH、正行列式世界矩阵、scene scale_length=1、一个活动 Principled→Surface、基本颜色/金属度/粗糙度/Alpha/发光常量，以及直接 Base Color 的打包 sRGB RGBA8 PNG、Linear/REPEAT/default-active-UV。其他 Principled 输入只能保持锁定 Blender 的默认值。自定义属性精确比较；candidate 的 `bcx_`/`acceptance_` 属性先被 R2 拒绝，再由受信导出器注入身份。省略的 EMPTY 不允许携带要求保留的自定义属性。曲线、文字、集合实例、负尺度、HDR、UDIM、自定义 shader、glTF 扩展均不在首发完整闭环范围。

collection 结构允许省略，已支持 modifier 允许烘焙；使用中的表面必须匹配。全部 UV 角点值保留，名称不作为 GLB layer 身份，纹理绑定以 UV 索引对账；不宣称 UV 剪裁已验证。顶点/槽计数只是诊断，不能替代三角表面与使用材质比较。匹配上限 4096 三角和 2,000,000 次候选比较；超预算为未验证，不准截断后判 Pass。

原生 135 原图与 99 差异图完整保留。M3 追加 source projection / import 各 36 图和 36 差异图；clay/silhouette 的 18 对是 source-import 硬门，wire/beauty 的其余 18 对完整测量留证并纳入所需审阅。几何/PBR/纹理字段仍全部硬判。消费者字段非 null 而没有该版本适配器时 `interchange.consumer` 未完成，技术 success=false、上层 UNVERIFIED。

Khronos 的 npm 包没有 `bin` 入口；不运行不存在的 `gltf_validator` CLI。官方接口是 `validateBytes` 及 `externalResourceFunction`，报告有 `issues.truncated` 和 `info.resources`。图像资源行给出解码 image 元数据，未必有 byteLength；buffers 和 images 分别判读。[官方 Node API](https://github.com/KhronosGroup/glTF-Validator/blob/434283be08a668a8fb4e437145630ddbf93b0686/node/README.md)，[官方报告 schema](https://github.com/KhronosGroup/glTF-Validator/blob/434283be08a668a8fb4e437145630ddbf93b0686/docs/validation.schema.json)。

每个新 shell 的准备命令：

```bash
export PYTHON_BIN="$PWD/.venv/bin/python"
export BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
export NODE_BIN="$(command -v node)"
export GLTF_PACKAGE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/blenderdesign-validator.XXXXXX")"
printf '%s\n' '{"private":true,"dependencies":{"gltf-validator":"2.0.0-dev.3.10"}}' > "$GLTF_PACKAGE_ROOT/package.json"
npm install --prefix "$GLTF_PACKAGE_ROOT" --ignore-scripts --no-audit --no-fund --cache "$GLTF_PACKAGE_ROOT/npm-cache"
"$NODE_BIN" --version
```

预期安装精确版本，Node 输出 `v20.20.2`。随后锁定 Node 二进制和本计划 wrapper、`index.js`、`gltf_validator.dart.js`、package.json、package-lock.json 的完整 bytes/SHA-256；任何变化需要新 C。不得把 npm install 成功当作 validator 真正读完资产。


### Task 1: 冻结 GLB 有限政策与测试夹具

**Files:**
- Create: `acceptance/interchange_policy.py`
- Create: `tests/unit/interchange_support.py`
- Create: `tests/unit/test_interchange_policy.py`

**Interfaces:**
- Consumes: M1 `Contract.raw` / `thaw(value)`；M2 native policy 保持原形。
- Produces: `validate_interchange_policy(value: object) -> None`、`PRESET: dict`；`tests.unit.interchange_support.policy(package_root: Path) -> dict`。

- [ ] **Step 1: 写入可复现行为的失败测试。**

```python
import pytest
from acceptance.interchange_policy import validate_interchange_policy
from tests.unit.interchange_support import policy


@pytest.mark.parametrize(
    "mutation",
    [
        "nan",
        "bool",
        "unknown",
        "negative",
        "uv_loss",
        "package",
        "tolerance",
        "preset_bool",
    ],
)
def test_closed_policy_rejects_unsafe_values(tmp_path, mutation):
    value = policy(tmp_path)
    if mutation == "nan":
        value["reference_scale"] = float("nan")
    elif mutation == "bool":
        value["limits"]["max_nodes"] = True
    elif mutation == "unknown":
        value["extra"] = 1
    elif mutation == "negative":
        value["limits"]["max_glb_bytes"] = -1
    elif mutation == "uv_loss":
        value["losses"]["unused_uv_layers"] = "prune"
    elif mutation == "package":
        value["package_root"] = "relative"
    elif mutation == "preset_bool":
        value["preset"]["export_apply"] = 1
    else:
        value["tolerances"]["uv"]["abs"] = True
    with pytest.raises(ValueError):
        validate_interchange_policy(value)
```

- [ ] **Step 2: 运行当前任务测试，确认缺实现时失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_interchange_policy.py -q
```

预期：未添加模块时出现 import/行为断言失败；不得因测试跳过而记录绿色。

- [ ] **Step 3: 写入本任务的最小实现。**


`acceptance/interchange_policy.py`：

```python
from __future__ import annotations

import math
from pathlib import Path

PRESET = dict(
    export_format="GLB",
    export_apply=True,
    export_yup=True,
    export_draco_mesh_compression_enable=False,
    export_image_format="AUTO",
    export_cameras=False,
    export_lights=False,
    export_animations=False,
    export_extras=True,
    export_skins=False,
    export_morph=False,
    export_texcoords=True,
    export_normals=True,
    export_tangents=False,
    export_materials="EXPORT",
    use_selection=True,
    use_visible=False,
    use_renderable=False,
    use_active_collection=False,
)
LIMITS = {
    "max_glb_bytes",
    "max_json_bytes",
    "max_nodes",
    "max_meshes",
    "max_stored_triangles",
    "max_rendered_triangles",
    "max_draw_calls",
    "max_texture_pixels",
    "max_matches",
    "max_projection_triangles",
}


def validate_interchange_policy(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "profile",
        "preset",
        "package_root",
        "validator_version",
        "limits",
        "tolerances",
        "reference_scale",
        "allowed_extensions",
        "losses",
        "consumer",
    }:
        raise ValueError("closed interchange policy required")
    preset = value["preset"]
    if (
        value["profile"] != "glb-static-surface-v1"
        or not isinstance(preset, dict)
        or set(preset) != set(PRESET)
        or any(
            type(preset[k]) is not type(v) or preset[k] != v for k, v in PRESET.items()
        )
    ):
        raise ValueError("unsupported GLB preset/profile")
    if (
        value["validator_version"] != "2.0.0-dev.3.10"
        or not isinstance(value["package_root"], str)
        or (not Path(value["package_root"]).is_absolute())
    ):
        raise ValueError("locked validator package identity required")
    if not isinstance(value["limits"], dict) or set(value["limits"]) != LIMITS:
        raise ValueError("closed budget fields required")
    if any(type(n) is not int or n <= 0 for n in value["limits"].values()):
        raise ValueError("positive integer GLB budgets required")
    if (
        value["limits"]["max_projection_triangles"] > 4096
        or value["limits"]["max_matches"] > 2000000
    ):
        raise ValueError("bounded surface profile exceeded")
    if not isinstance(value["tolerances"], dict) or set(value["tolerances"]) != {
        "geometry",
        "normal",
        "uv",
        "material",
    }:
        raise ValueError("four typed tolerances required")
    for tolerance in value["tolerances"].values():
        if not isinstance(tolerance, dict) or set(tolerance) != {"abs", "rel"}:
            raise ValueError("closed abs/rel tolerance required")
        if any(
            type(n) not in (int, float) or not math.isfinite(n) or n < 0
            for n in tolerance.values()
        ):
            raise ValueError("finite nonnegative tolerance required")
    scale = value["reference_scale"]
    if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("positive frozen source reference scale required")
    if value["allowed_extensions"] != []:
        raise ValueError("first GLB profile accepts core glTF 2.0 only")
    if value["losses"] != {
        "collections": "omit",
        "modifiers": "bake",
        "unused_vertices": "prune",
        "unused_material_slots": "prune",
        "unused_uv_layers": "preserve",
    }:
        raise ValueError("explicit first-profile loss policy required")
    if value["consumer"] is not None and (
        not isinstance(value["consumer"], str) or not value["consumer"]
    ):
        raise ValueError("consumer must be null or a named required adapter")
```

`tests/unit/interchange_support.py`：

```python
import json
import struct
from pathlib import Path

from acceptance.interchange_policy import PRESET


def policy(package_root: Path):
    return {
        "profile": "glb-static-surface-v1",
        "preset": dict(PRESET),
        "package_root": str(package_root),
        "validator_version": "2.0.0-dev.3.10",
        "limits": {
            "max_glb_bytes": 8 * 1024 * 1024,
            "max_json_bytes": 1024 * 1024,
            "max_nodes": 100,
            "max_meshes": 100,
            "max_stored_triangles": 1000,
            "max_rendered_triangles": 2000,
            "max_draw_calls": 100,
            "max_texture_pixels": 1024 * 1024,
            "max_matches": 2000000,
            "max_projection_triangles": 4096,
        },
        "tolerances": {
            k: {"abs": 1e-5, "rel": 1e-6}
            for k in ("geometry", "normal", "uv", "material")
        },
        "reference_scale": 4.0,
        "allowed_extensions": [],
        "losses": {
            "collections": "omit",
            "modifiers": "bake",
            "unused_vertices": "prune",
            "unused_material_slots": "prune",
            "unused_uv_layers": "preserve",
        },
        "consumer": None,
    }


def projection():
    tri = {
        "corners": [
            {"position": p, "normal": [0.0, 0.0, 1.0], "uv": [[p[0], p[1]]]}
            for p in [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        ],
        "material": {
            "pbr": {
                "base_color": [0.2, 0.4, 0.8, 1.0],
                "metallic": 0.0,
                "roughness": 0.5,
                "alpha": 1.0,
                "emission": [0.0, 0.0, 0.0],
            },
            "texture": None,
            "double_sided": True,
        },
    }
    return {
        "schema_version": 2,
        "scale_length": 1,
        "objects": [
            {
                "id": ["OBJECT", "Asset"],
                "matrix": [
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 0.0],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "vertices": 12,
                "slots": 2,
                "custom": {"name": "kept"},
                "triangles": [tri],
            }
        ],
    }


def clean(report):
    return not any(report[k] for k in ("preserved", "transformed", "loss", "ambiguous"))


def make_budget_fixture(path, nodes):
    data = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": list(range(nodes))}],
        "nodes": [{"mesh": 0} for _ in range(nodes)],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [{"count": 3, "componentType": 5126, "type": "VEC3"}],
    }
    raw = json.dumps(data).encode()
    raw += b" " * ((-len(raw)) % 4)
    path.write_bytes(
        struct.pack("<4sIIII", b"glTF", 2, 20 + len(raw), len(raw), 0x4E4F534A) + raw
    )
```

- [ ] **Step 4: 复跑同一测试并确认行为通过。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_interchange_policy.py -q
```

预期：全部断言通过；本任务要求真实 Blender/Node 时须显式启用对应集成标志，不能把 skip 当实测。

- [ ] **Step 5: 审阅差异与提交门禁。**

```bash
git diff --check
```

预期退出 0。本包按末尾门禁做一次范围提交；提交前不包含用户原有改动、工具安装目录及证据缓存。


### Task 2: 有界表面比较与完整 Blender 采集

**Files:**
- Create: `acceptance/projection.py`
- Create: `acceptance/blender_scripts/projection_capture.py`
- Create: `tests/unit/test_projection_v2.py`

**Interfaces:**
- Consumes: Task 1 policy；Blender evaluated MESH、角点法线及 packed PNG；M2 R2 必须先完成安全/覆盖检查。
- Produces: `capture(objects, policy, *, imported=False) -> dict`、`render_manifest(objects) -> dict`、`validate_projection(value, max_triangles) -> None`、`compare_projection(source, imported, policy) -> dict`；报告固定四组 findings 和逐三角匹配。

- [ ] **Step 1: 写入可复现行为的失败测试。**

```python
import copy

import pytest
from acceptance.projection import compare_projection
from tests.unit.interchange_support import (
    clean,
    policy,
    projection,
)


def test_pruning_and_corner_rotation_preserve_the_actual_surface(tmp_path):
    source = projection()
    target = copy.deepcopy(source)
    target["objects"][0].update(vertices=3, slots=1)
    corners = target["objects"][0]["triangles"][0]["corners"]
    target["objects"][0]["triangles"][0]["corners"] = corners[1:] + corners[:1]
    assert clean(compare_projection(source, target, policy(tmp_path)))


@pytest.mark.parametrize(
    "field", ["position", "normal", "uv", "material", "custom", "identity", "winding"]
)
def test_same_counts_do_not_hide_semantic_loss(tmp_path, field):
    source = projection()
    target = copy.deepcopy(source)
    obj = target["objects"][0]
    tri = obj["triangles"][0]
    if field == "position":
        tri["corners"][0]["position"][0] += 0.1
    elif field == "normal":
        tri["corners"][0]["normal"][0] += 0.1
    elif field == "uv":
        tri["corners"][0]["uv"][0][0] += 0.1
    elif field == "material":
        tri["material"]["pbr"]["roughness"] = 0.9
    elif field == "custom":
        obj["custom"]["name"] = "lost"
    elif field == "identity":
        obj["id"][1] = "other"
    else:
        tri["corners"].reverse()
    assert not clean(compare_projection(source, target, policy(tmp_path)))


def test_duplicate_identity_and_matching_budget_do_not_pass(tmp_path):
    source = projection()
    target = copy.deepcopy(source)
    target["objects"].append(copy.deepcopy(target["objects"][0]))
    assert compare_projection(source, target, policy(tmp_path))["ambiguous"]
    source["objects"][0]["triangles"] *= 2
    limits = policy(tmp_path)
    limits["limits"]["max_matches"] = 1
    with pytest.raises(ValueError, match="matching budget"):
        compare_projection(source, copy.deepcopy(source), limits)
```

- [ ] **Step 2: 运行当前任务测试，确认缺实现时失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_projection_v2.py -q
```

预期：未添加模块时出现 import/行为断言失败；不得因测试跳过而记录绿色。

- [ ] **Step 3: 写入本任务的最小实现。**

对 p01/p09 比较 occurrence set，对 p02/p03/p04 比较世界三角表面及 bounds，对 p05 比较 UV 值/引用，对 p06–p08 比较使用中的 PBR/纹理解码，对 p12 精确比较属性，对 p13 比较世界变换及固定尺度；p10/p11 的允许变化固定在政策，p14 被 R2 支持门禁拒绝。cyclic rotation 可重排三角起点，反转 winding 不可接受。
`acceptance/projection.py`：

```python
from __future__ import annotations

import json
import math
from typing import Any


def exact(a: Any, b: Any) -> Any:
    return type(a) is type(b) and (
        a.keys() == b.keys() and all(exact(a[k], b[k]) for k in a)
        if isinstance(a, dict)
        else len(a) == len(b) and all(exact(x, y) for (x, y) in zip(a, b))
        if isinstance(a, list)
        else a == b
    )


def validate_projection(value: object, max_triangles: int) -> None:

    def fields(item: Any, keys: Any) -> Any:
        if not isinstance(item, dict) or set(item) != set(keys.split()):
            raise ValueError("closed projection fields mismatch")

    def vector(item: Any, n: Any) -> Any:
        if (
            not isinstance(item, list)
            or len(item) != n
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in item)
        ):
            raise ValueError("finite projection vector required")

    def finite_json(item: Any, depth: Any = 0) -> Any:
        if depth > 16:
            raise ValueError("custom property depth exceeded")
        if item is None or type(item) in (str, bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if isinstance(item, list):
            for child in item:
                finite_json(child, depth + 1)
            return
        if isinstance(item, dict) and all(isinstance(k, str) for k in item):
            for child in item.values():
                finite_json(child, depth + 1)
            return
        raise ValueError("unsupported projection JSON value")

    fields(value, "schema_version objects scale_length")
    assert isinstance(value, dict)
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 2
        or value["scale_length"] != 1
    ):
        raise ValueError("schema2 metre-scale projection required")
    if not isinstance(value["objects"], list) or not value["objects"]:
        raise ValueError("empty projection")
    total = 0
    for obj in value["objects"]:
        fields(obj, "id matrix vertices slots custom triangles")
        if (
            not isinstance(obj["id"], list)
            or len(obj["id"]) != 2
            or obj["id"][0] != "OBJECT"
            or (not isinstance(obj["id"][1], str))
            or (not obj["id"][1])
        ):
            raise ValueError("structured object identity required")
        if not isinstance(obj["matrix"], list) or len(obj["matrix"]) != 4:
            raise ValueError("4x4 matrix required")
        for row in obj["matrix"]:
            vector(row, 4)
        for key in ("vertices", "slots"):
            if type(obj[key]) is not int or obj[key] < 0:
                raise ValueError("nonnegative count required")
        if not isinstance(obj["custom"], dict):
            raise ValueError("custom mapping required")
        finite_json(obj["custom"])
        if not isinstance(obj["triangles"], list) or not obj["triangles"]:
            raise ValueError("nonempty triangle surface required")
        total += len(obj["triangles"])
        if total > max_triangles:
            raise ValueError("bounded triangle profile exceeded")
        for tri in obj["triangles"]:
            fields(tri, "corners material")
            if not isinstance(tri["corners"], list) or len(tri["corners"]) != 3:
                raise ValueError("three corners required")
            for corner in tri["corners"]:
                fields(corner, "position normal uv")
                vector(corner["position"], 3)
                vector(corner["normal"], 3)
                if not isinstance(corner["uv"], list):
                    raise ValueError("UV list required")
                for uv in corner["uv"]:
                    vector(uv, 2)
            material = tri["material"]
            fields(material, "pbr texture double_sided")
            if type(material["double_sided"]) is not bool:
                raise ValueError("boolean side policy required")
            pbr = material["pbr"]
            fields(pbr, "base_color metallic roughness alpha emission")
            if pbr["base_color"] is not None:
                vector(pbr["base_color"], 4)
            vector(pbr["emission"], 3)
            for key in ("metallic", "roughness", "alpha"):
                if (
                    type(pbr[key]) not in (int, float)
                    or not math.isfinite(pbr[key])
                    or (not 0 <= pbr[key] <= 1)
                ):
                    raise ValueError("bounded PBR scalar required")
            texture = material["texture"]
            if texture is not None:
                fields(
                    texture,
                    "size channels colorspace precision pixels sampling uv_index",
                )
                if (
                    not isinstance(texture["size"], list)
                    or len(texture["size"]) != 2
                    or any(type(n) is not int or n <= 0 for n in texture["size"])
                ):
                    raise ValueError("positive image size required")
                if (
                    texture["channels"] != 4
                    or texture["colorspace"] != "sRGB"
                    or texture["precision"] != "decoded-f32-le"
                ):
                    raise ValueError("supported texture representation required")
                if (
                    not isinstance(texture["pixels"], str)
                    or len(texture["pixels"]) != 64
                    or any(c not in "0123456789abcdef" for c in texture["pixels"])
                ):
                    raise ValueError("decoded texture digest required")
                if (
                    texture["sampling"] != ["Linear", "REPEAT"]
                    or type(texture["uv_index"]) is not int
                    or texture["uv_index"] < 0
                ):
                    raise ValueError("supported sampler/UV binding required")
                if any(texture["uv_index"] >= len(c["uv"]) for c in tri["corners"]):
                    raise ValueError("texture UV binding missing")
            if (pbr["base_color"] is None) != (texture is not None):
                raise ValueError("active base color representation mismatch")


def compare_projection(
    source: dict[str, Any], imported: dict[str, Any], policy: dict[str, Any]
) -> dict[str, Any]:
    cap = policy["limits"]["max_projection_triangles"]
    validate_projection(source, cap)
    validate_projection(imported, cap)
    report: dict[str, Any] = {
        "schema_version": 2,
        "preserved": [],
        "transformed": [],
        "loss": [],
        "ambiguous": [],
        "matches": [],
        "comparisons": 0,
    }

    def near(a: Any, b: Any, kind: Any) -> Any:
        if type(a) not in (int, float) or type(b) not in (int, float):
            return False
        t = policy["tolerances"][kind]
        scale = policy["reference_scale"] if kind == "geometry" else 1.0
        return abs(a - b) <= t["abs"] + t["rel"] * scale

    def sequence(a: Any, b: Any, kind: Any) -> Any:
        return len(a) == len(b) and all(
            sequence(x, y, kind)
            if isinstance(x, list) and isinstance(y, list)
            else near(x, y, kind)
            for (x, y) in zip(a, b)
        )

    def material(a: Any, b: Any) -> Any:
        if a["double_sided"] != b["double_sided"] or not exact(
            a["texture"], b["texture"]
        ):
            return False
        (x, y) = (a["pbr"], b["pbr"])
        if (x["base_color"] is None) != (y["base_color"] is None):
            return False
        if x["base_color"] is not None and (
            not sequence(x["base_color"], y["base_color"], "material")
        ):
            return False
        return sequence(x["emission"], y["emission"], "material") and all(
            near(x[k], y[k], "material") for k in ("metallic", "roughness", "alpha")
        )

    def corners(a: Any, b: Any) -> Any:
        return all(
            sequence(x["position"], y["position"], "geometry")
            and sequence(x["normal"], y["normal"], "normal")
            and sequence(x["uv"], y["uv"], "uv")
            for (x, y) in zip(a, b)
        )

    def indexed(data: Any) -> Any:
        return {
            json.dumps(o["id"], ensure_ascii=False, separators=(",", ":")): o
            for o in data["objects"]
        }

    (left, right) = (indexed(source), indexed(imported))
    if len(left) != len(source["objects"]) or len(right) != len(imported["objects"]):
        report["ambiguous"].append("duplicate occurrence identity")
        return report
    if left.keys() != right.keys():
        report["preserved"].append("p01/p09 occurrence set differs")
    for key in sorted(left.keys() & right.keys()):
        (a, b) = (left[key], right[key])
        if not exact(a["custom"], b["custom"]):
            report["preserved"].append(key + ":p12 custom properties differ")
        if not sequence(a["matrix"], b["matrix"], "geometry"):
            report["transformed"].append(key + ":p13 world matrix differs")
        (aa, bb) = (a["triangles"], b["triangles"])

        def bounds(triangles: Any) -> Any:
            points = [c["position"] for t in triangles for c in t["corners"]]
            return [[op(p[i] for p in points) for i in range(3)] for op in (min, max)]

        if not sequence(bounds(aa), bounds(bb), "geometry"):
            report["transformed"].append(key + ":p03 surface bounds differ")
        if len(aa) != len(bb):
            report["transformed"].append(key + ":p02 triangle count differs")
            continue
        adjacency = []
        for tri in aa:
            candidates = []
            for j, other in enumerate(bb):
                report["comparisons"] += 1
                if report["comparisons"] > policy["limits"]["max_matches"]:
                    raise ValueError("surface matching budget exceeded")
                if material(tri["material"], other["material"]) and any(
                    corners(tri["corners"], other["corners"][s:] + other["corners"][:s])
                    for s in range(3)
                ):
                    candidates.append(j)
            adjacency.append(candidates)
        owner: dict[int, int] = {}
        matched = True
        for start in range(len(aa)):
            queue = [start]
            seen = {start}
            predecessor = {}
            target = None
            for s in queue:
                for t in adjacency[s]:
                    if t in predecessor:
                        continue
                    predecessor[t] = s
                    if t not in owner:
                        target = t
                        break
                    if owner[t] not in seen:
                        seen.add(owner[t])
                        queue.append(owner[t])
                if target is not None:
                    break
            if target is None:
                matched = False
                break
            while target is not None:
                s = predecessor[target]
                old = next((t for (t, old_s) in owner.items() if old_s == s), None)
                owner[target] = s
                target = old
        if not matched:
            report["transformed"].append(
                key + ":p02-p08 corner surface/material mismatch"
            )
        report["matches"].append(
            {
                "id": a["id"],
                "complete": matched,
                "source_to_import": sorted([[s, t] for (t, s) in owner.items()]),
                "source_vertices": a["vertices"],
                "import_vertices": b["vertices"],
                "source_slots": a["slots"],
                "import_slots": b["slots"],
            }
        )
    return report
```

`acceptance/blender_scripts/projection_capture.py`：

```python
from __future__ import annotations

import hashlib
import json
import math
import struct
from array import array
from typing import Any

import bpy


def plain(value: Any) -> Any:
    if value is None or type(value) in (str, bool, int, float):
        return value
    if hasattr(value, "to_dict"):
        return {k: plain(v) for (k, v) in value.to_dict().items()}
    if hasattr(value, "to_list"):
        return [plain(v) for v in value.to_list()]
    return [plain(v) for v in value]


def material_record(material: Any, mesh: Any, max_pixels: Any) -> Any:
    if material is None or not material.use_nodes:
        raise ValueError("one explicit Principled material required")
    nodes = material.node_tree.nodes
    shaders = [n for n in nodes if n.type == "BSDF_PRINCIPLED"]
    outputs = [n for n in nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output]
    if len(shaders) != 1 or len(outputs) != 1:
        raise ValueError("one active PBR surface required")
    node = shaders[0]
    link = list(outputs[0].inputs["Surface"].links)
    if (
        len(link) != 1
        or link[0].from_node != node
        or outputs[0].inputs["Volume"].is_linked
        or outputs[0].inputs["Displacement"].is_linked
    ):
        raise ValueError("unsupported material output")
    supported = {
        "Base Color",
        "Metallic",
        "Roughness",
        "Alpha",
        "Emission Color",
        "Emission Strength",
    }
    default = bpy.data.materials.new("Evaluator PBR defaults")
    default.use_nodes = True
    try:
        baseline = default.node_tree.nodes.get("Principled BSDF")
        defaults = {
            socket.identifier: plain(socket.default_value)
            for socket in baseline.inputs
            if hasattr(socket, "default_value")
        }
        for socket in node.inputs:
            if socket.is_linked and socket.name != "Base Color":
                raise ValueError("unsupported linked PBR socket:" + socket.name)
            if (
                socket.name not in supported
                and hasattr(socket, "default_value")
                and (plain(socket.default_value) != defaults.get(socket.identifier))
            ):
                raise ValueError("unsupported nondefault PBR socket:" + socket.name)
    finally:
        bpy.data.materials.remove(default)
    pbr = {
        "base_color": list(node.inputs["Base Color"].default_value),
        "metallic": float(node.inputs["Metallic"].default_value),
        "roughness": float(node.inputs["Roughness"].default_value),
        "alpha": float(node.inputs["Alpha"].default_value),
        "emission": [
            float(x) * float(node.inputs["Emission Strength"].default_value)
            for x in node.inputs["Emission Color"].default_value[:3]
        ],
    }
    texture = None
    if node.inputs["Base Color"].is_linked:
        links = list(node.inputs["Base Color"].links)
        if (
            len(links) != 1
            or links[0].from_node.type != "TEX_IMAGE"
            or links[0].from_socket.name != "Color"
        ):
            raise ValueError("direct base-color texture required")
        image_node = links[0].from_node
        img = image_node.image
        if (
            img is None
            or img.is_float
            or img.packed_file is None
            or (img.channels != 4)
            or (img.colorspace_settings.name != "sRGB")
        ):
            raise ValueError("packed sRGB RGBA8 texture required")
        if (
            img.size[0] * img.size[1] > max_pixels
            or len(img.packed_file.data) < 33
            or (not img.packed_file.data.startswith(b"\x89PNG\r\n\x1a\n"))
            or (img.packed_file.data[24:26] != bytes([8, 6]))
        ):
            raise ValueError("bounded RGBA8 PNG texture required")
        if (
            image_node.interpolation != "Linear"
            or image_node.extension != "REPEAT"
            or image_node.projection != "FLAT"
        ):
            raise ValueError("supported linear repeat sampler required")
        if image_node.inputs["Vector"].is_linked:
            raise ValueError("first profile uses active render UV without vector nodes")
        uv_index = next(
            (i for (i, uv) in enumerate(mesh.uv_layers) if uv.active_render), None
        )
        if uv_index is None:
            raise ValueError("texture has no active render UV")
        data = array("f", [0.0]) * len(img.pixels)
        img.pixels.foreach_get(data)
        if not all(math.isfinite(x) for x in data):
            raise ValueError("finite texture pixels required")
        texture = {
            "size": list(img.size),
            "channels": img.channels,
            "colorspace": "sRGB",
            "precision": "decoded-f32-le",
            "pixels": hashlib.sha256(
                struct.pack("<" + str(len(data)) + "f", *data)
            ).hexdigest(),
            "sampling": ["Linear", "REPEAT"],
            "uv_index": uv_index,
        }
        pbr["base_color"] = None
    return {
        "pbr": pbr,
        "texture": texture,
        "double_sided": not material.use_backface_culling,
    }


def capture(objects: Any, policy: Any, *, imported: Any = False) -> Any:
    if bpy.context.scene.unit_settings.scale_length != 1:
        raise ValueError("metre scale required")
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    records = []
    total = 0
    for obj in sorted(objects, key=lambda x: x.name):
        if obj.type != "MESH" or obj.matrix_world.to_3x3().determinant() <= 0:
            raise ValueError("non-mirrored static mesh required")
        identity = json.loads(obj["bcx_uid"]) if imported else ["OBJECT", obj.name]
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        try:
            mesh.calc_loop_triangles()
            total += len(mesh.loop_triangles)
            if total > policy["limits"]["max_projection_triangles"]:
                raise ValueError("bounded projection triangle count exceeded")
            matrix = obj.matrix_world.to_3x3().inverted().transposed()
            triangles = []
            materials = {}
            for tri in mesh.loop_triangles:
                if tri.material_index not in materials:
                    material = (
                        mesh.materials[tri.material_index]
                        if tri.material_index < len(mesh.materials)
                        else None
                    )
                    materials[tri.material_index] = material_record(
                        material, mesh, policy["limits"]["max_texture_pixels"]
                    )
                corners = []
                for loop_id in tri.loops:
                    point = (
                        obj.matrix_world
                        @ mesh.vertices[mesh.loops[loop_id].vertex_index].co
                    )
                    normal = (matrix @ mesh.corner_normals[loop_id].vector).normalized()
                    corners.append(
                        {
                            "position": list(point),
                            "normal": list(normal),
                            "uv": [list(uv.data[loop_id].uv) for uv in mesh.uv_layers],
                        }
                    )
                triangles.append(
                    {"corners": corners, "material": materials[tri.material_index]}
                )
            records.append(
                {
                    "id": identity,
                    "matrix": [list(row) for row in obj.matrix_world],
                    "vertices": len(mesh.vertices),
                    "slots": len(mesh.materials),
                    "custom": {k: plain(obj[k]) for k in obj.keys() if k != "bcx_uid"},
                    "triangles": triangles,
                }
            )
        finally:
            evaluated.to_mesh_clear()
    return {"schema_version": 2, "objects": records, "scale_length": 1}


def render_manifest(objects: Any) -> Any:
    return {
        "scope_gaps": [],
        "occurrences": [
            {
                "source": ["OBJECT", o.name],
                "matrix_world": [list(row) for row in o.matrix_world],
            }
            for o in objects
        ],
    }
```

- [ ] **Step 4: 复跑同一测试并确认行为通过。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_projection_v2.py -q
```

预期：全部断言通过；本任务要求真实 Blender/Node 时须显式启用对应集成标志，不能把 skip 当实测。

- [ ] **Step 5: 审阅差异与提交门禁。**

```bash
git diff --check
```

预期退出 0。本包按末尾门禁做一次范围提交；提交前不包含用户原有改动、工具安装目录及证据缓存。


### Task 3: 真实 Validator 与逐实例预算

**Files:**
- Create: `acceptance/glb_budget.py`
- Create: `acceptance/glb_budget_worker.py`
- Create: `acceptance/node_scripts/validator_worker.mjs`
- Create: `tests/unit/test_glb_budget_v2.py`

**Interfaces:**
- Consumes: 已接收 `delivery.glb: BoundFile` 和 Task 1 policy；M1 request/result 八项身份。
- Produces: `measure_glb(path: Path, limits: dict) -> dict`；文件 `validator.report`、`validator.resources`、`glb.budget`；budget worker 仅拥有 `r3.budget.within_limits`，其余结论由 controller 判读。

- [ ] **Step 1: 写入可复现行为的失败测试。**

```python
import pytest
from acceptance.glb_budget import measure_glb
from tests.unit.interchange_support import make_budget_fixture, policy


def test_budget_counts_each_instance_separately(tmp_path):
    path = tmp_path / "scene.glb"
    make_budget_fixture(path, 2)
    limits = policy(tmp_path)["limits"]
    limits["max_rendered_triangles"] = 1
    measured = measure_glb(path, limits)
    assert measured["stored_triangles"] == 1 and measured["rendered_triangles"] == 2
    assert measured["draw_calls"] == 2 and measured["exceeded"] == [
        "rendered_triangles"
    ]


def test_short_glb_and_wrong_length_are_rejected(tmp_path):
    path = tmp_path / "bad.glb"
    path.write_bytes(b"glTF")
    with pytest.raises(ValueError, match="header"):
        measure_glb(path, policy(tmp_path)["limits"])
    make_budget_fixture(path, 1)
    path.write_bytes(path.read_bytes() + b"xxxx")
    with pytest.raises(ValueError, match="header"):
        measure_glb(path, policy(tmp_path)["limits"])
```

- [ ] **Step 2: 运行当前任务测试，确认缺实现时失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_glb_budget_v2.py -q
```

预期：未添加模块时出现 import/行为断言失败；不得因测试跳过而记录绿色。

- [ ] **Step 3: 写入本任务的最小实现。**

预算 parser 不替代格式 validator。`stored_triangles` 是唯一 mesh 数据，`rendered_triangles/draw_calls` 从实际 scene node 图累加；同一 mesh 两个 node 算两份绘制。外部/data URI 均不属于首发自包含 GLB。Task 5 还必须用真实 Node 验证零错误、缺资源、截断和报告资源行。
`acceptance/glb_budget.py`：

```python
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

from acceptance.strict_json import strict_json_loads


def measure_glb(path: Path, limits: dict[str, Any]) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(limits["max_glb_bytes"] + 1)
    if len(raw) > limits["max_glb_bytes"]:
        raise ValueError("GLB byte budget exceeded")
    if len(raw) < 20 or struct.unpack_from("<4sII", raw) != (b"glTF", 2, len(raw)):
        raise ValueError("invalid GLB header/length")
    offset = 12
    chunks = []
    while offset < len(raw):
        if offset + 8 > len(raw):
            raise ValueError("short GLB chunk")
        (length, kind) = struct.unpack_from("<II", raw, offset)
        offset += 8
        if length % 4 or offset + length > len(raw):
            raise ValueError("invalid chunk boundary")
        chunks.append((kind, raw[offset : offset + length]))
        offset += length
    if (
        len(chunks) not in (1, 2)
        or chunks[0][0] != 1313821514
        or (len(chunks) == 2 and chunks[1][0] != 5130562)
    ):
        raise ValueError("one JSON and optional BIN chunk required")
    if len(chunks[0][1]) > limits["max_json_bytes"]:
        raise ValueError("GLB JSON budget exceeded")
    document = strict_json_loads(chunks[0][1])
    if (
        not isinstance(document, dict)
        or document.get("asset", {}).get("version") != "2.0"
    ):
        raise ValueError("glTF 2.0 required")
    meshes = document.get("meshes", [])
    nodes = document.get("nodes", [])
    accessors = document.get("accessors", [])
    if len(meshes) > limits["max_meshes"] or len(nodes) > limits["max_nodes"]:
        raise ValueError("GLB node/mesh budget exceeded")

    def index(items: Any, i: Any) -> Any:
        if type(i) is not int or not 0 <= i < len(items):
            raise ValueError("GLB index outside array")
        return items[i]

    mesh_counts = []
    for mesh in meshes:
        triangles = 0
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) != 4:
                raise ValueError("triangle primitive required")
            accessor = index(
                accessors, primitive.get("indices", primitive["attributes"]["POSITION"])
            )
            count = accessor["count"]
            if type(count) is not int or count < 0 or count % 3:
                raise ValueError("triangle count malformed")
            triangles += count // 3
        mesh_counts.append((triangles, len(mesh["primitives"])))
    scenes = document.get("scenes", [])
    roots = index(scenes, document.get("scene", 0))["nodes"]
    seen = set()
    pending = list(roots)
    rendered = 0
    draws = 0
    while pending:
        n = pending.pop()
        node = index(nodes, n)
        if n in seen:
            raise ValueError("cycle or multiple-parent scene graph")
        seen.add(n)
        if "mesh" in node:
            (triangles, calls) = index(mesh_counts, node["mesh"])
            rendered += triangles
            draws += calls
        pending.extend(node.get("children", []))
    resources = document.get("buffers", []) + document.get("images", [])
    if any("uri" in r for r in resources):
        raise ValueError("self-contained GLB forbids every URI including data URI")
    result: dict[str, Any] = {
        "schema_version": 2,
        "bytes": len(raw),
        "nodes": len(nodes),
        "meshes": len(meshes),
        "stored_triangles": sum(x[0] for x in mesh_counts),
        "rendered_triangles": rendered,
        "draw_calls": draws,
        "extensions": sorted(
            set(document.get("extensionsUsed", []))
            | set(document.get("extensionsRequired", []))
        ),
        "external_resources": 0,
        "resource_pointers": [
            "/buffers/" + str(i) for i in range(len(document.get("buffers", [])))
        ]
        + ["/images/" + str(i) for i in range(len(document.get("images", [])))],
        "exceeded": [],
    }
    for field, limit in [
        ("stored_triangles", "max_stored_triangles"),
        ("rendered_triangles", "max_rendered_triangles"),
        ("draw_calls", "max_draw_calls"),
    ]:
        if result[field] > limits[limit]:
            result["exceeded"].append(field)
    return result
```

`acceptance/glb_budget_worker.py`：

```python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from acceptance.glb_budget import measure_glb
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.worker_protocol import read_request, write_result


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    request = read_request(parser.parse_args().request)
    policy = request["parameters"]["policy"]
    validate_interchange_policy(policy)
    entry = next(x for x in request["inputs"] if x["id"] == "delivery.glb")
    value = measure_glb(Path(request["input_root"]) / entry["path"], policy["limits"])
    output = next(x for x in request["outputs"] if x["id"] == "glb.budget")
    target = Path(request["output_root"]) / output["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
    findings = [
        {
            "code": "budget_exceeded",
            "severity": "error",
            "pointer": None,
            "detail": name,
        }
        for name in value["exceeded"]
    ]
    write_result(
        request,
        [
            {
                "id": "r3.budget.within_limits",
                "findings": findings,
                "metrics": {
                    "stored_triangles": value["stored_triangles"],
                    "rendered_triangles": value["rendered_triangles"],
                    "draw_calls": value["draw_calls"],
                },
            }
        ],
        {"pid": str(os.getpid())},
    )


if __name__ == "__main__":
    main()
```

`acceptance/node_scripts/validator_worker.mjs`：

```javascript
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const argv=process.argv.slice(2);
if(argv.length!==2 || argv[0]!=='--request') throw Error('exact --request argument required');
const request=JSON.parse(fs.readFileSync(argv[1],'utf8'));
const policy=request.parameters.policy;
const validator=require(path.join(policy.package_root,'node_modules/gltf-validator/index.js'));
if(validator.version()!==policy.validator_version) throw Error('validator version mismatch');
const input=request.inputs.find(x=>x.id==='delivery.glb');
if(!input || input.bytes>policy.limits.max_glb_bytes) throw Error('bounded GLB input required');
const raw=fs.readFileSync(path.join(request.input_root,input.path));
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
if(raw.length!==input.bytes || sha(raw)!==input.sha256) throw Error('GLB input identity mismatch');
const external=[];
const report=await validator.validateBytes(new Uint8Array(raw),{
    format:'glb',uri:'delivery.glb',maxIssues:10000,writeTimestamp:false,
    externalResourceFunction:async uri=>{external.push(uri);throw Error('external resource forbidden');}
});
const data={'validator.report':report,'validator.resources':{
    schema_version:2,input_sha256:input.sha256,input_bytes:raw.length,
    external_requests:external,resources:report.info?.resources??[]
}};
const artifacts=[];
for(const output of request.outputs){
    if(!Object.hasOwn(data,output.id)) throw Error('unknown validator output');
    const bytes=Buffer.from(JSON.stringify(data[output.id])+'\n');
    if(bytes.length>output.max_bytes) throw Error('validator report exceeds file budget');
    const target=path.join(request.output_root,output.path);
    fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,bytes,{flag:'wx'});
    artifacts.push({id:output.id,path:output.path,bytes:bytes.length,sha256:sha(bytes)});
}
const result=Object.fromEntries(['schema_version','run_id','attempt','nonce','job_id','writer','contract_digest','source_digest'].map(k=>[k,request[k]]));
Object.assign(result,{checks:[],artifacts,observations:{node:process.version,validator:validator.version(),pid:String(process.pid)}});
fs.writeFileSync(path.join(request.output_root,'result.json'),JSON.stringify(result)+'\n',{flag:'wx'});
```

- [ ] **Step 4: 复跑同一测试并确认行为通过。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_glb_budget_v2.py -q
```

预期：全部断言通过；本任务要求真实 Blender/Node 时须显式启用对应集成标志，不能把 skip 当实测。

- [ ] **Step 5: 审阅差异与提交门禁。**

```bash
git diff --check
```

预期退出 0。本包按末尾门禁做一次范围提交；提交前不包含用户原有改动、工具安装目录及证据缓存。


### Task 4: 交付作业、controller 复核与 CLI 完整接线

**Files:**
- Create: `acceptance/blender_scripts/glb_worker.py`
- Create: `acceptance/projection_worker.py`
- Create: `acceptance/interchange_plan.py`
- Create: `acceptance/interchange_results.py`
- Create: `acceptance/interchange_run.py`
- Create: `tests/integration/interchange_runtime_support.py`
- Create: `tests/integration/test_asset_interchange.py`
- Create: `tests/unit/test_interchange_results.py`
- Modify: `acceptance/contract.py:validate_document`
- Modify: `scripts/asset_accept.py:dispatch_run`
- Create: `tests/unit/test_interchange_contract.py`

**Interfaces:**
- Consumes: M1 `read_request/write_result`、`JobSpec(...,blocking_check_ids=())`、`assemble_plan(...,gate_ids=())`、`run_jobs`、`finalize_run(...,delivery:BoundFile|None,coordinator_findings,gates)`；M2 `native_jobs(contract,*,include_reopen=True)`、`native_results(contract,run)->(findings,gates)`、`render_images`、`compare`、`prepare_native_case`/`AssetCase`/`write_case`/`run_case`。
- Produces: `build_interchange_plan(contract)->RunPlan`、`interchange_commands(blender,node,python,repository)->dict[str,tuple[str,...]]`、`interchange_results(contract,run)->(dict[str,list[Finding]],dict[str,Gate])`、`run_interchange(contract_path,source_root,evidence_root,scratch_root)->dict`；CLI 状态字段沿用 M1 的 `state`，manifest 控制文件是 `evidence-manifest.json`。

该任务作为一个集成单元，避免中途提交一个可调度却不能复核或封装的 GLB 入口。几何算法与格式/预算已由前三个任务独立验收；本任务的每个写入步骤只接通一个边界，最后共享一次真实 CLI 红绿回归。

- [ ] **Step 1: 写入真实 CLI 夹具适配器和失败回归。**

`tests/integration/interchange_runtime_support.py`：

```python
import subprocess
from pathlib import Path

from acceptance import check_registry as reg
from acceptance.interchange_plan import interchange_commands
from tests.integration.asset_runtime_support import (
    REPO,
    prepare_native_case,
    write_case,
)
from tests.unit.asset_v2_support import file_lock
from tests.unit.interchange_support import policy


def prepare_interchange_case(
    blender: Path,
    node: Path,
    python: Path,
    package_root: Path,
    root: Path,
    fixture_name="good",
    *,
    calibration_root=None,
):
    case = prepare_native_case(
        blender, root, fixture_name, calibration_root=calibration_root
    )
    doc = case.document
    doc["artifact_kind"] = "interchange"
    doc["checks"] = [
        {"id": s.id, "impl": s.impl, "order": s.order}
        for s in sorted(reg.checks_for_kind("interchange"), key=reg.sort_key)
    ]
    doc["na_check_ids"] = list(reg.na_check_ids("interchange"))
    doc["interchange"] = policy(package_root)
    doc["tools"].append(
        {
            "id": "node",
            "path": str(node.resolve()),
            "version": subprocess.check_output(
                [str(node), "--version"], text=True
            ).strip(),
            "sha256": file_lock(node)["sha256"],
            "files": [
                file_lock(p)
                for p in [
                    REPO / "acceptance/node_scripts/validator_worker.mjs",
                    package_root / "package.json",
                    package_root / "package-lock.json",
                    package_root / "node_modules/gltf-validator/package.json",
                    package_root / "node_modules/gltf-validator/index.js",
                    package_root / "node_modules/gltf-validator/gltf_validator.dart.js",
                ]
            ],
        }
    )
    gltf_root = (
        blender.resolve().parents[1]
        / "Resources/5.2/scripts/addons_core/io_scene_gltf2"
    )
    if not (gltf_root / "__init__.py").is_file():
        raise ValueError("locked Blender glTF module not found")
    for tool in doc["tools"]:
        if tool["id"] == "blender":
            tool["files"] += [
                file_lock(REPO / "acceptance/blender_scripts" / name)
                for name in ("glb_worker.py", "projection_capture.py")
            ] + [file_lock(path) for path in sorted(gltf_root.rglob("*.py"))]
        if tool["id"] == "python":
            tool["files"] += [
                file_lock(REPO / "acceptance" / name)
                for name in ("glb_budget_worker.py", "projection_worker.py")
            ]
    doc["limits"]["timeout_seconds"] = {
        key: 600 for key in interchange_commands(blender, node, python, REPO)
    }
    doc["review"]["required_image_ids"] += [
        "image.projection_source.0.front.beauty",
        "image.projection_import.0.front.beauty",
        "image.projection_source.0.bottom.silhouette",
        "image.projection_import.0.bottom.silhouette",
    ]
    write_case(case)
    return case
```

`tests/integration/test_asset_interchange.py`：

```python
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest
from acceptance.evidence import deliver, finish_review
from tests.integration.asset_runtime_support import (
    prepare_calibration,
    run_case,
    write_case,
)
from tests.integration.interchange_runtime_support import prepare_interchange_case

pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_INTERCHANGE") != "1",
        reason="explicit real Blender+Node integration",
    ),
]


@pytest.fixture(scope="module")
def environment(tmp_path_factory):
    blender = Path(os.environ["BLENDER_BIN"])
    node = Path(os.environ["NODE_BIN"])
    package = Path(os.environ["GLTF_PACKAGE_ROOT"])
    root = tmp_path_factory.mktemp("m3-calibration")
    calibration = prepare_calibration(blender, root / "reference")
    return blender, node, Path(sys.executable), package, calibration


def test_real_interchange_full_chain_and_exact_delivery(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender, node, python, package, tmp_path, calibration_root=calibration
    )
    code, status = run_case(case)
    assert status["state"] == "NEEDS_REVIEW", status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is True and not summary["failed_check_ids"]
    assert (
        len(
            [
                x
                for x in summary["checks"]
                if x["raw_status"] != "NotApplicableByContract"
            ]
        )
        == 34
    )
    assert all(x["complete"] for x in summary["gates"].values())
    # This record authorizes only this generated test asset.
    manifest = json.loads((case.evidence_root / "evidence-manifest.json").read_text())
    files = {x["id"]: x for x in manifest["files"]}
    delivery = case.evidence_root / "payload" / files["delivery.glb"]["path"]
    before = hashlib.sha256(delivery.read_bytes()).hexdigest()
    review = {
        "schema_version": 2,
        "bindings": status["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_at": "2026-09-08T00:00:00+00:00",
                "reviewed_images": [
                    {"id": fid, "sha256": files[fid]["sha256"]}
                    for fid in case.document["review"]["required_image_ids"]
                ],
                "note": "Generated known-fixture approval only; no production artwork authorized",
            }
        ],
    }
    done = finish_review(case.evidence_root, delivery_path=delivery, review=review)
    assert done["state"] in {"SHIP", "SHIP_WITH_NOTES"}
    assert hashlib.sha256(delivery.read_bytes()).hexdigest() == before
    assert (case.evidence_root / "completion.json").is_file()
    destination = tmp_path / "delivered.glb"
    receipt = deliver(
        case.evidence_root, delivery_path=delivery, destination=destination
    )
    assert (
        receipt["D"] == before
        and hashlib.sha256(destination.read_bytes()).hexdigest() == before
    )
    assert (
        receipt["T"]
        == hashlib.sha256(
            (case.evidence_root / "completion.json").read_bytes()
        ).hexdigest()
    )


def test_missing_consumer_cannot_ship(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender, node, python, package, tmp_path, calibration_root=calibration
    )
    case.document["interchange"]["consumer"] = "required-engine-with-no-adapter"
    write_case(case)
    code, status = run_case(case)
    assert status["state"] == "UNVERIFIED" and code != 0, status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is False
    assert not summary["gates"]["interchange.consumer"]["complete"]


def test_actual_missing_bottom_is_not_approved(environment, tmp_path):
    blender, node, python, package, calibration = environment
    case = prepare_interchange_case(
        blender,
        node,
        python,
        package,
        tmp_path,
        "missing_bottom",
        calibration_root=calibration,
    )
    code, status = run_case(case)
    assert status["state"] == "REJECTED" and code != 0, status
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is False
    assert summary["gates"]["native.reference"]["findings"]
```

- [ ] **Step 2: 确认生产入口尚未实现该闭环时失败。**

```bash
RUN_ASSET_INTERCHANGE=1 "$PYTHON_BIN" -m pytest tests/integration/test_asset_interchange.py -q
```

预期未实现入口/文件导致失败；不接受 skip。测试 fixture-reviewer 只授权测试生成的已知资产，不授权用户作品。

- [ ] **Step 3: 写入 Blender 导出/导入/投影视觉与独立表面报告 worker。**

`acceptance/blender_scripts/glb_worker.py`：

```python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import bpy

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from acceptance.blender_scripts.native_render import (
    compare,
    render_images,
)
from acceptance.blender_scripts.native_worker import (
    read_json,
    sha,
    write_json,
)
from acceptance.blender_scripts.projection_capture import (
    capture,
    render_manifest,
)
from acceptance.interchange_policy import (
    PRESET,
    validate_interchange_policy,
)
from acceptance.native_policy import PASSES, VIEWS
from acceptance.projection import validate_projection
from acceptance.worker_protocol import read_request, write_result


def work(request: Any) -> Any:
    p = request["parameters"]
    if set(p) != {"operation", "policy", "native"} or p["operation"] not in {
        "export",
        "import",
        "source_render",
        "compare",
    }:
        raise ValueError("closed GLB worker operation required")
    policy = p["policy"]
    validate_interchange_policy(policy)
    inputs = {
        x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]
    }
    outputs = {
        x["id"]: Path(request["output_root"]) / x["path"] for x in request["outputs"]
    }
    if p["operation"] == "compare":
        rows = []
        for view in VIEWS:
            for render_pass in PASSES:
                left = f"image.projection_source.0.{view}.{render_pass}"
                right = f"image.projection_import.0.{view}.{render_pass}"
                diff = f"diff.projection.{view}.{render_pass}"
                outputs[diff].parent.mkdir(parents=True, exist_ok=True)
                row = compare(
                    inputs[left],
                    inputs[right],
                    outputs[diff],
                    p["native"]["geometry_limits"]["max_image_pixels"],
                )
                row.update(
                    {
                        "view": view,
                        "pass": render_pass,
                        "left_id": left,
                        "right_id": right,
                        "diff_id": diff,
                    }
                )
                rows.append(row)
        write_json(
            outputs["projection.visual"], {"schema_version": 2, "comparisons": rows}
        )
        return []
    if p["operation"] == "import":
        validation = read_json(inputs["validator.report"])
        budget = read_json(inputs["glb.budget"])
        if (
            validation["issues"]["truncated"]
            or validation["issues"]["numErrors"]
            or budget["extensions"]
            or budget["exceeded"]
        ):
            raise ValueError(
                "import blocked by unsafe/incomplete GLB validation or budget"
            )
        bpy.ops.wm.read_factory_settings(use_empty=True)
        before = sha(inputs["delivery.glb"])
        bpy.ops.import_scene.gltf(filepath=str(inputs["delivery.glb"]))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        projection = capture(objects, policy, imported=True)
        validate_projection(projection, policy["limits"]["max_projection_triangles"])
        write_json(outputs["projection.import"], projection)
        report = render_images(
            render_manifest(objects),
            p["native"]["render"],
            outputs,
            "projection_import",
        )
        report["input_sha256_before"] = before
        report["input_sha256_after"] = sha(inputs["delivery.glb"])
        write_json(outputs["render.projection_import"], report)
        return [
            {
                "id": "r4.import.manifest_written",
                "findings": [],
                "metrics": {"objects": len(objects)},
            }
        ]
    before = sha(inputs["asset"])
    bpy.ops.wm.open_mainfile(
        filepath=str(inputs["asset"]), load_ui=False, use_scripts=False
    )
    native = p["native"]
    bpy.context.window.scene = bpy.data.scenes[native["scene"]]
    bpy.context.window.view_layer = bpy.context.scene.view_layers[native["view_layer"]]
    bpy.context.scene.frame_set(native["frame"])
    manifest = read_json(inputs["native.manifest"])
    objects = [
        bpy.context.scene.objects[o["source"][1]] for o in manifest["occurrences"]
    ]
    if any(o.type == "EMPTY" and list(o.keys()) for o in bpy.context.scene.objects):
        raise ValueError("custom properties on omitted EMPTY unsupported")
    if any(
        k.startswith(("bcx_", "acceptance_"))
        for o in bpy.context.scene.objects
        for k in o.keys()
    ):
        raise ValueError("candidate cannot supply evaluator identity")
    projection = capture(objects, policy)
    validate_projection(projection, policy["limits"]["max_projection_triangles"])
    if p["operation"] == "source_render":
        report = render_images(
            render_manifest(objects), native["render"], outputs, "projection_source"
        )
        report["input_sha256_before"] = before
        report["input_sha256_after"] = sha(inputs["asset"])
        write_json(outputs["render.projection_source"], report)
        return []
    write_json(outputs["projection.source"], projection)
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj["bcx_uid"] = json.dumps(
            ["OBJECT", obj.name], ensure_ascii=False, separators=(",", ":")
        )
        obj.select_set(True)
    if not objects:
        raise ValueError("no exportable surfaces")
    bpy.context.view_layer.objects.active = objects[0]
    outputs["delivery.glb"].parent.mkdir(parents=True, exist_ok=True)
    if outputs["delivery.glb"].exists():
        raise FileExistsError(outputs["delivery.glb"])
    bpy.ops.export_scene.gltf(filepath=str(outputs["delivery.glb"]), **PRESET)
    after = sha(inputs["asset"])
    write_json(
        outputs["export.measurements"],
        {
            "schema_version": 2,
            "source_before": before,
            "source_after": after,
            "delivery_sha256": sha(outputs["delivery.glb"]),
            "exported_ids": [x["id"] for x in projection["objects"]],
            "preset": PRESET,
        },
    )

    def finding(code: Any) -> Any:
        return {"code": code, "severity": "error", "pointer": None, "detail": code}

    return [
        {
            "id": "r3.export.file_nonempty",
            "findings": []
            if outputs["delivery.glb"].stat().st_size > 20
            else [finding("empty_export")],
            "metrics": {},
        },
        {
            "id": "r3.export.source_unchanged",
            "findings": [] if before == after else [finding("source_modified")],
            "metrics": {},
        },
    ]


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    request = read_request(args.request)
    checks = work(request)
    write_result(
        request, checks, {"pid": str(os.getpid()), "blender": bpy.app.version_string}
    )


if __name__ == "__main__":
    main()
```

`acceptance/projection_worker.py`：

```python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from acceptance.native_results import load
from acceptance.projection import compare_projection
from acceptance.worker_protocol import read_request, write_result


def main() -> Any:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    request = read_request(parser.parse_args().request)
    inputs = {
        x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]
    }
    value = compare_projection(
        load(inputs["projection.source"]),
        load(inputs["projection.import"]),
        request["parameters"]["policy"],
    )
    output = next(x for x in request["outputs"] if x["id"] == "projection.matches")
    target = Path(request["output_root"]) / output["path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
    write_result(request, [], {"pid": str(os.getpid())})


if __name__ == "__main__":
    main()
```


- [ ] **Step 4: 写入唯一作业展开和固定命令构造。**

34 个适用 check 各只有一个 writer；native reopen 三项转为 N/A。重复/import/compare 作业不重发 source check IDs。GLB、完整 validator/budget/匹配报告、每张原图/差异图和每个协议结果均固定到一个文件 writer。只有 R2 安全前置失败才阻止后续作业；一般质量差异继续收集诊断。import 自身先检查完整 validator 和预算，未满足安全前置不解析 D。

```python
from pathlib import Path
from typing import Any

from acceptance.contract import thaw
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.native_plan import NATIVE_GATES, UNSAFE_R2, native_commands, native_jobs
from acceptance.native_policy import PASSES, VIEWS
from acceptance.plan import FileSpec, JobSpec, assemble_plan

GLB_GATES = ("interchange.scope_supported", "interchange.consumer")


def build_interchange_plan(contract: Any) -> Any:
    if contract.artifact_kind != "interchange":
        raise ValueError("interchange contract required")
    policy = thaw(contract.raw["interchange"])
    validate_interchange_policy(policy)
    native = thaw(contract.raw["native"])

    def output(fid: Any, writer: Any, extension: Any = "json") -> Any:
        return FileSpec(
            fid,
            ("images/" if extension == "png" else "data/") + fid + "." + extension,
            writer,
            "image/png"
            if extension == "png"
            else "model/gltf-binary"
            if extension == "glb"
            else "application/json",
            policy["limits"]["max_glb_bytes"]
            if extension == "glb"
            else 64 * 1024 * 1024,
        )

    def job(
        jid: Any,
        writer: Any,
        tool: Any,
        checks: Any,
        inputs: Any,
        outputs: Any,
        operation: Any,
    ) -> Any:
        return JobSpec(
            jid,
            writer,
            tool,
            tuple(checks),
            tuple(inputs),
            tuple(outputs),
            {"operation": operation, "policy": policy, "native": native},
            UNSAFE_R2,
        )

    jobs = list(native_jobs(contract, include_reopen=False))
    jobs.append(
        job(
            "glb.export",
            "export_glb",
            "blender",
            ["r3.export.file_nonempty", "r3.export.source_unchanged"],
            ["asset", "native.manifest"],
            [
                output("delivery.glb", "export_glb", "glb"),
                output("projection.source", "export_glb"),
                output("export.measurements", "export_glb"),
            ],
            "export",
        )
    )
    jobs.append(
        job(
            "glb.validator",
            "validator",
            "node",
            [],
            ["delivery.glb"],
            [
                output("validator.report", "validator"),
                output("validator.resources", "validator"),
            ],
            "validator",
        )
    )
    jobs.append(
        job(
            "glb.budget",
            "glb_budget",
            "python",
            ["r3.budget.within_limits"],
            ["delivery.glb"],
            [output("glb.budget", "glb_budget")],
            "budget",
        )
    )
    all_images: list[str] = []
    for experiment, writer, operation in [
        ("projection_source", "render_views(projection-source)", "source_render"),
        ("projection_import", "reimport_probe", "import"),
    ]:
        images = [
            output(f"image.{experiment}.0.{v}.{p}", writer, "png")
            for v in VIEWS
            for p in PASSES
        ]
        all_images.extend(x.id for x in images)
        outputs = images + [output("render." + experiment, writer)]
        if operation == "import":
            outputs.append(output("projection.import", writer))
        jobs.append(
            job(
                "glb." + experiment,
                writer,
                "blender",
                ["r4.import.manifest_written"] if operation == "import" else [],
                ["delivery.glb", "glb.budget", "validator.report"]
                if operation == "import"
                else ["asset", "native.manifest"],
                outputs,
                operation,
            )
        )
    jobs.append(
        job(
            "glb.surface_compare",
            "projection_compare",
            "python",
            [],
            ["projection.source", "projection.import"],
            [output("projection.matches", "projection_compare")],
            "projection",
        )
    )
    jobs.append(
        job(
            "glb.visual_compare",
            "glb_compare",
            "blender",
            [],
            all_images,
            [output("projection.visual", "glb_compare")]
            + [
                output(f"diff.projection.{v}.{p}", "glb_compare", "png")
                for v in VIEWS
                for p in PASSES
            ],
            "compare",
        )
    )
    return assemble_plan(contract, tuple(jobs), gate_ids=NATIVE_GATES + GLB_GATES)


def interchange_commands(
    blender: Path, node: Path, python: Path, repository: Path
) -> Any:
    result = native_commands(blender, repository)
    prefix = (
        str(blender),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--offline-mode",
        "--python-exit-code",
        "1",
        "--python",
        str(repository / "acceptance/blender_scripts/glb_worker.py"),
        "--",
    )
    result.update(
        {
            writer: prefix
            for writer in (
                "export_glb",
                "reimport_probe",
                "render_views(projection-source)",
                "glb_compare",
            )
        }
    )
    result["validator"] = (
        str(node),
        str(repository / "acceptance/node_scripts/validator_worker.mjs"),
    )
    result["glb_budget"] = (
        str(python),
        str(repository / "acceptance/glb_budget_worker.py"),
    )
    result["projection_compare"] = (
        str(python),
        str(repository / "acceptance/projection_worker.py"),
    )
    return result
```

- [ ] **Step 5: 写入 controller 对事实、资源和技术门禁的复核。**

缺原始报告留 NotTested。Node 版本、issue 计数/截断、每个资源指针、GLB 复测预算、角点匹配、原图 hash、完整 view/pass 集、差异图及真实 job PID 都要对账。图像 `left/right_rgb_energy` 明确为解码 RGB 总和；诊断各 pass 至少一个视角有前景，拒绝稳定的全黑空图。消费者字段有值而适配器不存在时，gate 未完成并进入技术失败。

```python
from __future__ import annotations

import json
import math
from typing import Any

from acceptance.contract import thaw
from acceptance.decide import Finding, Gate
from acceptance.glb_budget import measure_glb
from acceptance.interchange_policy import validate_interchange_policy
from acceptance.native_policy import PASSES, VIEWS
from acceptance.native_results import load, native_results
from acceptance.primitives import AcceptanceFailure
from acceptance.projection import compare_projection

GLB_CHECKS = (
    "r3.validator.no_error",
    "r3.validator.resources_read",
    "r3.validator.report_complete",
    "r3.extension.none_forbidden",
    "r4.projection.preserved_fields_match",
    "r4.projection.transformed_within_tolerance",
    "r4.projection.undeclared_loss",
    "r4.projection.ambiguous_object_names",
    "r4.visual.source_import_match",
)


def validate_export_evidence(
    value: Any,
    source: Any,
    native: Any,
    *,
    source_sha256: Any,
    delivery_sha256: Any,
    preset: Any,
) -> Any:
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema_version",
            "source_before",
            "source_after",
            "delivery_sha256",
            "exported_ids",
            "preset",
        }
        or type(value["schema_version"]) is not int
        or (value["schema_version"] != 2)
    ):
        raise AcceptanceFailure(
            "tool_output_invalid", "export measurement schema mismatch"
        )
    if (
        value["source_before"] != value["source_after"]
        or value["source_before"] != source_sha256
        or value["delivery_sha256"] != delivery_sha256
    ):
        raise AcceptanceFailure("tool_output_invalid", "export byte identity mismatch")
    if value["preset"] != preset:
        raise AcceptanceFailure(
            "tool_output_invalid", "export preset differs from frozen policy"
        )
    ids = [obj["id"] for obj in source["objects"]]
    expected = [row["source"] for row in native["occurrences"]]

    def encode(rows: list[Any]) -> list[str]:
        return sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in rows)

    if (
        value["exported_ids"] != ids
        or len(encode(ids)) != len(set(encode(ids)))
        or encode(ids) != encode(expected)
    ):
        raise AcceptanceFailure(
            "tool_output_invalid", "export occurrence set differs from inspected source"
        )


def interchange_results(contract: Any, run: Any) -> Any:
    (findings, gates) = native_results(contract, run)
    policy = thaw(contract.raw["interchange"])
    validate_interchange_policy(policy)
    gates.update(
        {
            "interchange.scope_supported": Gate(False, ()),
            "interchange.consumer": Gate(
                policy["consumer"] is None,
                ()
                if policy["consumer"] is None
                else (
                    Finding(
                        "consumer_adapter_missing", "error", detail=policy["consumer"]
                    ),
                ),
            ),
        }
    )

    def require(condition: Any, message: Any) -> Any:
        if not condition:
            raise AcceptanceFailure("tool_output_invalid", message)

    if "export.measurements" in run.files:
        require(
            all(
                k in run.files
                for k in ("projection.source", "native.manifest", "delivery.glb")
            ),
            "incomplete export identity evidence",
        )
        source_sha = next(
            row["sha256"]
            for row in contract.raw["input"]["files"]
            if row["id"] == "asset"
        )
        validate_export_evidence(
            load(run.files["export.measurements"].path),
            load(run.files["projection.source"].path),
            load(run.files["native.manifest"].path),
            source_sha256=source_sha,
            delivery_sha256=run.files["delivery.glb"].sha256,
            preset=policy["preset"],
        )
    if all(
        k in run.files
        for k in (
            "validator.report",
            "validator.resources",
            "glb.budget",
            "delivery.glb",
        )
    ):
        report = load(run.files["validator.report"].path)
        require(
            set(report) <= {"uri", "mimeType", "validatorVersion", "issues", "info"}
            and {"uri", "mimeType", "validatorVersion", "issues"} <= set(report),
            "validator top-level schema mismatch",
        )
        require(
            report["uri"] == "delivery.glb"
            and report["mimeType"] == "model/gltf-binary"
            and (report["validatorVersion"] == policy["validator_version"]),
            "validator identity mismatch",
        )
        issues = report["issues"]
        require(
            isinstance(issues, dict)
            and set(issues)
            == {
                "numErrors",
                "numWarnings",
                "numInfos",
                "numHints",
                "messages",
                "truncated",
            },
            "validator issues schema mismatch",
        )
        require(
            type(issues["truncated"]) is bool and isinstance(issues["messages"], list),
            "validator report completeness malformed",
        )
        counts = [
            issues[k] for k in ("numErrors", "numWarnings", "numInfos", "numHints")
        ]
        require(
            all(type(n) is int and n >= 0 for n in counts), "validator counts malformed"
        )
        actual = [0] * 4
        asset_findings = []
        for item in issues["messages"]:
            require(
                isinstance(item, dict)
                and {"code", "message", "severity"} <= set(item)
                and (set(item) <= {"code", "message", "severity", "pointer", "offset"}),
                "validator message schema mismatch",
            )
            severity = item["severity"]
            require(
                type(severity) is int and 0 <= severity <= 3,
                "validator severity malformed",
            )
            require(
                isinstance(item["code"], str) and isinstance(item["message"], str),
                "validator message text malformed",
            )
            actual[severity] += 1
            if severity < 2:
                asset_findings.append(
                    Finding(
                        "validator_" + item["code"], "error", detail=item["message"]
                    )
                )
        require(
            issues["truncated"] or actual == counts,
            "validator issue counts inconsistent",
        )
        findings["r3.validator.no_error"] = asset_findings
        findings["r3.validator.report_complete"] = (
            [] if not issues["truncated"] else [Finding("validator_truncated", "error")]
        )
        budget = measure_glb(run.files["delivery.glb"].path, policy["limits"])
        require(
            load(run.files["glb.budget"].path) == budget,
            "budget report differs from controller remeasurement",
        )
        findings["r3.extension.none_forbidden"] = [
            Finding("forbidden_extension", "error", detail=x)
            for x in budget["extensions"]
            if x not in policy["allowed_extensions"]
        ]
        resources = load(run.files["validator.resources"].path)
        require(
            set(resources)
            == {
                "schema_version",
                "input_sha256",
                "input_bytes",
                "external_requests",
                "resources",
            }
            and resources["schema_version"] == 2,
            "resource report schema mismatch",
        )
        require(
            resources["input_sha256"] == run.files["delivery.glb"].sha256
            and resources["input_bytes"] == run.files["delivery.glb"].bytes,
            "validator read different delivery bytes",
        )
        require(
            resources["resources"] == report.get("info", {}).get("resources", []),
            "resource log differs from validator report",
        )
        rows = resources["resources"]
        require(isinstance(rows, list), "resource rows required")
        pointers = [row.get("pointer") for row in rows]

        def resource_read(row: Any) -> Any:
            if row.get("pointer", "").startswith("/buffers/"):
                return (
                    row.get("storage") == "glb"
                    and type(row.get("byteLength")) is int
                    and (row["byteLength"] > 0)
                )
            image = row.get("image", {})
            return (
                row.get("storage") == "buffer-view"
                and row.get("mimeType") == "image/png"
                and all(
                    type(image.get(k)) is int and image[k] > 0
                    for k in ("width", "height")
                )
                and (image.get("bits") == 8)
                and (
                    image["width"] * image["height"]
                    <= policy["limits"]["max_texture_pixels"]
                )
            )

        all_read = (
            not resources["external_requests"]
            and len(pointers) == len(set(pointers))
            and (set(pointers) == set(budget["resource_pointers"]))
            and all(resource_read(row) for row in rows)
        )
        findings["r3.validator.resources_read"] = (
            [] if all_read else [Finding("resources_not_proven_read", "error")]
        )
    if all(
        k in run.files
        for k in ("projection.source", "projection.import", "projection.matches")
    ):
        measured = compare_projection(
            load(run.files["projection.source"].path),
            load(run.files["projection.import"].path),
            policy,
        )
        require(
            load(run.files["projection.matches"].path) == measured,
            "surface report differs from trusted comparator",
        )
        for group, check in [
            ("preserved", "r4.projection.preserved_fields_match"),
            ("transformed", "r4.projection.transformed_within_tolerance"),
            ("loss", "r4.projection.undeclared_loss"),
            ("ambiguous", "r4.projection.ambiguous_object_names"),
        ]:
            findings[check] = [
                Finding("projection_" + group, "error", detail=x)
                for x in measured[group]
            ]
        gates["interchange.scope_supported"] = Gate(True, ())
    if "projection.visual" not in run.files:
        return (findings, gates)
    data = load(run.files["projection.visual"].path)
    require(
        set(data) == {"schema_version", "comparisons"}
        and data["schema_version"] == 2
        and isinstance(data["comparisons"], list),
        "projection visual schema mismatch",
    )
    seen = []
    failures = []
    energy = {
        side: {p: 0.0 for p in ("clay", "silhouette", "wire")}
        for side in ("left", "right")
    }
    for row in data["comparisons"]:
        require(
            set(row)
            == {
                "decoder",
                "size",
                "channels",
                "precision",
                "color_interpretation",
                "left_bytes_sha256",
                "right_bytes_sha256",
                "different_channels",
                "different_pixels",
                "max_abs",
                "left_rgb_energy",
                "right_rgb_energy",
                "view",
                "pass",
                "left_id",
                "right_id",
                "diff_id",
            },
            "projection visual row schema mismatch",
        )
        (view, render_pass) = (row["view"], row["pass"])
        seen.append((view, render_pass))
        require(
            view in VIEWS and render_pass in PASSES, "unplanned projection visual pair"
        )
        require(
            (row["left_id"], row["right_id"], row["diff_id"])
            == (
                f"image.projection_source.0.{view}.{render_pass}",
                f"image.projection_import.0.{view}.{render_pass}",
                f"diff.projection.{view}.{render_pass}",
            ),
            "wrong projection image pair",
        )
        require(
            row["color_interpretation"] == "Blender PNG decode, Standard output"
            and row["decoder"] == "blender-rgba-f32-v1"
            and (row["precision"] == "float32")
            and (row["channels"] == 4)
            and (row["size"] == [1024, 1024]),
            "projection decoder mismatch",
        )
        for side in ("left", "right"):
            require(
                row[side + "_id"] in run.files
                and row[side + "_bytes_sha256"] == run.files[row[side + "_id"]].sha256,
                "projection compared different image bytes",
            )
        require(row["diff_id"] in run.files, "missing projection difference image")
        require(
            type(row["max_abs"]) in (int, float)
            and math.isfinite(row["max_abs"])
            and (0 <= row["max_abs"] <= 1),
            "projection metric malformed",
        )
        for side in ("left", "right"):
            value = row[side + "_rgb_energy"]
            require(
                type(value) in (int, float)
                and math.isfinite(value)
                and (0 <= value <= 3 * 1024 * 1024),
                "projection foreground metric malformed",
            )
            if render_pass in energy[side]:
                energy[side][render_pass] += value
        (dc, dp) = (row["different_channels"], row["different_pixels"])
        require(
            type(dc) is int
            and type(dp) is int
            and (0 <= dp <= 1024 * 1024)
            and (dp <= dc <= 4 * dp)
            and ((dc == 0) == (row["max_abs"] == 0)),
            "projection counts inconsistent",
        )
        if (
            render_pass in {"clay", "silhouette"}
            and row["max_abs"]
            > contract.raw["native"]["render"]["max_abs"][render_pass]
        ):
            failures.append(
                Finding(
                    "projection_pixel_mismatch",
                    "error",
                    detail=view + "." + render_pass,
                )
            )
    require(
        len(seen) == len(set(seen))
        and set(seen) == {(v, p) for v in VIEWS for p in PASSES},
        "incomplete projection visual set",
    )
    hashes = {x["id"]: x["sha256"] for x in contract.raw["input"]["files"]}
    hashes.update({key: value.sha256 for (key, value) in run.files.items()})
    for experiment, input_id in [
        ("projection_source", "asset"),
        ("projection_import", "delivery.glb"),
    ]:
        require("render." + experiment in run.files, "projection render report missing")
        report = load(run.files["render." + experiment].path)
        require(
            set(report)
            == {
                "schema_version",
                "platform",
                "settings",
                "images",
                "input_sha256_before",
                "input_sha256_after",
            }
            and report["schema_version"] == 2,
            "projection render schema mismatch",
        )
        require(
            report["settings"] == thaw(contract.raw["native"]["render"])
            and report["platform"]
            == thaw(contract.raw["native"]["render"]["platform"]),
            "unfrozen projection platform/settings",
        )
        require(
            report["input_sha256_before"]
            == report["input_sha256_after"]
            == hashes[input_id],
            "projection rendered changed input",
        )
        process = next(x for x in run.jobs if x["job_id"] == "glb." + experiment)
        ids = []
        for row in report["images"]:
            require(
                set(row)
                == {"id", "view", "pass", "repetition", "pid", "experiment", "engine"},
                "projection image metadata malformed",
            )
            require(
                row["id"] == f"image.{experiment}.0.{row['view']}.{row['pass']}"
                and row["experiment"] == experiment
                and (
                    row["engine"]
                    == (
                        "BLENDER_EEVEE"
                        if row["pass"] == "beauty"
                        else "BLENDER_WORKBENCH"
                    )
                )
                and (type(row["repetition"]) is int)
                and (row["repetition"] == 0)
                and process["started"]
                and (row["pid"] == process["pid"]),
                "projection image process mismatch",
            )
            ids.append(row["id"])
        require(
            len(ids) == len(set(ids))
            and set(ids)
            == {f"image.{experiment}.0.{v}.{p}" for v in VIEWS for p in PASSES},
            "projection render image set mismatch",
        )
    for side in energy:
        for render_pass, value in energy[side].items():
            if value <= 0:
                failures.append(
                    Finding(
                        "empty_projection_diagnostic",
                        "error",
                        detail=side + "." + render_pass,
                    )
                )
    findings["r4.visual.source_import_match"] = failures
    return (findings, gates)
```

`tests/unit/test_interchange_results.py`：

```python
import pytest
from acceptance.interchange_results import validate_export_evidence
from acceptance.primitives import AcceptanceFailure
from tests.unit.interchange_support import PRESET, projection


@pytest.mark.parametrize(
    "field",
    [
        "schema_version",
        "source_before",
        "source_after",
        "delivery_sha256",
        "preset",
        "exported_ids",
        "unknown",
        "native_scope",
    ],
)
def test_controller_rejects_each_export_measurement_mismatch(field):
    source = projection()
    native = {"occurrences": [{"source": ["OBJECT", "Asset"]}]}
    value = {
        "schema_version": 2,
        "source_before": "a" * 64,
        "source_after": "a" * 64,
        "delivery_sha256": "b" * 64,
        "preset": dict(PRESET),
        "exported_ids": [["OBJECT", "Asset"]],
    }
    validate_export_evidence(
        value,
        source,
        native,
        source_sha256="a" * 64,
        delivery_sha256="b" * 64,
        preset=PRESET,
    )
    if field == "schema_version":
        value[field] = True
    elif field in {"source_before", "source_after", "delivery_sha256"}:
        value[field] = "c" * 64
    elif field == "preset":
        value[field]["export_yup"] = False
    elif field == "exported_ids":
        value[field] = []
    elif field == "unknown":
        value[field] = "extra"
    else:
        native["occurrences"] = []
    with pytest.raises(AcceptanceFailure):
        validate_export_evidence(
            value,
            source,
            native,
            source_sha256="a" * 64,
            delivery_sha256="b" * 64,
            preset=PRESET,
        )
```


运行 `.venv/bin/python -m pytest tests/unit/test_interchange_results.py -q`，预期 8 个 export 证据字段/范围篡改反例均被拒。首次写入时先观察失败，再补上述实现。

- [ ] **Step 6: 写入入口封装，启用严格合同分支。**

`acceptance/interchange_run.py`：

```python
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from acceptance.contract import load_contract, thaw
from acceptance.controller import run_jobs
from acceptance.decide import Finding, Gate
from acceptance.evidence import finalize_run
from acceptance.input_bundle import verify_bundle
from acceptance.interchange_plan import (
    GLB_GATES,
    build_interchange_plan,
    interchange_commands,
)
from acceptance.interchange_results import interchange_results
from acceptance.native_plan import NATIVE_GATES
from acceptance.primitives import AcceptanceFailure


def run_interchange(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    contract = load_contract(contract_path, candidate_root=source_root)
    plan = build_interchange_plan(contract)
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    tools = {x["id"]: Path(x["path"]) for x in contract.raw["tools"]}
    run = run_jobs(
        contract,
        plan,
        run_id=uuid4().hex,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands=interchange_commands(
            tools["blender"], tools["node"], tools["python"], repository
        ),
    )
    try:
        (findings, gates) = interchange_results(contract, run)
    except (
        AcceptanceFailure,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        OSError,
        StopIteration,
    ) as exc:
        code = exc.code if isinstance(exc, AcceptanceFailure) else "tool_output_invalid"
        run = replace(run, infra_failures=run.infra_failures + (code,))
        error = Finding("interchange_evidence_unverified", "error", detail=str(exc))
        findings = {}
        gates = {key: Gate(False, (error,)) for key in NATIVE_GATES + GLB_GATES}
    delivery = run.files.get("delivery.glb")
    return finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=delivery,
        coordinator_findings=findings,
        gates=gates,
    )
```

在 `acceptance.contract.validate_document` 中，以此完整片段替换 M1 的 native/interchange 两个 null 拦截条件。M2 已启用的原生政策调用合并到同一片段，避免双重分支：

```python
    if value["native"] is not None:
        from acceptance.native_policy import validate_native_policy
        try:
            validate_native_policy(value["native"])
        except ValueError as exc:
            raise AcceptanceFailure("contract_invalid", str(exc)) from exc
        input_ids = {item["id"] for item in value["input"]["files"]}
        native_ids = {value["native"]["reference_manifest_id"], value["native"]["reference_authority"]}
        native_ids.update(value["native"]["render"]["reference_images"].values())
        require(native_ids <= input_ids, "native references must be frozen input members")
        require(value["input"]["main"] == "asset", "native main file ID must be asset")
    if value["interchange"] is not None:
        require(value["artifact_kind"] == "interchange" and value["native"] is not None,
                "interchange requires an explicit native inspection/render policy")
        from acceptance.interchange_policy import validate_interchange_policy
        try:
            validate_interchange_policy(value["interchange"])
        except ValueError as exc:
            raise AcceptanceFailure("contract_invalid", str(exc)) from exc
```


`tests/unit/test_interchange_contract.py`：

```python
from copy import deepcopy

import pytest
from acceptance import check_registry as registry
from acceptance.contract import validate_document
from acceptance.input_bundle import source_digest
from acceptance.primitives import AcceptanceFailure
from tests.unit.asset_v2_support import valid_document
from tests.unit.interchange_support import policy as interchange_policy
from tests.unit.test_native_policy import policy as native_policy


def integrated_document(tmp_path, kind):
    value = valid_document(tmp_path)
    value["artifact_kind"] = kind
    value["checks"] = [
        {"id": item.id, "impl": item.impl, "order": item.order}
        for item in sorted(registry.checks_for_kind(kind), key=registry.sort_key)
    ]
    value["na_check_ids"] = list(registry.na_check_ids(kind))
    value["native"] = native_policy()
    value["interchange"] = (
        interchange_policy(tmp_path) if kind == "interchange" else None
    )
    ids = {
        "asset",
        "alternate",
        value["native"]["reference_manifest_id"],
        value["native"]["reference_authority"],
    }
    ids.update(value["native"]["render"]["reference_images"].values())
    rows = [
        {"id": key, "path": key + ".bin", "bytes": 1, "sha256": "a" * 64}
        for key in sorted(ids)
    ]
    value["input"] = {"main": "asset", "sha256": source_digest(rows), "files": rows}
    return value


@pytest.mark.parametrize("kind", ["blend_native", "interchange"])
def test_combined_contract_accepts_complete_frozen_references(tmp_path, kind):
    validate_document(integrated_document(tmp_path, kind))


@pytest.mark.parametrize("kind", ["blend_native", "interchange"])
@pytest.mark.parametrize(
    "mutation", ["authority", "manifest", "image", "main", "invalid_policy"]
)
def test_combined_contract_preserves_native_binding_guards(tmp_path, kind, mutation):
    value = deepcopy(integrated_document(tmp_path, kind))
    if mutation == "authority":
        value["native"]["reference_authority"] = "unfrozen.authority"
    elif mutation == "manifest":
        value["native"]["reference_manifest_id"] = "unfrozen.manifest"
    elif mutation == "image":
        value["native"]["render"]["reference_images"]["front.beauty"] = "unfrozen.image"
    elif mutation == "main":
        value["input"]["main"] = "alternate"
    else:
        value["native"]["frame"] = True
    with pytest.raises(AcceptanceFailure) as caught:
        validate_document(value)
    assert caught.value.code == "contract_invalid"
```

先运行 `.venv/bin/python -m pytest tests/unit/test_interchange_contract.py -q` 验证旧分支无法拒绝未冻结 authority，再应用上述合同合并片段，预期全部通过。此校验属于完整合同边界，不能只测试单独的 native/interchange policy。

`dispatch_run` 整体替换如下；旧 M1 未接线合同仍失败关闭，不读取任意 candidate argv：

```python
def dispatch_run(contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path) -> dict[str, Any]:
    contract = load_contract(contract_path, candidate_root=source_root)
    if contract.artifact_kind == "interchange" and contract.raw["interchange"] is not None:
        from acceptance.interchange_run import run_interchange
        return run_interchange(contract_path, source_root, evidence_root, scratch_root)
    if contract.artifact_kind == "blend_native" and contract.raw["native"] is not None:
        from acceptance.native_run import run_native
        return run_native(contract_path, source_root, evidence_root, scratch_root)
    plan = assemble_plan(contract, ())
    inputs = verify_bundle(source_root, thaw(contract.raw["input"]["files"]),
                           max_file_bytes=contract.raw["budget"]["max_file_bytes"])
    run = run_jobs(contract, plan, run_id=evidence_root.name, input_files=inputs,
                   scratch_root=scratch_root, evidence_root=evidence_root, commands={})
    return finalize_run(contract, plan, run, contract_path=contract_path, source_root=source_root,
                        evidence_root=evidence_root, delivery=inputs[contract.raw["input"]["main"]],
                        coordinator_findings={}, gates={})
```

- [ ] **Step 7: 运行同一真实 CLI 回归。**

```bash
RUN_ASSET_INTERCHANGE=1 "$PYTHON_BIN" -m pytest tests/integration/test_asset_interchange.py -q
```

预期正向合同完成 34 个适用检查和全部技术门禁，先 NEEDS_REVIEW，再由测试记录形成 Q/T；缺实际消费者为 UNVERIFIED；缺底部真实资产技术失败。D 是同一已验 GLB，export 失败时 D=null，不拿 source 假充交付物。

- [ ] **Step 8: 检查范围差异。**

```bash
git diff --check
```

预期退出 0；进入 Task 5 的可复现 adversarial probe 与整包提交门禁。


### Task 5: 真实导入反例、Validator 反例与交付门禁

**Files:**
- Create: `tests/fixtures/asset_interchange.py`
- Create: `tests/integration/test_interchange_surface.py`
- Create: `tests/integration/test_gltf_validator.py`
- Modify: `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`
- Modify: `docs/validation.md`

**Interfaces:**
- Consumes: Tasks 1–4 的 capture/comparator/validator/CLI；M2 `blender_script(blender,script,*arguments)` 与仓库外 calibration helper。
- Produces: 三个真实 GLB 正例的 source/import 原始投影、匹配表、真实移动/材质变化负例；Node 内嵌资源、外部缺失和截断完整报告；M3 是否完成的独立证据记录。

- [ ] **Step 1: 写入两进程 Blender 正反夹具及测试。**

`tests/fixtures/asset_interchange.py`：

```python
import copy
import json
import sys
from pathlib import Path

import bpy

repository = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repository))
from acceptance.blender_scripts.projection_capture import capture
from acceptance.interchange_policy import (
    PRESET,
    validate_interchange_policy,
)
from acceptance.projection import compare_projection
from tests.unit.interchange_support import policy as make_policy

args = sys.argv[sys.argv.index("--") + 1 :]
p = Path(args[0])
p.mkdir(parents=True, exist_ok=True)
mode = args[1]
policy = make_policy(Path(args[2]))
validate_interchange_policy(policy)
names = ("cube", "pruning", "texture")
result = {}
for name in names:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if mode == "build":
        if name == "pruning":
            mesh = bpy.data.meshes.new("Pruned")
            mesh.from_pydata(
                [(0, 0, 0), (1, 0, 0), (0, 1, 0)] + [(9 + i, 9, 9) for i in range(9)],
                [],
                [(0, 1, 2)],
            )
            obj = bpy.data.objects.new("Asset", mesh)
            bpy.context.collection.objects.link(obj)
            mesh.uv_layers.new(name="UVMap")
            mesh.uv_layers.new(name="Unused")
        else:
            bpy.ops.mesh.primitive_cube_add(location=(1, 2, 3))
            obj = bpy.context.object
            obj.name = "Asset"
        mat = bpy.data.materials.new("Visible")
        mat.use_nodes = True
        mat.node_tree.nodes.get("Principled BSDF").inputs[
            "Base Color"
        ].default_value = (0.2, 0.4, 0.8, 1)
        obj.data.materials.append(mat)
        obj["label"] = "fixture"
        if name == "pruning":
            unused = bpy.data.materials.new("Unused")
            unused.use_nodes = True
            obj.data.materials.append(unused)
        if name == "texture":
            img = bpy.data.images.new("Texture", width=2, height=2, alpha=True)
            img.pixels = [1, 0, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 1, 1, 1, 1]
            img.filepath_raw = str(p / "texture.png")
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)
            img = bpy.data.images.load(str(p / "texture.png"))
            img.pack()
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            mat.node_tree.links.new(
                node.outputs["Color"],
                mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"],
            )
        bpy.context.view_layer.update()
        (p / (name + "-source.json")).write_text(
            json.dumps(capture([obj], policy), allow_nan=False)
        )
        bpy.ops.wm.save_as_mainfile(filepath=str(p / (name + ".blend")))
        obj["bcx_uid"] = json.dumps(["OBJECT", obj.name])
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.gltf(filepath=str(p / (name + ".glb")), **PRESET)
    else:
        bpy.ops.import_scene.gltf(filepath=str(p / (name + ".glb")))
        objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        got = capture(objects, policy, imported=True)
        expected = json.loads((p / (name + "-source.json")).read_text())
        (p / (name + "-import.json")).write_text(json.dumps(got, allow_nan=False))
        r = compare_projection(expected, got, policy)
        assert all(
            not r[k] for k in ("preserved", "transformed", "loss", "ambiguous")
        ), r
        case = {
            "source_vertices": expected["objects"][0]["vertices"],
            "import_vertices": got["objects"][0]["vertices"],
            "source_slots": expected["objects"][0]["slots"],
            "import_slots": got["objects"][0]["slots"],
            "positive": r,
            "negative": {},
        }
        for mutation in (
            "surface",
            "material",
            "uv",
            "identity",
            "custom",
            "texture" if name == "texture" else "normal",
        ):
            bad = copy.deepcopy(got)
            first = bad["objects"][0]
            if mutation == "surface":
                first["triangles"][0]["corners"][0]["position"][0] += 0.1
            elif mutation == "material":
                first["triangles"][0]["material"]["pbr"]["roughness"] = 0.99
            elif mutation == "uv":
                first["triangles"][0]["corners"][0]["uv"][0][0] += 0.1
            elif mutation == "identity":
                first["id"][1] = "forged"
            elif mutation == "custom":
                first["custom"]["label"] = "changed"
            elif mutation == "texture":
                first["triangles"][0]["material"]["texture"]["pixels"] = "0" * 64
            else:
                first["triangles"][0]["corners"][0]["normal"][0] += 0.2
            checked = compare_projection(expected, bad, policy)
            assert any(
                checked[k] for k in ("preserved", "transformed", "loss", "ambiguous")
            ), (name, mutation)
            case["negative"][mutation] = [
                k
                for k in ("preserved", "transformed", "loss", "ambiguous")
                if checked[k]
            ]
        obj = objects[0]
        obj.location.x += 0.2
        bpy.context.view_layer.update()
        moved = compare_projection(
            expected, capture(objects, policy, imported=True), policy
        )
        assert moved["transformed"]
        case["actual_transform_negative"] = moved["transformed"]
        obj.location.x -= 0.2
        bpy.context.view_layer.update()
        rough = (
            obj.data.materials[0]
            .node_tree.nodes.get("Principled BSDF")
            .inputs["Roughness"]
        )
        rough.default_value = 0.95
        changed = compare_projection(
            expected, capture(objects, policy, imported=True), policy
        )
        assert changed["transformed"]
        case["actual_material_negative"] = changed["transformed"]
        result[name] = case
if mode == "build":
    (p / "policy.json").write_text(json.dumps(policy, indent=2))
else:
    (p / "probe-results.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
```

`tests/integration/test_interchange_surface.py`：

```python
import json
import os
from pathlib import Path

import pytest
from tests.integration.asset_runtime_support import REPO, blender_script

pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_INTERCHANGE") != "1",
        reason="explicit two-process Blender projection test",
    ),
]


def test_actual_split_prune_texture_and_changed_import(tmp_path):
    blender = Path(os.environ["BLENDER_BIN"])
    script = REPO / "tests/fixtures/asset_interchange.py"
    for mode in ("build", "import"):
        blender_script(
            blender, script, str(tmp_path), mode, os.environ["GLTF_PACKAGE_ROOT"]
        )
    result = json.loads((tmp_path / "probe-results.json").read_text())
    assert (
        result["cube"]["source_vertices"] == 8
        and result["cube"]["import_vertices"] == 24
    )
    assert (
        result["pruning"]["source_vertices"] == 12
        and result["pruning"]["import_vertices"] == 3
    )
    assert (
        result["pruning"]["source_slots"] == 2
        and result["pruning"]["import_slots"] == 1
    )
    for case in result.values():
        assert not any(
            case["positive"][k]
            for k in ("preserved", "transformed", "loss", "ambiguous")
        )
        assert all(case["negative"].values())
        assert case["actual_transform_negative"] and case["actual_material_negative"]
```

`tests/integration/test_gltf_validator.py`：

```python
import json
import os
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from acceptance import interchange_results as reducer
from acceptance.glb_budget import measure_glb
from acceptance.input_bundle import measure_file
from tests.unit.interchange_support import policy

pytestmark = [
    pytest.mark.timeout(900),
    pytest.mark.skipif(
        os.environ.get("RUN_GLTF_VALIDATOR") != "1",
        reason="explicit real Node validator",
    ),
]
REPO = Path(__file__).resolve().parents[2]


def glb(path, document, binary=b""):
    raw = json.dumps(document).encode()
    raw += b" " * ((-len(raw)) % 4)
    body = struct.pack("<II", len(raw), 0x4E4F534A) + raw
    if binary:
        binary += b"\0" * ((-len(binary)) % 4)
        body += struct.pack("<II", len(binary), 0x004E4942) + binary
    path.write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)


def triangle():
    return {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [1, 1, 0],
            }
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36, "target": 34962}
        ],
        "buffers": [{"byteLength": 36}],
    }


def run_validator(tmp_path, document, binary):
    source = tmp_path / "input"
    source.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    asset = source / "asset.glb"
    glb(asset, document, binary)
    p = policy(Path(os.environ["GLTF_PACKAGE_ROOT"]))
    row = measure_file(asset, p["limits"]["max_glb_bytes"], file_id="delivery.glb")
    request = {
        "schema_version": 2,
        "run_id": "fixture",
        "attempt": 1,
        "nonce": "a" * 32,
        "job_id": "glb.validator",
        "writer": "validator",
        "contract_digest": "c" * 64,
        "source_digest": "d" * 64,
        "input_root": str(source),
        "output_root": str(output),
        "inputs": [row.descriptor("asset.glb")],
        "outputs": [
            {
                "id": fid,
                "path": name,
                "media_type": "application/json",
                "max_bytes": 64 * 1024 * 1024,
            }
            for fid, name in [
                ("validator.report", "report.json"),
                ("validator.resources", "resources.json"),
            ]
        ],
        "parameters": {"operation": "validator", "policy": p, "native": {}},
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request))
    completed = subprocess.run(
        [
            os.environ["NODE_BIN"],
            str(REPO / "acceptance/node_scripts/validator_worker.mjs"),
            "--request",
            str(request_path),
        ],
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return asset, output, p


def test_real_validator_reads_embedded_bytes_and_controller_rechecks(
    tmp_path, monkeypatch
):
    binary = struct.pack("<9f", 0, 0, 0, 1, 0, 0, 0, 1, 0)
    asset, out, p = run_validator(tmp_path, triangle(), binary)
    report = json.loads((out / "report.json").read_text())
    assert report["issues"]["numErrors"] == 0 and not report["issues"]["truncated"]
    budget = measure_glb(asset, p["limits"])
    (out / "budget.json").write_text(json.dumps(budget))
    files = {
        fid: measure_file(path, 64 * 1024 * 1024, file_id=fid)
        for fid, path in [
            ("delivery.glb", asset),
            ("validator.report", out / "report.json"),
            ("validator.resources", out / "resources.json"),
            ("glb.budget", out / "budget.json"),
        ]
    }
    monkeypatch.setattr(reducer, "native_results", lambda contract, run: ({}, {}))
    findings, gates = reducer.interchange_results(
        SimpleNamespace(raw={"interchange": p}), SimpleNamespace(files=files)
    )
    assert (
        not findings["r3.validator.no_error"]
        and not findings["r3.validator.resources_read"]
    )
    bad = json.loads((out / "resources.json").read_text())
    bad["resources"] = []
    (out / "resources.json").write_text(json.dumps(bad))
    with pytest.raises(Exception, match="resource log differs"):
        reducer.interchange_results(
            SimpleNamespace(raw={"interchange": p}), SimpleNamespace(files=files)
        )


def test_real_validator_reports_external_read_failure(tmp_path):
    doc = triangle()
    doc["buffers"][0]["uri"] = "missing.bin"
    asset, out, p = run_validator(tmp_path, doc, b"")
    report = json.loads((out / "report.json").read_text())
    resources = json.loads((out / "resources.json").read_text())
    assert report["issues"]["numErrors"] > 0
    assert resources["external_requests"] == ["missing.bin"]
    with pytest.raises(ValueError, match="URI"):
        measure_glb(asset, p["limits"])


def test_real_validator_retains_truncation_instead_of_hiding_it(tmp_path):
    doc = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": list(range(12000))}],
        "nodes": [{"mesh": 9} for _ in range(12000)],
    }
    asset, out, p = run_validator(tmp_path, doc, b"")
    report = json.loads((out / "report.json").read_text())
    assert report["issues"]["truncated"] is True
    assert report["issues"]["numErrors"] > 0
```


- [ ] **Step 2: 运行真实夹具与 Validator 对抗回归。**

```bash
RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1 "$PYTHON_BIN" -m pytest tests/integration/test_interchange_surface.py tests/integration/test_gltf_validator.py -q
```

预期 4 个测试通过：8→24 顶点、12→3 顶点及 2→1 槽、打包纹理均保留实际语义；修改导入对象的实际位置/材质被拒；同计数表面/UV/身份/属性及纹理解码差异被拒；缺外部资源报错；12000 个坏 node 报告保留 truncated=true，不能接受为完整。

- [ ] **Step 3: 跑完整 M3，再复测已验 D 的交付字节。**

```bash
RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1 "$PYTHON_BIN" -m pytest tests/integration/test_asset_interchange.py tests/integration/test_interchange_surface.py tests/integration/test_gltf_validator.py -q
```

预期没有 skip，真实正向通过、实际质量失败与缺能力分类正确。M1 的 deliver 篡改/中断测试保持通过；只有已有 SHIP/SHIP_WITH_NOTES 的 T 才允许 deliver，复制已验 D 并形成 receipt。命令不向外部平台发布。

- [ ] **Step 4: 更新 V5 与 validation 中的 M3 状态和命令。**

追加的规范文本必须完整包含以下内容：

```markdown
### M3 静态 GLB 实现范围与证据

M3 保留全部 34 个适用 check，并要求 native.scope_supported、native.cross_process、native.reference、interchange.scope_supported、interchange.consumer 五个技术 gate。未实现实际消费者、未知类型/平台、缺证据及导出无 D 都禁止技术成功。

有限 profile 为 glb-static-surface-v1：普通非镜像静态 MESH，单位 scale_length=1，显式固定导出 preset，基本 PBR 与直接 Base Color 打包 sRGB RGBA8 PNG，Linear/REPEAT/default-active-UV；collection 可省略、已支持 modifier 烘焙、未用顶点/槽可裁剪，UV 层仍保留。存在所需扩展、非默认额外 shader 输入、HDR 或外部资源时不声称支持。

Validator 的格式/资源结论、逐 node 绘制预算、表面保真和实际消费者分别报告。原始 GLB 与所有报告/图像进入 E；R5 结论只在 V；Q 绑定实际图像与 C/S/D/E/V。没有真实所需审阅时停在 NEEDS_REVIEW。测试 reviewer 不授权用户作品。
```

在 `docs/validation.md` 追加：

```markdown
### 独立 M3 资产门禁

先完成 M0/M1 与 M2；准备锁定 Python、Blender、Node 和 gltf-validator 2.0.0-dev.3.10 及其真实工具/包文件摘要。显式运行 RUN_ASSET_INTERCHANGE=1 RUN_GLTF_VALIDATOR=1 的三份 integration 测试，并记录 source/C/D、工具身份、退出状态、summary、E/Q/T 和实际交付 receipt。

这组门禁只证明声明的 GLB 静态 L0 支持范围。独立两进程 surface probe、Node validator probe、完整 CLI、人工 Q 和正式交付分别记录，不互相替代。没有对应证据不得把状态标为已完成。
```

- [ ] **Step 5: 最后一次代码/文档修改后运行必要门禁并提交本包。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_interchange_policy.py tests/unit/test_projection_v2.py tests/unit/test_glb_budget_v2.py tests/unit/test_interchange_results.py -q
bash scripts/checks.sh
graft build .
graft check .
git diff --check
```

预期 pure unit 27 passed；仓库完整检查出现 ALL CHECKS PASSED；Graft build/check 退出 0。Node/Blender 集成不由默认 unit 代替。此后再修改文件则重跑对应检查及 Graft；不提交 `graft/`、外部证据、依赖安装目录或用户原有改动。

```bash
git add acceptance/interchange_policy.py acceptance/projection.py acceptance/glb_budget.py acceptance/glb_budget_worker.py acceptance/projection_worker.py acceptance/interchange_plan.py acceptance/interchange_results.py acceptance/interchange_run.py acceptance/blender_scripts/projection_capture.py acceptance/blender_scripts/glb_worker.py acceptance/node_scripts/validator_worker.mjs acceptance/contract.py scripts/asset_accept.py tests/unit/interchange_support.py tests/unit/test_interchange_policy.py tests/unit/test_projection_v2.py tests/unit/test_glb_budget_v2.py tests/unit/test_interchange_results.py tests/unit/test_interchange_contract.py tests/integration/interchange_runtime_support.py tests/integration/test_asset_interchange.py tests/integration/test_interchange_surface.py tests/integration/test_gltf_validator.py tests/fixtures/asset_interchange.py docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md docs/validation.md
git commit -m "feat(acceptance): complete bounded GLB projection acceptance"
```

提交按执行阶段已有授权处理；没有提交授权时保留完整可审阅差异，不自行推送。

## 计划自审与审计边界

p01–p14 均落到硬比较、固定允许变化或明确未支持门禁；未承诺通用三角等价/动画/所有实例/所有消费者。新进程导入的对象身份只接受受信导出器在候选 reserved-prop 检查之后注入的标记；导入后的实际表面/PBR仍独立验证，不能用身份标签替代语义。

计划编写期间在仓库外运行的原型和报告见[对抗审计记录](../reviews/2026-09-08-plans-adversarial-review.md)。原型通过只证明相应片段/接口与有限夹具，不能把本文件的代码块当作生产功能已安装或未来任意资产已获签收。
