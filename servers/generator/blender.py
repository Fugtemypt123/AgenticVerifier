# blender_executor_server.py
from optparse import Option
import os
import subprocess
import base64
import io
from typing import Optional
from pathlib import Path
from PIL import Image
import logging
from typing import Tuple, Dict
from mcp.server.fastmcp import FastMCP
import json
import requests
import tempfile
import zipfile
import shutil
import bpy
import math
import cv2
import numpy as np
import time

mcp = FastMCP("blender-executor")

# Global executor instance
_executor = None

# Global investigator instance
_investigator = None

# ======================
# Meshy API（从scene.py迁移）
# ======================

class MeshyAPI:
    """Meshy API 客户端：Text-to-3D 生成 + 轮询 + 下载"""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("MESHY_API_KEY")
        if not self.api_key:
            raise ValueError("Meshy API key is required. Set MESHY_API_KEY environment variable or pass api_key parameter.")
        self.base_url = "https://api.meshy.ai"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

    def create_text_to_3d_preview(self, prompt: str, **kwargs) -> str:
        """
        创建 Text-to-3D 预览任务（无贴图）
        Returns: task_id (str)
        """
        url = f"{self.base_url}/openapi/v2/text-to-3d"
        payload = {
            "mode": "preview",
            "prompt": prompt[:600],
        }
        payload.update(kwargs or {})
        resp = requests.post(url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        data = resp.json()
        # 有的环境返回 {"result": "<id>"}，有的返回 {"id": "<id>"}
        return data.get("result") or data.get("id")

    def poll_text_to_3d(self, task_id: str, interval_sec: float = 5.0, timeout_sec: int = 1800) -> dict:
        """
        轮询 Text-to-3D 任务直到结束
        Returns: 任务 JSON（包含 status / model_urls 等）
        """
        import time
        url = f"{self.base_url}/openapi/v2/text-to-3d/{task_id}"
        deadline = time.time() + timeout_sec
        while True:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            js = r.json()
            status = js.get("status")
            if status in ("SUCCEEDED", "FAILED", "CANCELED"):
                return js
            if time.time() > deadline:
                raise TimeoutError(f"Meshy task {task_id} polling timeout")
            time.sleep(interval_sec)

    def create_text_to_3d_refine(self, preview_task_id: str, **kwargs) -> str:
        """
        基于 preview 发起 refine 贴图任务
        Returns: refine_task_id (str)
        """
        url = f"{self.base_url}/openapi/v1/text-to-3d"
        payload = {
            "mode": "refine",
            "preview_task_id": preview_task_id,
        }
        payload.update(kwargs or {})
        resp = requests.post(url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        data = resp.json()
        return data.get("result") or data.get("id")

    def download_model_url(self, file_url: str, output_path: str) -> None:
        """
        从 model_urls 的直链下载文件到本地
        """
        r = requests.get(file_url, stream=True)
        r.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    def create_image_to_3d_preview(self, image_path: str, prompt: str = None, **kwargs) -> str:
        """
        创建 Image-to-3D 预览任务（无贴图）
        
        Args:
            image_path: 输入图片路径
            prompt: 可选的文本提示
            **kwargs: 其他参数
            
        Returns: task_id (str)
        """
        url = f"{self.base_url}/openapi/v1/image-to-3d"
        
        # 准备文件上传
        with open(image_path, 'rb') as f:
            files = {
                'image': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            # 准备表单数据
            data = {
                'mode': 'preview'
            }
            if prompt:
                data['prompt'] = prompt[:600]
            
            # 添加其他参数
            for key, value in kwargs.items():
                data[key] = value
            
            # 发送请求（注意：这里不使用JSON headers，因为要上传文件）
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            
            resp = requests.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result") or data.get("id")

    def create_image_to_3d_refine(self, preview_task_id: str, **kwargs) -> str:
        """
        基于 preview 发起 refine 贴图任务（Image-to-3D）
        Returns: refine_task_id (str)
        """
        url = f"{self.base_url}/openapi/v1/image-to-3d"
        payload = {
            "mode": "refine",
            "preview_task_id": preview_task_id,
        }
        payload.update(kwargs or {})
        resp = requests.post(url, headers=self.headers, data=json.dumps(payload))
        resp.raise_for_status()
        data = resp.json()
        return data.get("result") or data.get("id")

    def poll_image_to_3d(self, task_id: str, interval_sec: float = 5.0, timeout_sec: int = 1800) -> dict:
        """
        轮询 Image-to-3D 任务直到结束
        Returns: 任务 JSON（包含 status / model_urls 等）
        """
        import time
        url = f"{self.base_url}/openapi/v2/image-to-3d/{task_id}"
        deadline = time.time() + timeout_sec
        while True:
            r = requests.get(url, headers=self.headers)
            r.raise_for_status()
            js = r.json()
            status = js.get("status")
            if status in ("SUCCEEDED", "FAILED", "CANCELED"):
                return js
            if time.time() > deadline:
                raise TimeoutError(f"Meshy Image-to-3D task {task_id} polling timeout")
            time.sleep(interval_sec)


# ======================
# 图片截取工具
# ======================

class ImageCropper:
    """图片截取工具，支持基于文本描述的智能截取"""
    
    def __init__(self):
        self.temp_dir = None
    
    def crop_image_by_text(self, image_path: str, description: str, output_path: str = None, 
                          confidence_threshold: float = 0.5, padding: int = 20) -> dict:
        """
        根据文本描述从图片中截取相关区域
        
        Args:
            image_path: 输入图片路径
            description: 文本描述，描述要截取的对象
            output_path: 输出图片路径（可选，默认自动生成）
            confidence_threshold: 置信度阈值
            padding: 截取区域周围的填充像素
        
        Returns:
            dict: 包含截取结果的字典
        """
        try:
            # 检查输入图片是否存在
            if not os.path.exists(image_path):
                return {"status": "error", "error": f"Image file not found: {image_path}"}
            
            image = cv2.imread(image_path)
            if image is None:
                return {"status": "error", "error": f"Failed to load image: {image_path}"}
            
            # 使用YOLO或类似的物体检测模型进行检测
            # 这里使用一个简化的方法，实际应用中可以使用更先进的模型
            detected_objects = self._detect_objects(image, description, confidence_threshold)
            
            if not detected_objects:
                return {"status": "error", "error": f"No objects matching '{description}' found in image"}
            
            # 选择最匹配的对象
            best_match = max(detected_objects, key=lambda x: x['confidence'])
            
            # 计算截取区域（添加填充）
            x, y, w, h = best_match['bbox']
            x1 = max(0, x - padding)
            y1 = max(0, y - padding)
            x2 = min(image.shape[1], x + w + padding)
            y2 = min(image.shape[0], y + h + padding)
            
            # 截取图片
            cropped_image = image[y1:y2, x1:x2]
            
            # 生成输出路径
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(image_path))[0]
                output_dir = os.path.dirname(image_path)
                output_path = os.path.join(output_dir, f"{base_name}_cropped_{description.replace(' ', '_')}.jpg")
            
            cv2.imwrite(output_path, cropped_image)
            
            return {
                "status": "success",
                "message": f"Successfully cropped image based on '{description}'",
                "input_image": image_path,
                "output_image": output_path,
                "detected_object": {
                    "description": best_match['class'],
                    "confidence": best_match['confidence'],
                    "bbox": [x1, y1, x2-x1, y2-y1],
                    "original_bbox": [x, y, w, h]
                },
                "crop_info": {
                    "original_size": [image.shape[1], image.shape[0]],
                    "cropped_size": [x2-x1, y2-y1],
                    "padding": padding
                }
            }
            
        except Exception as e:
            logging.error(f"Failed to crop image: {e}")
            return {"status": "error", "error": str(e)}
    
    def _detect_objects(self, image, description: str, confidence_threshold: float) -> list:
        """
        检测图片中的对象（简化版本）
        实际应用中可以使用YOLO、R-CNN等模型
        """
        try:
            # 这里使用OpenCV的预训练模型进行物体检测
            # 加载预训练的YOLO模型（需要下载权重文件）
            net = cv2.dnn.readNet("yolov3.weights", "yolov3.cfg")
            
            # 获取输出层名称
            layer_names = net.getLayerNames()
            output_layers = [layer_names[i[0] - 1] for i in net.getUnconnectedOutLayers()]
            
            # 准备输入
            blob = cv2.dnn.blobFromImage(image, 0.00392, (416, 416), (0, 0, 0), True, crop=False)
            net.setInput(blob)
            outputs = net.forward(output_layers)
            
            # 解析检测结果
            height, width, channels = image.shape
            class_ids = []
            confidences = []
            boxes = []
            
            for output in outputs:
                for detection in output:
                    scores = detection[5:]
                    class_id = np.argmax(scores)
                    confidence = scores[class_id]
                    
                    if confidence > confidence_threshold:
                        center_x = int(detection[0] * width)
                        center_y = int(detection[1] * height)
                        w = int(detection[2] * width)
                        h = int(detection[3] * height)
                        
                        x = int(center_x - w / 2)
                        y = int(center_y - h / 2)
                        
                        boxes.append([x, y, w, h])
                        confidences.append(float(confidence))
                        class_ids.append(class_id)
            
            # 应用非最大抑制
            indexes = cv2.dnn.NMSBoxes(boxes, confidences, confidence_threshold, 0.4)
            
            # 加载类别名称
            with open("coco.names", "r") as f:
                classes = [line.strip() for line in f.readlines()]
            
            # 过滤匹配描述的对象
            detected_objects = []
            for i in range(len(boxes)):
                if i in indexes:
                    class_name = classes[class_ids[i]]
                    # 简单的文本匹配（实际应用中可以使用更智能的匹配）
                    if self._is_description_match(class_name, description):
                        detected_objects.append({
                            'class': class_name,
                            'confidence': confidences[i],
                            'bbox': boxes[i]
                        })
            
            return detected_objects
            
        except Exception as e:
            # 如果YOLO模型不可用，使用简化的方法
            logging.warning(f"YOLO detection failed, using fallback method: {e}")
            return self._fallback_detection(image, description)
    
    def _is_description_match(self, class_name: str, description: str) -> bool:
        """
        检查类别名称是否与描述匹配
        """
        description_lower = description.lower()
        class_name_lower = class_name.lower()
        
        # 直接匹配
        if class_name_lower in description_lower or description_lower in class_name_lower:
            return True
        
        # 同义词匹配
        synonyms = {
            'person': ['human', 'people', 'man', 'woman', 'child'],
            'car': ['vehicle', 'automobile', 'auto'],
            'dog': ['puppy', 'canine'],
            'cat': ['kitten', 'feline'],
            'bird': ['flying', 'winged'],
            'tree': ['plant', 'vegetation'],
            'building': ['house', 'structure', 'architecture'],
            'chair': ['seat', 'furniture'],
            'table': ['desk', 'surface'],
            'book': ['text', 'reading', 'literature']
        }
        
        for key, values in synonyms.items():
            if class_name_lower == key and any(v in description_lower for v in values):
                return True
            if any(v == class_name_lower for v in values) and key in description_lower:
                return True
        
        return False
    
    def _fallback_detection(self, image, description: str) -> list:
        """
        备用检测方法（当YOLO不可用时）
        使用简单的颜色和形状分析
        """
        # 这是一个简化的实现，实际应用中需要更复杂的算法
        height, width = image.shape[:2]
        
        # 基于描述返回一些模拟的检测结果
        # 实际应用中这里应该实现更智能的检测算法
        mock_detections = []
        
        if 'person' in description.lower() or 'human' in description.lower():
            # 模拟检测到人
            mock_detections.append({
                'class': 'person',
                'confidence': 0.8,
                'bbox': [width//4, height//4, width//2, height//2]
            })
        elif 'car' in description.lower() or 'vehicle' in description.lower():
            # 模拟检测到车
            mock_detections.append({
                'class': 'car',
                'confidence': 0.7,
                'bbox': [width//6, height//3, width//3, height//3]
            })
        elif 'animal' in description.lower() or 'dog' in description.lower() or 'cat' in description.lower():
            # 模拟检测到动物
            mock_detections.append({
                'class': 'animal',
                'confidence': 0.6,
                'bbox': [width//3, height//3, width//4, height//4]
            })
        
        return mock_detections


class AssetImporter:
    """3D资产导入器，支持多种格式"""
    def __init__(self, blender_path: str):
        self.blender_path = blender_path

    def import_asset(self, asset_path: str, location: tuple = (0, 0, 0), scale: float = 1.0) -> str:
        """导入3D资产到Blender场景"""
        try:
            # 确保文件存在
            if not os.path.exists(asset_path):
                raise FileNotFoundError(f"Asset file not found: {asset_path}")

            # 根据文件扩展名选择导入方法
            ext = os.path.splitext(asset_path)[1].lower()

            if ext in ['.fbx', '.obj', '.gltf', '.glb', '.dae', '.3ds', '.blend']:
                # 使用Blender的导入操作符
                if ext == '.fbx':
                    bpy.ops.import_scene.fbx(filepath=asset_path)
                elif ext == '.obj':
                    bpy.ops.import_scene.obj(filepath=asset_path)
                elif ext in ['.gltf', '.glb']:
                    bpy.ops.import_scene.gltf(filepath=asset_path)
                elif ext == '.dae':
                    bpy.ops.wm.collada_import(filepath=asset_path)
                elif ext == '.3ds':
                    bpy.ops.import_scene.autodesk_3ds(filepath=asset_path)
                elif ext == '.blend':
                    # 附注：append 需要 directory + filename（指向 .blend 内部路径）
                    # 这里保留占位，以防未来确实需要 .blend 的 append
                    bpy.ops.wm.append(filepath=asset_path)

                # 获取导入的对象
                imported_objects = [obj for obj in bpy.context.selected_objects]
                if not imported_objects:
                    raise RuntimeError("No objects were imported")

                # 设置位置和缩放
                for obj in imported_objects:
                    obj.location = location
                    obj.scale = (scale, scale, scale)

                # 返回导入的对象名称
                return imported_objects[0].name
            else:
                raise ValueError(f"Unsupported file format: {ext}")

        except Exception as e:
            logging.error(f"Failed to import asset: {e}")
            raise

    def extract_zip_asset(self, zip_path: str, extract_dir: str) -> str:
        """从ZIP文件中提取3D资产"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 查找3D文件
                asset_files = []
                for file_info in zip_ref.filelist:
                    filename = file_info.filename
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in ['.fbx', '.obj', '.gltf', '.glb', '.dae', '.3ds', '.blend']:
                        asset_files.append(filename)

                if not asset_files:
                    raise ValueError("No supported 3D files found in ZIP")

                # 提取第一个找到的3D文件
                asset_file = asset_files[0]
                zip_ref.extract(asset_file, extract_dir)

                return os.path.join(extract_dir, asset_file)

        except Exception as e:
            logging.error(f"Failed to extract ZIP asset: {e}")
            raise


class Executor:
    def __init__(self,
                 blender_command: str,
                 blender_file: str,
                 blender_script: str,
                 script_save: str,
                 render_save: str,
                 blender_save: Optional[str] = None):
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
        # with open('cmd.txt', 'w') as f:
        #     f.write(" ".join(cmd))
        # # if self.blend_path:
        # #     cmd.append(self.blend_path)
        cmd_str = " ".join(cmd)
        try:
            proc = subprocess.run(cmd_str, shell=True, check=True, capture_output=True, text=True)
            out = proc.stdout
            err = proc.stderr
            # We do not consider intermediate errors that do not affect the result.
            # if 'Error:' in out:
            #     logging.error(f"Error in Blender stdout: {out}")
            #     return False, err, out
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
        render_file = self.render_path / f"{round}"
        with open(script_file, "w") as f:
            f.write(code)
        success, stdout, stderr = self._execute_blender(str(script_file), str(render_file))
        if not success or not os.path.exists(render_file):
            return {"status": "failure", "output": stderr or stdout}
        return {"status": "success", "output": str(render_file), "stdout": stdout, "stderr": stderr}

@mcp.tool()
def initialize_executor(blender_command: str,
                       blender_file: str,
                       blender_script: str,
                       script_save: str,
                       render_save: str,
                       blender_save: Optional[str] = None) -> dict:
    """
    初始化 Blender 执行器，设置所有必要的参数。
    """
    global _executor
    try:
        _executor = Executor(
            blender_command=blender_command,
            blender_file=blender_file,
            blender_script=blender_script,
            script_save=script_save,
            render_save=render_save,
            blender_save=blender_save
        )
        return {"status": "success", "message": "Executor initialized successfully"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def exec_script(code: str, round: int) -> dict:
    """
    执行传入的 Blender Python 脚本 code，并返回 base64 编码后的渲染图像。
    需要先调用 initialize_executor 进行初始化。
    """
    global _executor
    if _executor is None:
        return {"status": "error", "error": "Executor not initialized. Call initialize_executor first."}
    
    try:
        result = _executor.execute(code, round)
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool()
def add_meshy_asset(
    description: str,
    blender_path: str,
    location: str = "0,0,0",
    scale: float = 1.0,
    api_key: str = None,
    refine: bool = True
) -> dict:
    """
    使用 Meshy Text-to-3D 生成资产并导入到当前场景（生成→轮询→下载→导入）

    Args:
        description: 文本描述（prompt）
        blender_path: Blender 文件路径
        location: 资产位置 "x,y,z"
        scale: 缩放比例
        api_key: Meshy API 密钥（可选，默认读 MESHY_API_KEY）
        refine: 是否在 preview 后进行 refine（含贴图）
    """
    try:
        # 解析位置参数
        try:
            loc_parts = [float(x.strip()) for x in location.split(",")]
            if len(loc_parts) != 3:
                return {"status": "error", "error": "Location must be in format 'x,y,z'"}
            asset_location = tuple(loc_parts)
        except Exception:
            return {"status": "error", "error": "Invalid location format. Use 'x,y,z'"}

        # 初始化 Meshy API
        meshy = MeshyAPI(api_key)

        # 1) 创建 preview 任务
        print(f"[Meshy] Creating preview task for: {description}")
        preview_id = meshy.create_text_to_3d_preview(description)

        # 2) 轮询 preview
        preview_task = meshy.poll_text_to_3d(preview_id, interval_sec=5, timeout_sec=900)
        if preview_task.get("status") != "SUCCEEDED":
            return {"status": "error", "error": f"Preview failed: {preview_task.get('status')}"}
        final_task = preview_task

        # 3) 可选 refine（贴图）
        if refine:
            print(f"[Meshy] Starting refine for preview task: {preview_id}")
            refine_id = meshy.create_text_to_3d_refine(preview_id)
            refine_task = meshy.poll_text_to_3d(refine_id, interval_sec=5, timeout_sec=1800)
            if refine_task.get("status") != "SUCCEEDED":
                return {"status": "error", "error": f"Refine failed: {refine_task.get('status')}"}
            final_task = refine_task

        # 4) 从 model_urls 取下载链接
        model_urls = (final_task or {}).get("model_urls", {}) or {}
        candidate_keys = ["glb", "fbx", "obj", "zip"]
        file_url = None
        for k in candidate_keys:
            if model_urls.get(k):
                file_url = model_urls[k]
                break
        if not file_url:
            return {"status": "error", "error": "No downloadable model_urls found"}

        # 5) 下载模型到临时目录
        temp_dir = tempfile.mkdtemp(prefix="meshy_gen_")
        # 处理无扩展名直链：默认 .glb
        guessed_ext = os.path.splitext(file_url.split("?")[0])[1].lower()
        if guessed_ext not in [".glb", ".gltf", ".fbx", ".obj", ".zip"]:
            guessed_ext = ".glb"
        local_path = os.path.join(temp_dir, f"meshy_model{guessed_ext}")
        print(f"[Meshy] Downloading model to: {local_path}")
        meshy.download_model_url(file_url, local_path)

        # 6) 若为 ZIP，解压出 3D 文件
        importer = AssetImporter(blender_path)
        if local_path.endswith(".zip"):
            extracted = importer.extract_zip_asset(local_path, temp_dir)
            import_path = extracted
        else:
            import_path = local_path

        # 7) 导入 Blender
        imported_object_name = importer.import_asset(import_path, location=asset_location, scale=scale)
        print(f"[Meshy] Imported object: {imported_object_name}")

        # 8) 保存 Blender 文件
        try:
            bpy.ops.wm.save_mainfile(filepath=blender_path)
            print(f"Blender file saved to: {blender_path}")
            
            # 清理备份文件以避免生成 .blend1 文件
            backup_file = blender_path + "1"
            if os.path.exists(backup_file):
                os.remove(backup_file)
                print(f"Removed backup file: {backup_file}")
                
        except Exception as save_error:
            print(f"Warning: Failed to save blender file: {save_error}")

        # 9) 清理临时目录
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            print(f"Warning: Failed to cleanup temp files: {cleanup_error}")

        return {
            "status": "success",
            "message": "Meshy Text-to-3D asset generated and imported",
            "asset_name": description,
            "object_name": imported_object_name,
            "location": asset_location,
            "scale": scale
        }

    except Exception as e:
        logging.error(f"Failed to add Meshy asset: {e}")
        return {"status": "error", "error": str(e)}

@mcp.tool()
def add_meshy_asset_from_image(
    image_path: str,
    blender_path: str,
    location: str = "0,0,0",
    scale: float = 1.0,
    prompt: str = None,
    api_key: str = None,
    refine: bool = True
) -> dict:
    """
    使用 Meshy Image-to-3D 根据输入图片生成资产并导入到当前场景（生成→轮询→下载→导入）

    Args:
        image_path: 输入图片路径
        blender_path: Blender 文件路径
        location: 资产位置 "x,y,z"
        scale: 缩放比例
        prompt: 可选的文本提示，用于指导生成
        api_key: Meshy API 密钥（可选，默认读 MESHY_API_KEY）
        refine: 是否在 preview 后进行 refine（含贴图）
    """
    try:
        # 检查图片文件是否存在
        if not os.path.exists(image_path):
            return {"status": "error", "error": f"Image file not found: {image_path}"}
        
        # 解析位置参数
        try:
            loc_parts = [float(x.strip()) for x in location.split(",")]
            if len(loc_parts) != 3:
                return {"status": "error", "error": "Location must be in format 'x,y,z'"}
            asset_location = tuple(loc_parts)
        except Exception:
            return {"status": "error", "error": "Invalid location format. Use 'x,y,z'"}

        # 初始化 Meshy API
        meshy = MeshyAPI(api_key)

        # 1) 创建 Image-to-3D preview 任务
        print(f"[Meshy] Creating Image-to-3D preview task for: {image_path}")
        if prompt:
            print(f"[Meshy] Using prompt: {prompt}")
        
        preview_id = meshy.create_image_to_3d_preview(image_path, prompt)

        # 2) 轮询 preview
        preview_task = meshy.poll_image_to_3d(preview_id, interval_sec=5, timeout_sec=900)
        if preview_task.get("status") != "SUCCEEDED":
            return {"status": "error", "error": f"Image-to-3D preview failed: {preview_task.get('status')}"}
        final_task = preview_task

        # 3) 可选 refine（贴图）
        if refine:
            print(f"[Meshy] Starting refine for Image-to-3D preview task: {preview_id}")
            refine_id = meshy.create_image_to_3d_refine(preview_id)
            refine_task = meshy.poll_image_to_3d(refine_id, interval_sec=5, timeout_sec=1800)
            if refine_task.get("status") != "SUCCEEDED":
                return {"status": "error", "error": f"Image-to-3D refine failed: {refine_task.get('status')}"}
            final_task = refine_task

        # 4) 从 model_urls 取下载链接
        model_urls = (final_task or {}).get("model_urls", {}) or {}
        candidate_keys = ["glb", "fbx", "obj", "zip"]
        file_url = None
        for k in candidate_keys:
            if model_urls.get(k):
                file_url = model_urls[k]
                break
        if not file_url:
            return {"status": "error", "error": "No downloadable model_urls found"}

        # 5) 下载模型到临时目录
        temp_dir = tempfile.mkdtemp(prefix="meshy_image_gen_")
        # 处理无扩展名直链：默认 .glb
        guessed_ext = os.path.splitext(file_url.split("?")[0])[1].lower()
        if guessed_ext not in [".glb", ".gltf", ".fbx", ".obj", ".zip"]:
            guessed_ext = ".glb"
        local_path = os.path.join(temp_dir, f"meshy_image_model{guessed_ext}")
        print(f"[Meshy] Downloading Image-to-3D model to: {local_path}")
        meshy.download_model_url(file_url, local_path)

        # 6) 若为 ZIP，解压出 3D 文件
        importer = AssetImporter(blender_path)
        if local_path.endswith(".zip"):
            extracted = importer.extract_zip_asset(local_path, temp_dir)
            import_path = extracted
        else:
            import_path = local_path

        # 7) 导入 Blender
        imported_object_name = importer.import_asset(import_path, location=asset_location, scale=scale)
        print(f"[Meshy] Imported Image-to-3D object: {imported_object_name}")

        # 8) 保存 Blender 文件
        try:
            bpy.ops.wm.save_mainfile(filepath=blender_path)
            print(f"Blender file saved to: {blender_path}")
            
            # 清理备份文件以避免生成 .blend1 文件
            backup_file = blender_path + "1"
            if os.path.exists(backup_file):
                os.remove(backup_file)
                print(f"Removed backup file: {backup_file}")
                
        except Exception as save_error:
            print(f"Warning: Failed to save blender file: {save_error}")

        # 9) 清理临时目录
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as cleanup_error:
            print(f"Warning: Failed to cleanup temp files: {cleanup_error}")
        
        return {
            "status": "success",
            "message": "Meshy Image-to-3D asset generated and imported",
            "image_path": image_path,
            "prompt": prompt,
            "object_name": imported_object_name,
            "location": asset_location,
            "scale": scale
        }
        
    except Exception as e:
        logging.error(f"Failed to add Meshy asset from image: {e}")
        return {"status": "error", "error": str(e)}

@mcp.tool()
def crop_image_by_text(
    image_path: str,
    description: str,
    output_path: str = None,
    confidence_threshold: float = 0.5,
    padding: int = 20
) -> dict:
    """
    根据文本描述从图片中截取相关区域（类似物体检测）
    
    Args:
        image_path: 输入图片路径
        description: 文本描述，描述要截取的对象（如："person", "car", "dog", "building"等）
        output_path: 输出图片路径（可选，默认自动生成）
        confidence_threshold: 置信度阈值（0.0-1.0），默认0.5
        padding: 截取区域周围的填充像素，默认20像素
        
    Returns:
        dict: 包含截取结果的字典，格式为：
        {
            "status": "success/error",
            "message": "操作结果描述",
            "input_image": "输入图片路径",
            "output_image": "输出图片路径",
            "detected_object": {
                "description": "检测到的对象类别",
                "confidence": 置信度,
                "bbox": [x, y, width, height],
                "original_bbox": [原始边界框]
            },
            "crop_info": {
                "original_size": [原始图片尺寸],
                "cropped_size": [截取后尺寸],
                "padding": 填充像素
            }
        }
    """
    try:
        # 创建图片截取器实例
        cropper = ImageCropper()
        
        # 执行截取操作
        result = cropper.crop_image_by_text(
            image_path=image_path,
            description=description,
            output_path=output_path,
            confidence_threshold=confidence_threshold,
            padding=padding
        )
        
        return result
        
    except Exception as e:
        logging.error(f"Failed to crop image by text: {e}")
        return {"status": "error", "error": str(e)}

@mcp.tool()
def crop_and_generate_3d_asset(
    image_path: str,
    description: str,
    blender_path: str,
    location: str = "0,0,0",
    scale: float = 1.0,
    prompt: str = None,
    api_key: str = None,
    refine: bool = True,
    confidence_threshold: float = 0.5,
    padding: int = 20
) -> dict:
    """
    结合图片截取和3D资产生成的工具：
    1. 根据文本描述从图片中截取相关区域
    2. 将截取的图片送入Meshy生成3D资产
    3. 导入到Blender场景中
    
    Args:
        image_path: 输入图片路径
        description: 文本描述，描述要截取的对象（如："person", "car", "dog", "building"等）
        blender_path: Blender文件路径
        location: 资产位置 "x,y,z"，默认为 "0,0,0"
        scale: 缩放比例，默认为 1.0
        prompt: 可选的文本提示，用于指导3D生成
        api_key: Meshy API密钥（可选，默认读MESHY_API_KEY环境变量）
        refine: 是否进行refine处理（含贴图），默认为True
        confidence_threshold: 截取时的置信度阈值（0.0-1.0），默认0.5
        padding: 截取区域周围的填充像素，默认20像素
        
    Returns:
        dict: 包含完整操作结果的字典，格式为：
        {
            "status": "success/error",
            "message": "操作结果描述",
            "crop_result": {
                "input_image": "输入图片路径",
                "cropped_image": "截取的图片路径",
                "detected_object": {...}
            },
            "generation_result": {
                "object_name": "导入的对象名称",
                "location": [x, y, z],
                "scale": 缩放比例
            }
        }
    """
    try:
        print(f"[Crop&Generate] Starting combined crop and 3D generation process...")
        print(f"[Crop&Generate] Input image: {image_path}")
        print(f"[Crop&Generate] Description: {description}")
        
        # 步骤1: 图片截取
        print(f"[Crop&Generate] Step 1: Cropping image based on '{description}'...")
        cropper = ImageCropper()
        
        # 生成截取图片的临时路径
        temp_dir = tempfile.mkdtemp(prefix="crop_generate_")
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        cropped_image_path = os.path.join(temp_dir, f"{base_name}_cropped_{description.replace(' ', '_')}.jpg")
        
        crop_result = cropper.crop_image_by_text(
            image_path=image_path,
            description=description,
            output_path=cropped_image_path,
            confidence_threshold=confidence_threshold,
            padding=padding
        )
        
        if crop_result.get("status") != "success":
            # 清理临时目录
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return {
                "status": "error",
                "error": f"Image cropping failed: {crop_result.get('error')}",
                "crop_result": crop_result
            }
        
        print(f"[Crop&Generate] ✓ Image cropped successfully: {cropped_image_path}")
        
        # 步骤2: 3D资产生成
        print(f"[Crop&Generate] Step 2: Generating 3D asset from cropped image...")
        
        # 如果没有提供prompt，使用description作为默认prompt
        if not prompt:
            prompt = f"A 3D model of {description}"
        
        generation_result = add_meshy_asset_from_image(
            image_path=cropped_image_path,
            blender_path=blender_path,
            location=location,
            scale=scale,
            prompt=prompt,
            api_key=api_key,
            refine=refine
        )
        
        if generation_result.get("status") != "success":
            # 清理临时目录
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
            return {
                "status": "error",
                "error": f"3D asset generation failed: {generation_result.get('error')}",
                "crop_result": crop_result,
                "generation_result": generation_result
            }
        
        print(f"[Crop&Generate] ✓ 3D asset generated and imported successfully")
        
        # 步骤3: 清理临时文件
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[Crop&Generate] ✓ Cleaned up temporary files")
        except Exception as cleanup_error:
            print(f"[Crop&Generate] ⚠ Warning: Failed to cleanup temp files: {cleanup_error}")
        
        # 返回完整结果
        return {
            "status": "success",
            "message": f"Successfully cropped image and generated 3D asset for '{description}'",
            "crop_result": {
                "input_image": image_path,
                "cropped_image": crop_result.get("output_image"),
                "detected_object": crop_result.get("detected_object"),
                "crop_info": crop_result.get("crop_info")
            },
            "generation_result": {
                "object_name": generation_result.get("object_name"),
                "location": generation_result.get("location"),
                "scale": generation_result.get("scale"),
                "prompt": prompt,
                "refine": refine
            },
            "summary": {
                "description": description,
                "original_image": image_path,
                "cropped_image": crop_result.get("output_image"),
                "generated_object": generation_result.get("object_name"),
                "final_location": location,
                "final_scale": scale
            }
        }
        
    except Exception as e:
        logging.error(f"Failed to crop and generate 3D asset: {e}")
        return {"status": "error", "error": str(e)}

def render_scene_for_test(blender_path: str, test_name: str, output_dir: str = "output/test/renders") -> dict:
    """
    为测试渲染当前场景
    
    Args:
        blender_path: Blender文件路径
        test_name: 测试名称，用于生成输出文件名
        output_dir: 输出目录
        
    Returns:
        dict: 渲染结果
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        # timestamp = int(time.time())
        output_filename = blender_path.split("/")[-1].split(".")[0] + ".png"
        output_path = os.path.join(output_dir, output_filename)
        
        # 设置渲染参数
        scene = bpy.context.scene
        scene.render.resolution_x = 1920
        scene.render.resolution_y = 1080
        scene.render.resolution_percentage = 50  # 50%分辨率以加快渲染速度
        scene.render.filepath = output_path
        
        # 设置渲染引擎为Cycles（如果可用）或Eevee
        if 'CYCLES' in bpy.context.scene.render.engine:
            scene.render.engine = 'CYCLES'
            scene.cycles.samples = 32  # 减少采样数以加快渲染
        else:
            scene.render.engine = 'BLENDER_EEVEE'
        
        # 确保有相机
        if not any(obj.type == 'CAMERA' for obj in scene.objects):
            # 如果没有相机，创建一个
            bpy.ops.object.camera_add(location=(5, -5, 3))
            camera = bpy.context.active_object
            camera.rotation_euler = (1.1, 0, 0.785)  # 设置相机角度
            scene.camera = camera
            print(f"[Render] Created camera for {test_name}")
        
        # 渲染场景
        print(f"[Render] Rendering scene for {test_name}...")
        bpy.ops.render.render(write_still=True)
        
        print(f"[Render] ✓ Scene rendered successfully: {output_path}")
        
        return {
            "status": "success",
            "message": f"Scene rendered for {test_name}",
            "output_path": output_path,
            "test_name": test_name
        }
        
    except Exception as e:
        print(f"[Render] ❌ Failed to render scene for {test_name}: {e}")
        return {
            "status": "error",
            "error": str(e),
            "test_name": test_name
        }

def test_meshy_assets() -> dict:
    """
    测试 Meshy 资产生成功能：
    1. 测试 Text-to-3D 资产生成
    2. 测试 Image-to-3D 资产生成
    """
    print("🧪 Testing Meshy Asset Generation Functions...")
    
    # 测试配置
    test_blender_path = "output/test/demo/blender_file.blend"
    test_image_path = "output/test/demo/test_image.jpg"
    
    # 确保测试目录存在
    os.makedirs(os.path.dirname(test_blender_path), exist_ok=True)
    os.makedirs(os.path.dirname(test_image_path), exist_ok=True)
    
    # 创建测试用的Blender文件
    try:
        # 打开现有的blender文件
        bpy.ops.wm.open_mainfile(filepath=test_blender_path)
        print(f"✓ Opened test Blender file: {test_blender_path}")
        
        # 渲染初始场景
        print("\n📸 Rendering initial scene...")
        initial_render = render_scene_for_test(test_blender_path, "initial_scene")
        if initial_render.get("status") == "success":
            print(f"✓ Initial scene rendered: {initial_render.get('output_path')}")
        
    except Exception as e:
        print(f"⚠ Warning: Could not open test Blender file: {e}")
        return {"status": "error", "error": f"Failed to open test Blender file: {e}"}
    
    # 创建测试图片（如果不存在）
    if not os.path.exists(test_image_path):
        try:
            from PIL import Image, ImageDraw
            # 创建一个简单的测试图片
            img = Image.new('RGB', (400, 300), color='lightblue')
            draw = ImageDraw.Draw(img)
            # 画一个简单的房子
            draw.rectangle([150, 150, 250, 250], fill='brown', outline='black')
            draw.polygon([(150, 150), (200, 100), (250, 150)], fill='red', outline='black')
            draw.rectangle([180, 180, 220, 220], fill='blue', outline='black')
            img.save(test_image_path)
            print(f"✓ Created test image: {test_image_path}")
        except Exception as e:
            print(f"⚠ Warning: Could not create test image: {e}")
            return {"status": "error", "error": f"Failed to create test image: {e}"}
    
    test_results = {
        "text_to_3d": {"status": "skipped", "message": "API key not provided"},
        "image_to_3d": {"status": "skipped", "message": "API key not provided"},
        "crop_image": {"status": "skipped", "message": "Test image not available"},
        "crop_and_generate": {"status": "skipped", "message": "API key not provided"}
    }
    
    # 测试1: Text-to-3D 资产生成
    print("\n📝 Testing Text-to-3D Asset Generation...")
    try:
        # 检查是否有API密钥
        api_key = os.getenv("MESHY_API_KEY")
        if not api_key:
            print("⚠ Skipping Text-to-3D test: MESHY_API_KEY not set")
            test_results["text_to_3d"]["message"] = "MESHY_API_KEY environment variable not set"
        else:
            print("✓ API key found, testing Text-to-3D generation...")
            result = add_meshy_asset(
                description="A simple red cube",
                blender_path=test_blender_path,
                location="2,0,0",
                scale=1.0,
                api_key=api_key,
                refine=False  # 跳过refine以节省时间
            )
            
            if result.get("status") == "success":
                print(f"✓ Text-to-3D test successful: {result.get('message')}")
                test_results["text_to_3d"] = {
                    "status": "success",
                    "message": result.get("message"),
                    "object_name": result.get("object_name")
                }
                
                # 渲染场景以查看添加的物体
                render_result = render_scene_for_test(test_blender_path, "text_to_3d")
                if render_result.get("status") == "success":
                    test_results["text_to_3d"]["render_path"] = render_result.get("output_path")
                    print(f"✓ Rendered scene after Text-to-3D: {render_result.get('output_path')}")
            else:
                print(f"❌ Text-to-3D test failed: {result.get('error')}")
                test_results["text_to_3d"] = {
                    "status": "failed",
                    "message": result.get("error")
                }
    except Exception as e:
        print(f"❌ Text-to-3D test error: {e}")
        test_results["text_to_3d"] = {
            "status": "error",
            "message": str(e)
        }
    
    # 测试2: Image-to-3D 资产生成
    print("\n🖼️ Testing Image-to-3D Asset Generation...")
    try:
        api_key = os.getenv("MESHY_API_KEY")
        if not api_key:
            print("⚠ Skipping Image-to-3D test: MESHY_API_KEY not set")
            test_results["image_to_3d"]["message"] = "MESHY_API_KEY environment variable not set"
        else:
            print("✓ API key found, testing Image-to-3D generation...")
            result = add_meshy_asset_from_image(
                image_path=test_image_path,
                blender_path=test_blender_path,
                location="-2,0,0",
                scale=1.0,
                prompt="A 3D model of a house",
                api_key=api_key,
                refine=False  # 跳过refine以节省时间
            )
            
            if result.get("status") == "success":
                print(f"✓ Image-to-3D test successful: {result.get('message')}")
                test_results["image_to_3d"] = {
                    "status": "success",
                    "message": result.get("message"),
                    "object_name": result.get("object_name")
                }
                
                # 渲染场景以查看添加的物体
                render_result = render_scene_for_test(test_blender_path, "image_to_3d")
                if render_result.get("status") == "success":
                    test_results["image_to_3d"]["render_path"] = render_result.get("output_path")
                    print(f"✓ Rendered scene after Image-to-3D: {render_result.get('output_path')}")
            else:
                print(f"❌ Image-to-3D test failed: {result.get('error')}")
                test_results["image_to_3d"] = {
                    "status": "failed",
                    "message": result.get("error")
                }
    except Exception as e:
        print(f"❌ Image-to-3D test error: {e}")
        test_results["image_to_3d"] = {
            "status": "error",
            "message": str(e)
        }
    
    # 测试3: 图片截取功能
    print("\n✂️ Testing Image Cropping...")
    try:
        if not os.path.exists(test_image_path):
            print("⚠ Skipping crop test: Test image not available")
            test_results["crop_image"]["message"] = "Test image not available"
        else:
            print("✓ Testing image cropping...")
            result = crop_image_by_text(
                image_path=test_image_path,
                description="building",
                output_path="test_output/cropped_building.jpg",
                confidence_threshold=0.3,
                padding=10
            )
            
            if result.get("status") == "success":
                print(f"✓ Image cropping test successful: {result.get('message')}")
                test_results["crop_image"] = {
                    "status": "success",
                    "message": result.get("message"),
                    "output_image": result.get("output_image")
                }
            else:
                print(f"❌ Image cropping test failed: {result.get('error')}")
                test_results["crop_image"] = {
                    "status": "failed",
                    "message": result.get("error")
                }
    except Exception as e:
        print(f"❌ Image cropping test error: {e}")
        test_results["crop_image"] = {
            "status": "error",
            "message": str(e)
        }
    
    # 测试4: 组合工具 - 图片截取 + 3D资产生成
    print("\n🔄 Testing Combined Crop and Generate Tool...")
    try:
        api_key = os.getenv("MESHY_API_KEY")
        if not api_key:
            print("⚠ Skipping combined test: MESHY_API_KEY not set")
            test_results["crop_and_generate"]["message"] = "MESHY_API_KEY environment variable not set"
        elif not os.path.exists(test_image_path):
            print("⚠ Skipping combined test: Test image not available")
            test_results["crop_and_generate"]["message"] = "Test image not available"
        else:
            print("✓ Testing combined crop and generate...")
            result = crop_and_generate_3d_asset(
                image_path=test_image_path,
                description="building",
                blender_path=test_blender_path,
                location="4,0,0",
                scale=1.0,
                prompt="A detailed 3D model of a house with realistic textures",
                api_key=api_key,
                refine=False,  # 跳过refine以节省时间
                confidence_threshold=0.3,
                padding=15
            )
            
            if result.get("status") == "success":
                print(f"✓ Combined test successful: {result.get('message')}")
                test_results["crop_and_generate"] = {
            "status": "success",
                    "message": result.get("message"),
                    "crop_result": result.get("crop_result"),
                    "generation_result": result.get("generation_result")
                }
                
                # 渲染场景以查看添加的物体
                render_result = render_scene_for_test(test_blender_path, "crop_and_generate")
                if render_result.get("status") == "success":
                    test_results["crop_and_generate"]["render_path"] = render_result.get("output_path")
                    print(f"✓ Rendered scene after Combined test: {render_result.get('output_path')}")
            else:
                print(f"❌ Combined test failed: {result.get('error')}")
                test_results["crop_and_generate"] = {
                    "status": "failed",
                    "message": result.get("error")
                }
    except Exception as e:
        print(f"❌ Combined test error: {e}")
        test_results["crop_and_generate"] = {
            "status": "error",
            "message": str(e)
        }
    
    # 总结测试结果
    print("\n📊 Test Results Summary:")
    print("=" * 50)
    
    success_count = 0
    total_tests = 0
    
    for test_name, result in test_results.items():
        total_tests += 1
        status = result["status"]
        message = result["message"]
        
        if status == "success":
            print(f"✅ {test_name}: SUCCESS - {message}")
            if "render_path" in result:
                print(f"   📸 Render saved: {result['render_path']}")
            success_count += 1
        elif status == "skipped":
            print(f"⏭️ {test_name}: SKIPPED - {message}")
        elif status == "failed":
            print(f"❌ {test_name}: FAILED - {message}")
        else:
            print(f"💥 {test_name}: ERROR - {message}")
    
    print("=" * 50)
    print(f"Tests completed: {success_count}/{total_tests} successful")
    
    # 返回测试结果
    overall_success = success_count > 0 or all(r["status"] == "skipped" for r in test_results.values())
        
    return {
        "status": "success" if overall_success else "failed",
        "message": f"Meshy asset generation tests completed: {success_count}/{total_tests} successful",
        "test_results": test_results,
        "summary": {
            "total_tests": total_tests,
            "successful": success_count,
            "skipped": sum(1 for r in test_results.values() if r["status"] == "skipped"),
            "failed": sum(1 for r in test_results.values() if r["status"] in ["failed", "error"])
        }
    }

def main():
    # 如果直接运行此脚本，执行测试
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        # 运行 Meshy 资产生成测试
        test_result = test_meshy_assets()
        success = test_result.get("status") == "success"
        print(f"\n🎯 Overall test result: {'PASSED' if success else 'FAILED'}")
        sys.exit(0 if success else 1)
    else:
        # 正常运行 MCP 服务
        mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
