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
    def __init__(self, task_dir: str, output_dir: str):
        self.task_dir = Path(task_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _execute_slide_code(self, code_path: str) -> str:
        generate_dir = "utils/slides"
        env = os.environ.copy()
        env['PYTHONPATH'] = f"{generate_dir}:{env.get('PYTHONPATH', '')}"
        try:
            result = subprocess.run(["python", code_path], capture_output=True, text=True, check=True, env=env)
            pptx_file = code_path.replace("runned_code.py", "refine.pptx")
            subprocess.run(["/usr/bin/python3", "/usr/bin/unoconv", "-f", "jpg", pptx_file], check=True)
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
            round_dir = self.output_dir / f"{round}"
            round_dir.mkdir(exist_ok=True)
            code_path = round_dir / "refine.py"
            runned_code_path = round_dir / "runned_code.py"
            slide_path = code_path.with_suffix(".pptx")
            image_path = code_path.with_suffix(".jpg")
            
            with open(code_path, "w") as f:
                f.write(code)

            # Replace hardcoded .save("xx.pptx") with dynamic save path
            code = re.sub(r'presentation\.save\("([^"]+\.pptx)"\)',
                          f'presentation.save("{slide_path}")',
                          code)
            # replace all '{xxx}/media/image_{}.jpg' to 'self.task_dir/media/image_{}.jpg'
            code = re.sub(r'media/image_(\d+)\.jpg',
                          f'{self.task_dir}/media/image_\\1.jpg',
                          code)
            
            with open(runned_code_path, "w") as f:
                f.write(code)

            result = self._execute_slide_code(str(runned_code_path))

            if result == "Success" and image_path.exists():
                encoded_image = self._encode_image(str(image_path))
                return {"status": "success", "output": str(image_path)}
            else:
                return {"status": "failure", "output": result}
        except Exception as e:
            return {"status": "failure", "output": str(e)}

@mcp.tool()
def initialize_executor(task_dir: str, output_dir: str) -> dict:
    """
    初始化 Slides 执行器，设置所有必要的参数。
    """
    global _executor
    try:
        _executor = SlidesExecutor(task_dir, output_dir)
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

def test_specific_file():
    """
    测试特定的文件 output/autopresent/20250817_172322/slide_11/1/refine.py 能否正常运行
    """
    test_file_path = "data/autopresent/examples/art_photos/slide_1/start.py"
    
    print(f"开始测试文件: {test_file_path}")
    print("=" * 60)
    
    # 检查文件是否存在
    if not os.path.exists(test_file_path):
        print(f"❌ 文件不存在: {test_file_path}")
        return False
    
    print(f"✅ 文件存在: {test_file_path}")
    
    # 读取文件内容
    try:
        with open(test_file_path, 'r', encoding='utf-8') as f:
            code_content = f.read()
        print(f"✅ 文件读取成功，代码长度: {len(code_content)} 字符")
    except Exception as e:
        print(f"❌ 文件读取失败: {e}")
        return False
    
    # 创建临时执行器进行测试
    try:
        task_dir = "data/autopresent/examples/art_photos/slide_1"
        temp_output_dir = "output/test"
        executor = SlidesExecutor(task_dir, temp_output_dir)
        print(f"✅ 执行器初始化成功，输出目录: {temp_output_dir}")
    except Exception as e:
        print(f"❌ 执行器初始化失败: {e}")
        return False
    
    # 执行代码
    try:
        print("正在执行代码...")
        result = executor.execute(code_content, 1)
        
        if result["status"] == "success":
            print("✅ 代码执行成功!")
            print(f"   生成的图片路径: {result.get('image_path', 'N/A')}")
            print(f"   图片base64长度: {len(result.get('image_base64', ''))} 字符")
            
            return True
        else:
            print(f"❌ 代码执行失败: {result.get('output', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ 执行过程中出现异常: {e}")
        return False

def main():
    # 如果直接运行此脚本，执行测试
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        success = test_specific_file()
        sys.exit(0 if success else 1)
    else:
        # 正常运行 MCP 服务
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
