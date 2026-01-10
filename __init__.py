import bpy
from bpy.props import CollectionProperty, IntProperty

from . import props, operators, ui

# Keep the register list together so I don't forget a class later.
all_classes = props.CLASSES + operators.CLASSES + ui.CLASSES


def register():
    for c in all_classes:
        bpy.utils.register_class(c)

    # These are on Object because that's where the mesh data sits anyway.
    bpy.types.Object.sculpt_mask_layers = CollectionProperty(type=props.SculptMaskLayerItem)
    bpy.types.Object.sculpt_mask_layers_index = IntProperty(default=0)

    ui.append_menu_hooks()

    # Simple log, helpful when Blender silently fails to load add-ons.
    print("[Sculpt Mask Layers] registered v1.2.1")


def unregister():
    ui.remove_menu_hooks()

    del bpy.types.Object.sculpt_mask_layers
    del bpy.types.Object.sculpt_mask_layers_index

    for c in reversed(all_classes):
        bpy.utils.unregister_class(c)

    print("[Sculpt Mask Layers] unregistered")


if __name__ == "__main__":
    register()
