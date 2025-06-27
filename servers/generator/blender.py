# blender_executor_server.py
import os
import subprocess
import base64
import io
from pathlib import Path
from PIL import Image
import logging
from typing import Tuple, Dict
from mcp import McpServer, ToolResult

class Executor:
    def __init__(self,
                 blender_command: str,
                 blender_file: str,
                 blender_script: str,
                 script_save: str,
                 render_save: str,
                 blender_save: str = None):
        self.blender_command = blender_command
        self.blender_file = blender_file
        self.blender_script = blender_script
        self.script_path = Path(script_save)
        self.render_path = Path(render_save)
        self.blend_path = blender_save

        self.script_path.mkdir(parents=True, exist_ok=True)
        self.render_path.mkdir(parents=True, exist_ok=True)

    def _execute_blender(self, script_path: str, render_path: str) -> Tuple[bool, str, str]:
        cmd = [
            self.blender_command,
            "--background", self.blender_file,
            "--python", self.blender_script,
            "--", script_path, render_path
        ]
        if self.blend_path:
            cmd.append(self.blend_path)
        cmd_str = " ".join(cmd)
        try:
            proc = subprocess.run(cmd_str, shell=True, check=True, capture_output=True, text=True)
            out = proc.stdout
            err = proc.stderr
            if 'Error:' in out:
                logging.error(f"Error in Blender stdout: {out}")
                return False, err, out
            # find rendered image(s)
            if os.path.isdir(render_path):
                imgs = sorted([str(p) for p in Path(render_path).glob("*") if p.suffix in ['.png','.jpg']])
                if not imgs:
                    return False, "No images", out
                paths = imgs[:2]
                return True, "PATH:" + ",".join(paths), out
            return True, out, err
        except subprocess.CalledProcessError as e:
            logging.error(f"Blender failed: {e}")
            return False, e.stderr, e.stdout

    def _encode_image(self, img_path: str) -> str:
        img = Image.open(img_path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def execute(self, code: str, round: int) -> Dict:
        script_file = self.script_path / f"{round}.py"
        render_file = self.render_path / f"{round}.png"
        with open(script_file, "w") as f:
            f.write(code)
        success, stdout, stderr = self._execute_blender(str(script_file), str(render_file))
        if not success or not os.path.exists(render_file):
            return {"status": "failure", "output": stderr or stdout}
        img_b64 = self._encode_image(str(render_file))
        return {"status": "success", "output": img_b64, "stdout": stdout, "stderr": stderr}

def main():
    server = McpServer()

    @server.tool()
    def exec_script(blender_command: str,
                    blender_file: str,
                    blender_script: str,
                    code: str,
                    round: int,
                    script_save: str,
                    render_save: str,
                    blender_save: str = None) -> ToolResult:
        """
        执行传入的 Blender Python 脚本 code，并返回 base64 编码后的渲染图像。
        """
        executor = Executor(
            blender_command=blender_command,
            blender_file=blender_file,
            blender_script=blender_script,
            script_save=script_save,
            render_save=render_save,
            blender_save=blender_save
        )
        try:
            result = executor.execute(code, round)
            return ToolResult(result=result)
        except Exception as e:
            return ToolResult(isError=True, error=str(e))

    server.run()

if __name__ == "__main__":
    main()
