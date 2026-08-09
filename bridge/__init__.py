"""扩展入口 shim（§3.1 约束 1）。bpy 缺席时保持可 import——pytest 依赖这一点。"""
try:
    import bpy  # type: ignore[import-not-found]  # noqa: F401
except ModuleNotFoundError:
    pass                                  # 仓库/测试环境：只用 bridge.core，不暴露入口
else:
    from .blender import register, unregister  # noqa: F401
