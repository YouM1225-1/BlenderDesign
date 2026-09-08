# 自包含原生静态资产闭环（M2）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让支持范围内的真实 `blend_native + static_render + local-trusted` 冻结资产完成全部 24 个现有适用检查以及固定的能力、参考与跨进程门禁，并用真实坏资产证明拒收理由、未验证状态与交付身份。

**Architecture:** 复用 M0/M1 的 v2 不可变合同、文件计划、worker 协议、进程回收、唯一判定器与 E/V/Q/T 封装。只增加原生采集、受控渲染、像素比较与调度适配模块；Blender 子进程只产出 findings、测量及注册文件。普通网格 occurrence 与 authored/evaluated 几何关联，未知类型显式未验证；独立可信参考证明质量，同资产重复只证明该实验的稳定性。

**Tech Stack:** CPython 3.13.13；锁定的 Blender 5.2.0 LTS / `fbe6228777e7`；标准库 JSON、hashlib、array；pytest；现有 acceptance 安全原语。图像由同一受锁 Blender 解码成 RGBA float32，不增加第三方像素库或 PNG 解析器。

## Global Constraints

- 「首发支持 `blend_native + static_render + local-trusted`」。来源授权、自包含、单场景及固定帧缺一不可。
- 「所有必需检查均须真实执行；不能通过减少 required 集合、合成 Pass 或放宽阈值制造成功。」
- 「范围外返回未验证及具体能力缺口；不能伪造空几何，也不能宣称所有曲线、文字或实例已支持。」
- 「内部 collection path 用字符串数组，身份用结构化元组，不用 `/` 拼接产生歧义。」
- 「文件 SHA-256 证明证据字节身份；解码像素由锁定比较器、通道、精度、颜色空间、阈值和掩码比较。」
- 「两组原图均进入文件注册，hash 不能替代被丢弃图像。」
- 「分别报告同进程重复、新进程读取同一冻结资产、从建模步骤重建三个实验。」本包实现前两项；重建要求出现时能力门禁未完成，不把重渲充作重建。
- 「批准本设计本身不构成未来某个资产的签收。」Q 由合同要求的真实审阅主体给出；测试 reviewer 仅限测试。
- 「不得将 `bpy` 引入 `bridge/core` 或 `protocol`。不为本设计把 `acceptance/` 提前加入 wheel/sdist。」
- 「每个实施包提交前运行一次 `bash scripts/checks.sh` 并确认 `ALL CHECKS PASSED`；最后修改后执行 `graft build .`，交付前 `graft check .` 退出 0。」

---

## 前置与文件职责

前置：先完成同目录的 core-v2 计划 M0/M1。本文使用其 `Contract/thaw`、`FileSpec/JobSpec/RunPlan/assemble_plan`、`run_jobs`、`worker_protocol.read_request/write_result`、`Finding/Gate`、`finalize_run/finish_review`，不得在本包复制它们。执行前先核对这些接口；接口漂移必须同步两个计划与测试，不能以同名替代行为。

| 文件 | 单一职责 |
|---|---|
| `acceptance/native_policy.py` | 无 bpy 的闭合原生政策与参数验证 |
| `acceptance/native_checks.py` | manifest schema 与几何/依赖/参考 findings，无最终 verdict |
| `acceptance/blender_scripts/__init__.py` | Blender worker 包边界 |
| `acceptance/blender_scripts/native_collect.py` | authored/evaluated/occurrence/材质/依赖采集 |
| `acceptance/blender_scripts/native_render.py` | 受控场景、九视角、四 pass 与锁定解码比较 |
| `acceptance/blender_scripts/native_worker.py` | stdJSON 作业入口及精确 D 的独立路径重开 |
| `acceptance/native_plan.py` | 单一作业/文件展开；向 M3 导出 source 作业 |
| `acceptance/native_results.py` | controller 对比较输出和进程身份复核，生成固定门禁 |
| `tests/unit/test_native_policy.py`、`tests/unit/test_native_checks.py`、`tests/unit/test_native_plan.py` | 无 Blender 默认回归 |
| `tests/fixtures/asset_native.py`、`tests/integration/test_asset_native.py` | 仓库外真实正反资产与端到端运行 |
| `acceptance/contract.py`、`scripts/asset_accept.py` | 只接通原生政策和可信调度 |
| `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`、`docs/validation.md` | 能力状态与独立原生门禁命令 |

根目录准备命令（每个新 shell 执行）：

```bash
export PYTHON_BIN="$PWD/.venv/bin/python"
export BLENDER_BIN=/Applications/Blender.app/Contents/MacOS/Blender
"$PYTHON_BIN" -c 'import sys; assert sys.version_info[:3] == (3, 13, 13)'
"$BLENDER_BIN" --version
```

预期：Python 断言退出 0；Blender 首行 `Blender 5.2.0 LTS`，build hash `fbe6228777e7`。执行环境不同则先生成对应工具锁与平台校准政策；不修改已有合同的 build 或阈值来通过。

## 支持表与完成口径

| 数据 | 首发接受 | 未支持或不同处理 |
|---|---|---|
| 普通对象 | 静态 MESH，父子关系，原生名称、分段 collection path、世界矩阵、JSON 自定义属性 | CURVE/FONT/SURFACE/META/VOLUME/POINTCLOUD、集合/几何节点实例：保留 inventory 和能力缺口，UNVERIFIED |
| 辅助对象 | EMPTY 无实例，CAMERA/LIGHT 只作 authored inventory | 不计入网格 occurrence；候选灯光/world 不参与受控诊断。合同要求用户成片流程时须另建对应能力，不能把受控 beauty 当作已验用户构图 |
| 可见性 | `hide_render` 及显式 render 范围排除，必需部件仍由参考对账 | eye/`hide_viewport`/layer exclude 导致 viewport depsgraph 与 render 求值不一致的组合，本支持表记录缺口；不能用 `visible_get` 自授排除 |
| modifier | TRIANGULATE 的 `quad_method/ngon_method/min_vertices/keep_custom_normals`；BEVEL 下文列出的全部实际相关字段 | BEVEL 只接受 `limit_method=NONE/ANGLE`、空 vertex_group、`profile_type=SUPERELLIPSE`；所有 modifier 必须同时开启 show_viewport/show_render；其他类型及配置均未验证 |
| 材质 | 一个 Principled 与一个 Material Output；Principled 常量输入全部保留；最多按现有节点图出现的静态打包 Image Texture Color→Base Color | 自定义 node group、程序纹理、任意其他连接、非节点材质、驱动/动画均未验证；空的实际使用槽为资产失败 |
| 图像依赖 | FILE/GENERATED 已打包图像，记录原始 packed 字节 SHA-256、长度、尺寸、通道、float/色彩属性及链接语义 | 外部图像、序列、UDIM、视频、linked library、外部缓存未支持；读取实际使用依赖，不把路径字符串当身份。原生保存 float/HDR 字节，不以 PNG8 诊断声称 HDR 同一性 |
| 拓扑 | 位置、边/缝/锐边、loop、面范围/绑定、锁定三角化、corner normals、UV/颜色属性、world transform | copy.validate 发现修正即原资产不干净；零世界三角面积拒收；不声称非流形/自相交/壁厚已验证 |

24 项现有 native required ID 不变；新增固定门禁 `native.scope_supported`、`native.cross_process`、`native.reference` 全部进入 v2 技术 summary 判定。NA 仍由 M1 从 kind 生成。Q 只影响审阅状态，不能抵消技术失败。

默认九视角是原八视角加 bottom；固定 1024²、Standard/None/exposure=0/gamma=1、RGBA8。source 第一次 36 图，source 同进程重复 27 个诊断图；fresh A/B 各 36 图，合计 **135 原图**。27 同进程对 + 36 跨进程对 + 36 可信参考对 = **99 比较记录与 99 差异图**。所有图、完整报告、元数据与 controller 作业记录都进入唯一文件计划，数量由循环展开，业务代码不以这些展示数字代替集合校验。

`beauty_hard_gate=false` 是本平台首份政策在冻结前作出的决定：beauty 必须生成、解码、比较与留证，但不声称 EEVEE 像素确定。几何与实际使用材质的可信 reference 精确比较仍是硬门，三个诊断 pass 的重复/参考比较也是硬门。合同冻结后不得自动切换此字段或提高阈值；另需 beauty 硬判时重新校准好/坏资产并创建新合同。

### Task 1: 冻结原生支持政策与闭合参数

**Files:**
- Create: `acceptance/native_policy.py`
- Test: `tests/unit/test_native_policy.py`

**Interfaces:**
- Consumes: M1 的 native nullable 字段与冻结输入 ID 清单。
- Produces: `validate_native_policy(value: Any) -> None`、`validate_native_parameters(parameters: Any) -> None`；失败抛 `ValueError`。

- [ ] **Step 1: 写失败测试。** 将以下完整测试加入所列文件。

```python
from copy import deepcopy
import pytest
from acceptance.native_policy import (
    validate_native_policy,
    validate_native_parameters,
    VIEWS,
    PASSES,
)


def policy():
    return {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "trusted-native-fixture-v1",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": {
                "blender": "5.2.0 LTS",
                "build": "fbe6228777e7",
                "os": "Darwin",
                "arch": "arm64",
                "backend": "METAL",
                "vendor": "Apple M4",
                "gpu": "Metal API",
                "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
                "view_transform": "Standard",
                "look": "None",
                "format": "PNG_RGBA8",
                "comparator": "blender-rgba-f32-v1",
            },
            "max_abs": {p: 0 for p in PASSES},
            "reference_images": {
                v + "." + p: "reference." + v + "." + p for v in VIEWS for p in PASSES
            },
        },
    }


def test_complete_policy_and_closed_job_parameters():
    value = policy()
    validate_native_policy(value)
    validate_native_parameters({"operation": "inspect", "policy": value, "experiment": "none"})
    with pytest.raises(ValueError):
        validate_native_parameters(
            {"operation": "inspect", "policy": value, "experiment": "fresh_a"}
        )


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(frame=True),
        lambda x: x["render"].update(reference_radius=float("nan")),
        lambda x: x["render"].update(views=list(VIEWS)[:-1]),
        lambda x: x["render"].update(extra="silently accepted"),
        lambda x: x["render"]["max_abs"].update(clay=True),
        lambda x: x["geometry_limits"].update(max_image_pixels=1024),
    ],
)
def test_policy_rejects_incomplete_or_ill_typed_values(change):
    value = deepcopy(policy())
    change(value)
    with pytest.raises(ValueError):
        validate_native_policy(value)
```

- [ ] **Step 2: 运行测试确认失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_policy.py -q
```

预期：新模块/入口尚不存在时导入或所述行为断言失败；退出非零，不能把 0 collected 当通过。

- [ ] **Step 3: 写最小实现。** 以下各代码块为对应新文件的完整初始内容。

`acceptance/native_policy.py`：

```python
from __future__ import annotations
import math
from typing import Any

VIEWS = ("front", "back", "left", "right", "top", "bottom", "persp", "obliqueA", "obliqueB")
PASSES = ("beauty", "clay", "silhouette", "wire")
PLATFORM_FIELDS = {
    "blender",
    "build",
    "os",
    "arch",
    "backend",
    "vendor",
    "gpu",
    "engines",
    "view_transform",
    "look",
    "format",
    "comparator",
}


def exact(value: Any, keys: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("closed native policy keys mismatch")


def number(value: Any, *, positive: bool = False) -> None:
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or (value <= 0 if positive else value < 0)
    ):
        raise ValueError("finite native number required")


def validate_native_policy(value: Any) -> None:
    exact(
        value,
        {
            "scene",
            "view_layer",
            "frame",
            "support_profile",
            "reference_manifest_id",
            "reference_authority",
            "render",
            "geometry_limits",
        },
    )
    for key in ("scene", "view_layer", "reference_manifest_id", "reference_authority"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 1024:
            raise ValueError("native policy text required")
    if type(value["frame"]) is not int or not -1048574 <= value["frame"] <= 1048574:
        raise ValueError("native frame outside Blender range")
    if value["support_profile"] != "native-static-v1":
        raise ValueError("unsupported native profile")
    limits = value["geometry_limits"]
    exact(limits, {"max_objects", "max_vertices", "max_triangles", "max_image_pixels"})
    for item in limits.values():
        if type(item) is not int or item <= 0:
            raise ValueError("positive integer geometry limit required")
    render = value["render"]
    exact(
        render,
        {
            "resolution",
            "views",
            "reference_center",
            "reference_radius",
            "platform",
            "max_abs",
            "reference_images",
            "beauty_hard_gate",
        },
    )
    if render["resolution"] != 1024 or type(render["resolution"]) is not int:
        raise ValueError("native-static-v1 uses 1024x1024")
    if render["views"] != list(VIEWS):
        raise ValueError("full 3D native profile requires all nine views")
    if not isinstance(render["reference_center"], list) or len(render["reference_center"]) != 3:
        raise ValueError("reference center needs three coordinates")
    for item in render["reference_center"]:
        if type(item) not in (int, float) or not math.isfinite(item):
            raise ValueError("reference center must be finite")
    number(render["reference_radius"], positive=True)
    exact(render["platform"], PLATFORM_FIELDS)
    if any(not isinstance(v, str) or not v for v in render["platform"].values()):
        raise ValueError("complete calibrated platform identity required")
    exact(render["max_abs"], set(PASSES))
    for item in render["max_abs"].values():
        number(item)
        if item > 1:
            raise ValueError("RGBA float32 comparison threshold outside [0,1]")
    exact(render["reference_images"], {v + "." + p for v in VIEWS for p in PASSES})
    image_ids = list(render["reference_images"].values())
    if any(not isinstance(v, str) or not v for v in image_ids) or len(set(image_ids)) != len(
        image_ids
    ):
        raise ValueError("unique frozen reference image IDs required")
    if type(render["beauty_hard_gate"]) is not bool:
        raise ValueError("beauty_hard_gate must be bool")
    if limits["max_image_pixels"] < 1024 * 1024:
        raise ValueError("image budget cannot cover the mandatory image")


def validate_native_parameters(parameters: Any) -> None:
    exact(parameters, {"operation", "policy", "experiment"})
    if parameters["operation"] not in {"inspect", "reopen", "render", "compare"}:
        raise ValueError("unknown native operation")
    if parameters["experiment"] not in {"none", "same_process", "fresh_a", "fresh_b"}:
        raise ValueError("unknown native experiment")
    if (parameters["operation"] == "render") != (parameters["experiment"] != "none"):
        raise ValueError("operation/experiment mismatch")
    validate_native_policy(parameters["policy"])
```

- [ ] **Step 4: 运行相同测试确认通过。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_policy.py -q
```

预期：目标测试全部通过；真实 Blender 测试必须实际启动进程，跳过只表示缺环境，不能作为本任务验收。

- [ ] **Step 5: 复核本任务边界后提交。**

```bash
git add acceptance/native_policy.py tests/unit/test_native_policy.py
git commit -m "feat(acceptance): define native static policy"
```

### Task 2: 增加实际几何、依赖与可信参考判断

**Files:**
- Create: `acceptance/native_checks.py`
- Test: `tests/unit/test_native_checks.py`

**Interfaces:**
- Consumes: 本文 Task 3 的 native manifest schema v2。
- Produces: `inspect_checks(manifest: dict[str,Any], digest_stable: bool) -> list[dict[str,Any]]`；`scene_geometry_findings(manifest) -> list[dict]`；`reference_findings(candidate,reference) -> list[dict]`；`validate_manifest(value,limits) -> None`。所有输出都是 findings，不产生 success 或 N/A。

- [ ] **Step 1: 写失败测试。** 将以下完整测试加入所列文件。

```python
from copy import deepcopy
from acceptance.native_checks import inspect_checks, scene_geometry_findings, reference_findings


def sample():
    geometry = {
        "vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
        "loops": [0, 1, 2],
        "polygons": [[0, 3, 0, False]],
        "triangles": [[0, 1, 2]],
        "validate_corrected": False,
        "triangles_complete": True,
    }
    matrix = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]
    return {
        "scope_gaps": [],
        "invalid_numbers": [],
        "reserved_props": [],
        "objects": [
            {
                "id": ["OBJECT", "Body"],
                "type": "MESH",
                "materials": ["Paint"],
                "matrix_world": matrix,
            }
        ],
        "meshes": {"Body": {"authored": deepcopy(geometry), "evaluated": deepcopy(geometry)}},
        "occurrences": [
            {"key": [["OBJECT", "Body"], []], "source": ["OBJECT", "Body"], "matrix_world": matrix}
        ],
        "dependencies": [],
        "materials": [{"id": ["MATERIAL", "Paint"]}],
        "units": {"scale_length": 1},
    }


def test_actual_used_material_is_required():
    value = sample()
    value["objects"][0]["materials"] = []
    failed = {c["id"] for c in inspect_checks(value, True) if c["findings"]}
    assert "r2.material.slots_resolved" in failed


def test_same_count_surface_change_is_not_an_equal_reference():
    reference = sample()
    candidate = deepcopy(reference)
    candidate["meshes"]["Body"]["evaluated"]["vertices"][0][0] = 0.25
    assert reference_findings(candidate, reference)
    assert not reference_findings(reference, reference)


def test_zero_transform_has_occurrence_but_degenerate_surface():
    value = sample()
    value["occurrences"][0]["matrix_world"] = [[0, 0, 0, 0]] * 3 + [[0, 0, 0, 1]]
    assert value["occurrences"]
    assert {f["code"] for f in scene_geometry_findings(value)} == {"degenerate_world_triangle"}


def test_missing_bottom_cannot_be_fixed_by_repeating_wrong_asset():
    reference = sample()
    candidate = deepcopy(reference)
    candidate["occurrences"] = []
    assert reference_findings(candidate, reference)
    assert scene_geometry_findings(candidate)


def test_nan_is_error_evidence_not_nonstandard_json():
    value = sample()
    value["invalid_numbers"] = [{"path": ["objects", 0, "matrix_world", 0, 0], "value": "nan"}]
    value["objects"][0]["matrix_world"][0][0] = None
    rows = inspect_checks(value, True)
    assert any(c["id"] == "r2.inventory.no_nan_inf" and c["findings"] for c in rows)
```

- [ ] **Step 2: 运行测试确认失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_checks.py tests/unit/test_native_policy.py -q
```

预期：新模块/入口尚不存在时导入或所述行为断言失败；退出非零，不能把 0 collected 当通过。

- [ ] **Step 3: 写最小实现。** 以下各代码块为对应新文件的完整初始内容。

`acceptance/native_checks.py`：

```python
from __future__ import annotations
import math
from typing import Any

R2 = (
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.inventory.no_reserved_props",
    "r2.geometry.validate_clean",
    "r2.geometry.manifest_written",
    "r2.material.slots_resolved",
    "r2.dependency.all_present",
    "r2.source.digest_stable",
)


def finding(code: str, detail: str) -> dict[str, Any]:
    return {"code": code, "severity": "error", "pointer": None, "detail": detail}


def inspect_checks(manifest: dict[str, Any], digest_stable: bool) -> list[dict[str, Any]]:
    failures: dict[str, list[dict[str, Any]]] = {key: [] for key in R2}

    def fail(key: str, code: str, detail: str) -> None:
        failures[key].append(finding(code, detail))

    if manifest["scope_gaps"]:
        fail(R2[0], "capability_gap", repr(manifest["scope_gaps"]))
    if manifest["invalid_numbers"]:
        fail(R2[1], "non_finite_data", repr(manifest["invalid_numbers"]))
    if manifest["reserved_props"]:
        fail(R2[2], "reserved_property", repr(manifest["reserved_props"]))
    for name, stages in manifest["meshes"].items():
        for stage, geometry in stages.items():
            if geometry["validate_corrected"]:
                fail(R2[3], "mesh_validate_changed", name + ":" + stage)
            if not geometry["triangles_complete"]:
                fail(R2[4], "incomplete_geometry", name + ":" + stage)
    for obj in manifest["objects"]:
        if obj["type"] != "MESH":
            continue
        for polygon in manifest["meshes"][obj["id"][1]]["evaluated"]["polygons"]:
            slot = polygon[2]
            if slot < 0 or slot >= len(obj["materials"]) or obj["materials"][slot] is None:
                fail(R2[5], "used_material_unresolved", repr(obj["id"]))
    for dependency in manifest["dependencies"]:
        if not dependency["packed"] or not dependency["bytes"] or not dependency["sha256"]:
            fail(R2[6], "dependency_missing", repr(dependency["id"]))
    if not digest_stable:
        fail(R2[7], "source_changed", "Source bytes changed while inspecting")
    return [{"id": key, "findings": failures[key], "metrics": {}} for key in R2]


def scene_geometry_findings(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest["scope_gaps"] or manifest["invalid_numbers"]:
        return [finding("geometry_not_verified", "Capability/finite-data gate blocked geometry")]
    problems = []
    if not manifest["occurrences"]:
        problems.append(finding("no_render_occurrence", "No supported render geometry"))
    for occurrence in manifest["occurrences"]:
        geometry = manifest["meshes"][occurrence["source"][1]]["evaluated"]
        matrix = occurrence["matrix_world"]
        if not geometry["triangles"]:
            problems.append(finding("empty_geometry", repr(occurrence["key"])))
        points = [
            [sum(matrix[i][k] * v[k] for k in range(3)) + matrix[i][3] for i in range(3)]
            for v in geometry["vertices"]
        ]
        for triangle in geometry["triangles"]:
            a, b, c = [points[geometry["loops"][i]] for i in triangle]
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            if not all(math.isfinite(x) for x in cross) or sum(x * x for x in cross) <= 0:
                problems.append(finding("degenerate_world_triangle", repr(occurrence["key"])))
                break
    return problems


def reference_findings(
    candidate: dict[str, Any], reference: dict[str, Any]
) -> list[dict[str, Any]]:
    fields = ("units", "objects", "meshes", "occurrences", "materials", "dependencies")
    return [
        finding(
            "reference_" + key + "_mismatch", key + " differs from independently approved reference"
        )
        for key in fields
        if candidate[key] != reference[key]
    ]


def validate_manifest(value: Any, limits: dict[str, int]) -> None:
    def closed(item: Any, fields: set[str]) -> None:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError("native manifest closed fields mismatch")

    def sequence(item: Any, limit: int) -> None:
        if not isinstance(item, list) or len(item) > limit:
            raise ValueError("native manifest list exceeds schema/budget")

    def vector(item: Any, width: int) -> None:
        if (
            not isinstance(item, list)
            or len(item) != width
            or any(
                x is not None and (type(x) not in (int, float) or not math.isfinite(x))
                for x in item
            )
        ):
            raise ValueError("native manifest vector malformed")

    closed(
        value,
        {
            "schema_version",
            "support_profile",
            "scene",
            "view_layer",
            "frame",
            "units",
            "auxiliary_inventory",
            "coverage",
            "scope_gaps",
            "occurrences_complete",
            "reserved_props",
            "collections",
            "objects",
            "meshes",
            "occurrences",
            "materials",
            "dependencies",
            "invalid_numbers",
        },
    )
    if value["schema_version"] != 2 or value["support_profile"] != "native-static-v1":
        raise ValueError("native manifest version mismatch")
    sequence(value["objects"], limits["max_objects"])
    ids = []
    object_fields = {
        "id",
        "type",
        "paths",
        "parent",
        "matrix_world",
        "hide_render",
        "hide_viewport",
        "hide_get",
        "render_included",
        "exclusion_reason",
        "modifiers",
        "custom_props",
        "materials",
    }
    for obj in value["objects"]:
        closed(obj, object_fields)
        if (
            not isinstance(obj["id"], list)
            or len(obj["id"]) != 2
            or obj["id"][0] != "OBJECT"
            or not isinstance(obj["id"][1], str)
        ):
            raise ValueError("structured object ID required")
        ids.append(obj["id"][1])
        if not isinstance(obj["matrix_world"], list) or len(obj["matrix_world"]) != 4:
            raise ValueError("matrix must have four rows")
        for row in obj["matrix_world"]:
            vector(row, 4)
        if not isinstance(obj["paths"], list) or any(
            not isinstance(path, list) or any(not isinstance(segment, str) for segment in path)
            for path in obj["paths"]
        ):
            raise ValueError("collection paths must preserve segments")
        if any(
            type(obj[key]) is not bool
            for key in ("hide_render", "hide_viewport", "hide_get", "render_included")
        ):
            raise ValueError("visibility must be bool")
    if len(ids) != len(set(ids)):
        raise ValueError("ambiguous object identities")
    geometry_fields = {
        "vertices",
        "edges",
        "edge_seams",
        "edge_sharp",
        "loops",
        "polygons",
        "uv",
        "colors",
        "validate_corrected",
        "triangulation",
        "triangles_complete",
        "triangles",
        "corner_normals",
    }
    total_vertices = total_triangles = 0
    for name, stages in value["meshes"].items():
        if name not in ids:
            raise ValueError("geometry without authored identity")
        closed(stages, {"authored", "evaluated"})
        for geometry in stages.values():
            closed(geometry, geometry_fields)
            for vertex in geometry["vertices"]:
                vector(vertex, 3)
            for row in geometry["corner_normals"]:
                vector(row, 3)
            if any(type(x) is not int for x in geometry["loops"]):
                raise ValueError("loop indices must be integers")
            if (
                type(geometry["validate_corrected"]) is not bool
                or type(geometry["triangles_complete"]) is not bool
            ):
                raise ValueError("geometry completeness must be bool")
            for triangle in geometry["triangles"]:
                if len(triangle) != 3 or any(
                    type(i) is not int or i < 0 or i >= len(geometry["loops"]) for i in triangle
                ):
                    raise ValueError("invalid triangulation loop indices")
            if geometry["triangles_complete"] and any(
                i < 0 or i >= len(geometry["vertices"]) for i in geometry["loops"]
            ):
                raise ValueError("complete geometry has invalid vertex indices")
            for uv in geometry["uv"]:
                closed(uv, {"name", "active_render", "values"})
                for coordinate in uv["values"]:
                    vector(coordinate, 2)
            for color in geometry["colors"]:
                closed(color, {"name", "domain", "type", "values"})
                for rgba in color["values"]:
                    vector(rgba, 4)
        total_vertices += len(stages["evaluated"]["vertices"])
        total_triangles += len(stages["evaluated"]["triangles"])
    if total_vertices > limits["max_vertices"] or total_triangles > limits["max_triangles"]:
        raise ValueError("native geometry exceeds frozen budget")
    for occurrence in value["occurrences"]:
        closed(occurrence, {"key", "source", "instancer_chain", "geometry", "matrix_world"})
        if occurrence["source"][1] not in value["meshes"] or occurrence["instancer_chain"] != []:
            raise ValueError("unsupported or dangling native occurrence")
    for entry in value["invalid_numbers"]:
        closed(entry, {"path", "value"})
        if entry["value"] not in {"nan", "inf", "-inf"}:
            raise ValueError("invalid numeric diagnostic token")
        current = value
        for segment in entry["path"]:
            current = current[segment]
        if current is not None:
            raise ValueError("invalid-number pointer must identify its null marker")
    if (
        type(value["frame"]) is not int
        or not isinstance(value["scene"], str)
        or not isinstance(value["view_layer"], str)
    ):
        raise ValueError("scene/layer/frame schema mismatch")
    closed(value["units"], {"system", "scale_length"})
    if (
        type(value["units"]["scale_length"]) not in (int, float)
        or value["units"]["scale_length"] <= 0
    ):
        raise ValueError("positive native unit scale required")
    closed(value["auxiliary_inventory"], {"worlds", "cameras", "lights"})
    for names in value["auxiliary_inventory"].values():
        if not isinstance(names, list) or any(not isinstance(n, str) for n in names):
            raise ValueError("auxiliary names must be strings")
    for record in value["coverage"]:
        closed(record, {"type", "count", "policy"})
        if (
            not isinstance(record["type"], str)
            or type(record["count"]) is not int
            or record["count"] < 0
            or record["policy"]
            not in {"ignored-ui", "collected", "unsupported", "inventory-only-controlled-lighting"}
        ):
            raise ValueError("coverage record malformed")
    for record in value["collections"]:
        closed(record, {"path", "exclude", "hide_render"})
        if (
            not isinstance(record["path"], list)
            or any(not isinstance(x, str) for x in record["path"])
            or type(record["exclude"]) is not bool
            or type(record["hide_render"]) is not bool
        ):
            raise ValueError("collection record malformed")
    for obj in value["objects"]:
        for modifier in obj["modifiers"]:
            closed(modifier, {"name", "type", "show_viewport", "show_render", "params"})
            if not isinstance(modifier["params"], dict) or any(
                type(modifier[k]) is not bool for k in ("show_viewport", "show_render")
            ):
                raise ValueError("modifier record malformed")
        if (
            not isinstance(obj["custom_props"], dict)
            or not isinstance(obj["materials"], list)
            or any(x is not None and not isinstance(x, str) for x in obj["materials"])
        ):
            raise ValueError("object properties/material references malformed")
    for material in value["materials"]:
        closed(material, {"id", "nodes", "links"})
        for node in material["nodes"]:
            fields = {"name", "type", "inputs"}
            if node["type"] == "TEX_IMAGE":
                fields |= {"image", "interpolation", "projection", "extension"}
            closed(node, fields)
            if not isinstance(node["inputs"], dict):
                raise ValueError("node inputs must be a socket mapping")
        if any(
            not isinstance(link, list)
            or len(link) != 4
            or any(not isinstance(x, str) for x in link)
            for link in material["links"]
        ):
            raise ValueError("material link schema mismatch")
    for dependency in value["dependencies"]:
        closed(
            dependency,
            {
                "id",
                "source",
                "packed",
                "bytes",
                "sha256",
                "size",
                "channels",
                "is_float",
                "colorspace",
                "path",
            },
        )
        if type(dependency["packed"]) is not bool or type(dependency["is_float"]) is not bool:
            raise ValueError("dependency flags must be bool")
        if dependency["packed"] and (
            type(dependency["bytes"]) is not int
            or dependency["bytes"] <= 0
            or not isinstance(dependency["sha256"], str)
            or len(dependency["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in dependency["sha256"])
        ):
            raise ValueError("packed dependency lacks actual bytes identity")
    if not isinstance(value["scope_gaps"], list) or any(
        not isinstance(x, str) for x in value["scope_gaps"]
    ):
        raise ValueError("capability gaps must be explicit strings")
    if type(value["occurrences_complete"]) is not bool or value["occurrences_complete"] != (
        not value["scope_gaps"]
    ):
        raise ValueError("occurrence completeness contradicts capability gaps")
```

- [ ] **Step 4: 运行相同测试确认通过。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_checks.py tests/unit/test_native_policy.py -q
```

预期：目标测试全部通过；真实 Blender 测试必须实际启动进程，跳过只表示缺环境，不能作为本任务验收。

- [ ] **Step 5: 复核本任务边界后提交。**

```bash
git add acceptance/native_checks.py tests/unit/test_native_checks.py
git commit -m "feat(acceptance): check native surfaces and trusted references"
```

### Task 3: 在 disposable Blender 中形成完整原生采集与正反夹具

**Files:**
- Create: `acceptance/blender_scripts/__init__.py`
- Create: `acceptance/blender_scripts/native_collect.py`
- Create: `tests/fixtures/asset_native.py`

**Interfaces:**
- Consumes: 固定 scene/view layer/frame；原生文件必须已由 M1 接收器冻结且获得 local-trusted 来源授权。
- Produces: `collect(scene_name: str, layer_name: str, frame: int) -> dict[str,Any]`；对象身份 `["OBJECT", name]`，occurrence key 为 `[source_id, instancer_chain]`，普通 MESH 的 chain 为 `[]`；`meshes[object_name]` 同时含 authored/evaluated。M3 可直接复用此结构，不能用 mesh/object 计数替代表面数据。

- [ ] **Step 1: 写真实生成夹具脚本。** 以下文件本身即集成回归输入生成器；随后 Step 2 的断言检查实际 Blender 输出，不构造假的 worker Pass。

`tests/fixtures/asset_native.py`：

```python
# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
import bpy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts.native_collect import collect

root = Path(sys.argv[sys.argv.index("--") + 1])
root.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
mat = bpy.data.materials.new("Body material")
mat.use_nodes = True
mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.8, 0.2, 0.05, 1)
for name, location, scale in [
    ("Body", (0, 0, 0), (1, 1, 0.7)),
    ("Top", (0, 0, 1), (1.1, 1.1, 0.12)),
    ("Bottom", (0, 0, -0.9), (0.6, 0.6, 0.1)),
]:
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=str(root / "good.blend"))
(root / "reference.json").write_text(
    json.dumps(collect("Scene", "ViewLayer", 1), sort_keys=True, allow_nan=False)
)
for variant in (
    "missing_bottom",
    "zero_scale",
    "material_missing",
    "invalid_face",
    "curve",
    "triangulate",
    "bevel",
    "packed_image",
    "nan",
    "same_counts_surface",
    "transform_wrong",
    "material_changed",
    "nested_custom",
    "reserved_material",
    "missing_dependency",
):
    bpy.ops.wm.open_mainfile(filepath=str(root / "good.blend"), load_ui=False, use_scripts=False)
    body = bpy.data.objects["Body"]
    if variant == "missing_bottom":
        bpy.data.objects.remove(bpy.data.objects["Bottom"], do_unlink=True)
    if variant == "zero_scale":
        body.scale = (0, 0, 0)
    if variant == "material_missing":
        body.data.materials.clear()
    if variant == "invalid_face":
        mesh = bpy.data.meshes.new("Invalid")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 0, 1)])
        body.data = mesh
    if variant == "curve":
        curve = bpy.data.objects.new("Curve object", bpy.data.curves.new("Curve", "CURVE"))
        bpy.context.scene.collection.objects.link(curve)
    if variant == "triangulate":
        body.modifiers.new("Triangulate", "TRIANGULATE")
    if variant == "bevel":
        body.modifiers.new("Bevel", "BEVEL")
    if variant == "packed_image":
        image = bpy.data.images.new("Packed color", width=2, height=2)
        image.pixels[:] = [0.8, 0.2, 0.1, 1] * 4
        image.pack()
        tree = body.data.materials[0].node_tree
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    if variant == "nan":
        body.data.vertices[0].co.x = float("nan")
    if variant == "same_counts_surface":
        body.data.vertices[0].co.x += 0.2
    if variant == "transform_wrong":
        body.location.x += 0.1
    if variant == "material_changed":
        body.data.materials[0].node_tree.nodes["Principled BSDF"].inputs[
            "Base Color"
        ].default_value = (1, 1, 1, 1)
    if variant == "nested_custom":
        body["nested"] = {"review": {"weight": [1.0, 2.5], "visible": True}}
    if variant == "reserved_material":
        body.data.materials[0]["bcx_uid"] = "candidate-forged"
    if variant == "missing_dependency":
        image = bpy.data.images.new("Missing external", width=2, height=2)
        image.source = "FILE"
        image.filepath = "//does-not-exist.png"
        tree = body.data.materials[0].node_tree
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        tree.links.new(node.outputs["Color"], tree.nodes["Principled BSDF"].inputs["Base Color"])
    bpy.ops.wm.save_as_mainfile(filepath=str(root / f"{variant}.blend"))
    result = collect("Scene", "ViewLayer", 1)
    (root / f"{variant}.json").write_text(json.dumps(result, sort_keys=True, allow_nan=False))
```

- [ ] **Step 2: 运行夹具确认采集器尚不存在时失败。**

```bash
export NATIVE_RUN="$(mktemp -d /tmp/asset-native-m2.XXXXXX)"
"$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/asset_native.py -- "$NATIVE_RUN/fixtures"
```

预期：尚未创建 collector 时非零退出；`--python-exit-code 1` 必须保留。目录只能是仓库外本轮新建目录。

- [ ] **Step 3: 写采集器。**

`acceptance/blender_scripts/__init__.py`：

```python
"""Blender-only asset workers; never imported by protocol or bridge/core."""
```

`acceptance/blender_scripts/native_collect.py`：

```python
from __future__ import annotations
import hashlib
import math
from typing import Any
import bpy

MODIFIERS = {
    "TRIANGULATE": ("quad_method", "ngon_method", "min_vertices", "keep_custom_normals"),
    "BEVEL": (
        "width",
        "width_pct",
        "segments",
        "affect",
        "limit_method",
        "angle_limit",
        "use_clamp_overlap",
        "offset_type",
        "profile_type",
        "profile",
        "material",
        "loop_slide",
        "mark_seam",
        "mark_sharp",
        "harden_normals",
        "face_strength_mode",
        "miter_outer",
        "miter_inner",
        "spread",
        "vmesh_method",
    ),
}
IGNORED_IDS = {"screens", "workspaces", "window_managers", "brushes", "palettes"}
SUPPORTED_IDS = {
    "objects",
    "collections",
    "scenes",
    "meshes",
    "materials",
    "images",
    "worlds",
    "cameras",
    "lights",
}


def value(v: Any) -> Any:
    if isinstance(v, dict):
        return {str(k): value(x) for k, x in v.items()}
    if hasattr(v, "to_dict"):
        return value(v.to_dict())
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    return [value(x) for x in v]


def finite(v: Any) -> bool:
    if isinstance(v, float):
        return math.isfinite(v)
    if isinstance(v, dict):
        return all(finite(x) for x in v.values())
    if isinstance(v, list):
        return all(finite(x) for x in v)
    return True


def geometry(mesh: Any, limits: dict[str, int]) -> dict[str, Any]:
    if (
        len(mesh.vertices) > limits["max_vertices"]
        or len(mesh.polygons) > limits["max_triangles"]
        or sum(max(0, p.loop_total - 2) for p in mesh.polygons) > limits["max_triangles"]
    ):
        raise ValueError("geometry exceeds bounded native collection profile")
    raw: dict[str, Any] = {
        "vertices": [list(v.co) for v in mesh.vertices],
        "edges": [list(e.vertices) for e in mesh.edges],
        "edge_seams": [e.use_seam for e in mesh.edges],
        "edge_sharp": [e.use_edge_sharp for e in mesh.edges],
        "loops": [int(x.vertex_index) for x in mesh.loops],
        "polygons": [
            [p.loop_start, p.loop_total, p.material_index, p.use_smooth] for p in mesh.polygons
        ],
        "uv": [
            {
                "name": uv.name,
                "active_render": uv.active_render,
                "values": [list(x.uv) for x in uv.data],
            }
            for uv in mesh.uv_layers
        ],
        "colors": [
            {
                "name": a.name,
                "domain": a.domain,
                "type": a.data_type,
                "values": [list(x.color) for x in a.data],
            }
            for a in mesh.color_attributes
        ],
    }
    duplicate = mesh.copy()
    try:
        corrected = bool(duplicate.validate(verbose=False, clean_customdata=True))
    finally:
        bpy.data.meshes.remove(duplicate)
    raw["validate_corrected"] = corrected
    raw["triangulation"] = "Blender Mesh.calc_loop_triangles locked build"
    raw["triangles_complete"] = not corrected and finite(raw)
    raw["triangles"] = []
    raw["corner_normals"] = []
    if raw["triangles_complete"]:
        mesh.calc_loop_triangles()
        raw["triangles"] = [list(t.loops) for t in mesh.loop_triangles]
        raw["corner_normals"] = [list(n.vector) for n in mesh.corner_normals]
    return raw


def collect(
    scene_name: str, layer_name: str, frame: int, *, limits: dict[str, int] | None = None
) -> dict[str, Any]:
    if limits is None:
        limits = {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 16777216,
        }
    gaps: list[str] = []
    if len(bpy.data.scenes) != 1 or scene_name not in bpy.data.scenes:
        raise ValueError("single named scene required")
    scene = bpy.data.scenes[scene_name]
    if len(scene.objects) > limits["max_objects"]:
        raise ValueError("object count exceeds bounded native collection profile")
    if layer_name not in scene.view_layers:
        raise ValueError("named view layer missing")
    scene.frame_set(frame)
    bpy.context.window.scene = scene
    bpy.context.window.view_layer = scene.view_layers[layer_name]
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    coverage = []
    reserved = []
    for prop in bpy.data.bl_rna.properties:
        if prop.type != "COLLECTION" or prop.identifier == "all_ids":
            continue
        name = prop.identifier
        members = list(getattr(bpy.data, name))
        policy = (
            "ignored-ui"
            if name in IGNORED_IDS
            else "inventory-only-controlled-lighting"
            if name in {"worlds", "cameras", "lights"}
            else "collected"
        )
        if members and name not in IGNORED_IDS | SUPPORTED_IDS:
            policy = "unsupported"
            gaps.append("datablock:" + name)
        coverage.append({"type": name, "count": len(members), "policy": policy})
        for block in members:
            if hasattr(block, "keys"):
                for key in block.keys():
                    if key.startswith(("bcx_", "acceptance_")):
                        reserved.append([name, block.name, key])
            if getattr(block, "library", None) is not None:
                gaps.append("linked:" + name + ":" + block.name)
            animation = getattr(block, "animation_data", None)
            if animation is not None:
                gaps.append("animation:" + name + ":" + block.name)
    paths: dict[str, list[list[str]]] = {}
    renderable: set[str] = set()
    collections = []

    def visit(layer: Any, parent: list[str], excluded: bool) -> None:
        path = parent + [layer.collection.name]
        blocked = excluded or layer.exclude or layer.collection.hide_render
        if layer.exclude or layer.hide_viewport or layer.collection.hide_viewport:
            gaps.append("layer-evaluation-disabled:" + repr(path))
        collections.append(
            {"path": path, "exclude": layer.exclude, "hide_render": layer.collection.hide_render}
        )
        for obj in layer.collection.objects:
            paths.setdefault(obj.name, []).append(path)
            if not blocked and not obj.hide_render:
                renderable.add(obj.name)
        for child in layer.children:
            visit(child, path, blocked)

    visit(scene.view_layers[layer_name].layer_collection, [], False)
    materials, dependencies = [], []
    for image in sorted(bpy.data.images, key=lambda x: x.name):
        if image.type == "RENDER_RESULT":
            continue
        packed = image.packed_file
        if packed is None or image.source not in {"FILE", "GENERATED"}:
            gaps.append("external-image:" + image.name)
        dependencies.append(
            {
                "id": ["IMAGE", image.name],
                "source": image.source,
                "packed": packed is not None,
                "bytes": packed.size if packed else None,
                "sha256": hashlib.sha256(bytes(packed.data)).hexdigest() if packed else None,
                "size": list(image.size),
                "channels": image.channels,
                "is_float": image.is_float,
                "colorspace": image.colorspace_settings.name,
                "path": image.filepath,
            }
        )
    for mat in sorted(bpy.data.materials, key=lambda x: x.name):
        if not mat.use_nodes or mat.node_tree is None:
            gaps.append("material-without-principled:" + mat.name)
            continue
        nodes = list(mat.node_tree.nodes)
        if (
            sum(n.type == "BSDF_PRINCIPLED" for n in nodes) != 1
            or sum(n.type == "OUTPUT_MATERIAL" for n in nodes) != 1
        ):
            gaps.append("material-node-count:" + mat.name)
        record: dict[str, Any] = {"id": ["MATERIAL", mat.name], "nodes": [], "links": []}
        for node in sorted(nodes, key=lambda x: x.name):
            if node.type not in {"BSDF_PRINCIPLED", "OUTPUT_MATERIAL", "TEX_IMAGE"}:
                gaps.append("material-node:" + mat.name + ":" + node.type)
            item = {"name": node.name, "type": node.type, "inputs": {}}
            for socket in node.inputs:
                if hasattr(socket, "default_value"):
                    item["inputs"][socket.identifier] = value(socket.default_value)
            if node.type == "TEX_IMAGE":
                if node.image is None or node.image.packed_file is None:
                    gaps.append("image-node-not-packed:" + mat.name)
                item.update(
                    {
                        "image": node.image.name if node.image else None,
                        "interpolation": node.interpolation,
                        "projection": node.projection,
                        "extension": node.extension,
                    }
                )
                if node.projection != "FLAT":
                    gaps.append("image-projection:" + mat.name)
            record["nodes"].append(item)
        for link in mat.node_tree.links:
            allowed = (
                link.from_node.type == "BSDF_PRINCIPLED"
                and link.from_socket.name == "BSDF"
                and link.to_node.type == "OUTPUT_MATERIAL"
                and link.to_socket.name == "Surface"
            ) or (
                link.from_node.type == "TEX_IMAGE"
                and link.from_socket.name == "Color"
                and link.to_node.type == "BSDF_PRINCIPLED"
                and link.to_socket.name == "Base Color"
            )
            if not allowed:
                gaps.append("material-link:" + mat.name)
            record["links"].append(
                [
                    link.from_node.name,
                    link.from_socket.identifier,
                    link.to_node.name,
                    link.to_socket.identifier,
                ]
            )
        record["links"].sort()
        materials.append(record)
    objects, meshes, occurrences = [], {}, []
    for obj in sorted(scene.objects, key=lambda x: x.name):
        if obj.type not in {"MESH", "EMPTY", "CAMERA", "LIGHT"}:
            gaps.append("object-type:" + obj.name + ":" + obj.type)
        if obj.hide_viewport or obj.hide_get():
            gaps.append("viewport-evaluation-disabled:" + obj.name)
        if obj.instance_type != "NONE" or obj.constraints:
            gaps.append("instancer-or-constraint:" + obj.name)
        modifiers = []
        for mod in obj.modifiers:
            fields = MODIFIERS.get(mod.type)
            if fields is None or not mod.show_viewport or not mod.show_render:
                gaps.append("modifier:" + obj.name + ":" + mod.type)
            if mod.type == "BEVEL" and (
                mod.limit_method not in {"NONE", "ANGLE"}
                or mod.vertex_group
                or mod.profile_type != "SUPERELLIPSE"
            ):
                gaps.append("bevel-mode:" + obj.name)
            modifiers.append(
                {
                    "name": mod.name,
                    "type": mod.type,
                    "show_viewport": mod.show_viewport,
                    "show_render": mod.show_render,
                    "params": {k: value(getattr(mod, k)) for k in fields or ()},
                }
            )
        if obj.data is not None and obj.type == "MESH":
            for attribute in obj.data.attributes:
                if not attribute.is_internal and attribute.name not in {
                    u.name for u in obj.data.uv_layers
                } | {c.name for c in obj.data.color_attributes} | {
                    "position",
                    ".edge_verts",
                    ".corner_vert",
                    ".corner_edge",
                    "sharp_face",
                    "sharp_edge",
                    "material_index",
                }:
                    gaps.append("mesh-attribute:" + obj.name + ":" + attribute.name)
        custom = {}
        for key in obj.keys():
            if key.startswith(("bcx_", "acceptance_")):
                reserved.append(["OBJECT", obj.name, key])
            try:
                custom[key] = value(obj[key])
            except TypeError:
                gaps.append("custom-property:" + obj.name + ":" + key)
        record = {
            "id": ["OBJECT", obj.name],
            "type": obj.type,
            "paths": sorted(paths.get(obj.name, [])),
            "parent": ["OBJECT", obj.parent.name] if obj.parent else None,
            "matrix_world": [list(r) for r in obj.matrix_world],
            "hide_render": obj.hide_render,
            "hide_viewport": obj.hide_viewport,
            "hide_get": obj.hide_get(),
            "render_included": obj.name in renderable,
            "exclusion_reason": None if obj.name in renderable else "object-or-layer-render-policy",
            "modifiers": modifiers,
            "custom_props": custom,
            "materials": [s.material.name if s.material else None for s in obj.material_slots],
        }
        objects.append(record)
        if obj.type != "MESH":
            continue
        meshes[obj.name] = {"authored": geometry(obj.data, limits)}
        evaluated = obj.evaluated_get(dg)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        try:
            meshes[obj.name]["evaluated"] = geometry(mesh, limits)
        finally:
            evaluated.to_mesh_clear()
        if obj.name in renderable:
            occurrences.append(
                {
                    "key": [["OBJECT", obj.name], []],
                    "source": ["OBJECT", obj.name],
                    "instancer_chain": [],
                    "geometry": ["MESH", obj.name, "evaluated"],
                    "matrix_world": record["matrix_world"],
                }
            )
    manifest: dict[str, Any] = {
        "schema_version": 2,
        "support_profile": "native-static-v1",
        "scene": scene_name,
        "view_layer": layer_name,
        "frame": frame,
        "units": {
            "system": scene.unit_settings.system,
            "scale_length": scene.unit_settings.scale_length,
        },
        "auxiliary_inventory": {
            name: sorted(x.name for x in getattr(bpy.data, name))
            for name in ("worlds", "cameras", "lights")
        },
        "coverage": coverage,
        "scope_gaps": sorted(set(gaps)),
        "occurrences_complete": not gaps,
        "reserved_props": sorted(reserved),
        "collections": collections,
        "objects": objects,
        "meshes": meshes,
        "occurrences": occurrences,
        "materials": materials,
        "dependencies": dependencies,
    }
    invalid_numbers = []

    def scrub(item: Any, pointer: list[Any]) -> Any:
        if isinstance(item, float) and not math.isfinite(item):
            invalid_numbers.append({"path": pointer, "value": repr(item)})
            return None
        if isinstance(item, dict):
            return {k: scrub(v, pointer + [k]) for k, v in item.items()}
        if isinstance(item, list):
            return [scrub(v, pointer + [i]) for i, v in enumerate(item)]
        return item

    manifest = scrub(manifest, [])
    manifest["invalid_numbers"] = invalid_numbers
    return manifest
```

- [ ] **Step 4: 在新目录重跑并检查真实正反结果。**

```bash
export NATIVE_RUN="$(mktemp -d /tmp/asset-native-m2.XXXXXX)"
"$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/asset_native.py -- "$NATIVE_RUN/fixtures"
"$PYTHON_BIN" - "$NATIVE_RUN/fixtures" <<'PYTEST'
import json,sys
from pathlib import Path
from acceptance.native_checks import inspect_checks,scene_geometry_findings,reference_findings,validate_manifest
root=Path(sys.argv[1]);read=lambda n:json.loads((root/(n+'.json')).read_text())
limits={'max_objects':1000,'max_vertices':1000000,'max_triangles':2000000,'max_image_pixels':1048576}
for name in ('reference','bevel','triangulate','packed_image'):
    value=read(name);validate_manifest(value,limits)
    assert not value['scope_gaps'] and not any(c['findings'] for c in inspect_checks(value,True))
    assert not scene_geometry_findings(value)
reference=read('reference')
assert reference_findings(read('missing_bottom'),reference)
assert scene_geometry_findings(read('zero_scale'))
assert any(c['id']=='r2.material.slots_resolved' and c['findings'] for c in inspect_checks(read('material_missing'),True))
assert read('invalid_face')['meshes']['Body']['authored']['validate_corrected']
assert read('curve')['scope_gaps']
print('NATIVE_COLLECTOR_FIXTURES_OK')
PYTEST
```

预期输出 `NATIVE_COLLECTOR_FIXTURES_OK`。BEVEL、TRIANGULATE、packed-image 相对无 modifier 的 reference 应不同；它们做完整通过测试时必须使用各自经可信生成器确定的 reference，不能因此放松比较。

- [ ] **Step 5: 提交本任务。**

```bash
git add acceptance/blender_scripts/__init__.py acceptance/blender_scripts/native_collect.py tests/fixtures/asset_native.py
git commit -m "feat(acceptance): collect supported native authored and evaluated data"
```

### Task 4: 受控九视角、同进程/新进程实验与解码比较

**Files:**
- Create: `acceptance/blender_scripts/native_render.py`
- Create: `tests/fixtures/native_visual_probe.py`

**Interfaces:**
- Consumes: Task 3 manifest；固定可信参考中心/半径，不能根据坏候选重新自动构图扩大 reference_scale；`outputs: dict[file_id, Path]` 来自唯一文件计划。
- Produces: `render_images(manifest, settings, outputs, experiment) -> dict`；`decode(path:Path,max_pixels:int) -> (size,array('f'))`；`compare(left,right,diff,max_pixels) -> dict`。比较器记录原始文件 hash 和实际 RGBA float32 像素差，不能混用。

- [ ] **Step 1: 写独立可执行视觉探针。**

`tests/fixtures/native_visual_probe.py`：

```python
# ruff: noqa: E402 -- Establish the trusted repository path before local imports.
import sys
import json
from pathlib import Path
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from acceptance.blender_scripts.native_collect import collect
from acceptance.blender_scripts.native_render import render_images, compare, PASSES, VIEWS

args = sys.argv[sys.argv.index("--") + 1 :]
root = Path(args[0])
operation = args[1]
if operation == "compare":
    destination = root / "comparison"
    destination.mkdir()
    records = []
    for group in ("same", "fresh"):
        for view in VIEWS:
            for render_pass in PASSES:
                if group == "same" and render_pass == "beauty":
                    continue
                first = (
                    root
                    / ("same_process" if group == "same" else "fresh_a")
                    / f"0-{view}-{render_pass}.png"
                )
                second = (
                    root
                    / ("same_process" if group == "same" else "fresh_b")
                    / f"{1 if group == 'same' else 0}-{view}-{render_pass}.png"
                )
                result = compare(
                    first, second, destination / f"{group}-{view}-{render_pass}.png", 1048576
                )
                result.update(group=group, view=view, render_pass=render_pass)
                records.append(result)
    (root / "comparisons.json").write_text(json.dumps(records, allow_nan=False))
    assert len(records) == 63
    assert not [r for r in records if r["render_pass"] != "beauty" and r["different_pixels"]]
    for render_pass in ("clay", "silhouette", "wire"):
        assert sum(r["left_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
        assert sum(r["right_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
    for render_pass in ("clay", "silhouette", "wire"):
        assert sum(r["left_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
        assert sum(r["right_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
    for render_pass in ("clay", "silhouette", "wire"):
        assert sum(r["left_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
        assert sum(r["right_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
    for render_pass in ("clay", "silhouette", "wire"):
        assert sum(r["left_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
        assert sum(r["right_rgb_energy"] for r in records if r["render_pass"] == render_pass) > 0
    print("NATIVE_27_SAME_AND_27_FRESH_DIAGNOSTIC_PAIRS_OK")
else:
    destination = root / operation
    destination.mkdir()
    bpy.ops.wm.open_mainfile(
        filepath=str(root / "fixtures/good.blend"), load_ui=False, use_scripts=False
    )
    manifest = collect("Scene", "ViewLayer", 1)
    settings = {
        "resolution": 1024,
        "views": list(VIEWS),
        "reference_center": [0, 0, 0],
        "reference_radius": 2,
    }
    outputs = {
        f"image.{operation}.{r}.{v}.{p}": destination / f"{r}-{v}-{p}.png"
        for r in range(2 if operation == "same_process" else 1)
        for v in VIEWS
        for p in PASSES
        if not (r == 1 and p == "beauty")
    }
    report = render_images(manifest, settings, outputs, operation)
    (destination / "render.json").write_text(json.dumps(report, allow_nan=False))
```

- [ ] **Step 2: 确认渲染器尚未加入时失败。**

```bash
"$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/native_visual_probe.py -- "$NATIVE_RUN" same_process
```

预期模块不存在而非零退出。失败目录不能重用为成功证据。

- [ ] **Step 3: 写完整受控渲染/比较模块。** 直接使用 Workbench WIREFRAME 在本机离线渲染中生成了全黑图，不能作为 wire 证据。这里从 evaluated 网格的真实边创建世界空间细管曲线，以固定 `reference_radius × 0.0015` 半径、SOLID/FLAT 白色渲染全部边。wire 期间隐藏诊断面的副本，其他 pass 隐藏这些细管；这是固定的全边诊断，不声称物理线宽或遮挡线处理。保留空材质槽位置，不压缩材质槽来“修好”坏资产。

`acceptance/blender_scripts/native_render.py`：

```python
from __future__ import annotations
from array import array
import hashlib
import os
import platform
import math
import struct
from pathlib import Path
from typing import Any
import bpy
import gpu
from mathutils import Vector, Matrix

VIEWS = {
    "front": ("ORTHO", (0, -1, 0)),
    "back": ("ORTHO", (0, 1, 0)),
    "left": ("ORTHO", (-1, 0, 0)),
    "right": ("ORTHO", (1, 0, 0)),
    "top": ("ORTHO", (0, 0, 1)),
    "bottom": ("ORTHO", (0, 0, -1)),
    "persp": ("PERSP", (1, -1, 0.8)),
    "obliqueA": ("PERSP", (1, -1, 0.6)),
    "obliqueB": ("PERSP", (-1, -1, 0.35)),
}
PASSES = ("beauty", "clay", "silhouette", "wire")


def platform_key() -> dict[str, str]:
    return {
        "blender": bpy.app.version_string,
        "build": bpy.app.build_hash.decode(),
        "os": platform.system(),
        "arch": platform.machine(),
        "backend": gpu.platform.backend_type_get(),
        "vendor": gpu.platform.vendor_get(),
        "gpu": gpu.platform.renderer_get(),
        "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
        "view_transform": "Standard",
        "look": "None",
        "format": "PNG_RGBA8",
        "comparator": "blender-rgba-f32-v1",
    }


def diagnostic_scene(manifest: dict[str, Any], wire_radius: float) -> Any:
    source = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    scene = bpy.data.scenes.new("Evaluator controlled diagnostics")
    scene.world = bpy.data.worlds.new("Evaluator world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.05, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1
    for occurrence in manifest["occurrences"]:
        original = source.objects[occurrence["source"][1]]
        evaluated = original.evaluated_get(dg)
        mesh = bpy.data.meshes.new_from_object(
            evaluated, preserve_all_data_layers=True, depsgraph=dg
        )
        mesh.materials.clear()
        for slot in original.material_slots:
            mesh.materials.append(slot.material)
        obj = bpy.data.objects.new(original.name, mesh)
        scene.collection.objects.link(obj)
        obj.matrix_world = Matrix(occurrence["matrix_world"])
        curve = bpy.data.curves.new(original.name + " evaluator edges", "CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 1
        curve.bevel_depth = wire_radius
        curve.bevel_resolution = 0
        curve.fill_mode = "FULL"
        for edge in mesh.edges:
            spline = curve.splines.new("POLY")
            spline.points.add(1)
            for point, vertex_index in zip(spline.points, edge.vertices, strict=True):
                co = obj.matrix_world @ mesh.vertices[vertex_index].co
                point.co = (*co, 1.0)
        wire = bpy.data.objects.new(original.name + " evaluator wire", curve)
        scene.collection.objects.link(wire)
        wire.hide_render = True
    for name, direction, energy in [
        ("key", (1, -1, -1), 3),
        ("fill", (-1, -0.5, -0.3), 1),
        ("rim", (0, 1, -0.5), 1.5),
    ]:
        light = bpy.data.lights.new(name, "SUN")
        light.energy = energy
        obj = bpy.data.objects.new(name, light)
        scene.collection.objects.link(obj)
        obj.rotation_euler = Vector(direction).to_track_quat("-Z", "Y").to_euler()
    cam = bpy.data.objects.new("Evaluator camera", bpy.data.cameras.new("Evaluator camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    scene.render.film_transparent = False
    scene.render.use_file_extension = True
    scene.render.use_stamp = False
    scene.render.use_compositing = False
    scene.render.use_sequencer = False
    return scene


def render_images(
    manifest: dict[str, Any], settings: dict[str, Any], outputs: dict[str, Path], experiment: str
) -> dict[str, Any]:
    if manifest["scope_gaps"]:
        raise ValueError("unsupported asset must not enter renderer")
    scene = diagnostic_scene(manifest, settings["reference_radius"] * 0.0015)
    bpy.context.window.scene = scene
    scene.render.resolution_x = settings["resolution"]
    scene.render.resolution_y = settings["resolution"]
    center = Vector(settings["reference_center"])
    radius = settings["reference_radius"]
    records = []
    for repetition in range(2 if experiment == "same_process" else 1):
        for view in settings["views"]:
            projection, offset = VIEWS[view]
            direction = Vector(offset).normalized()
            scene.camera.data.type = projection
            scene.camera.data.lens = 50
            scene.camera.data.sensor_width = 36
            scene.camera.data.ortho_scale = 2.2 * radius
            scene.camera.data.clip_start = (0.1 if projection == "ORTHO" else 0.05) * radius
            scene.camera.data.clip_end = 10 * radius
            scene.camera.location = (
                center + direction * (4 if projection == "ORTHO" else 3.25) * radius
            )
            scene.camera.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
            for render_pass in PASSES:
                if repetition == 1 and render_pass == "beauty":
                    continue
                shading = scene.display.shading
                shading.type = "SOLID"
                shading.light = "STUDIO" if render_pass == "clay" else "FLAT"
                shading.color_type = "SINGLE"
                shading.single_color = (0.8, 0.8, 0.8) if render_pass == "clay" else (1, 1, 1)
                shading.show_shadows = False
                shading.show_cavity = False
                shading.show_specular_highlight = False
                shading.background_type = "VIEWPORT"
                shading.background_color = (0, 0, 0)
                for obj in scene.objects:
                    if obj.type == "MESH":
                        obj.display_type = "SOLID"
                        obj.hide_render = render_pass == "wire"
                    elif obj.type == "CURVE":
                        obj.hide_render = render_pass != "wire"
                scene.render.engine = (
                    "BLENDER_EEVEE" if render_pass == "beauty" else "BLENDER_WORKBENCH"
                )
                scene.display.render_aa = "8"
                scene.eevee.taa_render_samples = 64
                fid = f"image.{experiment}.{repetition}.{view}.{render_pass}"
                path = outputs[fid]
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists():
                    raise FileExistsError(path)
                scene.render.filepath = str(path)
                bpy.ops.render.render(write_still=True, scene=scene.name)
                records.append(
                    {
                        "id": fid,
                        "view": view,
                        "pass": render_pass,
                        "repetition": repetition,
                        "pid": os.getpid(),
                        "experiment": experiment,
                        "engine": scene.render.engine,
                    }
                )
    return {
        "schema_version": 2,
        "platform": platform_key(),
        "settings": settings,
        "images": records,
    }


def decode(path: Path, max_pixels: int) -> tuple[tuple[int, int], array[float]]:
    with path.open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError("locked decoder accepts PNG only")
    width, height, depth, color, compression, filter_method, interlace = struct.unpack(
        ">IIBBBBB", header[16:29]
    )
    if (
        width <= 0
        or height <= 0
        or width * height > max_pixels
        or (depth, color, compression, filter_method, interlace) != (8, 6, 0, 0, 0)
    ):
        raise ValueError("bounded noninterlaced RGBA8 PNG required")
    image = bpy.data.images.load(str(path), check_existing=False)
    try:
        w, h = image.size
        if w <= 0 or h <= 0 or w * h > max_pixels or image.channels != 4:
            raise ValueError("RGBA image dimensions/channels outside frozen budget")
        pixels = array("f", [0.0]) * (w * h * 4)
        image.pixels.foreach_get(pixels)
        # Float32 values and bounded pixel counts cannot overflow a float64 sum.
        if not math.isfinite(sum(pixels)):
            raise ValueError("non-finite decoded image")
        return (w, h), pixels
    finally:
        bpy.data.images.remove(image)


def compare(left: Path, right: Path, diff: Path, max_pixels: int) -> dict[str, Any]:
    ls, lp = decode(left, max_pixels)
    rs, rp = decode(right, max_pixels)
    if ls != rs:
        raise ValueError("image dimension mismatch")
    if lp == rp:
        changed_channels = changed_pixels = 0
        maximum = 0.0
        delta = array("f", [0.0, 0.0, 0.0, 1.0]) * (ls[0] * ls[1])
    else:
        delta = array("f", (abs(a - b) for a, b in zip(lp, rp, strict=True)))
        changed_channels = sum(v != 0 for v in delta)
        changed_pixels = sum(any(delta[i : i + 4]) for i in range(0, len(delta), 4))
        maximum = max(delta)
        for i in range(3, len(delta), 4):
            delta[i] = 1.0
    difference = bpy.data.images.new(
        "Evaluator diff", width=ls[0], height=ls[1], alpha=True, float_buffer=True
    )
    try:
        difference.pixels.foreach_set(delta)
        difference.filepath_raw = str(diff)
        difference.file_format = "PNG"
        difference.save()
    finally:
        bpy.data.images.remove(difference)
    return {
        "decoder": "blender-rgba-f32-v1",
        "size": list(ls),
        "channels": 4,
        "precision": "float32",
        "color_interpretation": "Blender PNG decode, Standard output",
        "left_bytes_sha256": hashlib.sha256(left.read_bytes()).hexdigest(),
        "right_bytes_sha256": hashlib.sha256(right.read_bytes()).hexdigest(),
        "different_channels": changed_channels,
        "different_pixels": changed_pixels,
        "max_abs": maximum,
        "left_rgb_energy": sum(lp) - sum(lp[3::4]),
        "right_rgb_energy": sum(rp) - sum(rp[3::4]),
    }
```

- [ ] **Step 4: 在新目录执行全部实验。**

```bash
export NATIVE_RUN="$(mktemp -d /tmp/asset-native-visual-m2.XXXXXX)"
"$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/asset_native.py -- "$NATIVE_RUN/fixtures"
for experiment in same_process fresh_a fresh_b; do
  "$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/native_visual_probe.py -- "$NATIVE_RUN" "$experiment" || exit 1
done
"$BLENDER_BIN" --background --factory-startup --disable-autoexec --offline-mode --python-exit-code 1 --python tests/fixtures/native_visual_probe.py -- "$NATIVE_RUN" compare
```

预期：135 原图、63 该探针对比记录；27 同进程及 27 新进程诊断对均通过当前校准。所有 9 beauty 跨进程对也实际测量并保留，不能在有差异时删图或调整零阈值。此探针尚不含 36 可信参考对、controller 验证、Q/T，因此不叫 M2 完整通过。

- [ ] **Step 5: 提交本任务。**

```bash
git add acceptance/blender_scripts/native_render.py tests/fixtures/native_visual_probe.py
git commit -m "feat(acceptance): render and compare complete native visual experiments"
```

### Task 5: 接通隔离作业、精确 D 重开与单一文件展开

**Files:**
- Create: `acceptance/blender_scripts/native_worker.py`
- Create: `acceptance/native_plan.py`
- Test: `tests/unit/test_native_plan.py`
- Modify: `acceptance/contract.py` 的 M1 native null 拒绝分支

**Interfaces:**
- Consumes: `worker_protocol.read_request(path: Path) -> dict`、`write_result(request, checks, observations) -> Path`；request 身份字段 `schema_version/run_id/attempt/nonce/job_id/writer/contract_digest/source_digest` 原样绑定；`input_root/inputs/output_root/outputs/parameters` 来自 controller。
- Produces: `native_jobs(contract: Contract, *, include_reopen: bool=True) -> tuple[JobSpec,...]`、`build_native_plan(contract) -> RunPlan`、`native_commands(blender:Path,repository:Path) -> dict[writer,tuple[str,...]]`。M3 使用 `include_reopen=False`，禁止把 native 三项重开 check 重复塞给 interchange。
- Core 签名：`FileSpec(id,path,writer,media_type,max_bytes)`；`JobSpec(job_id,writer,tool_id,check_ids,input_ids,outputs,parameters,blocking_check_ids=())`；`assemble_plan(contract,jobs,*,gate_ids=())`。
- core 为每个 job 自动添加 `job_id.result` 和 controller 作业记录；worker 的业务 artifact 列表排除 result 自身。`outputs.path` 是该 job 的相对路径，RunPlan 最终加 job_id 前缀。命令按 writer 映射；Blender prefix 以 `--` 结尾，core 再附 `--request <request.json>`。

- [ ] **Step 1: 写文件/检查唯一性与启动参数测试。**

`tests/unit/test_native_plan.py`：

```python
from types import SimpleNamespace
from pathlib import Path
from acceptance.native_plan import native_jobs, native_commands, UNSAFE_R2
from acceptance.native_policy import VIEWS, PASSES


def test_native_jobs_preserve_required_images_and_unique_owners():
    platform = {
        "blender": "5.2.0 LTS",
        "build": "fbe6228777e7",
        "os": "Darwin",
        "arch": "arm64",
        "backend": "METAL",
        "vendor": "Apple M4",
        "gpu": "Metal API",
        "engines": "BLENDER_EEVEE,BLENDER_WORKBENCH",
        "view_transform": "Standard",
        "look": "None",
        "format": "PNG_RGBA8",
        "comparator": "blender-rgba-f32-v1",
    }
    policy = {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "trusted-native-fixture-v1",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": platform,
            "max_abs": {p: 0 for p in PASSES},
            "reference_images": {
                v + "." + p: "reference." + v + "." + p for v in VIEWS for p in PASSES
            },
        },
    }
    contract = SimpleNamespace(raw={"native": policy}, artifact_kind="blend_native")
    jobs = native_jobs(contract)
    files = [f for job in jobs for f in job.outputs]
    assert len([f for f in files if f.id.startswith("image.")]) == 135
    assert len([f for f in files if f.id.startswith("diff.")]) == 99
    assert len({f.id for f in files}) == len(files)
    assert len([c for job in jobs for c in job.check_ids]) == 14
    assert all(
        job.blocking_check_ids == UNSAFE_R2 for job in jobs if job.job_id != "native.inspect"
    )
    assert not any(
        "r4.reopen." in c
        for job in native_jobs(contract, include_reopen=False)
        for c in job.check_ids
    )
    assert all(f.writer == job.writer for job in jobs for f in job.outputs)


def test_commands_cannot_come_from_candidate_properties():
    commands = native_commands(
        Path("/Applications/Blender.app/Contents/MacOS/Blender"), Path("/trusted/repo")
    )
    for argv in commands.values():
        assert "--disable-autoexec" in argv and "--offline-mode" in argv
        assert argv[argv.index("--python-exit-code") + 1] == "1"
        assert argv[-1] == "--" and "--request" not in argv
```

- [ ] **Step 2: 运行新测试确认缺模块时失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_plan.py -q
```

- [ ] **Step 3: 加入作业展开与 worker 全代码。**

`acceptance/native_plan.py`：

```python
from __future__ import annotations
from pathlib import Path
from acceptance.check_registry import CHECKS
from acceptance.contract import Contract, thaw
from acceptance.plan import FileSpec, JobSpec, RunPlan, assemble_plan
from acceptance.native_policy import validate_native_policy, VIEWS, PASSES

NATIVE_GATES = ("native.scope_supported", "native.cross_process", "native.reference")
UNSAFE_R2 = (
    "r2.inventory.coverage_complete",
    "r2.inventory.no_nan_inf",
    "r2.geometry.validate_clean",
    "r2.geometry.manifest_written",
    "r2.source.digest_stable",
)


def native_jobs(contract: Contract, *, include_reopen: bool = True) -> tuple[JobSpec, ...]:
    policy = thaw(contract.raw["native"])
    validate_native_policy(policy)

    def output(fid: str, writer: str, image: bool = False) -> FileSpec:
        return FileSpec(
            fid,
            ("images/" if image else "data/") + fid + (".png" if image else ".json"),
            writer,
            "image/png" if image else "application/json",
            16 * 1024 * 1024 if image else 64 * 1024 * 1024,
        )

    def job(
        job_id: str,
        writer: str,
        operation: str,
        inputs: tuple[str, ...],
        outputs: tuple[FileSpec, ...],
        experiment: str = "none",
    ) -> JobSpec:
        return JobSpec(
            job_id,
            writer,
            "blender",
            tuple(c.id for c in CHECKS if c.writer == writer),
            inputs,
            outputs,
            {"operation": operation, "policy": policy, "experiment": experiment},
            () if operation == "inspect" else UNSAFE_R2,
        )

    jobs = [
        job(
            "native.inspect",
            "inspector",
            "inspect",
            ("asset",),
            (output("native.manifest", "inspector"), output("native.dependencies", "inspector")),
        )
    ]
    if include_reopen:
        jobs.append(
            job(
                "native.reopen",
                "reopen_probe",
                "reopen",
                ("asset", "native.manifest"),
                (
                    output("native.reopened", "reopen_probe"),
                    output("native.reopen_dependencies", "reopen_probe"),
                ),
            )
        )
    image_ids: list[str] = []
    for experiment, writer in (
        ("same_process", "render_views(src)"),
        ("fresh_a", "render_views(src-fresh-a)"),
        ("fresh_b", "render_views(src-fresh-b)"),
    ):
        images = tuple(
            output(f"image.{experiment}.{r}.{view}.{render_pass}", writer, True)
            for r in range(2 if experiment == "same_process" else 1)
            for view in VIEWS
            for render_pass in PASSES
            if not (r == 1 and render_pass == "beauty")
        )
        image_ids.extend(x.id for x in images)
        jobs.append(
            job(
                "native.render." + experiment,
                writer,
                "render",
                ("asset", "native.manifest"),
                images + (output("render." + experiment, writer),),
                experiment,
            )
        )
    diffs = tuple(
        output(f"diff.{group}.{view}.{render_pass}", "native_compare", True)
        for group in ("same", "fresh", "reference")
        for view in VIEWS
        for render_pass in PASSES
        if not (group == "same" and render_pass == "beauty")
    )
    comparison_inputs = (
        tuple(image_ids)
        + ("native.manifest", policy["reference_manifest_id"])
        + tuple(policy["render"]["reference_images"][v + "." + p] for v in VIEWS for p in PASSES)
    )
    jobs.append(
        job(
            "native.compare",
            "native_compare",
            "compare",
            comparison_inputs,
            diffs + (output("native.comparisons", "native_compare"),),
        )
    )
    return tuple(jobs)


def build_native_plan(contract: Contract) -> RunPlan:
    if contract.artifact_kind != "blend_native":
        raise ValueError("native entrypoint requires blend_native")
    return assemble_plan(contract, native_jobs(contract), gate_ids=NATIVE_GATES)


def native_commands(blender: Path, repository: Path) -> dict[str, tuple[str, ...]]:
    prefix = (
        str(blender),
        "--background",
        "--factory-startup",
        "--disable-autoexec",
        "--offline-mode",
        "--python-exit-code",
        "1",
        "--python",
        str(repository / "acceptance/blender_scripts/native_worker.py"),
        "--",
    )
    return {
        writer: prefix
        for writer in (
            "inspector",
            "reopen_probe",
            "render_views(src)",
            "render_views(src-fresh-a)",
            "render_views(src-fresh-b)",
            "native_compare",
        )
    }
```

`acceptance/blender_scripts/native_worker.py`：

```python
# ruff: noqa: E402 -- Blender --python entrypoint must establish the trusted repo path.
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from acceptance.worker_protocol import read_request, write_result
from acceptance.native_policy import validate_native_parameters, VIEWS, PASSES
from acceptance.native_checks import (
    inspect_checks,
    scene_geometry_findings,
    reference_findings,
    finding,
    validate_manifest,
)
from acceptance.blender_scripts.native_collect import collect
from acceptance.blender_scripts.native_render import render_images, compare
from acceptance.strict_json import strict_json_loads


def read_json(path: Path, limit: int = 64 * 1024 * 1024) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("native JSON exceeds bounded input")
    data = strict_json_loads(raw)
    if not isinstance(data, dict):
        raise ValueError("native JSON object required")
    return data


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            value,
            stream,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        stream.write("\n")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def work(request: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = request["parameters"]
    validate_native_parameters(parameters)
    operation = parameters["operation"]
    policy = parameters["policy"]
    inputs = {x["id"]: Path(request["input_root"]) / x["path"] for x in request["inputs"]}
    outputs = {x["id"]: Path(request["output_root"]) / x["path"] for x in request["outputs"]}
    if operation == "compare":
        comparisons = []
        for group in ("same", "fresh", "reference"):
            for view in VIEWS:
                for render_pass in PASSES:
                    if group == "same" and render_pass == "beauty":
                        continue
                    left = (
                        f"image.fresh_a.0.{view}.{render_pass}"
                        if group == "fresh"
                        else f"image.same_process.0.{view}.{render_pass}"
                    )
                    right = (
                        f"image.same_process.1.{view}.{render_pass}"
                        if group == "same"
                        else f"image.fresh_b.0.{view}.{render_pass}"
                        if group == "fresh"
                        else policy["render"]["reference_images"][view + "." + render_pass]
                    )
                    diff_id = f"diff.{group}.{view}.{render_pass}"
                    outputs[diff_id].parent.mkdir(parents=True, exist_ok=True)
                    result = compare(
                        inputs[left],
                        inputs[right],
                        outputs[diff_id],
                        policy["geometry_limits"]["max_image_pixels"],
                    )
                    result.update(
                        {
                            "group": group,
                            "view": view,
                            "pass": render_pass,
                            "left_id": left,
                            "right_id": right,
                            "diff_id": diff_id,
                        }
                    )
                    comparisons.append(result)
        source = read_json(inputs["native.manifest"])
        reference = read_json(inputs[policy["reference_manifest_id"]])
        validate_manifest(source, policy["geometry_limits"])
        validate_manifest(reference, policy["geometry_limits"])
        write_json(
            outputs["native.comparisons"],
            {
                "schema_version": 2,
                "comparisons": comparisons,
                "reference_findings": reference_findings(source, reference),
                "geometry_findings": scene_geometry_findings(source),
                "scope_gaps": source["scope_gaps"],
                "platform": {
                    "blender": bpy.app.version_string,
                    "build": bpy.app.build_hash.decode(),
                    "decoder": "blender-rgba-f32-v1",
                    "execution": "cpu-image-decode",
                },
            },
        )
        return []
    original = inputs["asset"]
    before = sha(original)
    # Only trusted local source is accepted; no OS/network isolation is claimed.
    with tempfile.TemporaryDirectory(prefix="native-fresh-") as directory:
        fresh = Path(directory) / "asset.blend"
        with original.open("rb") as src, fresh.open("xb") as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
        if sha(fresh) != before:
            raise ValueError("fresh path copy is not exact D")
        bpy.ops.wm.open_mainfile(filepath=str(fresh), load_ui=False, use_scripts=False)
        manifest = collect(
            policy["scene"], policy["view_layer"], policy["frame"], limits=policy["geometry_limits"]
        )
        limits = policy["geometry_limits"]
        if (
            len(manifest["objects"]) > limits["max_objects"]
            or sum(len(m["evaluated"]["vertices"]) for m in manifest["meshes"].values())
            > limits["max_vertices"]
            or sum(len(m["evaluated"]["triangles"]) for m in manifest["meshes"].values())
            > limits["max_triangles"]
        ):
            raise ValueError("bounded native profile geometry limit exceeded")
        validate_manifest(manifest, limits)
        stable = sha(original) == before == sha(fresh)
        if operation == "inspect":
            write_json(outputs["native.manifest"], manifest)
            write_json(
                outputs["native.dependencies"],
                {"schema_version": 2, "dependencies": manifest["dependencies"]},
            )
            return inspect_checks(manifest, stable)
        if operation == "reopen":
            source = read_json(inputs["native.manifest"])
            write_json(outputs["native.reopened"], manifest)
            write_json(
                outputs["native.reopen_dependencies"],
                {
                    "schema_version": 2,
                    "dependencies": manifest["dependencies"],
                    "offline_mode": bpy.app.online_access is False,
                    "input_sha256": before,
                    "reopened_sha256": sha(fresh),
                    "fresh_path": str(fresh),
                    "external_dependency_count": sum(
                        not d["packed"] for d in manifest["dependencies"]
                    ),
                },
            )
            return [
                {
                    "id": "r4.reopen.offline_ok",
                    "findings": []
                    if not bpy.app.online_access and stable
                    else [
                        finding("offline_reopen_not_proven", "Offline flag or D digest mismatch")
                    ],
                    "metrics": {},
                },
                {
                    "id": "r4.reopen.dependencies_resolved",
                    "findings": []
                    if all(d["packed"] and d["sha256"] for d in manifest["dependencies"])
                    else [finding("dependency_missing", "Native dependency not packed")],
                    "metrics": {},
                },
                {
                    "id": "r4.reopen.manifest_matches_source",
                    "findings": []
                    if source == manifest
                    else [
                        finding(
                            "reopen_manifest_mismatch", "Authored/evaluated/dependencies changed"
                        )
                    ],
                    "metrics": {},
                },
            ]
        experiment = parameters["experiment"]
        report = render_images(manifest, policy["render"], outputs, experiment)
        report["source_digest_before"] = before
        report["source_digest_after"] = sha(original)
        write_json(outputs["render." + experiment], report)
        if experiment != "same_process":
            return []
        return [
            {
                "id": "r4.visual.scene_not_empty",
                "findings": scene_geometry_findings(manifest),
                "metrics": {},
            },
            {
                "id": "r4.visual.self_determinism",
                "findings": [],
                "metrics": {"measurement_ready": True},
            },
            {
                "id": "r4.visual.platform_key_known",
                "findings": []
                if report["platform"] == policy["render"]["platform"]
                else [finding("unknown_platform", "Observed platform differs from calibration")],
                "metrics": {},
            },
        ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    request = read_request(args.request)
    checks = work(request)
    write_result(
        request,
        checks,
        {
            "pid": str(os.getpid()),
            "blender": bpy.app.version_string,
            "build": bpy.app.build_hash.decode(),
        },
    )


if __name__ == "__main__":
    main()
```

在 M1 `acceptance/contract.py` 的深 schema 验证函数中，替换原有这一行：

```python
require(value["native"] is None, "native worker policy is not implemented in M1")
```

为：

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
```

`native=None` 在 M1 仍能形成明确未接线结果；只有存在完整政策时才接通本包。不要让 None 走原生 dispatch 再崩溃。工具锁的 blender `files` 必须包括本包新脚本；acceptance provenance 同时覆盖新纯 Python 代码。`reference_authority` 是冻结输入 ID，来源说明文件与参考 manifest/图像同属 S；自由文本来源名不能代替文件身份。此包锁 Blender 可执行文件 hash、build 与显式脚本，未声称已经锁住整个 `.app` 目录；M3 另锁它使用的 `io_scene_gltf2` 模块文件。`reference_authority` 是冻结输入 ID，来源说明文件与参考 manifest/图像同属 S；自由文本来源名不能代替文件身份。此包锁 Blender 可执行文件 hash、build 与显式脚本，未声称已经锁住整个 `.app` 目录；M3 另锁它使用的 `io_scene_gltf2` 模块文件。`reference_authority` 是冻结输入 ID，来源说明文件与参考 manifest/图像同属 S；自由文本来源名不能代替文件身份。此包锁 Blender 可执行文件 hash、build 与显式脚本，未声称已经锁住整个 `.app` 目录；M3 另锁它使用的 `io_scene_gltf2` 模块文件。`reference_authority` 是冻结输入 ID，来源说明文件与参考 manifest/图像同属 S；自由文本来源名不能代替文件身份。此包锁 Blender 可执行文件 hash、build 与显式脚本，未声称已经锁住整个 `.app` 目录；M3 另锁它使用的 `io_scene_gltf2` 模块文件。

安全阻断表：coverage、NaN、非法/未完成几何或源字节变化时，controller 不启动依赖这些数据的下游 job，并记录 `blocked_by`。未运行项保持 NotTested，混合实际失败/未完成项的上层状态为 UNVERIFIED；安全的缺件、变换或材质错误仍继续生成诊断，全部完成后为 REJECTED。worker 不以异常冒充已发现坏几何的资产失败。

- [ ] **Step 4: 运行 unit，并用 M1 真实 receiver 驱动 inspector/reopen。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_plan.py tests/unit/test_native_policy.py tests/unit/test_native_checks.py -q
```

预期：文件/检查 ID 无冲突，所有 135 原图和 99 差异输出被展开，reopen 是独立进程/新临时路径，读到的 D 与输入成员实际 hash 相同；错误 attempt/nonce/writer 仍由 M1 的既有 receiver 负例阻断。完整 CLI 驱动命令见 Task 7，不能用手工 result.json 作为本任务真实重开验收。

- [ ] **Step 5: 提交。**

```bash
git add acceptance/native_plan.py acceptance/blender_scripts/native_worker.py acceptance/contract.py tests/unit/test_native_plan.py
git commit -m "feat(acceptance): schedule native workers and exact-byte reopen"
```

### Task 6: controller 复核比较集合、机器门禁与进程身份

**Files:**
- Create: `acceptance/native_results.py`
- Test: `tests/unit/test_native_results.py`

**Interfaces:**
- Consumes: `RunResult.files: dict[id,BoundFile]`、`results: dict[job_id,dict]`、`jobs: tuple[dict,...]`；controller 作业记录包括 `job_id/writer/started/pid/started_at/exit_code/blocked_by/failure_code/error`。
- Produces: `native_results(contract:Contract,run:RunResult) -> (dict[check_id,list[Finding]], dict[gate_id,Gate])`，其中 `Gate(complete:bool,findings:tuple[Finding,...])` 由 `acceptance.decide` 定义。缺门禁、complete=false 或必需失败都会使 v2 技术 summary.success=false，只有 Q 业务签收留在上层。

- [ ] **Step 1: 写缺比较证据不能自确定通过的回归。**

`tests/unit/test_native_results.py`：

```python
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import pytest
from acceptance.native_results import native_results
from acceptance.native_plan import NATIVE_GATES
from acceptance.native_policy import VIEWS, PASSES
from acceptance.primitives import AcceptanceFailure


def result_case(tmp_path):
    digest = hashlib.sha256(b"fixture").hexdigest()
    render = {
        "platform": {"blender": "locked-fixture-platform"},
        "max_abs": {p: 0 for p in PASSES},
        "beauty_hard_gate": False,
        "reference_images": {v + "." + p: f"reference.{v}.{p}" for v in VIEWS for p in PASSES},
    }
    contract = SimpleNamespace(
        raw={
            "native": {"render": render},
            "input": {
                "files": [
                    {"id": fid, "sha256": digest}
                    for fid in ("asset", *render["reference_images"].values())
                ]
            },
        }
    )
    files = {}

    def record(fid, value):
        path = tmp_path / (fid + ".json")
        path.write_text(json.dumps(value))
        files[fid] = SimpleNamespace(path=path, sha256=digest)

    jobs = []
    for experiment in ("same_process", "fresh_a", "fresh_b"):
        records = []
        pid = 100 + len(jobs)
        for repetition in range(2 if experiment == "same_process" else 1):
            for view in VIEWS:
                for render_pass in PASSES:
                    if repetition == 1 and render_pass == "beauty":
                        continue
                    fid = f"image.{experiment}.{repetition}.{view}.{render_pass}"
                    files[fid] = SimpleNamespace(sha256=digest)
                    records.append(
                        {
                            "id": fid,
                            "view": view,
                            "pass": render_pass,
                            "repetition": repetition,
                            "pid": pid,
                            "experiment": experiment,
                            "engine": "BLENDER_EEVEE"
                            if render_pass == "beauty"
                            else "BLENDER_WORKBENCH",
                        }
                    )
        record(
            "render." + experiment,
            {
                "schema_version": 2,
                "platform": render["platform"],
                "settings": render,
                "images": records,
                "source_digest_before": digest,
                "source_digest_after": digest,
            },
        )
        jobs.append(
            {
                "job_id": "native.render." + experiment,
                "started": True,
                "started_at": "2026-09-08T00:00:00+00:00",
                "pid": pid,
            }
        )
    comparisons = []
    for group in ("same", "fresh", "reference"):
        for view in VIEWS:
            for render_pass in PASSES:
                if group == "same" and render_pass == "beauty":
                    continue
                left = (
                    f"image.fresh_a.0.{view}.{render_pass}"
                    if group == "fresh"
                    else f"image.same_process.0.{view}.{render_pass}"
                )
                right = (
                    f"image.same_process.1.{view}.{render_pass}"
                    if group == "same"
                    else f"image.fresh_b.0.{view}.{render_pass}"
                    if group == "fresh"
                    else render["reference_images"][view + "." + render_pass]
                )
                diff = f"diff.{group}.{view}.{render_pass}"
                files[diff] = SimpleNamespace(sha256=digest)
                comparisons.append(
                    {
                        "decoder": "blender-rgba-f32-v1",
                        "size": [1024, 1024],
                        "channels": 4,
                        "precision": "float32",
                        "color_interpretation": "Blender PNG decode, Standard output",
                        "left_bytes_sha256": digest,
                        "right_bytes_sha256": digest,
                        "different_channels": 0,
                        "different_pixels": 0,
                        "max_abs": 0,
                        "left_rgb_energy": 100,
                        "right_rgb_energy": 100,
                        "group": group,
                        "view": view,
                        "pass": render_pass,
                        "left_id": left,
                        "right_id": right,
                        "diff_id": diff,
                    }
                )
    data = {
        "schema_version": 2,
        "comparisons": comparisons,
        "reference_findings": [],
        "geometry_findings": [],
        "scope_gaps": [],
        "platform": {
            "blender": "locked-fixture-platform",
            "build": "fixture-build",
            "decoder": "blender-rgba-f32-v1",
            "execution": "cpu-image-decode",
        },
    }
    record("native.comparisons", data)
    record("native.manifest", {"scope_gaps": []})
    run = SimpleNamespace(
        files=files,
        results={},
        jobs=jobs,
        findings={"r4.visual.self_determinism": (), "r4.visual.scene_not_empty": ()},
    )
    return contract, run, data, record


def test_absent_worker_stays_not_tested():
    contract = SimpleNamespace(raw={"native": {}})
    run = SimpleNamespace(files={}, results={}, jobs=(), findings={})
    findings, gates = native_results(contract, run)
    assert findings == {}
    assert set(gates) == set(NATIVE_GATES)
    assert all(not gate.complete for gate in gates.values())


def test_absent_comparator_cannot_leave_completed_render_check_passed():
    contract = SimpleNamespace(raw={"native": {}})
    run = SimpleNamespace(
        files={}, results={}, jobs=(), findings={"r4.visual.self_determinism": ()}
    )
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.self_determinism"]
    assert all(not gate.complete for gate in gates.values())


def test_exact_measurements_complete_the_frozen_gate(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    findings, gates = native_results(contract, run)
    assert not findings["r4.visual.self_determinism"]
    assert all(gate.complete and not gate.findings for gate in gates.values())


@pytest.mark.parametrize(
    "mutation",
    ["wrong_pair", "missing_pair", "duplicate_pair", "contradiction", "wrong_hash", "wrong_color"],
)
def test_invalid_comparison_cannot_pass_even_if_pixels_match(tmp_path, mutation):
    contract, run, data, record = result_case(tmp_path)
    first = data["comparisons"][0]
    if mutation == "wrong_pair":
        first["right_id"] = first["left_id"]
    elif mutation == "missing_pair":
        data["comparisons"].pop()
    elif mutation == "duplicate_pair":
        data["comparisons"].append(deepcopy(first))
    elif mutation == "contradiction":
        first["different_pixels"] = 1
    elif mutation == "wrong_hash":
        first["left_bytes_sha256"] = "0" * 64
    else:
        first["color_interpretation"] = "arbitrary uncalibrated space"
    record("native.comparisons", data)
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_render_pid_must_match_controller_observation(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    run.jobs[0]["pid"] += 1
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_missing_image_cannot_pass_with_unchanged_report(tmp_path):
    contract, run, _, _ = result_case(tmp_path)
    del run.files["image.same_process.0.bottom.wire"]
    with pytest.raises(AcceptanceFailure):
        native_results(contract, run)


def test_black_wire_is_incomplete_diagnostic_evidence(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    for item in data["comparisons"]:
        if item["pass"] == "wire":
            item["left_rgb_energy"] = item["right_rgb_energy"] = 0
    record("native.comparisons", data)
    findings, gates = native_results(contract, run)
    assert findings["r4.visual.scene_not_empty"]
    assert not gates["native.reference"].complete


def test_observe_only_beauty_never_relaxes_diagnostic_gate(tmp_path):
    contract, run, data, record = result_case(tmp_path)
    beauty = next(
        row for row in data["comparisons"] if row["group"] == "fresh" and row["pass"] == "beauty"
    )
    beauty.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert not gates["native.cross_process"].findings
    clay = next(
        row for row in data["comparisons"] if row["group"] == "fresh" and row["pass"] == "clay"
    )
    clay.update(max_abs=0.1, different_pixels=1, different_channels=1)
    record("native.comparisons", data)
    _, gates = native_results(contract, run)
    assert gates["native.cross_process"].findings
```

- [ ] **Step 2: 确认新模块不存在时失败。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_results.py -q
```

- [ ] **Step 3: 写 controller 复核代码。** worker 的比较 JSON 只传测量，不传 accepted/effective/disposition；此适配器核对具体左右输入 ID、实际字节 hash、解码格式、完整图对集合与 controller 记录的进程。进程身份是 `(job_id, started_at, pid)`，PID 数值可以被操作系统重用。

`acceptance/native_results.py`：

```python
from __future__ import annotations
import math
from pathlib import Path
from typing import Any
from acceptance.contract import Contract, thaw
from acceptance.decide import Finding, Gate
from acceptance.native_policy import VIEWS, PASSES
from acceptance.native_plan import NATIVE_GATES
from acceptance.strict_json import strict_json_loads
from acceptance.primitives import AcceptanceFailure


def load(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        raw = stream.read(64 * 1024 * 1024 + 1)
    if len(raw) > 64 * 1024 * 1024:
        raise AcceptanceFailure("tool_output_invalid", "Native JSON exceeds bound")
    value = strict_json_loads(raw)
    if not isinstance(value, dict):
        raise AcceptanceFailure("tool_output_invalid", "Native JSON object required")
    return value


def native_results(
    contract: Contract, run: Any
) -> tuple[dict[str, list[Finding]], dict[str, Gate]]:
    policy = thaw(contract.raw["native"])
    gates = {key: Gate(False, ()) for key in NATIVE_GATES}
    findings: dict[str, list[Finding]] = {}
    if "r4.visual.self_determinism" in run.findings:
        findings["r4.visual.self_determinism"] = [
            Finding("repeat_unverified", "error", detail="Comparison evidence unavailable")
        ]
    if "native.manifest" in run.files:
        manifest = load(run.files["native.manifest"].path)
        gaps = manifest["scope_gaps"]
        gates["native.scope_supported"] = Gate(
            not gaps, tuple(Finding("capability_gap", "error", detail=x) for x in gaps)
        )
    if "native.comparisons" not in run.files:
        return findings, gates
    data = load(run.files["native.comparisons"].path)
    if (
        set(data)
        != {
            "schema_version",
            "comparisons",
            "reference_findings",
            "geometry_findings",
            "scope_gaps",
            "platform",
        }
        or data["schema_version"] != 2
    ):
        raise AcceptanceFailure("tool_output_invalid", "Closed comparison schema mismatch")
    expected = {
        (g, v, p)
        for g in ("same", "fresh", "reference")
        for v in VIEWS
        for p in PASSES
        if not (g == "same" and p == "beauty")
    }
    actual = []
    same: list[Finding] = []
    fresh: list[Finding] = []
    reference: list[Finding] = []
    input_hashes = {row["id"]: row["sha256"] for row in contract.raw["input"]["files"]}
    input_hashes.update({fid: item.sha256 for fid, item in run.files.items()})
    fields = {
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
        "group",
        "view",
        "pass",
        "left_id",
        "right_id",
        "diff_id",
        "left_rgb_energy",
        "right_rgb_energy",
    }
    for item in data["comparisons"]:
        if set(item) != fields:
            raise AcceptanceFailure("tool_output_invalid", "Comparison row fields mismatch")
        key = (item["group"], item["view"], item["pass"])
        actual.append(key)
        if (
            key not in expected
            or item["decoder"] != "blender-rgba-f32-v1"
            or item["precision"] != "float32"
            or item["channels"] != 4
            or item["color_interpretation"] != "Blender PNG decode, Standard output"
            or item["size"] != [1024, 1024]
        ):
            raise AcceptanceFailure("tool_output_invalid", "Comparison identity/format mismatch")
        for metric in ("different_channels", "different_pixels"):
            if (
                type(item[metric]) is not int
                or item[metric] < 0
                or item[metric] > (4 if metric == "different_channels" else 1) * 1024 * 1024
            ):
                raise AcceptanceFailure("tool_output_invalid", "Comparison count malformed")
        if (
            type(item["max_abs"]) not in (int, float)
            or not math.isfinite(item["max_abs"])
            or not 0 <= item["max_abs"] <= 1
        ):
            raise AcceptanceFailure("tool_output_invalid", "Comparison metric malformed")
        group, view, render_pass = key
        expected_left = (
            f"image.fresh_a.0.{view}.{render_pass}"
            if group == "fresh"
            else f"image.same_process.0.{view}.{render_pass}"
        )
        expected_right = (
            f"image.same_process.1.{view}.{render_pass}"
            if group == "same"
            else f"image.fresh_b.0.{view}.{render_pass}"
            if group == "fresh"
            else policy["render"]["reference_images"][view + "." + render_pass]
        )
        if (item["left_id"], item["right_id"], item["diff_id"]) != (
            expected_left,
            expected_right,
            f"diff.{group}.{view}.{render_pass}",
        ):
            raise AcceptanceFailure("tool_output_invalid", "Comparison paired the wrong artifacts")
        if (item["max_abs"] == 0) != (item["different_channels"] == 0) or not item[
            "different_pixels"
        ] <= item["different_channels"] <= 4 * item["different_pixels"]:
            raise AcceptanceFailure(
                "tool_output_invalid", "Comparison metrics contradict one another"
            )
        for side in ("left", "right"):
            energy = item[side + "_rgb_energy"]
            if (
                type(energy) not in (int, float)
                or not math.isfinite(energy)
                or not 0 <= energy <= 3 * 1024 * 1024
            ):
                raise AcceptanceFailure("tool_output_invalid", "Decoded RGB energy malformed")
        for side in ("left", "right"):
            if (
                item[side + "_id"] not in input_hashes
                or item[side + "_bytes_sha256"] != input_hashes[item[side + "_id"]]
            ):
                raise AcceptanceFailure(
                    "tool_output_invalid", "Comparison input byte identity mismatch"
                )
        if item["diff_id"] not in run.files:
            raise AcceptanceFailure("tool_output_invalid", "Required difference image missing")
        hard = item["pass"] != "beauty" or policy["render"]["beauty_hard_gate"]
        if hard and item["max_abs"] > policy["render"]["max_abs"][item["pass"]]:
            target = (
                same
                if item["group"] == "same"
                else fresh
                if item["group"] == "fresh"
                else reference
            )
            target.append(
                Finding("pixel_mismatch", "error", detail=repr(key) + ":" + str(item["max_abs"]))
            )
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise AcceptanceFailure(
            "tool_output_invalid", "Comparison pair set differs from frozen plan"
        )
    platform_complete = True
    for experiment in ("same_process", "fresh_a", "fresh_b"):
        report = load(run.files["render." + experiment].path)
        if (
            set(report)
            != {
                "schema_version",
                "platform",
                "settings",
                "images",
                "source_digest_before",
                "source_digest_after",
            }
            or report["schema_version"] != 2
            or report["settings"] != policy["render"]
        ):
            raise AcceptanceFailure("tool_output_invalid", "Render report schema/settings mismatch")
        if report["platform"] != policy["render"]["platform"]:
            platform_complete = False
        if (
            report["source_digest_before"] != input_hashes["asset"]
            or report["source_digest_after"] != input_hashes["asset"]
        ):
            raise AcceptanceFailure("toolchain_mismatch", "Source changed during render")
        ids = [item["id"] for item in report["images"]]
        expected_ids = {
            f"image.{experiment}.{r}.{v}.{p}"
            for r in range(2 if experiment == "same_process" else 1)
            for v in VIEWS
            for p in PASSES
            if not (r == 1 and p == "beauty")
        }
        if (
            len(ids) != len(set(ids))
            or set(ids) != expected_ids
            or any(fid not in run.files for fid in ids)
        ):
            raise AcceptanceFailure(
                "tool_output_invalid", "Render report does not cover full image set"
            )
        process_observation = next(
            row for row in run.jobs if row["job_id"] == "native.render." + experiment
        )
        if (
            not process_observation["started"]
            or not process_observation["started_at"]
            or any(item["pid"] != process_observation["pid"] for item in report["images"])
        ):
            raise AcceptanceFailure("tool_output_invalid", "Images do not bind to observed process")
        for image in report["images"]:
            if (
                set(image) != {"id", "view", "pass", "repetition", "pid", "experiment", "engine"}
                or image["experiment"] != experiment
                or image["id"]
                != f"image.{experiment}.{image['repetition']}.{image['view']}.{image['pass']}"
                or image["engine"]
                != ("BLENDER_EEVEE" if image["pass"] == "beauty" else "BLENDER_WORKBENCH")
            ):
                raise AcceptanceFailure(
                    "tool_output_invalid", "Image identity/engine metadata mismatch"
                )
    for raw in data["reference_findings"]:
        if (
            set(raw) != {"code", "severity", "pointer", "detail"}
            or raw["severity"] != "error"
            or not isinstance(raw["code"], str)
            or not isinstance(raw["detail"], str)
            or raw["pointer"] is not None
        ):
            raise AcceptanceFailure("tool_output_invalid", "Reference finding malformed")
        reference.append(Finding(**raw))
    if "r4.visual.self_determinism" not in run.findings:
        raise AcceptanceFailure(
            "tool_output_invalid", "Comparison has no completed source render writer"
        )
    for render_pass in ("clay", "silhouette", "wire"):
        source_energy = sum(
            item["left_rgb_energy"]
            for item in data["comparisons"]
            if item["group"] == "same" and item["pass"] == render_pass
        )
        reference_energy = sum(
            item["right_rgb_energy"]
            for item in data["comparisons"]
            if item["group"] == "reference" and item["pass"] == render_pass
        )
        if source_energy <= 0:
            findings.setdefault("r4.visual.scene_not_empty", []).append(
                Finding("diagnostic_render_empty", "error", detail=render_pass)
            )
        if reference_energy <= 0:
            platform_complete = False
            reference.append(Finding("reference_diagnostic_empty", "error", detail=render_pass))
    findings["r4.visual.all_views_rendered"] = []
    findings["r4.visual.self_determinism"] = same
    gates["native.cross_process"] = Gate(platform_complete, tuple(fresh))
    gates["native.reference"] = Gate(platform_complete, tuple(reference))
    return findings, gates
```

- [ ] **Step 4: 运行 unit 与 Task 7 的真实混淆/缺图负例。**

```bash
"$PYTHON_BIN" -m pytest tests/unit/test_native_results.py tests/unit/test_native_plan.py -q
```

预期：worker 未完成时检查保持 NotTested，不能通过 coordinator findings 伪造已执行；source render 已完成而 comparison 缺失时 self_determinism 不得空 findings Pass。36 beauty 比较记录仍被解析/核对/保留。锁定政策规定它是观察项时，不能把其非零误报为 hard gate；锁定政策要求硬门时也不得在失败后降级。将 left/right 交换到错误但像素恰好相同的文件、删一张图、删一个 pair、重复 pair、伪造 pid、比较色彩语义、互相矛盾的指标或全黑诊断均不能通过。前景检测按每个诊断 pass 的九视角合计 RGB 能量执行，允许平面从个别边缘视角没有面积；不能要求每张图都非黑。

- [ ] **Step 5: 提交。**

```bash
git add acceptance/native_results.py tests/unit/test_native_results.py
git commit -m "feat(acceptance): bind native comparisons to evidence and process identity"
```

### Task 7: 真实 CLI、签收/交付与完整原生门禁

**Files:**
- Create: `acceptance/native_run.py`
- Create: `tests/integration/asset_runtime_support.py`
- Create: `tests/integration/test_asset_native.py`
- Modify: `scripts/asset_accept.py` 的 `dispatch_run()`
- Modify: `pyproject.toml` 的 Blender-only mypy override
- Modify: `docs/validation.md` 与 `docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md`

**Interfaces:**
- Consumes: M1 `verify_bundle()`、`run_jobs(...,input_files=...)`、`finalize_run()`；`run_jobs` 实测 R0/R1，native adapter 不重复造这些检查。
- Produces: `run_native(contract_path:Path,source_root:Path,evidence_root:Path,scratch_root:Path)->dict`；共享测试 `AssetCase`、`prepare_native_case()`、`write_case()`、`run_case()`，M3 可复用真实冻结/参考流程。

- [ ] **Step 1: 加入以下完整真实集成测试与夹具构造器。** 默认 unit 不拉起 Blender；显式门禁不得以 skipped 当成功。测试 reviewer 只是测试授权，不构成真实资产人工签收。

`tests/integration/asset_runtime_support.py`：

```python
from __future__ import annotations
import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from acceptance.input_bundle import freeze_bundle, source_digest
from acceptance.native_plan import native_commands
from acceptance.native_policy import VIEWS, PASSES
from tests.unit.asset_v2_support import file_lock, valid_document

REPO = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AssetCase:
    root: Path
    contract_path: Path
    source_root: Path
    evidence_root: Path
    scratch_root: Path
    document: dict[str, Any]


def blender_script(blender: Path, script: Path, *arguments: str) -> None:
    completed = subprocess.run(
        (
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--offline-mode",
            "--python-exit-code",
            "1",
            "--python",
            str(script),
            "--",
            *arguments,
        ),
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=900,
    )
    if completed.returncode:
        raise AssertionError(completed.stdout + "\n" + completed.stderr)


def prepare_calibration(blender: Path, root: Path, fixture_name: str = "good") -> Path:
    root.mkdir(parents=True)
    blender_script(blender, REPO / "tests/fixtures/asset_native.py", str(root / "fixtures"))
    if fixture_name != "good":
        shutil.copyfile(root / "fixtures" / f"{fixture_name}.blend", root / "fixtures/good.blend")
        shutil.copyfile(
            root / "fixtures" / f"{fixture_name}.json", root / "fixtures/reference.json"
        )
    for experiment in ("same_process", "fresh_a", "fresh_b", "compare"):
        blender_script(
            blender, REPO / "tests/fixtures/native_visual_probe.py", str(root), experiment
        )
    return root


def prepare_native_case(
    blender: Path, tmp_path: Path, fixture_name: str, *, calibration_root: Path | None = None
) -> AssetCase:
    tmp_path.mkdir(parents=True, exist_ok=True)
    if calibration_root is None:
        calibration_root = prepare_calibration(blender, tmp_path / "calibration")
    fixture_root = tmp_path / "policy-fixture"
    fixture_root.mkdir()
    document = valid_document(fixture_root)
    candidate = tmp_path / "candidate.blend"
    shutil.copyfile(calibration_root / "fixtures" / f"{fixture_name}.blend", candidate)
    authority = tmp_path / "reference-authority.json"
    authority.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "authority": "trusted-native-fixture-v1",
                "fixture_generator_sha256": hashlib.sha256(
                    (REPO / "tests/fixtures/asset_native.py").read_bytes()
                ).hexdigest(),
                "visual_generator_sha256": hashlib.sha256(
                    (REPO / "tests/fixtures/native_visual_probe.py").read_bytes()
                ).hexdigest(),
                "calibration_comparisons_sha256": hashlib.sha256(
                    (calibration_root / "comparisons.json").read_bytes()
                ).hexdigest(),
                "production_human_approval": False,
            },
            sort_keys=True,
        )
    )
    sources = [
        {"id": "asset", "path": "asset.blend", "source": str(candidate)},
        {
            "id": "native.reference",
            "path": "reference/manifest.json",
            "source": str(calibration_root / "fixtures/reference.json"),
        },
        {"id": "reference.authority", "path": "reference/authority.json", "source": str(authority)},
    ]
    for view in VIEWS:
        for render_pass in PASSES:
            sources.append(
                {
                    "id": f"reference.{view}.{render_pass}",
                    "path": f"reference/{view}-{render_pass}.png",
                    "source": str(
                        calibration_root / "same_process" / f"0-{view}-{render_pass}.png"
                    ),
                }
            )
    source_root = tmp_path / "bundle"
    rows = freeze_bundle(
        sources,
        source_root,
        max_files=1000,
        max_file_bytes=512 * 1024 * 1024,
        max_total_bytes=2 * 1024 * 1024 * 1024,
    )
    document["input"] = {"main": "asset", "sha256": source_digest(rows), "files": rows}
    report = json.loads((calibration_root / "same_process/render.json").read_text())
    document["native"] = {
        "scene": "Scene",
        "view_layer": "ViewLayer",
        "frame": 1,
        "support_profile": "native-static-v1",
        "reference_manifest_id": "native.reference",
        "reference_authority": "reference.authority",
        "geometry_limits": {
            "max_objects": 1000,
            "max_vertices": 1000000,
            "max_triangles": 2000000,
            "max_image_pixels": 1048576,
        },
        "render": {
            "resolution": 1024,
            "views": list(VIEWS),
            "reference_center": [0, 0, 0],
            "reference_radius": 2,
            "beauty_hard_gate": False,
            "platform": report["platform"],
            "max_abs": {p: 0 for p in PASSES},
            "reference_images": {v + "." + p: f"reference.{v}.{p}" for v in VIEWS for p in PASSES},
        },
    }
    document["tools"] = [tool for tool in document["tools"] if tool["id"] != "blender"]
    document["tools"].append(
        {
            "id": "blender",
            "path": str(blender.resolve()),
            "version": "Blender 5.2.0 LTS",
            "sha256": file_lock(blender)["sha256"],
            "files": [
                file_lock(REPO / "acceptance/blender_scripts" / name)
                for name in ("native_worker.py", "native_collect.py", "native_render.py")
            ],
        }
    )
    document["limits"].update(
        {
            "timeout_seconds": {writer: 600 for writer in native_commands(blender, REPO)},
            "cpu_seconds": 1200,
            "rss_bytes": 6 * 1024**3,
            "open_files": 256,
            "log_bytes": 16 * 1024 * 1024,
            "file_size_bytes": 512 * 1024 * 1024,
        }
    )
    document["budget"] = {
        "max_files": 1000,
        "max_file_bytes": 512 * 1024 * 1024,
        "max_total_bytes": 2 * 1024**3,
        "max_result_bytes": 4 * 1024 * 1024,
    }
    document["review"] = {
        "required": True,
        "reviewer_ids": ["fixture-reviewer"],
        "required_image_ids": [
            "image.same_process.0.front.beauty",
            "image.same_process.0.bottom.clay",
        ],
        "reason": "Test-only known fixture review; never authorizes production artwork",
    }
    case = AssetCase(
        tmp_path,
        tmp_path / "contract.json",
        source_root,
        tmp_path / "evidence",
        tmp_path / "scratch",
        document,
    )
    # Demonstrates that the worker only reads the frozen bundle, never this origin path.
    candidate.write_bytes(b"origin replaced after freeze; not a Blender file")
    write_case(case)
    return case


def write_case(case: AssetCase) -> None:
    case.contract_path.write_text(
        json.dumps(case.document, ensure_ascii=False, sort_keys=True, allow_nan=False)
    )


def run_case(case: AssetCase) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        (
            sys.executable,
            str(REPO / "scripts/asset_accept.py"),
            "run",
            "--contract",
            str(case.contract_path),
            "--input-root",
            str(case.source_root),
            "--evidence-root",
            str(case.evidence_root),
            "--scratch-root",
            str(case.scratch_root),
        ),
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=900,
    )
    try:
        document = json.loads(completed.stdout)
    except ValueError as exc:
        raise AssertionError(completed.stdout + "\n" + completed.stderr) from exc
    return completed.returncode, document
```

`tests/integration/test_asset_native.py`：

```python
from __future__ import annotations
import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from tests.integration.asset_runtime_support import (
    REPO,
    prepare_calibration,
    prepare_native_case,
    run_case,
    write_case,
)

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_ASSET_NATIVE") != "1",
        reason="Explicit native integration gate; unit tests never launch Blender",
    ),
    pytest.mark.timeout(900),
]
BLENDER = Path(os.environ.get("BLENDER_BIN", "/Applications/Blender.app/Contents/MacOS/Blender"))


@pytest.fixture(scope="module")
def calibration(tmp_path_factory):
    return prepare_calibration(BLENDER, tmp_path_factory.mktemp("native-calibration") / "run")


@pytest.mark.parametrize(
    "fixture_name,state",
    [
        ("good", "NEEDS_REVIEW"),
        ("missing_bottom", "REJECTED"),
        ("zero_scale", "REJECTED"),
        ("same_counts_surface", "REJECTED"),
        ("transform_wrong", "REJECTED"),
        ("material_missing", "REJECTED"),
        ("material_changed", "REJECTED"),
        ("invalid_face", "UNVERIFIED"),
        ("nan", "UNVERIFIED"),
        ("curve", "UNVERIFIED"),
        ("missing_dependency", "UNVERIFIED"),
        ("reserved_material", "REJECTED"),
    ],
)
def test_native_positive_and_actual_bad_assets(tmp_path, calibration, fixture_name, state):
    case = prepare_native_case(BLENDER, tmp_path, fixture_name, calibration_root=calibration)
    exit_code, result = run_case(case)
    assert exit_code == 1 and result["state"] == state
    summary = json.loads((case.evidence_root / "summary.json").read_text())
    assert summary["success"] is (fixture_name == "good")
    if fixture_name in {"invalid_face", "nan"}:
        assert summary["failure_code"] == "check_failed"
    if fixture_name == "good":
        assert not (case.evidence_root / "completion.json").exists()
        assert not (case.evidence_root / "review.json").exists()
        images = list((case.evidence_root / "payload").rglob("image.*.png"))
        diffs = list((case.evidence_root / "payload").rglob("diff.*.png"))
        assert len(images) == 135 and len(diffs) == 99
        assert (
            result["bindings"]["D"]
            == hashlib.sha256((case.source_root / "asset.blend").read_bytes()).hexdigest()
        )


@pytest.mark.parametrize("fixture_name", ["bevel", "triangulate", "packed_image", "nested_custom"])
def test_each_supported_capability_has_its_own_complete_positive(tmp_path, fixture_name):
    reference = prepare_calibration(BLENDER, tmp_path / "reference", fixture_name)
    case = prepare_native_case(BLENDER, tmp_path / "case", fixture_name, calibration_root=reference)
    exit_code, result = run_case(case)
    assert exit_code == 1 and result["state"] == "NEEDS_REVIEW"
    assert json.loads((case.evidence_root / "summary.json").read_text())["success"] is True


def fixture_review(case, result):
    images = []
    for fid in case.document["review"]["required_image_ids"]:
        path = case.evidence_root / "payload/native.render.same_process/images" / f"{fid}.png"
        images.append({"id": fid, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {
        "schema_version": 2,
        "bindings": result["bindings"],
        "records": [
            {
                "reviewer_id": "fixture-reviewer",
                "outcome": "approved",
                "reviewed_images": images,
                "reviewed_at": datetime.datetime.now(datetime.UTC).isoformat(),
                "note": "Test-only fixture authorization. This is not a human approval of production artwork.",
            }
        ],
    }


def call_cli(*args):
    return subprocess.run(
        (sys.executable, str(REPO / "scripts/asset_accept.py"), *map(str, args)),
        cwd=REPO,
        text=True,
        capture_output=True,
        timeout=900,
    )


def test_review_and_delivery_bind_exact_frozen_D(tmp_path, calibration):
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    _, result = run_case(case)
    review = case.root / "fixture-review.json"
    review.write_text(json.dumps(fixture_review(case, result)))
    before = (case.evidence_root / "summary.json").read_bytes()
    finished = call_cli(
        "review",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--review",
        review,
    )
    assert finished.returncode == 0, finished.stderr
    assert json.loads(finished.stdout)["state"] in {"SHIP", "SHIP_WITH_NOTES"}
    assert (case.evidence_root / "summary.json").read_bytes() == before
    assert (case.evidence_root / "review.json").is_file() and (
        case.evidence_root / "completion.json"
    ).is_file()
    wrong = case.root / "changed-delivery.blend"
    wrong.write_bytes((case.source_root / "asset.blend").read_bytes() + b"changed")
    destination = case.root / "rejected-delivery.blend"
    rejected = call_cli(
        "deliver",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        wrong,
        "--destination",
        destination,
    )
    assert rejected.returncode != 0 and not destination.exists()
    destination = case.root / "accepted-delivery.blend"
    delivered = call_cli(
        "deliver",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--destination",
        destination,
    )
    assert delivered.returncode == 0, delivered.stderr
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == result["bindings"]["D"]
    receipt = json.loads(delivered.stdout)
    assert receipt["D"] == result["bindings"]["D"]
    assert (
        receipt["T"]
        == hashlib.sha256((case.evidence_root / "completion.json").read_bytes()).hexdigest()
    )


def test_missing_image_cannot_be_signed_off(tmp_path, calibration):
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    _, result = run_case(case)
    review = case.root / "fixture-review.json"
    review.write_text(json.dumps(fixture_review(case, result)))
    image = (
        case.evidence_root
        / "payload/native.render.same_process/images/image.same_process.0.bottom.wire.png"
    )
    image.unlink()
    rejected = call_cli(
        "review",
        "--evidence-root",
        case.evidence_root,
        "--delivery",
        case.source_root / "asset.blend",
        "--review",
        review,
    )
    assert rejected.returncode != 0 and not (case.evidence_root / "completion.json").exists()


def test_uncalibrated_platform_remains_unverified(tmp_path, calibration):
    case = prepare_native_case(BLENDER, tmp_path, "good", calibration_root=calibration)
    case.document["native"]["render"]["platform"]["gpu"] = "unrecognized-fixture-platform"
    write_case(case)
    _, result = run_case(case)
    assert result["state"] == "UNVERIFIED"
    assert json.loads((case.evidence_root / "summary.json").read_text())["success"] is False
```

- [ ] **Step 2: 确认未接线时完整好资产失败关闭。**

```bash
NATIVE_FAILED_PROBE=$(mktemp -d /tmp/asset-native-m2-red.XXXXXX)
RUN_ASSET_NATIVE=1 "$PYTHON_BIN" -m pytest tests/integration/test_asset_native.py -q --basetemp "$NATIVE_FAILED_PROBE/pytest"
```

每次使用新目录，避免 pytest 清理旧证据。预期未接线版本无法技术通过；不降低断言。

- [ ] **Step 3: 接入原生 dispatch。**

`acceptance/native_run.py`：

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
from acceptance.native_plan import build_native_plan, native_commands, NATIVE_GATES
from acceptance.native_results import native_results
from acceptance.primitives import AcceptanceFailure


def run_native(
    contract_path: Path, source_root: Path, evidence_root: Path, scratch_root: Path
) -> dict[str, Any]:
    repository = Path(__file__).resolve().parents[1]
    contract = load_contract(contract_path, candidate_root=source_root)
    plan = build_native_plan(contract)
    inputs = verify_bundle(
        source_root,
        thaw(contract.raw["input"]["files"]),
        max_file_bytes=contract.raw["budget"]["max_file_bytes"],
    )
    blender = Path(next(tool["path"] for tool in contract.raw["tools"] if tool["id"] == "blender"))
    run = run_jobs(
        contract,
        plan,
        run_id=uuid4().hex,
        input_files=inputs,
        scratch_root=scratch_root,
        evidence_root=evidence_root,
        commands=native_commands(blender, repository),
    )
    try:
        findings, gates = native_results(contract, run)
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
        error = Finding("native_evidence_unverified", "error", detail=str(exc))
        findings = {}
        if "r4.visual.self_determinism" in run.findings:
            findings["r4.visual.self_determinism"] = [error]
        gates = {key: Gate(False, (error,)) for key in NATIVE_GATES}
    completion: dict[str, Any] = finalize_run(
        contract,
        plan,
        run,
        contract_path=contract_path,
        source_root=source_root,
        evidence_root=evidence_root,
        delivery=inputs[contract.raw["input"]["main"]],
        coordinator_findings=findings,
        gates=gates,
    )
    return completion
```

M1 `scripts/asset_accept.py` 的 `dispatch_run(contract_path,source_root,evidence_root,scratch_root)` 在 `load_contract` 后加入：

```python
if contract.artifact_kind == "blend_native" and contract.raw["native"] is not None:
    from acceptance.native_run import run_native

    return run_native(contract_path, source_root, evidence_root, scratch_root)
```

`pyproject.toml` 为仅存在于 Blender 内置 Python 的外部模块追加缺少存根配置。全部 `acceptance` 模块仍走 strict mypy，不关闭新脚本的错误检查：

```toml
[[tool.mypy.overrides]]
module = ["gpu", "gpu.*", "mathutils", "mathutils.*"]
ignore_missing_imports = true
```

- [ ] **Step 4: 在新目录执行完整端到端测试。**

```bash
export NATIVE_E2E="$(mktemp -d /tmp/asset-native-m2-e2e.XXXXXX)"
RUN_ASSET_NATIVE=1 "$PYTHON_BIN" -m pytest tests/integration/test_asset_native.py -q --basetemp "$NATIVE_E2E/pytest"
```

预期所有好资产技术通过；未签收时 `NEEDS_REVIEW` 且无 Q/T；真实缺件、变换、表面/材质丢失拒收；NaN/非法拓扑/未支持类型保留已发现问题和 blocked_by，未完成项令上层 UNVERIFIED；图片缺失或 D 验后变化不能交付。每个支持 modifier/packed-image 都有自己的可信正向参考，不以无 modifier 参考冒充它的质量线。

将以下门禁说明写入 `docs/validation.md` 的资产验收段，并在 V5 能力表把 M2 标为 implemented-and-enforced 的条件绑定到本门禁：

```markdown
原生资产 M2 门禁使用 `RUN_ASSET_NATIVE=1 .venv/bin/python -m pytest tests/integration/test_asset_native.py`，证据必须位于仓库外新目录。报告 24 个现有适用检查、固定原生 gates、135 原图、99 比较/差异图、fresh reopen 与真实 Q/T/D；未签收只报告 NEEDS_REVIEW。此门禁不代表 Phase 0 或 RELEASE 通过，未支持实例/曲线/动画仍为 UNVERIFIED。
```

- [ ] **Step 5: 运行仓库交付检查并提交。**

```bash
bash scripts/checks.sh
graft build .
graft check .
git add acceptance/native_run.py tests/integration/asset_runtime_support.py tests/integration/test_asset_native.py scripts/asset_accept.py pyproject.toml docs/validation.md docs/acceptance/blender_mcp_skill_acceptance_optimized_v5.md
git commit -m "feat(acceptance): enforce complete native asset delivery gate"
```

预期 `ALL CHECKS PASSED`、Graft build/check 退出 0。修改后只重跑受影响检查；正式 Phase 0 的 clean-tree 条件不是普通原生资产运行的额外门禁。所有 runtime 代码步骤完成后才能把本计划中的能力称为已实现。


## 计划编写期核验记录（不是已实施声明）

- 2026-09-08，在仓库外提取本计划代码，27 个 M2 unit 通过；八个新增 runtime 模块经过 strict mypy，Blender 外部 API 仅配置缺少存根，不关闭新模块错误检查。上游 core 接口使用同批 core-v2 计划原型。后续实际落库仍须执行本文全部门禁。
- Blender `5.2.0 LTS / fbe6228777e7` 实际生成九视角 135 原图；固定 wire 后的 27 同进程、36 跨进程对共 63 对全部解码像素相同，比较共 14.923 秒。此前校准曾观察到一个 beauty 视角非零，故冻结前选定 beauty 只观察政策；本轮零差异不能扩大成 EEVEE 普遍确定性承诺。
- 缺底板坏资产在 bottom 的 beauty/clay/silhouette 可与好资产像素相同，真实全边 wire 检出 3,346 个不同像素，`max_abs=0.9843137860298157`；因此不能用有限视图一致替代实际几何、材质和可信 reference 对账。全黑 wire 不能进入确定性证据。
- 已实际生成 16 种原生 fixture manifest，包括 NaN、非法面、缺材质、零缩放、缺底板、相同数量不同表面、变换偏移、材质变更、嵌套自定义属性、保留前缀、外部缺图、范围外曲线以及支持的 TRIANGULATE/BEVEL/packed image。NaN 被记录为 null 与具体 invalid_numbers，保持严格 JSON；原始 mesh 不被 validate 修复。
- 这些结果验证计划内算法、支持边界与脚本可执行性。M2 实际 CLI 全套完成、真实业务 reviewer 签收、仓库全量检查和正式 Phase 0 均不得由本段推导为通过。
