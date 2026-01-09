import bpy
from bpy.types import Operator
from bpy.props import IntProperty

from .props import ensure_layer_attr_for_item
from .utils import (
    active_mesh_object,
    get_or_create_sculpt_mask_attr,
    copy_attr_values,
    attr_max_abs,
    attrs_equal,
    EPS,
)


class SCULPTMASK_OT_add_layer(Operator):
    bl_idname = "sculptmask.add_layer"
    bl_label = "Add Mask Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        # New layer defaults; name update is a bit finicky so I do it here.
        item = obj.sculpt_mask_layers.add()
        item.name = f"Mask {len(obj.sculpt_mask_layers)}"

        try:
            ensure_layer_attr_for_item(obj, item)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            obj.sculpt_mask_layers.remove(len(obj.sculpt_mask_layers) - 1)
            return {'CANCELLED'}

        obj.sculpt_mask_layers_index = len(obj.sculpt_mask_layers) - 1
        obj.data.update()
        return {'FINISHED'}


class SCULPTMASK_OT_remove_layer(Operator):
    bl_idname = "sculptmask.remove_layer"
    bl_label = "Remove Mask Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        item = obj.sculpt_mask_layers[idx]
        attr_name = item.attr_name

        obj.sculpt_mask_layers.remove(idx)
        obj.sculpt_mask_layers_index = min(idx, len(obj.sculpt_mask_layers) - 1)

        if attr_name:
            attr = obj.data.attributes.get(attr_name)
            if attr:
                obj.data.attributes.remove(attr)

        obj.data.update()
        return {'FINISHED'}


class SCULPTMASK_OT_move_layer_up(Operator):
    bl_idname = "sculptmask.move_layer_up"
    bl_label = "Move Layer Up"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}
        idx = obj.sculpt_mask_layers_index
        if idx <= 0 or idx >= len(obj.sculpt_mask_layers):
            return {'CANCELLED'}
        obj.sculpt_mask_layers.move(idx, idx - 1)
        obj.sculpt_mask_layers_index = idx - 1

        return {'FINISHED'}


class SCULPTMASK_OT_move_layer_down(Operator):
    bl_idname = "sculptmask.move_layer_down"
    bl_label = "Move Layer Down"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}
        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers) - 1:
            return {'CANCELLED'}
        obj.sculpt_mask_layers.move(idx, idx + 1)
        obj.sculpt_mask_layers_index = idx + 1

        return {'FINISHED'}


def _assign_mask_to_layer(obj, idx):
    """Copy current sculpt mask into stored layer attribute."""
    mesh = obj.data
    item = obj.sculpt_mask_layers[idx]
    layer_attr_name = ensure_layer_attr_for_item(obj, item)

    dst = mesh.attributes[layer_attr_name]
    src = get_or_create_sculpt_mask_attr(mesh)

    status = copy_attr_values(src, dst, len(mesh.vertices), allow_mismatch=True)
    mesh.update()
    return status


class SCULPTMASK_OT_assign(Operator):
    bl_idname = "sculptmask.assign"
    bl_label = "Assign Mask To Layer"
    bl_description = "Store the current sculpt mask into the selected layer"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        mesh = obj.data
        item = obj.sculpt_mask_layers[idx]
        layer_attr_name = ensure_layer_attr_for_item(obj, item)

        dst = mesh.attributes[layer_attr_name]
        src = get_or_create_sculpt_mask_attr(mesh)

        if attr_max_abs(dst) > EPS and (not attrs_equal(src, dst)):
            bpy.ops.sculptmask.assign_overwrite('INVOKE_DEFAULT', layer_index=idx)
            return {'CANCELLED'}

        return self.execute(context)

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        try:
            status = _assign_mask_to_layer(obj, idx)
            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch: assigned with best effort (extra verts set to 0).")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SCULPTMASK_OT_assign_overwrite(Operator):
    bl_idname = "sculptmask.assign_overwrite"
    bl_label = "Replace stored mask with current sculpt mask?"
    bl_description = "Confirm overwrite of the selected mask layer"
    bl_options = {'REGISTER', 'UNDO'}

    layer_index: IntProperty(default=-1)

    def invoke(self, context, event):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}
        if self.layer_index < 0 or self.layer_index >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "Invalid layer index.")
            return {'CANCELLED'}
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}
        idx = self.layer_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            return {'CANCELLED'}

        try:
            status = _assign_mask_to_layer(obj, idx)
            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch: assigned with best effort (extra verts set to 0).")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "No layer selected.")
            return {'CANCELLED'}

        mesh = obj.data
        item = obj.sculpt_mask_layers[idx]

        if not item.attr_name or item.attr_name not in mesh.attributes:
            self.report({'ERROR'}, "Selected layer has no stored attribute (it may have been deleted).")
            return {'CANCELLED'}

        try:
            src = mesh.attributes[item.attr_name]
            dst = get_or_create_sculpt_mask_attr(mesh)

            status = copy_attr_values(src, dst, len(mesh.vertices), allow_mismatch=True)
            mesh.update()

            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch: set with best effort (extra verts set to 0).")
            return {'FINISHED'}

        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SCULPTMASK_OT_preview_toggle(Operator):
    """Apply a stored layer to the current sculpt mask."""
    bl_idname = "sculptmask.preview_toggle"
    bl_label = "Apply Mask Layer"
    bl_description = "Apply the selected layer to the current sculpt mask (Shift: add, Ctrl: subtract)"
    bl_options = {'REGISTER', 'UNDO'}

    layer_index: IntProperty(default=-1)
    op_mode: IntProperty(default=0)

    def invoke(self, context, event):
        if event and event.shift:
            self.op_mode = 1
        elif event and event.ctrl:
            self.op_mode = 2
        else:
            self.op_mode = 0
        return self.execute(context)

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}

        idx = self.layer_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            return {'CANCELLED'}

        mesh = obj.data
        item = obj.sculpt_mask_layers[idx]

        if not item.attr_name or item.attr_name not in mesh.attributes:
            self.report({'ERROR'}, "This layer has no stored mask. Use Assign first.")
            return {'CANCELLED'}

        src = mesh.attributes[item.attr_name]
        dst = get_or_create_sculpt_mask_attr(mesh)

        if self.op_mode == 0:
            copy_attr_values(src, dst, len(mesh.vertices), allow_mismatch=True)
            mesh.update()
            return {'FINISHED'}

        # I do add/sub here because Blender doesn't have a simple operator for this.
        n = min(len(src.data), len(dst.data), len(mesh.vertices))
        buf_src = [0.0] * len(src.data)
        buf_dst = [0.0] * len(dst.data)
        src.data.foreach_get("value", buf_src)
        dst.data.foreach_get("value", buf_dst)

        if self.op_mode == 1:
            for i in range(n):
                v = buf_dst[i] + buf_src[i]
                if v < 0.0:
                    v = 0.0
                elif v > 1.0:
                    v = 1.0
                buf_dst[i] = v
        else:
            for i in range(n):
                v = buf_dst[i] - buf_src[i]
                if v < 0.0:
                    v = 0.0
                elif v > 1.0:
                    v = 1.0
                buf_dst[i] = v

        dst.data.foreach_set("value", buf_dst)
        mesh.update()
        return {'FINISHED'}


class SCULPTMASK_OT_mask_invert(Operator):
    bl_idname = "sculptmask.mask_invert"
    bl_label = "Invert"
    bl_description = "Invert the current sculpt mask"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return active_mesh_object(context) is not None and context.mode == 'SCULPT'

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}
        if context.mode != 'SCULPT':
            self.report({'ERROR'}, "Switch to Sculpt mode.")
            return {'CANCELLED'}
        mesh = obj.data
        attr = get_or_create_sculpt_mask_attr(mesh)
        n = len(attr.data)
        if n == 0:
            return {'CANCELLED'}
        buf = [0.0] * n
        attr.data.foreach_get("value", buf)
        # Not sure if Blender clamps this internally, so do it here.
        for i in range(n):
            v = 1.0 - buf[i]
            if v < 0.0:
                v = 0.0
            elif v > 1.0:
                v = 1.0
            buf[i] = v
        attr.data.foreach_set("value", buf)
        mesh.update()
        return {'FINISHED'}


class SCULPTMASK_OT_mask_filter(Operator):
    bl_idname = "sculptmask.mask_filter"
    bl_label = "Mask Filter"
    bl_description = "Apply a mask filter to the current sculpt mask"
    bl_options = {'REGISTER'}

    filter_type: bpy.props.StringProperty(default="SMOOTH")

    @classmethod
    def poll(cls, context):
        return active_mesh_object(context) is not None and context.mode == 'SCULPT'

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}
        if context.mode != 'SCULPT':
            self.report({'ERROR'}, "Switch to Sculpt mode.")
            return {'CANCELLED'}
        # I left this as the Blender operator because it works and handles all modes.
        bpy.ops.sculpt.mask_filter(filter_type=self.filter_type)
        return {'FINISHED'}


class SCULPTMASK_OT_new_layer_from_mask(Operator):
    bl_idname = "sculptmask.new_layer_from_mask"
    bl_label = "New Layer From Mask"
    bl_description = "Create a new layer from the current sculpt mask"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "Select a mesh object.")
            return {'CANCELLED'}

        item = obj.sculpt_mask_layers.add()
        item.name = f"Mask {len(obj.sculpt_mask_layers)}"

        try:
            ensure_layer_attr_for_item(obj, item)
            status = _assign_mask_to_layer(obj, len(obj.sculpt_mask_layers) - 1)
            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch: assigned with best effort (extra verts set to 0).")
        except Exception as e:
            self.report({'ERROR'}, str(e))
            obj.sculpt_mask_layers.remove(len(obj.sculpt_mask_layers) - 1)
            return {'CANCELLED'}

        obj.sculpt_mask_layers_index = len(obj.sculpt_mask_layers) - 1
        obj.data.update()
        return {'FINISHED'}


CLASSES = (
    SCULPTMASK_OT_add_layer,
    SCULPTMASK_OT_remove_layer,
    SCULPTMASK_OT_move_layer_up,
    SCULPTMASK_OT_move_layer_down,
    SCULPTMASK_OT_assign,
    SCULPTMASK_OT_assign_overwrite,
    SCULPTMASK_OT_preview_toggle,
    SCULPTMASK_OT_mask_invert,
    SCULPTMASK_OT_mask_filter,
    SCULPTMASK_OT_new_layer_from_mask,
)
