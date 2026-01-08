bl_info = {
    "name": "Sculpt Mask Layers",
    "author": "Tomanov",
    "version": (1, 1, 4),
    "blender": (5, 0, 0),
    "location": "Sculpt Mode > Mask menu",
    "description": "Store/restore sculpt masks as per-object mask layers",
    "category": "Sculpt",
}

import bpy
from bpy.types import Operator, PropertyGroup, UIList
from bpy.props import CollectionProperty, IntProperty, StringProperty, BoolProperty

# Just a few global constants
SCULPT_MASK_ATTR = ".sculpt_mask"
ATTR_PREFIX = "mask__"
EPS = 1e-6  # floating point tolerance – probably good enough?


# ---------------------------------------------------
# General Utility Stuff
# ---------------------------------------------------

def active_mesh_object(ctx):
    # Get the currently active mesh object or bail
    obj = ctx.object
    if not obj or obj.type != 'MESH':
        return None
    return obj


def ensure_float_point_attr(mesh, name):
    # Add or verify a float attribute at point domain
    attr = mesh.attributes.get(name)
    if not attr:
        attr = mesh.attributes.new(name=name, type='FLOAT', domain='POINT')
    elif attr.domain != 'POINT' or attr.data_type != 'FLOAT':
        raise RuntimeError(f"Oops: '{name}' exists but is not a FLOAT/POINT attribute.")
    return attr


def get_or_create_sculpt_mask_attr(mesh):
    # Always try to use the standard .sculpt_mask attribute
    attr = mesh.attributes.get(SCULPT_MASK_ATTR)
    if not attr:
        attr = ensure_float_point_attr(mesh, SCULPT_MASK_ATTR)
        zero_vals = [0.0] * len(mesh.vertices)
        attr.data.foreach_set("value", zero_vals)
    return attr


def sanitize_layer_name(name: str) -> str:
    # Clean layer name to be safe as an attribute name
    raw = (name or "").strip().lower().replace(" ", "_")
    safe = "".join(c for c in raw if c.isalnum() or c == "_")
    return safe or "mask"


def unique_attr_name(mesh, base):
    # Ensure name doesn't collide
    names = {a.name for a in mesh.attributes}
    if base not in names:
        return base
    idx = 1
    while f"{base}_{idx:02d}" in names:
        idx += 1
    return f"{base}_{idx:02d}"


def rename_mesh_attribute(mesh, old_name, new_name):
    # Try renaming, fallback to copy-remove if needed
    if not old_name:
        return new_name
    src = mesh.attributes.get(old_name)
    if not src:
        return new_name
    if new_name in mesh.attributes and new_name != old_name:
        new_name = unique_attr_name(mesh, new_name)
    try:
        src.name = new_name
    except Exception:
        # Yep, Blender didn't like the rename – we'll do it manually
        dest = ensure_float_point_attr(mesh, new_name)
        vals = [0.0] * len(src.data)
        src.data.foreach_get("value", vals)
        dest.data.foreach_set("value", vals)
        mesh.attributes.remove(src)
    return new_name


def copy_attr_values(source, target, count, allow_mismatch=False):
    # Naive copy attempt
    src_len, dst_len = len(source.data), len(target.data)
    if src_len == dst_len == count:
        buf = [0.0] * count
        source.data.foreach_get("value", buf)
        target.data.foreach_set("value", buf)
        return "OK"
    if not allow_mismatch:
        raise RuntimeError("Vertex count mismatch.")
    # Partial copy in mismatch cases
    buf = [0.0] * src_len
    source.data.foreach_get("value", buf)
    for i in range(dst_len):
        target.data[i].value = buf[i] if i < src_len else 0.0
    return "MISMATCH"


def attr_max_abs(attr):
    # Get max absolute value in attr
    n = len(attr.data)
    if not n:
        return 0.0
    values = [0.0] * n
    attr.data.foreach_get("value", values)
    max_val = max(abs(v) for v in values)
    return max_val


def attrs_equal(a, b):
    # Quick compare
    if len(a.data) != len(b.data):
        return False
    vals_a = [0.0] * len(a.data)
    vals_b = [0.0] * len(b.data)
    a.data.foreach_get("value", vals_a)
    b.data.foreach_get("value", vals_b)
    return vals_a == vals_b


# ---------------------------------------------------
# Per-Object Mask Layer Data
# ---------------------------------------------------

class SculptMaskLayerItem(PropertyGroup):
    name: StringProperty(name="Name", default="Mask")
    attr_name: StringProperty(name="Attribute", default="")


def ensure_layer_attr_for_item(obj, item):
    mesh = obj.data
    if not item.attr_name:
        base = unique_attr_name(mesh, ATTR_PREFIX + sanitize_layer_name(item.name))
        item.attr_name = base
    ensure_float_point_attr(mesh, item.attr_name)
    return item.attr_name


def layer_name_update(self, ctx):
    obj = active_mesh_object(ctx)
    if not obj:
        return
    mesh = obj.data
    desired = ATTR_PREFIX + sanitize_layer_name(self.name)
    if not self.attr_name:
        self.attr_name = unique_attr_name(mesh, desired)
        ensure_float_point_attr(mesh, self.attr_name)
        mesh.update()
        return
    if desired != self.attr_name:
        desired = unique_attr_name(mesh, desired)
        self.attr_name = rename_mesh_attribute(mesh, self.attr_name, desired)
        mesh.update()


SculptMaskLayerItem.__annotations__["name"] = StringProperty(
    name="Name", default="Mask", update=layer_name_update
)


# ---------------------------------------------------
# Operator Definitions
# ---------------------------------------------------

class SCULPTMASK_OT_add_layer(Operator):
    bl_idname = "sculptmask.add_layer"
    bl_label = "Add Mask Layer"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            self.report({'ERROR'}, "You need to select a mesh.")
            return {'CANCELLED'}

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
            self.report({'ERROR'}, "No mesh selected.")
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            self.report({'ERROR'}, "No valid layer selected.")
            return {'CANCELLED'}

        attr_name = obj.sculpt_mask_layers[idx].attr_name
        obj.sculpt_mask_layers.remove(idx)
        obj.sculpt_mask_layers_index = min(idx, len(obj.sculpt_mask_layers) - 1)

        if attr_name:
            attr = obj.data.attributes.get(attr_name)
            if attr:
                obj.data.attributes.remove(attr)

        obj.data.update()
        return {'FINISHED'}

class SCULPTMASK_OT_assign(Operator):
    bl_idname = "sculptmask.assign"
    bl_label = "Assign"
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
        dst = mesh.attributes.get(ensure_layer_attr_for_item(obj, item))
        src = get_or_create_sculpt_mask_attr(mesh)

        if attr_max_abs(dst) > EPS and not attrs_equal(src, dst):
            bpy.ops.sculptmask.assign_overwrite('INVOKE_DEFAULT', layer_index=idx)
            return {'CANCELLED'}

        return self.execute(context)

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}

        idx = obj.sculpt_mask_layers_index
        if idx < 0 or idx >= len(obj.sculpt_mask_layers):
            return {'CANCELLED'}

        try:
            status = copy_attr_values(
                get_or_create_sculpt_mask_attr(obj.data),
                obj.data.attributes[ensure_layer_attr_for_item(obj, obj.sculpt_mask_layers[idx])],
                len(obj.data.vertices),
                allow_mismatch=True
            )
            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch: assigned with best effort.")
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
        if not obj or self.layer_index < 0 or self.layer_index >= len(obj.sculpt_mask_layers):
            return {'CANCELLED'}
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        obj = active_mesh_object(context)
        if not obj:
            return {'CANCELLED'}
        idx = self.layer_index
        try:
            status = copy_attr_values(
                get_or_create_sculpt_mask_attr(obj.data),
                obj.data.attributes[ensure_layer_attr_for_item(obj, obj.sculpt_mask_layers[idx])],
                len(obj.data.vertices),
                allow_mismatch=True
            )
            if status == "MISMATCH":
                self.report({'WARNING'}, "Topology mismatch handled.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class SCULPTMASK_OT_set(Operator):
    bl_idname = "sculptmask.set"
    bl_label = "Set"
    bl_description = "Set the current sculpt mask from the selected layer"
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
        mesh = obj.data

        if not item.attr_name or item.attr_name not in mesh.attributes:
            self.report({'ERROR'}, "Selected layer is missing attribute.")
            return {'CANCELLED'}

        try:
            status = copy_attr_values(
                mesh.attributes[item.attr_name],
                get_or_create_sculpt_mask_attr(mesh),
                len(mesh.vertices),
                allow_mismatch=True
            )
            mesh.update()
            if status == "MISMATCH":
                self.report({'WARNING'}, "Partial mask set (vertex mismatch).")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


# ----------------------------
# UI List & Popup UI
# ----------------------------

class SCULPTMASK_UL_layers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon='MOD_MASK')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='MOD_MASK')

class SCULPTMASK_OT_popup(Operator):
    bl_idname = "sculptmask.popup"
    bl_label = "Mask Layers"
    bl_description = "Manage sculpt mask layers (store/restore)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return active_mesh_object(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        obj = context.object

        row = layout.row()
        row.template_list("SCULPTMASK_UL_layers", "", obj, "sculpt_mask_layers", obj, "sculpt_mask_layers_index", rows=6)

        col = row.column(align=True)
        col.operator("sculptmask.add_layer", text="", icon='ADD')
        col.operator("sculptmask.remove_layer", text="", icon='REMOVE')

        layout.separator()

        row = layout.row(align=True)
        row.operator("sculptmask.set", text="Set", icon='IMPORT')
        row.operator("sculptmask.assign", text="Assign", icon='EXPORT')

    def execute(self, context):
        return {'FINISHED'}


# ----------------------------
# Menu Hook & Registration
# ----------------------------

def sculpt_mask_menu_func(self, context):
    self.layout.separator()
    self.layout.operator("sculptmask.popup", text="Mask Layers...", icon='MOD_MASK')

def _append_menu_hooks():
    for name in ("VIEW3D_MT_mask", "VIEW3D_MT_sculpt_mask"):
        mt = getattr(bpy.types, name, None)
        if mt is not None:
            try:
                mt.append(sculpt_mask_menu_func)
            except Exception:
                pass

def _remove_menu_hooks():
    for name in ("VIEW3D_MT_mask", "VIEW3D_MT_sculpt_mask"):
        mt = getattr(bpy.types, name, None)
        if mt is not None:
            try:
                mt.remove(sculpt_mask_menu_func)
            except Exception:
                pass

classes = (
    SculptMaskLayerItem,
    SCULPTMASK_OT_add_layer,
    SCULPTMASK_OT_remove_layer,
    SCULPTMASK_OT_assign,
    SCULPTMASK_OT_assign_overwrite,
    SCULPTMASK_OT_set,
    SCULPTMASK_UL_layers,
    SCULPTMASK_OT_popup,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Object.sculpt_mask_layers = CollectionProperty(type=SculptMaskLayerItem)
    bpy.types.Object.sculpt_mask_layers_index = IntProperty(default=0)

    _append_menu_hooks()

    print("[Sculpt Mask Layers] registered v1.1.4")

def unregister():
    _remove_menu_hooks()

    del bpy.types.Object.sculpt_mask_layers
    del bpy.types.Object.sculpt_mask_layers_index

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    print("[Sculpt Mask Layers] unregistered")

if __name__ == "__main__":
    register()
