"""路径策略：fail-closed 前置过滤。URS FR-30。Phase 0 无路径参数，交付并测试。

字符串校验不是写入安全边界：resolve() 与实际写入之间存在时间窗，路径组件可被替换为
symlink。Phase 1 的真实写入必须 fd-based——O_NOFOLLOW / dir-fd openat、同目录临时文件 +
原子 rename，授权绑定已打开的 fd。
"""
from __future__ import annotations

from pathlib import Path


class PathDenied(Exception):
    pass


def same_file(a: Path, b: Path) -> bool:
    """查询两个已存在路径当前是否指向同一 inode；不是写入安全边界。

    任一 stat 失败时，False 表示未知，不表示已证明不同。不得只调用本函数后写入。
    """
    try:
        sa, sb = a.stat(), b.stat()
    except (OSError, ValueError):
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


class PathPolicy:
    def __init__(self, roots: list[Path], allowed_exts: set[str]) -> None:
        self._roots = [root.expanduser().resolve() for root in roots]
        self._exts = allowed_exts

    def resolve(self, raw: str) -> Path:
        path = Path(raw).expanduser()
        try:
            path = path.resolve(strict=False)
        except (OSError, ValueError) as error:
            raise PathDenied(f"unresolvable: {raw}") from error
        for root in self._roots:
            if path == root or root in path.parents:
                break
        else:
            raise PathDenied(f"outside allowed roots: {path}")
        if path.suffix.lower() not in self._exts:
            raise PathDenied(f"extension not allowed: {path.suffix}")
        return path
