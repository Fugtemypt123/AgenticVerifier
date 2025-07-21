import os
import subprocess
import base64
import io
import re
from pathlib import Path
from PIL import Image
from typing import Optional
import logging
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("slides-executor")

_executor = None

class SlidesExecutor:
    def __init__(self, code_save: str):
        self.code_save = Path(code_save)
        self.code_save.mkdir(parents=True, exist_ok=True)

    def _execute_slide_code(self, code_path: str) -> str:
        generate_dir = "/home/shaofengyin/AutoPresent/generate"
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{generate_dir}:{env.get('PYTHONPATH', '')}"
        try:
            result = subprocess.run(["python", code_path], capture_output=True, text=True, check=True, env=env)
            pptx_file = code_path.replace(".py", ".pptx")
            subprocess.run(["unoconv", "-f", "jpg", pptx_file], check=True)
            return "Success"
        except subprocess.CalledProcessError as e:
            logging.error(f"PPTX compilation failed: {e.stderr}")
            return f"Error: {e.stderr}"

    def _encode_image(self, image_path: str) -> str:
        image = Image.open(image_path)
        img_byte_array = io.BytesIO()
        image.save(img_byte_array, format='PNG')
        return base64.b64encode(img_byte_array.getvalue()).decode()

    def execute(self, code: str, round: int) -> dict:
        try:
            round_dir = self.code_save / f"{round}"
            round_dir.mkdir(exist_ok=True)
            code_path = round_dir / "refine.py"
            slide_path = code_path.with_suffix(".pptx")
            image_path = code_path.with_suffix(".jpg")

            # Replace hardcoded .save("xx.pptx") with dynamic save path
            code = re.sub(r'presentation\.save\("([^"]+\.pptx)"\)',
                          f'presentation.save("{slide_path}")',
                          code)

            with open(code_path, "w") as f:
                f.write(code)

            result = self._execute_slide_code(str(code_path))

            if result == "Success" and image_path.exists():
                encoded_image = self._encode_image(str(image_path))
                return {"status": "success", "image_path": str(image_path), "image_base64": encoded_image}
            else:
                return {"status": "failure", "output": result}
        except Exception as e:
            return {"status": "failure", "output": str(e)}

@mcp.tool()
def initialize_executor(code_save: str) -> dict:
    """
    初始化 Slides 执行器，设置所有必要的参数。
    """
    global _executor
    try:
        _executor = SlidesExecutor(code_save)
        return {"status": "success", "message": "Slides executor initialized successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def exec_pptx(code: str, round: int) -> dict:
    """
    Compile and render PPTX from Python code.
    Args:
        code: str - Python code that generates a .pptx
        round: int - round index
    """
    global _executor
    if _executor is None:
        return {"status": "error", "error": "Executor not initialized. Call initialize_executor first."}
    try:
        result = _executor.execute(code, round)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
