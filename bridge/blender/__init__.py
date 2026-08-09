"""register/unregister 实现（根 shim 转发到这里）。"""
from __future__ import annotations

import bpy

from . import driver, panel

_registered: list[type] = []


def register() -> None:
    start = len(_registered)
    try:
        for cls in panel.CLASSES:
            if cls in _registered:
                continue
            bpy.utils.register_class(cls)
            _registered.append(cls)
    except BaseException:
        try:
            while len(_registered) > start:
                cls = _registered[-1]
                bpy.utils.unregister_class(cls)
                _registered.pop()
        except BaseException as rollback_error:
            raise RuntimeError("class registration rollback incomplete") from rollback_error
        raise


def unregister() -> None:
    if not driver.stop():
        # Keep the panel registered so the user can press Disconnect again
        # when transport cleanup needs a retry; do not hide a live session.
        raise RuntimeError("bridge cleanup incomplete; panel remains registered")
    while _registered:
        cls = _registered[-1]
        bpy.utils.unregister_class(cls)
        _registered.pop()
