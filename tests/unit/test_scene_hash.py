from bridge.core import scene_hash


def test_quantize_normalizes_negative_zero_and_noise():
    assert scene_hash.quantize(-0.0) == scene_hash.quantize(0.0) == "0.000000"
    assert scene_hash.quantize(-0.0000004) == "0.000000"
    assert scene_hash.quantize(1.0000004) == "1.000000"   # 1e-6 以下噪声被吸收
    assert scene_hash.quantize(1.000001) == "1.000001"    # 1e-6 级差异保留


def test_digest_is_order_independent():
    a = scene_hash.object_line("Cube", "MESH", tuple(range(16)), "MESH", (8, 12, 6))
    b = scene_hash.object_line("Lamp", "LIGHT", tuple(range(16)), "LIGHT", ())
    assert scene_hash.digest([a, b]) == scene_hash.digest([b, a])
    assert scene_hash.digest([a, b]).startswith("sha256:")


def test_rename_changes_digest():
    m = tuple(float(i) for i in range(16))
    a = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    b = scene_hash.object_line("Cube2", "MESH", m, "MESH", (8, 12, 6))
    assert scene_hash.digest([a]) != scene_hash.digest([b])


def test_snapshot_dataclass_shape():
    from bridge.core.contracts import SceneSnapshot
    s = SceneSnapshot(
        scene_revision=0, scene_hash="sha256:x", scene_name="Scene", scene_path=None,
        units_system="METRIC", units_scale_length=1.0, object_count=0, mesh_count=0,
        camera_count=0, light_count=0, collections=(),
    )
    assert s.managed_objects == ()   # Phase 0 恒空（§3.4）


def test_structure_hash_v1_covers_only_declared_fields():
    # 复审 R-04：object_line 的**签名**就是 v1 的全部覆盖面——顶点坐标、拓扑、
    # modifier、材质、可见性无处可传。这里断言产出行的字段结构，把边界钉死；
    # 「顶点移动 hash 不变」这类语义由 L3 真 Blender fixture 证明（§7.3）。
    line = scene_hash.object_line("Cube", "MESH", tuple(range(16)), "MESH", (8, 12, 6))
    fields = line.split("\t")
    assert len(fields) == 5
    assert fields[0] == "Cube" and fields[1] == "MESH" and fields[3] == "MESH"
    assert len(fields[2].split(",")) == 16          # 只有 16 个 matrix 分量
    assert fields[4] == "8,12,6"                    # 只有计数，没有坐标


def test_same_counts_different_topology_collide_by_design():
    # 同一对象在「顶点数/边数/面数不变但连接关系改变」后，v1 产出完全相同的行。
    # 这是已知盲区（模块 docstring + URS v1.2 术语表），不是缺陷。
    m = tuple(float(i) for i in range(16))
    before = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    after = scene_hash.object_line("Cube", "MESH", m, "MESH", (8, 12, 6))
    assert scene_hash.digest([before]) == scene_hash.digest([after])
    # 反证：v1 对声明字段确实敏感——改 matrix 即变
    moved = scene_hash.object_line("Cube", "MESH", tuple(range(1, 17)), "MESH", (8, 12, 6))
    assert scene_hash.digest([before]) != scene_hash.digest([moved])
