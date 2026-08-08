"""protocol 的双路径导入：仓库内走顶层包，打包进扩展后走 _vendor。
bl_ext.<repo>.<ext_id> 命名空间下不存在顶层 protocol（spec §3.1 约束 2 的跨包版）。"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from protocol import envelope, framing
else:
    try:
        from .._vendor.protocol import envelope, framing
    except ImportError:
        from protocol import envelope, framing

__all__ = ["envelope", "framing"]
