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

import bpy

bl_info = {
    "name": "Blender for Tangible Landscape",
    "author": "Payam Tabrizian (ptabriz)",
    "version": (1, 0),
    "blender": (2, 83, 0),
    "location": "Tools",
    "description": "Real-time 3D modeling with Tangible Landscape",
    "warning": "",
    "wiki_url": "https://github.com/ptabriz/tangible-landscape-immersive-extension/blob/master/README.md",
    "tracker_url": "",
    "category": "3D View",
}


from . import prefs
from . import Modeling3D


classes = (
    Modeling3D.ModalTimerOperator,
    Modeling3D.TL_OT_Assets,
    Modeling3D.TL_PT_GUI,
    Modeling3D.MessageOperator,
    Modeling3D.BirdCam,
    Modeling3D.ClearOperators,
    prefs.TL_OT_PREFS_SHOW,
    prefs.TL_PREFS,
)


def register():
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            bpy.utils.unregister_class(cls)
            bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
