# -*- coding:utf-8 -*-

#  ***** GPL LICENSE BLOCK *****
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#  All rights reserved.
#  ***** GPL LICENSE BLOCK *****\

bl_info = {
 "name": "Tangible Landscape Addon",
 "author": "Payam Tabrizian (ptabriz)",
 "version": (1, 0),
 "blender": (2, 83, 0),
 "location": "Tools",
 "description": "Real-time 3D modeling with Tangible Landscape",
 "warning": "",
 "wiki_url": "https://github.com/ptabriz/tangible-landscape-immersive-extension/blob/master/README.md",
 "tracker_url": "",
 "category": "view_3D"}

import bpy, os
import addon_utils
from . import prefs
from . import Modeling3D
from .settings import getSettings, setSettings

classes = (
    Modeling3D.ModalTimerOperator,
    Modeling3D.BirdCam,
    Modeling3D.HumanCam,
    Modeling3D.RotaryCam,
    Modeling3D.VantageCam,
    Modeling3D.mist,
    Modeling3D.Object_operators,
    Modeling3D.Engine_buttons,
    Modeling3D.TLGUI,
    Modeling3D.MessageOperator,
    prefs.TL_PREFS_SHOW,
    prefs.TL_PREFS
)


def make_annotations(cls):
    """Converts class fields to annotations if running with Blender 2.8"""
    if bpy.app.version < (2, 80):
        return cls
    bl_props = {k: v for k, v in cls.__dict__.items() if isinstance(v, tuple)}
    if bl_props:
        if '__annotations__' not in cls.__dict__:
            setattr(cls, '__annotations__', {})
        annotations = cls.__dict__['__annotations__']
        for k, v in bl_props.items():
            annotations[k] = v
            delattr(cls, k)
    return cls


def register():
    for cls in classes:
        make_annotations(cls)
        bpy.utils.register_class(cls)
    #prefs = bpy.context.user_preferences.addons[__package__].preferences

def unregister():  # note how unregistering is done in reverse
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

if __name__ == "__main__":
    register()
