"""规范 §7.1 的 check registry。本文件即该表的唯一机器可读形式。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CheckSpec:
    id: str
    stage: str
    order: int
    impl: int
    kind: str          # "all" | "interchange" | "blend_native"
    writer: str
    warning_codes: tuple[str, ...] = ()


CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec("r0.contract.schema_closed", "R0", 10, 1, "all", "coordinator"),
    CheckSpec("r0.contract.tools_locked", "R0", 20, 1, "all", "coordinator"),
    CheckSpec("r0.contract.na_set_declared", "R0", 30, 1, "all", "coordinator"),
    CheckSpec("r1.input.digest_recorded", "R1", 10, 1, "all", "coordinator"),
    CheckSpec("r1.input.no_link_or_device", "R1", 20, 1, "all", "coordinator"),
    CheckSpec("r1.input.size_within_limit", "R1", 30, 1, "all", "coordinator"),
    CheckSpec("r2.inventory.coverage_complete", "R2", 10, 1, "all", "inspector",
              ("unsupported_datablock_type", "unsupported_modifier_type")),
    CheckSpec("r2.inventory.no_nan_inf", "R2", 20, 1, "all", "inspector"),
    CheckSpec("r2.inventory.no_reserved_props", "R2", 25, 1, "all", "inspector"),
    CheckSpec("r2.geometry.validate_clean", "R2", 30, 1, "all", "inspector"),
    CheckSpec("r2.geometry.manifest_written", "R2", 40, 1, "all", "inspector"),
    CheckSpec("r2.material.slots_resolved", "R2", 50, 1, "all", "inspector",
              ("empty_material_slot",)),
    CheckSpec("r2.dependency.all_present", "R2", 60, 1, "all", "inspector",
              ("packed_dependency",)),
    CheckSpec("r2.source.digest_stable", "R2", 70, 1, "all", "inspector"),
    CheckSpec("r3.export.file_nonempty", "R3", 10, 1, "interchange", "export_glb"),
    CheckSpec("r3.export.source_unchanged", "R3", 20, 1, "interchange", "export_glb"),
    CheckSpec("r3.validator.no_error", "R3", 30, 1, "interchange", "coordinator"),
    CheckSpec("r3.validator.resources_read", "R3", 40, 1, "interchange", "coordinator"),
    CheckSpec("r3.validator.report_complete", "R3", 50, 1, "interchange", "coordinator"),
    CheckSpec("r3.extension.none_forbidden", "R3", 60, 1, "interchange", "coordinator"),
    CheckSpec("r3.budget.within_limits", "R3", 70, 1, "interchange", "glb_budget",
              ("budget_near_limit", "non_triangle_primitive")),
    CheckSpec("r4.reopen.offline_ok", "R4", 10, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.reopen.dependencies_resolved", "R4", 20, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.reopen.manifest_matches_source", "R4", 25, 1, "blend_native", "reopen_probe"),
    CheckSpec("r4.import.manifest_written", "R4", 30, 1, "interchange", "reimport_probe"),
    CheckSpec("r4.projection.preserved_fields_match", "R4", 40, 1, "interchange", "coordinator"),
    CheckSpec("r4.projection.transformed_within_tolerance", "R4", 45, 1, "interchange",
              "coordinator"),
    CheckSpec("r4.projection.undeclared_loss", "R4", 50, 1, "interchange", "coordinator"),
    CheckSpec("r4.projection.ambiguous_object_names", "R4", 55, 1, "interchange", "coordinator"),
    CheckSpec("r4.visual.scene_not_empty", "R4", 60, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.all_views_rendered", "R4", 70, 1, "all", "coordinator"),
    CheckSpec("r4.visual.self_determinism", "R4", 80, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.platform_key_known", "R4", 90, 1, "all", "render_views(src)"),
    CheckSpec("r4.visual.source_import_match", "R4", 100, 1, "interchange", "coordinator"),
    CheckSpec("r5.evidence.manifest_closed", "R5", 10, 1, "all", "coordinator"),
    CheckSpec("r5.evidence.hashes_match", "R5", 20, 1, "all", "coordinator"),
    CheckSpec("r5.contract.digest_stable", "R5", 30, 1, "all", "coordinator"),
)

_STAGE_INDEX = {"R0": 0, "R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}


def sort_key(spec: CheckSpec) -> tuple[int, int, str]:
    """规范 §2.5.1 规则 2 的全序键。"""
    return (_STAGE_INDEX[spec.stage], spec.order, spec.id)


def checks_for_kind(kind: str) -> tuple[CheckSpec, ...]:
    return tuple(c for c in CHECKS if c.kind in ("all", kind))


def na_check_ids(kind: str) -> tuple[str, ...]:
    return tuple(sorted(c.id for c in CHECKS if c.kind not in ("all", kind)))
