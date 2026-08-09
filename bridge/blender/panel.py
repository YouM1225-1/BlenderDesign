"""N 面板与显式会话开关（P0-D1）。"""
from __future__ import annotations

import bpy

from . import driver


class BCX_OT_allow_connect(bpy.types.Operator):
    bl_idname = "bcx.allow_connect"
    bl_label = "允许 Codex 连接"
    bl_description = "创建会话 socket 与一次性 token，开始接受本机 Codex 连接"

    def execute(self, context):
        driver.start()
        return {"FINISHED"}


class BCX_OT_disconnect(bpy.types.Operator):
    bl_idname = "bcx.disconnect"
    bl_label = "断开"
    bl_description = "关闭会话并删除 socket 与 token"

    def execute(self, context):
        return {"FINISHED"} if driver.stop() else {"CANCELLED"}


class BCX_PT_panel(bpy.types.Panel):
    bl_label = "Codex"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Codex"

    def draw(self, context):
        col = self.layout.column()
        s = driver.session()
        if s is not None:
            label = (f"已开启：{s.instance_id}" if not s.stopped
                     else "清理未完成，点击重试")
            col.label(text=label)   # §4.1：事务期提示的前身
            col.operator(BCX_OT_disconnect.bl_idname, icon="X")
        else:
            col.operator(BCX_OT_allow_connect.bl_idname, icon="PLAY")


CLASSES = (BCX_OT_allow_connect, BCX_OT_disconnect, BCX_PT_panel)
