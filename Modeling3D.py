import bpy
import os
import math
import bmesh
from timeit import default_timer as timer

from .settings import getSettings

from bpy.props import (
    StringProperty,
)

import bpy.utils.previews
from mathutils import Vector

watchName = "Watch"
terrainFile = "terrain.tif"
waterFile = "water.tif"
viewFile = "vantage.shp"
dynamic_cam = "dynamic_camera"
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
        self.water_path = os.path.join(self.watchFolder, waterFile)
        self.view_path = os.path.join(self.watchFolder, viewFile)
        self.CRS = "EPSG:" + getSettings()["CRS"]
        self.timer = getSettings()["timer"]
        self.trees = {}
        for c in getSettings()["trees"]:
            self.trees[c] = {}
            self.trees[c]["model"] = os.path.join(folder, getSettings()["trees"][c]["model"])
            self.trees[c]["texture"] = os.path.join(folder, getSettings()["trees"][c]["texture"])
        self.tree_model_path = os.path.join(
            folder, getSettings()["terrain"]["grass_texture_file"])


def load_objects_from_file(filepath):
    with bpy.data.libraries.load(filepath, link=False) as (src, dst):
        dst.objects = [name for name in src.objects]
    names = []
    for obj in dst.objects:
        bpy.context.collection.objects.link(obj)
        names.append(obj.name)
        obj.hide_set(True)
    return names


def assign_material(object_name, material_name):
    obj = bpy.data.objects[object_name]
    material = bpy.data.materials.get(material_name)
    # Assign it to object
    obj.data.materials.append(material)
    num_mat = len(obj.data.materials)
    if num_mat > 1:
        obj.active_material_index = num_mat - 1
        bpy.ops.object.material_slot_assign()


def create_particle_system(name, particle_object_name):
    tex = bpy.data.textures.new(name, type='IMAGE')
    # tex.image = bpy.data.images.load(filepath=texture_path)

    tmp_plane = "Plane"
    bpy.ops.mesh.primitive_plane_add()
    obj = bpy.data.objects[tmp_plane]
    mod = obj.modifiers.new(name=name, type='PARTICLE_SYSTEM')
    mod.particle_system.settings.name = name
    psys = bpy.data.particles[name]
    mtex = psys.texture_slots.add()
    mtex.texture = tex
    psys.distribution = 'RAND'
    psys.render_type = 'OBJECT'
    psys.use_rotations = True
    psys.rotation_mode = 'OB_Z'
    psys.use_rotation_instance = True
    psys.phase_factor_random = 2
    psys.particle_size = 1
    psys.size_random = 0.5
    psys.count = 1000
    psys.use_emit_random = True
    psys.use_modifier_stack = True
    psys.use_even_distribution = False

    psys.instance_object = bpy.data.objects[particle_object_name]
    psys.use_fake_user = True

    remove_object(tmp_plane)


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
    bsdf.inputs['Roughness'].default_value = 0.8


def create_fast_water_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    output = nodes["Material Output"]
    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    node_to_delete = nodes['Principled BSDF']
    nodes.remove(node_to_delete)
    diffuse.inputs[0].default_value = (0.1, 0.2, 0.8, 1)
    mix.inputs[0].default_value = 0.6
    mat.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(diffuse.outputs["BSDF"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])


def create_water_material(name):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    output = nodes["Material Output"]
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    noise = nodes.new("ShaderNodeTexNoise")
    glossy = nodes.new("ShaderNodeBsdfGlossy")
    node_to_delete = nodes['Principled BSDF']
    nodes.remove(node_to_delete)
    glossy.inputs[0].default_value = (0.5, 0.6, 0.8, 1)

    glossy.inputs[1].default_value = 0.1
    mix.inputs[0].default_value = 0.6
    noise.inputs[2].default_value = 5
    noise.inputs[3].default_value = 5
    noise.inputs[4].default_value = 1
    noise.inputs[5].default_value = 0.1
    mat.node_tree.links.new(transparent.outputs["BSDF"], mix.inputs[1])
    mat.node_tree.links.new(glossy.outputs["BSDF"], mix.inputs[2])
    mat.node_tree.links.new(mix.outputs["Shader"], output.inputs["Surface"])
    mat.node_tree.links.new(noise.outputs["Fac"], output.inputs["Displacement"])

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

def add_sun():
    sun = bpy.data.lights.new(name="Sun", type='SUN')
    light_object = bpy.data.objects.new(name="Sun", object_data=sun)
    sun.energy = 2
    light_object.location = (0, 0, 1000)
    light_object.rotation_euler = (0.9, 0.9, 0)
    sun.shadow_cascade_max_distance = 1000
    bpy.context.collection.objects.link(light_object)

def addSide(objName, mat):
    ter = bpy.data.objects[objName]
    fringe = ter.dimensions.x / 20
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
    zmin = min(dic["z"])

    tres = 0.1

    for vert in vertices:
        if vert.co[0] < xmin + tres and vert.co[0] > xmin - tres:
            vert.select_set(True)
            vert.co[2] = zmin - fringe

        elif vert.co[1] < ymin + tres and vert.co[1] > ymin - tres:
            vert.select_set(True)
            vert.co[2] = zmin - fringe

        elif vert.co[0] < xmax + tres and vert.co[0] > xmax - tres:
            vert.select_set(True)
            vert.co[2] = zmin - fringe
        elif vert.co[1] < ymax + tres and vert.co[1] > ymax - tres:
            vert.select_set(True)
            vert.co[2] = zmin - fringe

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


def create_dynamic_camera():
    scn = bpy.context.scene
    cam = bpy.data.cameras.new(dynamic_cam)
    cam_obj = bpy.data.objects.new(dynamic_cam, cam)
    scn.collection.objects.link(cam_obj)
    target = bpy.data.objects.new(dynamic_cam + "_target", None)
    scn.collection.objects.link(target)
    cam_obj.constraints.new("TRACK_TO")
    cam_obj.constraints["Track To"].target = target
    cam_obj.constraints["Track To"].track_axis = "TRACK_NEGATIVE_Z"
    cam_obj.constraints["Track To"].up_axis = "UP_Y"
    cam_obj.hide_set(True)
    target.hide_set(True)
    cam_obj.data.show_passepartout = False
    cam_obj.data.angle = 1.39626


def toggle_camera(name):
    camera = bpy.data.objects[name]
    bpy.context.scene.camera = camera
    bpy.context.view_layer.objects.active = camera

    area = next(area for area in bpy.context.screen.areas if area.type == "VIEW_3D")
    area.spaces[0].region_3d.view_perspective = "CAMERA"
    bpy.ops.view3d.view_center_camera()


def select_only(object_name):
    """selects the passed object"""

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
    if bpy.data.objects.get(object_name):
        bpy.data.objects.remove(bpy.data.objects[object_name])


class Adapt:
    def __init__(self):
        self.plane = "terrain"
        self.treePatch = "TreePatch"
        self.trail = "trail"
        self.texture = "texture.tif"
        self.water = "water"
        self.view = "vantage"
        self.dimensions = None

    def terrainChange(self, path, CRS):
        # TODO: apply previous particle systems
        remove_object(self.plane)
        bpy.ops.importgis.georaster(
            filepath=path, importMode="DEM", subdivision="mesh", step=2,
            rastCRS=CRS, 
        )
        select_only(self.plane)
        bpy.ops.object.convert(target="MESH")
        self.dimensions = bpy.data.objects['terrain'].dimensions
        assign_material(self.plane, material_name="terrain_material")
        addSide(self.plane, "terrain_material")
        os.remove(path)

    def waterFill(self, path, CRS):
        remove_object(self.water)
        bpy.ops.importgis.georaster(
            filepath=path, importMode="DEM", subdivision="mesh", step=2, rastCRS=CRS
        )
        select_only(self.water)
        bpy.ops.object.convert(target="MESH")
        assign_material(self.water, material_name="water_material")
        bpy.context.object.active_material.blend_method = "BLEND"
        os.remove(path)

    def camera_view(self, path, CRS):
        remove_object(self.view)
        bpy.ops.importgis.shapefile(filepath=path, shpCRS=CRS)
        van_line = bpy.data.objects[self.view]
        van_line.hide_set(True)
        cam = bpy.data.objects[dynamic_cam]
        target = bpy.data.objects[dynamic_cam + "_target"]

        me = van_line.to_mesh()
        me.transform(van_line.matrix_world)
        cam.location = [
            me.vertices[0].co.x,
            me.vertices[0].co.y,
            me.vertices[0].co.z + 5,
        ]
        target.location = [
            me.vertices[-1].co.x,
            me.vertices[-1].co.y,
            me.vertices[0].co.z + 2,
        ]
        toggle_camera(dynamic_cam)
        os.remove(path)

    def trees(self, patch_files, watchFolder):
        try:
            terrain = bpy.data.objects[self.plane]
        except KeyError:
            print("no terrain for particles")
            return
        while terrain.modifiers:
            terrain.modifiers.remove(terrain.modifiers[-1])
        for patch_file in patch_files:
            path = os.path.join(watchFolder, patch_file)
            patch_type = os.path.splitext(patch_file)[0].split("_")[1]
            if bpy.data.images.get(patch_file):
                bpy.data.images.remove(bpy.data.images[patch_file])
            bpy.data.textures[patch_type].image = bpy.data.images.load(path)
            bpy.data.images[patch_file].pack()
            terrain.modifiers.new(name=patch_type, type='PARTICLE_SYSTEM')
            terrain.particle_systems[patch_type].settings = bpy.data.particles[patch_type]
            for p in bpy.data.particles:
                if p.users == 0:
                    bpy.data.particles.remove(p)
            os.remove(path)


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
                if waterFile in fileList:
                    self.adapt.waterFill(self.prefs.water_path, self.prefs.CRS)
                if viewFile in fileList:
                    self.adapt.camera_view(self.prefs.view_path, self.prefs.CRS)

                patch_files = []
                for f in fileList:
                    if f.startswith("patch_"):
                        patch_files.append(f)
                if patch_files:
                    self.adapt.trees(patch_files, self.prefs.watchFolder)

        return {"PASS_THROUGH"}

    def execute(self, context):
        wm = context.window_manager
        wm.modal_handler_add(self)

        self.treePatch = "TreePatch"
        self.emptyTree = "empty.txt"
        self.adaptMode = None
        self.prefs = Prefs()
        self.adapt = Adapt()
        self.adapt.realism = "High"
        for file in os.listdir(self.prefs.watchFolder):
            try:
                os.remove(os.path.join(self.prefs.watchFolder, file))
            except:
                print("Could not remove file")
        self._timer = wm.event_timer_add(self.prefs.timer, window=context.window)


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
        add_sun()
        create_dynamic_camera()
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
        create_water_material(name="water_material")
        create_world(name="TL_world", texture_path=prefs.world_texture_path)
        bpy.context.scene.world = bpy.data.worlds.get("TL_world")
        bpy.context.space_data.shading.type = "RENDERED"
        bpy.context.space_data.overlay.show_floor = False
        bpy.context.space_data.overlay.show_axis_x = False
        bpy.context.space_data.overlay.show_axis_y = False
        bpy.context.space_data.overlay.show_axis_z = False
        bpy.context.space_data.overlay.show_cursor = False
        bpy.context.space_data.overlay.show_text = False
        bpy.context.space_data.show_gizmo_navigate = False
        bpy.context.space_data.overlay.show_outline_selected = False
        bpy.context.space_data.overlay.show_extras = False
        bpy.context.space_data.overlay.show_object_origins = False


        remove_object("Cube")
        for each in prefs.trees:
            tree_names = load_objects_from_file(prefs.trees[each]["model"])
            create_particle_system(each, particle_object_name=tree_names[0])

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
