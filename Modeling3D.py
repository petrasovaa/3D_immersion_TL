import bpy
import os
import math
import bmesh

from .settings import getSettings

from bpy.props import (
    StringProperty,
)

import bpy.utils.previews
from mathutils import Vector

watchName = "Watch"
terrainFile = "terrain.tif"
CRS = "EPSG:3358"


class Prefs:
    def __init__(self):
        folder = getSettings()["folder"]
        self.watchFolder = os.path.join(folder, watchName)
        self.terrainPath = os.path.join(self.watchFolder, terrainFile)
        self.terrain_texture_path = os.path.join(
            folder, getSettings()["terrain"]["grass_texture_file"]
        )
        self.terrain_sides_texture_path = os.path.join(
            folder, getSettings()["terrain"]["sides_texture_file"]
        )
        self.world_texture_path = os.path.join(
            folder, getSettings()["world"]["texture_file"]
        )
        self.CRS = "EPSG:" + getSettings()["CRS"]
        self.timer = getSettings()["timer"]


def assign_material(object_name, material_name):
    obj = bpy.data.objects[object_name]
    material = bpy.data.materials.get(material_name)
    # Assign it to object
    obj.data.materials.append(material)
    num_mat = len(obj.data.materials)
    if num_mat > 1:
        obj.active_material_index = num_mat - 1
        bpy.ops.object.material_slot_assign()


def create_terrain_material(name, texture_path, sides):
    # create material
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes["Principled BSDF"]
    output = nodes["Material Output"]
    tex_image = nodes.new("ShaderNodeTexImage")
    tex_image.image = bpy.data.images.load(texture_path)
    coor = nodes.new("ShaderNodeTexCoord")

    mat.node_tree.links.new(
        coor.outputs["Object" if sides else "UV"], tex_image.inputs["Vector"]
    )
    # Link image to Shading node color
    mat.node_tree.links.new(bsdf.inputs["Base Color"], tex_image.outputs["Color"])
    # Link shading node to surface of output material
    mat.node_tree.links.new(output.inputs["Surface"], bsdf.outputs["BSDF"])


def create_world(name, texture_path):
    world = bpy.data.worlds.new(name=name)
    world.use_nodes = True
    nodes = world.node_tree.nodes
    coor = nodes.new("ShaderNodeTexCoord")
    tex_image = nodes.new("ShaderNodeTexImage")
    tex_image.image = bpy.data.images.load(texture_path)
    bg = world.node_tree.nodes["Background"]
    out = world.node_tree.nodes["World Output"]
    world.node_tree.links.new(coor.outputs["Window"], tex_image.inputs["Vector"])
    world.node_tree.links.new(tex_image.outputs["Color"], bg.inputs["Color"])
    world.node_tree.links.new(bg.outputs["Background"], out.inputs["Surface"])
    return world


def addSide(objName, mat):
    ter = bpy.data.objects[objName]
    ter.select_set(True)

    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="DESELECT")
    me = ter.data

    if ter.mode == "EDIT":
        bm = bmesh.from_edit_mesh(ter.data)
        vertices = bm.verts

    else:
        vertices = ter.data.vertices

    verts = [ter.matrix_world @ vert.co for vert in vertices]

    dic = {"x": [], "y": [], "z": []}
    for vert in verts:
        if not math.isnan(vert[0]):
            dic["x"].append(vert[0])
            dic["y"].append(vert[1])
            dic["z"].append(vert[2])

    xmin = min(dic["x"])
    xmax = max(dic["x"])
    ymin = min(dic["y"])
    ymax = max(dic["y"])

    tres = 3

    for vert in vertices:
        if vert.co[0] < xmin + tres and vert.co[0] > xmin - tres:
            vert.select_set(True)
            vert.co[2] = -50

        elif vert.co[1] < ymin + tres and vert.co[1] > ymin - tres:
            vert.select_set(True)
            vert.co[2] = -50

        elif vert.co[0] < xmax + tres and vert.co[0] > xmax - tres:
            vert.select_set(True)
            vert.co[2] = -50
        elif vert.co[1] < ymax + tres and vert.co[1] > ymax - tres:
            vert.select_set(True)
            vert.co[2] = -50

    bmesh.update_edit_mesh(me, True)

    def NormalInDirection(normal, direction, limit=0.5):
        return direction.dot(normal) > limit

    def GoingUp(normal, limit=0.5):
        return NormalInDirection(normal, Vector((0, 0, 1)), limit)

    def GoingDown(normal, limit=0.5):
        return NormalInDirection(normal, Vector((0, 0, -1)), limit)

    def GoingSide(normal, limit=0.2):
        return GoingUp(normal, limit) is False and GoingDown(normal, limit) is False

    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)

    # Selects faces going side

    for face in ter.data.polygons:
        face.select = GoingSide(face.normal)

    bpy.ops.object.mode_set(mode="EDIT", toggle=False)

    assign_material(objName, "terrain_sides_material")
    bpy.ops.object.material_slot_assign()

    bpy.ops.object.mode_set(mode="OBJECT", toggle=False)


def smooth(object_name, factor=2, iterations=4):
    """Smooths a mesh by flattening the angles between adjacent faces in it.
    It smooths without subdividing the mesh - the number of vertices remains
    the same.
    Keyword arguments:
    object_name -- name of the object
    factor -- The factor to control the smoothing amount. Higher values will
    increase the effect.
    iterations -- number of smoothing iterations, equivalent to executing the
    smooth tool multiple times.
    """

    select_only(object_name)
    bpy.ops.object.modifier_add(type="SMOOTH")
    modifier = bpy.data.objects[object_name].modifiers["Smooth"]
    modifier.factor = factor
    modifier.iterations = iterations


def select_only(object_name):
    """ selects the passed object"""

    if bpy.data.objects.get(object_name):
        obj = bpy.data.objects[object_name]
        if obj.hide_get():
            obj.hide_set(False)
        # Deselect all
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        return obj
    return None


def remove_object(object_name):
    obj = select_only(object_name)
    if obj:
        bpy.ops.object.delete()


class Adapt:
    def __init__(self):
        self.plane = "terrain"
        self.treePatch = "TreePatch"
        self.trail = "trail"
        self.indexlist = []
        self.importedlist = []
        self.pointlist = []
        self.texture = "texture.tif"
        self.water = "water"

    def terrainChange(self, path, CRS):
        # Delete terrain object
        remove_object(self.plane)
        bpy.ops.importgis.georaster(
            filepath=path, importMode="DEM", subdivision="mesh", rastCRS=CRS
        )
        select_only(self.plane)
        bpy.ops.object.convert(target="MESH")
        assign_material(self.plane, material_name="terrain_material")
        addSide(self.plane, "terrain_material")

        os.remove(path)

        return "finished"


class ModalTimerOperator(bpy.types.Operator):
    """Operator which interatively runs from a timer"""

    bl_idname = "wm.modal_timer_operator"
    bl_label = "Modal Timer Operator"
    _timer = 0
    _timer_count = 0

    def modal(self, context, event):
        if event.type in {"RIGHTMOUSE", "ESC"}:
            return {"CANCELLED"}

        # this condition encomasses all the actions required for watching
        # the folder and related file/object operations .

        if event.type == "TIMER":

            if self._timer.time_duration != self._timer_count:
                self._timer_count = self._timer.time_duration
                fileList = os.listdir(self.prefs.watchFolder)

                if terrainFile in fileList:
                    self.adapt.terrainChange(self.prefs.terrainPath, self.prefs.CRS)
                    self.adaptMode = "TERRAIN"

        return {"PASS_THROUGH"}

    def execute(self, context):

        # bpy.context.space_data.show_manipulator = False
        wm = context.window_manager
        wm.modal_handler_add(self)

        self.treePatch = "TreePatch"
        self.emptyTree = "empty.txt"
        self.adaptMode = None
        self.prefs = Prefs()
        self.adapt = Adapt()
        self.adapt.realism = "High"
        self._timer = wm.event_timer_add(self.prefs.timer, window=context.window)

        for file in os.listdir(self.prefs.watchFolder):
            try:
                os.remove(os.path.join(self.prefs.watchFolder, file))
            except:
                print("Could not remove file")

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        wm = context.window_manager
        wm.event_timer_remove(self._timer)


# Panel
class TL_PT_GUI(bpy.types.Panel):
    # Create a Panel in the Tool Shelf
    bl_category = "Tangible Landscape"
    bl_label = "Tangibe Landscape "
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"

    # Draw
    def draw(self, context):
        layout = self.layout
        box = layout.box()
        box.label(text="System options")
        row = box.row(align=True)
        row.operator("tl.assets", text="Initialize Assets", icon="MESH_CYLINDER")
        row = box.row(align=True)
        row.operator(
            "wm.modal_timer_operator", text="Turn on Watch Mode", icon="GHOST_ENABLED"
        )


class TL_OT_Assets(bpy.types.Operator):
    bl_idname = "tl.assets"
    bl_label = "Asset initialization"

    def execute(self, context):
        prefs = Prefs()
        create_terrain_material(
            name="terrain_material",
            texture_path=prefs.terrain_texture_path,
            sides=False,
        )
        create_terrain_material(
            name="terrain_sides_material",
            texture_path=prefs.terrain_sides_texture_path,
            sides=True,
        )
        create_world(name="TL_world", texture_path=prefs.world_texture_path)
        bpy.context.scene.world = bpy.data.worlds.get("TL_world")
        bpy.context.space_data.shading.type = "RENDERED"
        return {"FINISHED"}


class MessageOperator(bpy.types.Operator):
    bl_idname = "error.message"
    bl_label = "Message"
    type = StringProperty()
    message = StringProperty()

    def execute(self, context):
        self.report({"INFO"}, self.message)
        print(self.message)
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_popup(self, width=400, height=1000)

    def draw(self, context):
        self.layout.label(self.message)
