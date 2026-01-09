import bpy
from bpy.types import AddonPreferences, Operator, Panel, UIList
from bpy.props import BoolProperty

from .utils import active_mesh_object

ADDON_ID = __package__ if __package__ else "sculpt_mask_layers"

def draw_mask_layers(layout, context):
    # Keeping this in one function so popup + sidebar stay in sync.
    obj = context.object

    row = layout.row()
    row.template_list(
        "SCULPTMASK_UL_layers",
        "",
        obj,
        "sculpt_mask_layers",
        obj,
        "sculpt_mask_layers_index",
        rows=7,
    )

    col = row.column(align=True)
    col.operator("sculptmask.add_layer", text="", icon='ADD')
    col.operator("sculptmask.remove_layer", text="", icon='REMOVE')
    col.separator()
    col.operator("sculptmask.move_layer_up", text="", icon='TRIA_UP')
    col.operator("sculptmask.move_layer_down", text="", icon='TRIA_DOWN')

    layout.separator()

    # Main action block. I prefer keeping these together so the user sees them.
    col = layout.column(align=True)
    col.operator("sculptmask.assign", text="Assign to selected layer", icon='EXPORT')
    col.operator("sculptmask.new_layer_from_mask", text="New layer from mask", icon='MOD_MASK')
    col.operator("sculptmask.duplicate_layer", text="Duplicate selected layer", icon='DUPLICATE')

    layout.separator()
    layout.label(text="Mask Operators")

    col = layout.column(align=True)

    row = col.row(align=True)
    row.operator("sculptmask.mask_invert", text="Invert", icon='ARROW_LEFTRIGHT')
    row.operator("sculptmask.mask_clear", text="Clear", icon='X')

    row = col.row(align=True)
    op = row.operator("sculptmask.mask_filter", text="Smooth", icon='MOD_SMOOTH')
    op.filter_type = 'SMOOTH'
    op = row.operator("sculptmask.mask_filter", text="Sharpen", icon='SHARPCURVE')
    op.filter_type = 'SHARPEN'

    row = col.row(align=True)
    op = row.operator("sculptmask.mask_filter", text="Grow", icon='ADD')
    op.filter_type = 'GROW'
    op = row.operator("sculptmask.mask_filter", text="Shrink", icon='REMOVE')
    op.filter_type = 'SHRINK'

    row = col.row(align=True)
    op = row.operator("sculptmask.mask_filter", text="Increase Contrast", icon='ADD')
    op.filter_type = 'CONTRAST_INCREASE'
    op = row.operator("sculptmask.mask_filter", text="Decrease Contrast", icon='REMOVE')
    op.filter_type = 'CONTRAST_DECREASE'


class SCULPTMASK_UL_layers(UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        op = row.operator("sculptmask.preview_toggle", text="", icon='MOD_MASK', emboss=False)
        op.layer_index = index
        row.prop(item, "name", text="", emboss=False)


class SCULPTMASK_OT_popup(Operator):
    bl_idname = "sculptmask.popup"
    bl_label = "Mask Layers"
    bl_description = "Manage sculpt mask layers (store/restore)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return active_mesh_object(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=440)

    def draw(self, context):
        draw_mask_layers(self.layout, context)

    def execute(self, context):
        return {'FINISHED'}


def sculpt_mask_menu_func(self, context):
    self.layout.separator()
    self.layout.operator("sculptmask.popup", text="Mask Layers...", icon='MOD_MASK')


class SculptMaskLayersPreferences(AddonPreferences):
    bl_idname = ADDON_ID

    show_n_panel: BoolProperty(
        name="Add to Sidebar",
        description="Display the Mask Layers UI in the 3D View N panel (Sculpt mode only)",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "show_n_panel")


class SCULPTMASK_PT_panel(Panel):
    bl_label = "Mask Layers"
    bl_idname = "SCULPTMASK_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Mask Layers"
    @classmethod
    def poll(cls, context):
        if context.mode != 'SCULPT':
            return False
        addon = context.preferences.addons.get(ADDON_ID)
        if not addon:
            return False
        return bool(getattr(addon.preferences, "show_n_panel", False))

    def draw(self, context):
        draw_mask_layers(self.layout, context)


def append_menu_hooks():
    for name in ("VIEW3D_MT_mask", "VIEW3D_MT_sculpt_mask"):
        mt = getattr(bpy.types, name, None)
        if mt is not None:
            try:
                mt.append(sculpt_mask_menu_func)
            except Exception:
                pass


def remove_menu_hooks():
    for name in ("VIEW3D_MT_mask", "VIEW3D_MT_sculpt_mask"):
        mt = getattr(bpy.types, name, None)
        if mt is not None:
            try:
                mt.remove(sculpt_mask_menu_func)
            except Exception:
                pass


CLASSES = (
    SculptMaskLayersPreferences,
    SCULPTMASK_UL_layers,
    SCULPTMASK_OT_popup,
    SCULPTMASK_PT_panel,
)

