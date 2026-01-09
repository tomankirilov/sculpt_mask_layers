import bpy
from bpy.types import PropertyGroup
from bpy.props import StringProperty

from .utils import (
    active_mesh_object,
    unique_attr_name,
    sanitize_layer_name,
    ensure_float_point_attr,
    rename_mesh_attribute,
    ATTR_PREFIX,
)


class SculptMaskLayerItem(PropertyGroup):
    name: StringProperty(name="Name", default="Mask")
    attr_name: StringProperty(name="Attribute", default="")


def ensure_layer_attr_for_item(obj, item):
    mesh = obj.data
    if not item.attr_name:
        # I do the name here because name updates don't always fire
        # when the item is created.
        base = unique_attr_name(mesh, ATTR_PREFIX + sanitize_layer_name(item.name))
        item.attr_name = base

    ensure_float_point_attr(mesh, item.attr_name)
    return item.attr_name


def layer_name_update(self, context):
    obj = active_mesh_object(context)
    if not obj:
        return

    mesh = obj.data
    if not self.attr_name:
        self.attr_name = unique_attr_name(mesh, ATTR_PREFIX + sanitize_layer_name(self.name))
        ensure_float_point_attr(mesh, self.attr_name)
        mesh.update()
        return

    # Not sure if Blender allows renaming directly in all cases,
    # so we do it carefully in utils.rename_mesh_attribute.
    desired = ATTR_PREFIX + sanitize_layer_name(self.name)
    desired = unique_attr_name(mesh, desired) if desired != self.attr_name else desired

    new_name = rename_mesh_attribute(mesh, self.attr_name, desired)
    self.attr_name = new_name
    mesh.update()


SculptMaskLayerItem.__annotations__["name"] = StringProperty(
    name="Name", default="Mask", update=layer_name_update
)


CLASSES = (
    SculptMaskLayerItem,
)
