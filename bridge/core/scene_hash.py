"""场景**结构摘要 v1**（§3.5）——纯函数、零 bpy，进 L1。bpy 侧只负责喂原始元组。

语义边界（audit F-01，实测确认）：本摘要覆盖对象名/类型/量化 matrix_world/数据的 RNA
类型标识与顶边面**计数**。顶点坐标、拓扑连接、modifier 参数、材质/节点、可见性、collection
归属、相机/灯光/场景设置**均不在覆盖面内**。会话内细粒度变更由 scene_revision（depsgraph
计数器）承担；跨会话等价性判断**禁止**以本值单独作证；Phase 1 冲突判定的
plan_scope_hash 必须对 IR 目标对象追加几何摘要（URS v1.2 术语表）。"""
from __future__ import annotations

import hashlib


def quantize(v: float) -> str:
    s = f"{v:.6f}"
    return "0.000000" if s == "-0.000000" else s


def object_line(
    name: str,
    obj_type: str,
    matrix16: tuple[float, ...],
    data_kind: str,
    data_counts: tuple[int, ...],
) -> str:
    m = ",".join(quantize(v) for v in matrix16)
    c = ",".join(str(n) for n in data_counts)
    return f"{name}\t{obj_type}\t{m}\t{data_kind}\t{c}"


def digest(lines: list[str]) -> str:
    joined = "\n".join(sorted(lines))
    return "sha256:" + hashlib.sha256(joined.encode("utf-8")).hexdigest()
