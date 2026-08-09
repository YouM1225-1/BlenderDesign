# Official Blender MCP Modeling Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在隔离的 Blender 5.2.0 GUI 和 scratch fixtures 中完成风格化台灯建模，实测 Blender Lab 官方 MCP 的全部 26 个工具，并形成含逐阶段耗时、错误与根因的可信审计报告。

**Architecture:** 使用当前已证明为未保存、未修改 factory-startup 场景的单一 Blender GUI 作为隔离写入目标；用 `/tmp/bcx-official-mcp-modeling-20260810` 保存可丢弃的外部 library、CLI fixture 和复制后的渲染证据。三个结构化 `execute_blender_code` payload 分阶段创建模型，随后以 GUI、CLI、docs、navigation、screenshot、render 六类调用覆盖 26 个唯一工具。原始记录保存在忽略目录，提交的 audit 只保存脱敏结果、耗时、错误和 artifact hashes。

**Tech Stack:** Blender 5.2 Python API、Blender Lab official MCP 1.0.0、MCP SDK `>=1.2.0,<2`、Python 3.13、Markdown、Git。

## Global Constraints

- 技术产品版本保持 `0.1.0`；不得修改产品版本源。
- Blender 兼容下限是 `>=5.2`，本次唯一实测基线是 `5.2.0`、macOS arm64。
- 只使用官方 `blender` MCP 和官方 `mcp` Extension；不得安装、启用或调用 `blender-codex` 自研链路。
- 官方 source pin 保持 `4309a39646e644261624bfcd2bca669b343b7621`，MCP SDK 保持 `mcp[cli]>=1.2.0,<2` 与 Python `3.13`。
- 当前 catalog 必须恰好包含 26 个唯一工具；每个工具至少有一个可判定 outcome。
- 只修改 factory-startup 的三个已确认对象与 `MCP_Lamp_Isolated` collection；不打开、保存、覆盖或清理用户 `.blend`。
- 所有 fixture 位于 `/tmp/bcx-official-mcp-modeling-20260810`；若该目录预先存在则停止，不递归删除。
- 官方 render 工具的真实输出必须位于 `bpy.app.tempdir/blender_mcp`；验证后才复制到 run root，不能把官方 scratch 重定位误报为失败。
- 不提交 `.blend`、PNG、完整 Codex config、用户路径或隐私场景内容。
- 不修改冻结的 `docs/install.md`、ROADMAP、历史 audit/evidence/attestation、已批准 Phase 0 Plan。
- 每项实测记录 wall-clock；Blender 脚本内部时间单独记录，二者不得混称。
- 同一可恢复工具最多重试一次；第二次失败保留证据并进入根因分析。

---

### Task 1: Isolated run root, fixtures, and preflight evidence

**Files:**
- Create: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Create ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/run-report.md`
- Create runtime: `/tmp/bcx-official-mcp-modeling-20260810/library_source.blend`
- Create runtime: `/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend`

**Interfaces:**
- Consumes: installed official MCP entry `blender`, Blender GUI listener `127.0.0.1:9876`, source pin and config proven by the official install work.
- Produces: exact `RUN_ROOT`, ordinary `library_source.blend` and `lamp_fixture.blend`, initial audit metadata, and a preflight verdict consumed by Tasks 2–4.

- [ ] **Step 1: Verify the immutable starting state**

Run:

```bash
set -euo pipefail
cd /Users/yeminjie/Documents/BlenderDesign/.worktrees/official-blender-mcp-install
test "$(git branch --show-current)" = codex/official-blender-mcp-install
test -z "$(git status --porcelain=v1 --untracked-files=all)"
test "$(git -C /Users/yeminjie/blender_mcp rev-parse HEAD)" = 4309a39646e644261624bfcd2bca669b343b7621
test -z "$(git -C /Users/yeminjie/blender_mcp status --porcelain=v1 --untracked-files=all)"
test ! -e /Users/yeminjie/blender_mcp/uv.lock
test "$(pgrep -x Blender | wc -l | tr -d ' ')" = 1
/usr/sbin/lsof -nP -iTCP:9876 -sTCP:LISTEN | grep '127.0.0.1:9876'
```

Expected: all commands exit `0`, Git worktrees are clean, and exactly one Blender process owns the loopback listener.

Then call these read-only tools and record their returned `Wall time`:

```text
mcp__blender__get_blendfile_summary_path_info {}
mcp__blender__get_objects_summary {}
mcp__blender__get_screenshot_of_window_as_json {}
```

Expected: `filepath=""`, `is_saved=false`, `is_dirty=false`; objects are exactly `Camera`, `Cube`, `Light`; workspace contains a `VIEW_3D` area. If any value differs, stop before fixture or modeling writes.

- [ ] **Step 2: Create the protected run directories**

Run:

```bash
set -euo pipefail
RUN_ROOT=/tmp/bcx-official-mcp-modeling-20260810
AUDIT_RUN=.superpowers/sdd/modeling-runs/run-20260810-01
test ! -e "$RUN_ROOT"
test ! -L "$RUN_ROOT"
install -d -m 700 "$RUN_ROOT" "$RUN_ROOT/assets" "$RUN_ROOT/renders"
install -d -m 700 "$AUDIT_RUN"
test "$(stat -f '%u' "$RUN_ROOT")" = "$(id -u)"
test "$(stat -f '%p' "$RUN_ROOT")" = 40700
```

Expected: both roots are new; the runtime root is an owned, non-symlink `0700` directory. Do not create `assets/known-missing.png`.

- [ ] **Step 3: Write the exact background provisioner in the ignored run directory**

Create `.superpowers/sdd/modeling-runs/run-20260810-01/provision.py` with:

```python
from __future__ import annotations

import os
import time

import bpy

RUN_ROOT = "/tmp/bcx-official-mcp-modeling-20260810"
LIBRARY = os.path.join(RUN_ROOT, "library_source.blend")
FIXTURE = os.path.join(RUN_ROOT, "lamp_fixture.blend")
MISSING = os.path.join(RUN_ROOT, "assets", "known-missing.png")

assert os.path.isdir(RUN_ROOT) and not os.path.islink(RUN_ROOT)
assert not os.path.exists(MISSING)

started = time.perf_counter()
bpy.ops.wm.read_factory_settings(use_empty=True)
asset_collection = bpy.data.collections.new("Lamp_LinkedAsset")
bpy.context.scene.collection.children.link(asset_collection)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=0.55, location=(0.0, 0.0, 0.55))
accent = bpy.context.object
assert accent is not None
accent.name = "Library_Accent"
for source in list(accent.users_collection):
    if source != asset_collection:
        source.objects.unlink(accent)
if asset_collection not in accent.users_collection:
    asset_collection.objects.link(accent)
bpy.ops.wm.save_as_mainfile(filepath=LIBRARY)

bpy.ops.wm.read_factory_settings(use_empty=True)
fixture_collection = bpy.data.collections.new("Fixture")
bpy.context.scene.collection.children.link(fixture_collection)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.0, depth=0.4, location=(0.0, 0.0, 0.2))
fixture_base = bpy.context.object
assert fixture_base is not None
fixture_base.name = "Fixture_Base"
for source in list(fixture_base.users_collection):
    if source != fixture_collection:
        source.objects.unlink(fixture_base)
if fixture_collection not in fixture_base.users_collection:
    fixture_collection.objects.link(fixture_base)

with bpy.data.libraries.load(LIBRARY, link=True) as (data_from, data_to):
    assert "Lamp_LinkedAsset" in data_from.collections
    data_to.collections = ["Lamp_LinkedAsset"]
linked_collection = data_to.collections[0]
assert linked_collection is not None
instancer = bpy.data.objects.new("Fixture_LinkedProp", None)
instancer.instance_type = "COLLECTION"
instancer.instance_collection = linked_collection
instancer.location = (2.0, 0.0, 0.0)
fixture_collection.objects.link(instancer)

missing = bpy.data.images.new("Fixture_KnownMissing", width=1, height=1)
missing.source = "FILE"
missing.filepath = MISSING
bpy.ops.wm.save_as_mainfile(filepath=FIXTURE)

print({
    "library": LIBRARY,
    "fixture": FIXTURE,
    "missing": MISSING,
    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
})
```

- [ ] **Step 4a: Run the provisioner once**

Run:

```bash
set -euo pipefail
START_EPOCH="$(python3 -c 'import time; print(time.time_ns())')"
/Applications/Blender.app/Contents/MacOS/Blender \
  --background --factory-startup \
  --python .superpowers/sdd/modeling-runs/run-20260810-01/provision.py
END_EPOCH="$(python3 -c 'import time; print(time.time_ns())')"
python3 - "$START_EPOCH" "$END_EPOCH" <<'PY'
import sys
print(f"fixture_wall_ms={(int(sys.argv[2]) - int(sys.argv[1])) / 1_000_000:.3f}")
PY
```

Expected: background Blender exits `0`. Once this provisioner has succeeded, do not rerun it during verification-only recovery because it would overwrite the existing fixture files.

- [ ] **Step 4b: Verify the fixtures**

Run:

```bash
set -euo pipefail
for fixture_path in \
  /tmp/bcx-official-mcp-modeling-20260810/library_source.blend \
  /tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend; do
  test -f "$fixture_path"
  test ! -L "$fixture_path"
  test "$(stat -f '%u' "$fixture_path")" = "$(id -u)"
  test "$(stat -f '%z' "$fixture_path")" -gt 0
  shasum -a 256 "$fixture_path"
done
test ! -e /tmp/bcx-official-mcp-modeling-20260810/assets/known-missing.png
```

Expected: both `.blend` files are owned ordinary non-empty files; the missing asset is absent.

- [ ] **Step 5: Create the tracked audit skeleton and commit Task 1**

Create `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md` with these exact headings and fill the measured values from Steps 1–4:

```markdown
# Official Blender MCP Modeling Validation

Status: baseline running

## Scope and safety boundary
## Environment and catalog
## Stage timings
## 26-tool results
## Modeling contract
## Errors and recoveries
## Root-cause analysis
## Remediation decision
## Adversarial audit and retest
## Final verdict
```

Under `Scope and safety boundary`, state that no user `.blend` was opened or saved, the runtime binaries are untracked, and all paths in the report use `$RUN_ROOT` rather than the account name. Under `Stage timings`, record preflight and fixture wall time separately from Blender `elapsed_ms`.

Run:

```bash
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "test: record official MCP modeling preflight"
```

Expected: one tracked audit file is committed; runtime and ignored files are absent from `git status`.

---

### Task 2: Three-stage lamp modeling and structural acceptance

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Create ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/phase-1.py`
- Create ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/phase-2.py`
- Create ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/phase-3.py`

**Interfaces:**
- Consumes: Task 1 preflight verdict, exact run root, `library_source.blend`, and clean unsaved GUI.
- Produces: `MCP_Lamp_Isolated`, the complete named scene contract, structured phase results, and a GUI state usable by Task 3.

- [ ] **Step 1: Create and call Phase 1 payload**

Create the ignored `phase-1.py` with:

```python
import bpy
import time

started = time.perf_counter()
assert bpy.data.filepath == ""
assert bpy.context.mode == "OBJECT"
expected_default = {"Cube", "Camera", "Light"}
assert {obj.name for obj in bpy.context.scene.objects} == expected_default

for name in sorted(expected_default):
    obj = bpy.data.objects.get(name)
    assert obj is not None
    bpy.data.objects.remove(obj, do_unlink=True)

collection = bpy.data.collections.new("MCP_Lamp_Isolated")
bpy.context.scene.collection.children.link(collection)
bpy.context.scene["BCX_RUN_ROOT"] = "/tmp/bcx-official-mcp-modeling-20260810"

def move_to_collection(obj):
    if collection not in obj.users_collection:
        collection.objects.link(obj)
    for source in list(obj.users_collection):
        if source != collection:
            source.objects.unlink(obj)

def material(name, color, metallic=0.0, roughness=0.45):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = color
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    assert bsdf is not None
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat

materials = {
    "Mat_Base": material("Mat_Base", (0.035, 0.055, 0.08, 1.0), 0.15, 0.28),
    "Mat_Metal": material("Mat_Metal", (0.16, 0.19, 0.23, 1.0), 0.82, 0.2),
    "Mat_Shade": material("Mat_Shade", (0.78, 0.16, 0.055, 1.0), 0.05, 0.32),
    "Mat_Bulb": material("Mat_Bulb", (1.0, 0.62, 0.2, 1.0), 0.0, 0.2),
    "Mat_Ground": material("Mat_Ground", (0.13, 0.15, 0.18, 1.0), 0.0, 0.55),
}

bulb_bsdf = materials["Mat_Bulb"].node_tree.nodes.get("Principled BSDF")
assert bulb_bsdf is not None
for key in ("Emission Color", "Emission"):
    if key in bulb_bsdf.inputs:
        bulb_bsdf.inputs[key].default_value = (1.0, 0.32, 0.06, 1.0)
if "Emission Strength" in bulb_bsdf.inputs:
    bulb_bsdf.inputs["Emission Strength"].default_value = 4.0

bpy.ops.mesh.primitive_plane_add(size=20.0, location=(0.0, 0.0, 0.0))
ground = bpy.context.object
ground.name = "Lamp_Ground"
ground.data.name = "Lamp_Ground_Mesh"
ground.data.materials.append(materials["Mat_Ground"])
move_to_collection(ground)

bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=2.25, depth=0.62, location=(0.0, 0.0, 0.33))
base = bpy.context.object
base.name = "Lamp_Base"
base.data.name = "Lamp_Base_Mesh"
base.data.materials.append(materials["Mat_Base"])
bevel = base.modifiers.new("Base_Bevel", "BEVEL")
bevel.width = 0.16
bevel.segments = 4
move_to_collection(base)

bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.22, depth=4.8, location=(0.0, 0.0, 3.02))
stem = bpy.context.object
stem.name = "Lamp_Stem"
stem.data.name = "Lamp_Stem_Mesh"
stem.data.materials.append(materials["Mat_Metal"])
move_to_collection(stem)
stem.parent = base
stem.matrix_parent_inverse = base.matrix_world.inverted()

result = {
    "phase": 1,
    "objects": sorted(obj.name for obj in collection.objects),
    "materials": sorted(materials),
    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
}
```

Call `mcp__blender__execute_blender_code` with the entire file contents as `code`. Expected: `phase=1`, objects exactly `Lamp_Base`, `Lamp_Ground`, `Lamp_Stem`, and five materials. Record tool wall time and internal `elapsed_ms`.

- [ ] **Step 2: Create and call Phase 2 payload**

Create ignored `phase-2.py` with:

```python
import bpy
import time
from mathutils import Vector

started = time.perf_counter()
collection = bpy.data.collections["MCP_Lamp_Isolated"]

def move_to_collection(obj):
    if collection not in obj.users_collection:
        collection.objects.link(obj)
    for source in list(obj.users_collection):
        if source != collection:
            source.objects.unlink(obj)

def smooth(obj):
    for polygon in obj.data.polygons:
        polygon.use_smooth = True

def cylinder_between(name, start, end, radius, material):
    start_v = Vector(start)
    end_v = Vector(end)
    direction = end_v - start_v
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=48,
        radius=radius,
        depth=direction.length,
        location=(start_v + end_v) * 0.5,
    )
    obj = bpy.context.object
    obj.name = name
    obj.data.name = f"{name}_Mesh"
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = direction.to_track_quat("Z", "Y")
    obj.data.materials.append(material)
    smooth(obj)
    move_to_collection(obj)
    return obj

def preserve_parent(child, parent):
    world = child.matrix_world.copy()
    child.parent = parent
    child.matrix_world = world

metal = bpy.data.materials["Mat_Metal"]
shade_mat = bpy.data.materials["Mat_Shade"]
bulb_mat = bpy.data.materials["Mat_Bulb"]
stem = bpy.data.objects["Lamp_Stem"]

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.42, location=(0.0, 0.0, 5.55))
joint_lower = bpy.context.object
joint_lower.name = "Lamp_Joint_Lower"
joint_lower.data.name = "Lamp_Joint_Lower_Mesh"
joint_lower.data.materials.append(metal)
smooth(joint_lower)
move_to_collection(joint_lower)

arm_lower = cylinder_between("Lamp_Arm_Lower", (0.0, 0.0, 5.55), (2.05, 0.0, 7.05), 0.18, metal)

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.4, location=(2.05, 0.0, 7.05))
joint_upper = bpy.context.object
joint_upper.name = "Lamp_Joint_Upper"
joint_upper.data.name = "Lamp_Joint_Upper_Mesh"
joint_upper.data.materials.append(metal)
smooth(joint_upper)
move_to_collection(joint_upper)

arm_upper = cylinder_between("Lamp_Arm_Upper", (2.05, 0.0, 7.05), (3.75, 0.0, 6.35), 0.16, metal)

bpy.ops.mesh.primitive_cone_add(
    vertices=64,
    radius1=1.32,
    radius2=0.52,
    depth=1.75,
    location=(3.95, 0.0, 5.55),
)
shade = bpy.context.object
shade.name = "Lamp_Shade"
shade.data.name = "Lamp_Shade_Mesh"
shade.data.materials.append(shade_mat)
bevel = shade.modifiers.new("Shade_Bevel", "BEVEL")
bevel.width = 0.07
bevel.segments = 3
smooth(shade)
move_to_collection(shade)

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.5, location=(3.95, 0.0, 4.65))
bulb = bpy.context.object
bulb.name = "Lamp_Bulb"
bulb.data.name = "Lamp_Bulb_Mesh"
bulb.data.materials.append(bulb_mat)
smooth(bulb)
move_to_collection(bulb)

curve = bpy.data.curves.new("Lamp_Cable_Curve", "CURVE")
curve.dimensions = "3D"
curve.bevel_depth = 0.065
curve.bevel_resolution = 4
spline = curve.splines.new("BEZIER")
spline.bezier_points.add(4)
for point, coordinate in zip(
    spline.bezier_points,
    [(-1.0, 0.15, 0.14), (0.2, 0.1, 1.2), (1.6, 0.08, 4.7), (3.0, 0.05, 6.1), (3.95, 0.0, 5.0)],
    strict=True,
):
    point.co = coordinate
    point.handle_left_type = "AUTO"
    point.handle_right_type = "AUTO"
cable = bpy.data.objects.new("Lamp_Cable", curve)
curve.materials.append(metal)
collection.objects.link(cable)

preserve_parent(joint_lower, stem)
preserve_parent(arm_lower, joint_lower)
preserve_parent(joint_upper, arm_lower)
preserve_parent(arm_upper, joint_upper)
preserve_parent(shade, arm_upper)
preserve_parent(bulb, shade)

result = {
    "phase": 2,
    "objects": sorted(obj.name for obj in collection.objects),
    "parents": {name: bpy.data.objects[name].parent.name if bpy.data.objects[name].parent else None for name in (
        "Lamp_Joint_Lower", "Lamp_Arm_Lower", "Lamp_Joint_Upper", "Lamp_Arm_Upper", "Lamp_Shade", "Lamp_Bulb"
    )},
    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
}
```

Call `execute_blender_code`. Expected: all six parent entries form the declared chain, and the collection now includes all Phase 1 and Phase 2 names.

- [ ] **Step 3: Create and call Phase 3 payload**

Create ignored `phase-3.py` with:

```python
import bpy
import os
import time
from mathutils import Vector

started = time.perf_counter()
run_root = bpy.context.scene["BCX_RUN_ROOT"]
assert run_root == "/tmp/bcx-official-mcp-modeling-20260810"
library_path = os.path.join(run_root, "library_source.blend")
missing_path = os.path.join(run_root, "assets", "known-missing.png")
assert os.path.isfile(library_path) and not os.path.islink(library_path)
assert not os.path.exists(missing_path)
collection = bpy.data.collections["MCP_Lamp_Isolated"]

def point_at(obj, target):
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def add_area(name, location, energy, size, color):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    obj.location = location
    collection.objects.link(obj)
    point_at(obj, (1.8, 0.0, 3.2))
    return obj

camera_data = bpy.data.cameras.new("Lamp_Camera_Data")
camera_data.lens = 52.0
camera = bpy.data.objects.new("Lamp_Camera", camera_data)
camera.location = (12.5, -15.0, 10.0)
collection.objects.link(camera)
point_at(camera, (1.4, 0.0, 3.5))
bpy.context.scene.camera = camera

add_area("Lamp_Key", (4.5, -4.5, 10.0), 1150.0, 5.0, (1.0, 0.64, 0.38))
add_area("Lamp_Fill", (-4.0, 3.0, 6.0), 700.0, 4.0, (0.36, 0.54, 1.0))

with bpy.data.libraries.load(library_path, link=True) as (data_from, data_to):
    assert "Lamp_LinkedAsset" in data_from.collections
    data_to.collections = ["Lamp_LinkedAsset"]
linked_collection = data_to.collections[0]
assert linked_collection is not None
linked_prop = bpy.data.objects.new("Lamp_LinkedProp", None)
linked_prop.instance_type = "COLLECTION"
linked_prop.instance_collection = linked_collection
linked_prop.location = (-3.0, 1.8, 0.0)
collection.objects.link(linked_prop)

missing = bpy.data.images.new("Lamp_KnownMissing", width=1, height=1)
missing.source = "FILE"
missing.filepath = missing_path

world = bpy.context.scene.world or bpy.data.worlds.new("Lamp_World")
bpy.context.scene.world = world
world.use_nodes = True
background = world.node_tree.nodes.get("Background")
assert background is not None
background.inputs["Color"].default_value = (0.012, 0.018, 0.03, 1.0)
background.inputs["Strength"].default_value = 0.28

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE_NEXT"
scene.render.resolution_x = 640
scene.render.resolution_y = 640
scene.render.resolution_percentage = 75
scene.render.image_settings.file_format = "PNG"
scene.render.film_transparent = False

shade = bpy.data.objects["Lamp_Shade"]
bpy.context.view_layer.objects.active = shade
shade.select_set(True)

mesh_objects = [obj for obj in collection.objects if obj.type == "MESH"]
world_points = [obj.matrix_world @ Vector(corner) for obj in mesh_objects for corner in obj.bound_box]
minimum = [round(min(point[index] for point in world_points), 4) for index in range(3)]
maximum = [round(max(point[index] for point in world_points), 4) for index in range(3)]

result = {
    "phase": 3,
    "collection": collection.name,
    "objects": sorted(obj.name for obj in collection.objects),
    "materials": sorted(mat.name for mat in bpy.data.materials if mat.name.startswith("Mat_")),
    "camera": scene.camera.name,
    "lights": sorted(obj.name for obj in collection.objects if obj.type == "LIGHT"),
    "linked_library": linked_collection.library.filepath,
    "missing_path": missing.filepath,
    "bounds": {"min": minimum, "max": maximum},
    "elapsed_ms": round((time.perf_counter() - started) * 1000.0, 3),
}
```

Call `execute_blender_code`. Expected: collection name exact; camera `Lamp_Camera`; lights `Lamp_Fill` and `Lamp_Key`; linked path is the scratch library; missing path is the absent scratch asset; each maximum bound is greater than its minimum.

- [ ] **Step 4: Verify the modeling contract with read-only tools**

Call:

```text
mcp__blender__get_blendfile_summary_path_info {}
mcp__blender__get_objects_summary {}
mcp__blender__get_object_detail_summary {"name":"Lamp_Shade"}
mcp__blender__get_blendfile_summary_datablocks {}
```

Expected: current filepath remains empty; `is_dirty=true`; collection and all declared objects appear; `Lamp_Shade` is `MESH`, data name `Lamp_Shade_Mesh`, material `Mat_Shade`; datablocks include at least 15 objects, 5 materials, 1 camera and 2 lights.

- [ ] **Step 5: Update the audit and commit Task 2**

Record Phase 1–3 start/end, tool wall time, Blender `elapsed_ms`, first-attempt errors and exact recovery. Include a table of required objects, materials, parent chain, bounds and observed values. Do not claim a render result yet.

Run:

```bash
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "test: record official MCP lamp modeling"
```

Expected: only the audit changes; ignored payloads and runtime binaries stay untracked/ignored.

---

### Task 3: Complete the 26-tool matrix, screenshots, and renders

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Modify ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/run-report.md`

**Interfaces:**
- Consumes: Task 2 complete GUI scene, Task 1 CLI fixture and library, exact object/data names.
- Produces: one outcome and timing for each of 26 unique tools, two validated PNG evidence copies, and complete raw run notes.

- [ ] **Step 1: Exercise the CLI and paired summary tools**

Call each tool with the exact arguments below and record `Wall time`, outcome and result shape:

```text
mcp__blender__execute_blender_code_for_cli {
  "blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend",
  "code":"import bpy, os\nresult = {\"object_count\": len(bpy.data.objects), \"linked_libraries\": len(bpy.data.libraries), \"missing_image_path\": bpy.data.images[\"Fixture_KnownMissing\"].filepath, \"is_dirty\": bpy.data.is_dirty}\n"
}
mcp__blender__get_blendfile_summary_datablocks_for_cli {"blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend"}
mcp__blender__get_blendfile_summary_missing_files {}
mcp__blender__get_blendfile_summary_missing_files_for_cli {"blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend"}
mcp__blender__get_blendfile_summary_of_linked_libraries {}
mcp__blender__get_blendfile_summary_of_linked_libraries_for_cli {"blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend"}
mcp__blender__get_blendfile_summary_path_info_for_cli {"blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend"}
mcp__blender__get_blendfile_summary_usage_guess {}
mcp__blender__get_blendfile_summary_usage_guess_for_cli {"blend_file":"/tmp/bcx-official-mcp-modeling-20260810/lamp_fixture.blend"}
```

Expected: CLI arbitrary code reports at least two objects, one linked library, exact missing path and `is_dirty=false`; GUI and CLI missing summaries each include only the controlled missing path; linked summaries each report one direct library; CLI path info is a saved file under `$RUN_ROOT`; usage scores are integers in `0..100` and are treated as heuristic only.

- [ ] **Step 2: Exercise bundled documentation tools**

Call:

```text
mcp__blender__get_python_api_docs {"identifier":"bpy.types.Object"}
mcp__blender__search_api_docs {"query":"bpy.ops mesh primitive cylinder add","max_results":3}
mcp__blender__search_manual_docs {"query":"render output filepath","max_results":3}
```

Expected: exact API lookup has `found=true`; both searches return at least one result with path, text, breadcrumb and score. Record first-call wall time separately because bundled docs may have a normal cold-start cost.

- [ ] **Step 3: Exercise UI navigation and screenshots**

Call in this exact order:

```text
mcp__blender__get_screenshot_of_window_as_json {}
mcp__blender__jump_to_tab_by_name {"name":"布局"}
mcp__blender__jump_to_tab_by_space_type {"space_type":"VIEW_3D","allow_edits":false}
mcp__blender__jump_to_view3d_object_by_name {"name":"Lamp_Shade","allow_edits":false}
mcp__blender__jump_to_view3d_object_data_by_name {"name":"Lamp_Shade_Mesh","allow_edits":false}
mcp__blender__get_screenshot_of_window_as_json {}
mcp__blender__get_screenshot_of_area_as_image {"area_ui_type":"VIEW_3D","size_limit_in_bytes":2000000}
mcp__blender__get_screenshot_of_window_as_image {"size_limit_in_bytes":3000000}
```

Expected: navigation returns `status=ok`; the second JSON shows `Lamp_Shade` active and a `VIEW_3D` area; both image tools return PNG content. If workspace name differs from the preflight JSON, use that exact discovered name and record the discrepancy as an environment observation, not an LLM guess.

- [ ] **Step 4: Exercise both render tools and validate official scratch output**

First call `get_blendfile_summary_path_info` and assert the current file remains unsaved. Then call:

```text
mcp__blender__render_thumbnail_to_path {"output_path":"/tmp/bcx-official-mcp-modeling-20260810/thumbnail.png"}
mcp__blender__render_viewport_to_path {"output_path":"/tmp/bcx-official-mcp-modeling-20260810/viewport.png"}
```

For each returned filepath, run this containment and copy check with the actual path in `RETURNED_PATH`:

```bash
set -euo pipefail
RETURNED_PATH="${THUMBNAIL_RETURNED_PATH:?export the exact thumbnail filepath field returned by MCP}"
EXPECTED_BASENAME='thumbnail.png'
case "$RETURNED_PATH" in
  */blender_mcp/"$EXPECTED_BASENAME") ;;
  *) echo 'unexpected render scratch path' >&2; exit 1 ;;
esac
test -f "$RETURNED_PATH"
test ! -L "$RETURNED_PATH"
test "$(stat -f '%z' "$RETURNED_PATH")" -gt 0
cp -p "$RETURNED_PATH" "/tmp/bcx-official-mcp-modeling-20260810/renders/$EXPECTED_BASENAME"
shasum -a 256 "/tmp/bcx-official-mcp-modeling-20260810/renders/$EXPECTED_BASENAME"
```

Before the command, export `THUMBNAIL_RETURNED_PATH` directly from the successful MCP result and
record the same exact value in the ignored raw report. Repeat with
`RETURNED_PATH="${VIEWPORT_RETURNED_PATH:?export the exact viewport filepath field returned by MCP}"`
and `EXPECTED_BASENAME='viewport.png'`. After both renders, call
`get_blendfile_summary_path_info` again; expected filepath remains empty and no user file was saved.

- [ ] **Step 5: Prove exact 26-tool coverage and commit Task 3**

Add a 26-row table to the audit, one row for each exact tool name from the server catalog, with outcome, wall ms, expected/observed shape, retry count and issue ID. Validate the table with:

Before running the validator, change the audit status to
`Status: tool coverage complete; root-cause analysis pending`.

```bash
python3 - <<'PY'
from pathlib import Path

audit = Path("docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md").read_text(encoding="utf-8")
tools = [
    "execute_blender_code", "execute_blender_code_for_cli",
    "get_blendfile_summary_datablocks", "get_blendfile_summary_datablocks_for_cli",
    "get_blendfile_summary_missing_files", "get_blendfile_summary_missing_files_for_cli",
    "get_blendfile_summary_of_linked_libraries", "get_blendfile_summary_of_linked_libraries_for_cli",
    "get_blendfile_summary_path_info", "get_blendfile_summary_path_info_for_cli",
    "get_blendfile_summary_usage_guess", "get_blendfile_summary_usage_guess_for_cli",
    "get_object_detail_summary", "get_objects_summary", "get_python_api_docs",
    "get_screenshot_of_area_as_image", "get_screenshot_of_window_as_image",
    "get_screenshot_of_window_as_json", "jump_to_tab_by_name", "jump_to_tab_by_space_type",
    "jump_to_view3d_object_by_name", "jump_to_view3d_object_data_by_name",
    "render_thumbnail_to_path", "render_viewport_to_path", "search_api_docs", "search_manual_docs",
]
assert len(tools) == len(set(tools)) == 26
for tool in tools:
    marker = f"`{tool}`"
    assert marker in audit, marker
assert "Status: tool coverage complete; root-cause analysis pending" in audit
print("tool-coverage=26")
PY
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "test: record official MCP 26-tool modeling run"
```

Expected: `tool-coverage=26`; only the audit is committed.

---

### Task 4: Baseline root-cause analysis and remediation decision

**Files:**
- Modify: `docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md`
- Modify ignored: `.superpowers/sdd/modeling-runs/run-20260810-01/run-report.md`

**Interfaces:**
- Consumes: complete tool table, phase timings, raw errors, two PNG hashes and model contract from Tasks 1–3.
- Produces: issue ledger with root causes, abnormal-time verdicts, and a concrete list of files that a separate remediation plan must create or modify.

- [ ] **Step 1: Classify every observed error and slow call**

For each error or retry, add one audit row with exact fields:

```text
ID | phase/tool | symptom | first LLM hypothesis | evidence | root cause class | wall time lost | recovery | reproducible | preventable file
```

Root-cause class must be one of: `llm_plan`, `manual_gap`, `automation_gap`, `upstream_tool`, `environment_jitter`, `normal_cost`. A call is potentially abnormal only under these exact thresholds: docs/summary/navigation `>5000ms`, screenshot `>10000ms`, thumbnail `>30000ms`, viewport render `>60000ms`, or more than `3x` the median of successful same-case reruns. Do not label a single cold start abnormal without a same-case comparison.

- [ ] **Step 2: Visually inspect both PNG copies**

Use the local image viewer on:

```text
/tmp/bcx-official-mcp-modeling-20260810/renders/thumbnail.png
/tmp/bcx-official-mcp-modeling-20260810/renders/viewport.png
```

Record: full lamp visible, no clipping, materials distinguishable, bulb illuminated, ground shadow present, linked prop visible, and no user content. Any failed criterion becomes an issue; do not edit the PNG.

- [ ] **Step 3: Decide whether a persistent file is justified**

Apply this exact decision rule in `## Remediation decision`:

- add or modify a standalone operational manual when an LLM sequencing, safety, render-scratch, naming or timing mistake is reproducibly preventable by stable instructions;
- add a small smoke helper only when at least two stages repeat the same payload/validation logic or a deterministic regression cannot be checked reliably from prose;
- modify product code only for a minimal reproduction that fails twice in clean isolated sessions and is inside this repository's owned code;
- create no file for one-off environment jitter or normal render/docs startup cost.

List exact proposed file paths and exact issue IDs they prevent. This is analysis only: do not implement the remediation in Task 4.

- [ ] **Step 4: Finalize and commit the baseline audit**

Set audit `Status: baseline complete; remediation pending`. Fill every heading, add total stage wall time, sum of tool wall time, LLM/retry time, and explain why totals differ. State separately: 26 tools called, expected successes, expected errors, unexpected failures, retries, and unresolved issues.

Run:

```bash
set -euo pipefail
rg -n 'T[B]D|T[O]DO|baseline running' \
  docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md && exit 1 || true
git diff --check
git add -- docs/audits/2026-08-10-official-blender-mcp-modeling-validation.md
git diff --cached --check
git commit -m "docs: analyze official MCP modeling run"
git status --short --branch
```

Expected: audit is complete, contains no placeholder, and Git is clean. The controller then uses `writing-plans` again to write a separate remediation plan from the exact issue/file list; it must not silently implement fixes from this baseline plan.
