# blender_server.py
import bpy
import json
import math
import tempfile
import os
from pathlib import Path
import logging
from mcp import McpServer, ToolContext, ToolResult

# 内置工具

class GetSceneInfo:
    def __init__(self, blender_path: str):
        bpy.ops.wm.open_mainfile(filepath=blender_path)

    def get_info(self) -> dict:
        try:
            scene_info = {"objects": [], "materials": [], "lights": [], "cameras": [], "render_settings": {}}
            for obj in bpy.data.objects:
                obj_info = {"name": obj.name, "type": obj.type,
                            "location": list(obj.matrix_world.translation),
                            "rotation": list(obj.rotation_euler),
                            "scale": list(obj.scale),
                            "visible": not (obj.hide_viewport or obj.hide_render),
                            "active": obj == bpy.context.active_object}
                if obj.type == 'MESH':
                    obj_info["vertices"] = len(obj.data.vertices)
                    obj_info["faces"] = len(obj.data.polygons)
                    obj_info["materials"] = [mat.name for mat in obj.material_slots if mat.material]
                scene_info["objects"].append(obj_info)

            for mat in bpy.data.materials:
                scene_info["materials"].append({
                    "name": mat.name,
                    "use_nodes": mat.use_nodes,
                    "diffuse_color": list(mat.diffuse_color),
                    "metallic": getattr(mat, 'metallic', None),
                    "roughness": getattr(mat, 'roughness', None)
                })

            for light in [o for o in bpy.data.objects if o.type == 'LIGHT']:
                scene_info["lights"].append({
                    "name": light.name,
                    "type": light.data.type,
                    "energy": light.data.energy,
                    "color": list(light.data.color),
                    "location": list(light.matrix_world.translation),
                    "rotation": list(light.rotation_euler)
                })

            for cam in [o for o in bpy.data.objects if o.type == 'CAMERA']:
                scene = bpy.context.scene
                scene_info["cameras"].append({
                    "name": cam.name,
                    "lens": cam.data.lens,
                    "location": list(cam.matrix_world.translation),
                    "rotation": list(cam.rotation_euler),
                    "is_active": cam == scene.camera,
                    "dof_distance": cam.data.dof_distance if cam.data.dof.use_dof else None,
                    "dof_aperture_fstop": cam.data.dof.aperture_fstop if cam.data.dof.use_dof else None
                })

            rnd = bpy.context.scene.render
            scene_info["render_settings"] = {
                "resolution_x": rnd.resolution_x,
                "resolution_y": rnd.resolution_y,
                "resolution_percentage": rnd.resolution_percentage,
                "engine": rnd.engine,
                "samples": bpy.context.scene.cycles.samples if rnd.engine == 'CYCLES' else None
            }

            return scene_info
        except Exception as e:
            logging.error(f"scene info error: {e}")
            return {}

class Investigator3D:
    def __init__(self, thoughtprocess_save: str, blender_path: str, round_num: int):
        bpy.ops.wm.open_mainfile(filepath=blender_path)
        self.base = Path(thoughtprocess_save) / f"investigator_{round_num}"
        self.base.mkdir(parents=True, exist_ok=True)
        self.cam = self._get_or_create_cam()
        self.target = None
        self.radius = self.theta = self.phi = 0.0
        self.count = 0

    def _get_or_create_cam(self):
        if "InvestigatorCamera" in bpy.data.objects:
            return bpy.data.objects["InvestigatorCamera"]
        bpy.ops.object.camera_add()
        cam = bpy.context.active_object
        cam.name = "InvestigatorCamera"
        # optional: copy from existing Camera1
        return cam

    def _render(self):
        bpy.context.scene.camera = self.cam
        bpy.context.scene.render.engine = 'CYCLES'
        bpy.context.scene.render.filepath = str(self.base / f"{self.count:03d}.png")
        bpy.ops.render.render(write_still=True)
        out = bpy.context.scene.render.filepath
        self.count += 1
        return out

    def focus_on_object(self, object_name: str) -> str:
        obj = bpy.data.objects.get(object_name)
        if not obj:
            raise ValueError(f"{object_name} not found")
        self.target = obj
        # track-to
        constraint = None
        for c in self.cam.constraints:
            if c.type == 'TRACK_TO':
                constraint = c
                break
        if not constraint:
            constraint = self.cam.constraints.new('TRACK_TO')
        constraint.target = obj
        constraint.track_axis = 'TRACK_NEGATIVE_Z'
        constraint.up_axis = 'UP_Y'
        self.radius = (self.cam.matrix_world.translation - obj.matrix_world.translation).length
        self.theta = math.atan2(*(self.cam.matrix_world.translation[i] - obj.matrix_world.translation[i] for i in (1,0)))
        self.phi = math.asin((self.cam.matrix_world.translation.z - obj.matrix_world.translation.z)/self.radius)
        return self._render()

    def zoom(self, direction: str) -> str:
        if direction == 'in':
            self.radius = max(1, self.radius-3)
        elif direction == 'out':
            self.radius += 3
        return self._update_and_render()

    def move_camera(self, direction: str) -> str:
        step = self.radius
        theta_step = step/(self.radius*math.cos(self.phi))
        phi_step = step/self.radius
        if direction=='up': self.phi = min(math.pi/2-0.1, self.phi+phi_step)
        elif direction=='down': self.phi = max(-math.pi/2+0.1, self.phi-phi_step)
        elif direction=='left': self.theta -= theta_step
        elif direction=='right': self.theta += theta_step
        return self._update_and_render()

    def _update_and_render(self) -> str:
        t = self.target.matrix_world.translation
        x = self.radius*math.cos(self.phi)*math.cos(self.theta)
        y = self.radius*math.cos(self.phi)*math.sin(self.theta)
        z = self.radius*math.sin(self.phi)
        self.cam.matrix_world.translation = (t.x+x, t.y+y, t.z+z)
        return self._render()

# MCP Server 主体

def main():
    server = McpServer()

    @server.tool()
    def get_scene_info(blender_path: str) -> ToolResult:
        info = GetSceneInfo(Path(blender_path)).get_info()
        return ToolResult(result=info)

    @server.tool()
    def focus(blender_path: str, save_dir: str, round_num: int, object_name: str) -> ToolResult:
        img = Investigator3D(save_dir, blender_path, round_num).focus_on_object(object_name)
        return ToolResult(result={"image": img})

    @server.tool()
    def zoom(save_dir: str, direction: str) -> ToolResult:
        inst = Investigator3D(save_dir, "", 0)  # 注意：可重构以保持状态
        img = inst.zoom(direction)
        return ToolResult(result={"image": img})

    @server.tool()
    def move(save_dir: str, direction: str) -> ToolResult:
        inst = Investigator3D(save_dir, "", 0)
        img = inst.move_camera(direction)
        return ToolResult(result={"image": img})

    server.run()

if __name__ == "__main__":
    main()
