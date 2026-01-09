import bpy

SCULPT_MASK_ATTR = ".sculpt_mask"
ATTR_PREFIX = "mask__"

# Small value so we don't accidentally compare against floats that are "almost zero".
EPS = 1e-6


def active_mesh_object(context):
    obj = context.object
    if not obj or obj.type != 'MESH':
        return None
    return obj


def ensure_float_point_attr(mesh, name):
    attr = mesh.attributes.get(name)
    if attr is None:
        attr = mesh.attributes.new(name=name, type='FLOAT', domain='POINT')
    else:
        if attr.domain != 'POINT' or attr.data_type != 'FLOAT':
            raise RuntimeError(f"Attribute '{name}' exists but is not FLOAT/POINT.")
    return attr


def get_or_create_sculpt_mask_attr(mesh):
    attr = mesh.attributes.get(SCULPT_MASK_ATTR)
    if attr is None:
        attr = ensure_float_point_attr(mesh, SCULPT_MASK_ATTR)
        # If it doesn't exist Blender doesn't always init values,
        # so I just zero them here.
        zeros = [0.0] * len(mesh.vertices)
        attr.data.foreach_set("value", zeros)
    return attr


def sanitize_layer_name(name: str) -> str:
    s = (name or "").strip().lower().replace(" ", "_")
    s2 = []
    for ch in s:
        if ch.isalnum() or ch == "_":
            s2.append(ch)
    s = "".join(s2)
    return s or "mask"


def unique_attr_name(mesh, base):
    existing = {a.name for a in mesh.attributes}
    if base not in existing:
        return base
    i = 1
    while f"{base}_{i:02d}" in existing:
        i += 1
    return f"{base}_{i:02d}"


def rename_mesh_attribute(mesh, old_name: str, new_name: str) -> str:
    """Rename a mesh attribute if it exists; returns the final name."""
    if not old_name:
        return new_name
    attr = mesh.attributes.get(old_name)
    if not attr:
        return new_name

    if new_name in mesh.attributes and new_name != old_name:
        new_name = unique_attr_name(mesh, new_name)

    try:
        attr.name = new_name
    except Exception:
        # I hit weird cases where rename throws, so do the slow copy.
        src = attr
        dst = ensure_float_point_attr(mesh, new_name)
        buf = [0.0] * len(src.data)
        src.data.foreach_get("value", buf)
        dst.data.foreach_set("value", buf)
        mesh.attributes.remove(src)

    return new_name


def copy_attr_values(src_attr, dst_attr, vert_count, allow_mismatch=False):
    src_len = len(src_attr.data)
    dst_len = len(dst_attr.data)

    if (src_len == vert_count) and (dst_len == vert_count):
        buf = [0.0] * vert_count
        src_attr.data.foreach_get("value", buf)
        dst_attr.data.foreach_set("value", buf)
        return "OK"

    if not allow_mismatch:
        raise RuntimeError("Vertex count mismatch; cannot copy safely.")

    # Best effort mode for mismatched topo.
    n = min(src_len, dst_len, vert_count)
    buf = [0.0] * src_len
    src_attr.data.foreach_get("value", buf)

    for i in range(dst_len):
        dst_attr.data[i].value = buf[i] if i < n else 0.0

    return "MISMATCH"




def attr_max_abs(attr) -> float:
    n = len(attr.data)
    if n == 0:
        return 0.0
    buf = [0.0] * n
    attr.data.foreach_get("value", buf)
    m = 0.0
    for v in buf:
        av = v if v >= 0 else -v
        if av > m:
            m = av
    return m


def attrs_equal(a, b) -> bool:
    if len(a.data) != len(b.data):
        return False
    n = len(a.data)
    buf_a = [0.0] * n
    buf_b = [0.0] * n
    a.data.foreach_get("value", buf_a)
    b.data.foreach_get("value", buf_b)
    return buf_a == buf_b
