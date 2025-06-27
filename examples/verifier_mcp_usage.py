#!/usr/bin/env python3
"""
Example usage of the MCP Verifier Agent with Generator and Executor integration.

This example demonstrates how to:
1. Initialize a Verifier Agent session
2. Verify scenes against target images
3. Provide feedback to Generator Agent
4. Integrate with the complete generation-verification loop

Usage:
    python examples/verifier_mcp_usage.py --api-key "your-openai-api-key" --target-images path/to/target/images
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional
import requests
import base64
from PIL import Image
import io

# Add the project root to the path
sys.path.append(str(Path(__file__).parent.parent))

class MCPVerifierClient:
    """Client for interacting with the MCP Verifier Agent."""
    
    def __init__(self, verifier_server_url: str = "http://localhost:8004"):
        self.verifier_server_url = verifier_server_url
        self.session_id = None
    
    def create_session(self, **kwargs) -> str:
        """Create a new verification session."""
        response = requests.post(
            f"{self.verifier_server_url}/create_verification_session",
            json=kwargs
        )
        response.raise_for_status()
        result = response.json()
        self.session_id = result["session_id"]
        return self.session_id
    
    def verify_scene(self, code: str, render_path: str, round_num: int) -> Dict[str, Any]:
        """Verify a scene against the target."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.post(
            f"{self.verifier_server_url}/verify_scene",
            json={
                "session_id": self.session_id,
                "code": code,
                "render_path": render_path,
                "round_num": round_num
            }
        )
        response.raise_for_status()
        return response.json()
    
    def exec_pil_code(self, code: str) -> Dict[str, Any]:
        """Execute PIL code for image processing."""
        response = requests.post(
            f"{self.verifier_server_url}/exec_pil_code",
            json={"code": code}
        )
        response.raise_for_status()
        return response.json()
    
    def compare_images(self, path1: str, path2: str, api_key: str) -> Dict[str, Any]:
        """Compare two images and describe differences."""
        response = requests.post(
            f"{self.verifier_server_url}/compare_images",
            json={
                "path1": path1,
                "path2": path2,
                "api_key": api_key
            }
        )
        response.raise_for_status()
        return response.json()
    
    def save_thought_process(self) -> None:
        """Save the thought process for the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.post(
            f"{self.verifier_server_url}/save_thought_process",
            json={"session_id": self.session_id}
        )
        response.raise_for_status()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.get(
            f"{self.verifier_server_url}/get_session_info",
            params={"session_id": self.session_id}
        )
        response.raise_for_status()
        return response.json()


class MCPGeneratorClient:
    """Client for interacting with the MCP Generator Agent."""
    
    def __init__(self, generator_server_url: str = "http://localhost:8000"):
        self.generator_server_url = generator_server_url
        self.session_id = None
    
    def create_session(self, **kwargs) -> str:
        """Create a new generation session."""
        response = requests.post(
            f"{self.generator_server_url}/create_generation_session",
            json=kwargs
        )
        response.raise_for_status()
        result = response.json()
        self.session_id = result["session_id"]
        return self.session_id
    
    def generate_code(self, feedback: Optional[str] = None) -> Dict[str, Any]:
        """Generate code for the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.post(
            f"{self.generator_server_url}/generate_code",
            json={
                "session_id": self.session_id,
                "feedback": feedback
            }
        )
        response.raise_for_status()
        return response.json()
    
    def add_feedback(self, feedback: str) -> None:
        """Add feedback to the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.post(
            f"{self.generator_server_url}/add_feedback",
            json={
                "session_id": self.session_id,
                "feedback": feedback
            }
        )
        response.raise_for_status()


class BlenderExecutorClient:
    """Client for interacting with the Blender Executor."""
    
    def __init__(self, blender_server_url: str = "http://localhost:8001"):
        self.blender_server_url = blender_server_url
    
    def execute_script(self, code: str, round_num: int, **kwargs) -> Dict[str, Any]:
        """Execute a Blender script."""
        response = requests.post(
            f"{self.blender_server_url}/exec_script",
            json={
                "code": code,
                "round": round_num,
                **kwargs
            }
        )
        response.raise_for_status()
        return response.json()


def save_base64_image(base64_data: str, output_path: str) -> None:
    """Save a base64 encoded image to file."""
    try:
        image_data = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_data))
        image.save(output_path)
        print(f"Saved image to: {output_path}")
    except Exception as e:
        print(f"Failed to save image: {e}")


def run_complete_workflow_example(args):
    """Run the complete generation-verification workflow example."""
    print("=== Complete Generation-Verification Workflow Example ===")
    
    # Initialize clients
    generator_client = MCPGeneratorClient()
    verifier_client = MCPVerifierClient()
    blender_client = BlenderExecutorClient()
    
    # Create generation session
    print("Creating generation session...")
    generator_session_id = generator_client.create_session(
        vision_model=args.vision_model,
        api_key=args.api_key,
        thoughtprocess_save=args.thoughtprocess_save,
        max_rounds=args.max_rounds,
        generator_hints=args.generator_hints,
        init_code=args.init_code,
        init_image_path=args.init_image_path,
        target_image_path=args.target_image_path,
        target_description=args.target_description
    )
    print(f"Generator session created: {generator_session_id}")
    
    # Create verification session
    print("Creating verification session...")
    verifier_session_id = verifier_client.create_session(
        vision_model=args.vision_model,
        api_key=args.api_key,
        thoughtprocess_save=args.verifier_thoughtprocess_save,
        max_rounds=args.max_rounds,
        verifier_hints=args.verifier_hints,
        target_image_path=args.target_image_path,
        blender_save=args.blender_save
    )
    print(f"Verifier session created: {verifier_session_id}")
    
    # Generation-verification loop
    for round_num in range(args.max_rounds):
        print(f"\n--- Round {round_num + 1} ---")
        
        # Generate code
        print("Generating code...")
        generation_result = generator_client.generate_code()
        
        if generation_result["status"] == "max_rounds_reached":
            print("Maximum rounds reached. Stopping.")
            break
        elif generation_result["status"] == "error":
            print(f"Generation error: {generation_result['error']}")
            break
        
        code = generation_result["code"]
        print(f"Generated code for round {generation_result['round']}")
        
        # Execute code
        print("Executing code...")
        execution_result = blender_client.execute_script(
            code=code,
            round_num=round_num,
            blender_command=args.blender_command,
            blender_file=args.blender_file,
            blender_script=args.blender_script,
            script_save=args.script_save,
            render_save=args.render_save,
            blender_save=args.blender_save
        )
        
        if execution_result["status"] == "success":
            print("Code executed successfully")
            
            # Save the rendered image
            if "output" in execution_result:
                image_path = f"output/round_{round_num}_render.png"
                save_base64_image(execution_result["output"], image_path)
            
            # Verify result
            print("Verifying result...")
            verify_result = verifier_client.verify_scene(
                code=code,
                render_path=args.render_save,
                round_num=round_num
            )
            
            if verify_result["status"] == "end":
                print("Verification successful - task completed!")
                break
            elif verify_result["status"] == "continue":
                feedback = verify_result["output"]
                print(f"Verification feedback: {feedback}")
                generator_client.add_feedback(feedback)
            else:
                print(f"Verification status: {verify_result['status']}")
                if "error" in verify_result:
                    print(f"Verification error: {verify_result['error']}")
        else:
            print(f"Execution failed: {execution_result['output']}")
            generator_client.add_feedback(f"Execution error: {execution_result['output']}")
        
        # Save thought processes
        generator_client.save_thought_process()
        verifier_client.save_thought_process()
        
        # Brief pause between rounds
        time.sleep(1)
    
    print("\n=== Workflow Complete ===")
    
    # Get final session info
    generator_info = generator_client.get_session_info()
    verifier_info = verifier_client.get_session_info()
    print(f"Generator session info: {json.dumps(generator_info, indent=2)}")
    print(f"Verifier session info: {json.dumps(verifier_info, indent=2)}")


def run_verification_only_example(args):
    """Run verification-only example."""
    print("=== Verification Only Example ===")
    
    # Initialize verifier client
    verifier_client = MCPVerifierClient()
    
    # Create verification session
    print("Creating verification session...")
    session_id = verifier_client.create_session(
        vision_model=args.vision_model,
        api_key=args.api_key,
        thoughtprocess_save=args.verifier_thoughtprocess_save,
        max_rounds=args.max_rounds,
        verifier_hints=args.verifier_hints,
        target_image_path=args.target_image_path,
        blender_save=args.blender_save
    )
    print(f"Session created: {session_id}")
    
    # Test PIL code execution
    print("Testing PIL code execution...")
    pil_code = """
from PIL import Image, ImageDraw
import numpy as np

# Create a test image
img = Image.new('RGB', (200, 200), 'white')
draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 150, 150], fill='red')
result = img
"""
    
    pil_result = verifier_client.exec_pil_code(pil_code)
    if pil_result["success"]:
        print("PIL code executed successfully")
        # Save the result image
        if "result" in pil_result and pil_result["result"]:
            save_base64_image(pil_result["result"], "output/pil_test_result.png")
    else:
        print(f"PIL code failed: {pil_result['error']}")
    
    # Test image comparison (if we have two images to compare)
    if args.compare_image1 and args.compare_image2:
        print("Testing image comparison...")
        compare_result = verifier_client.compare_images(
            args.compare_image1, 
            args.compare_image2, 
            args.api_key
        )
        print(f"Comparison result: {compare_result}")
    
    # Test scene verification with mock data
    print("Testing scene verification...")
    test_code = """
import bpy
# Test Blender code
bpy.ops.mesh.primitive_cube_add()
"""
    
    # Create mock render directory
    os.makedirs(args.render_save, exist_ok=True)
    
    # Create mock render images
    from PIL import Image, ImageDraw
    
    # Mock render1.png
    render1 = Image.new('RGB', (400, 300), 'lightblue')
    draw1 = ImageDraw.Draw(render1)
    draw1.rectangle([100, 100, 300, 200], fill='gray')
    render1.save(os.path.join(args.render_save, 'render1.png'))
    
    # Mock render2.png
    render2 = Image.new('RGB', (400, 300), 'lightgreen')
    draw2 = ImageDraw.Draw(render2)
    draw2.rectangle([150, 150, 250, 250], fill='gray')
    render2.save(os.path.join(args.render_save, 'render2.png'))
    
    print("Created mock render images")
    
    # Verify scene
    verify_result = verifier_client.verify_scene(
        code=test_code,
        render_path=args.render_save,
        round_num=0
    )
    
    print(f"Verification result: {verify_result}")
    
    # Save thought process
    verifier_client.save_thought_process()
    
    print("\n=== Verification Only Example Complete ===")
    session_info = verifier_client.get_session_info()
    print(f"Session info: {json.dumps(session_info, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="MCP Verifier Agent Usage Example")
    parser.add_argument("--mode", choices=["complete", "verification"], default="verification",
                       help="Example mode")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--api-key", required=True,
                       help="OpenAI API key")
    parser.add_argument("--thoughtprocess-save", default="generator_thought_process.json",
                       help="Path to save generator thought process")
    parser.add_argument("--verifier-thoughtprocess-save", default="verifier_thought_process.json",
                       help="Path to save verifier thought process")
    parser.add_argument("--max-rounds", type=int, default=5,
                       help="Maximum number of rounds")
    parser.add_argument("--generator-hints", default=None,
                       help="Hints for code generation")
    parser.add_argument("--verifier-hints", default=None,
                       help="Hints for verification")
    parser.add_argument("--init-code", default=None,
                       help="Path to initial code file")
    parser.add_argument("--init-image-path", default=None,
                       help="Path to initial images directory")
    parser.add_argument("--target-image-path", default=None,
                       help="Path to target images directory")
    parser.add_argument("--target-description", default=None,
                       help="Description of target")
    parser.add_argument("--blender-save", default=None,
                       help="Blender save path")
    
    # Blender-specific arguments
    parser.add_argument("--blender-command", default="blender",
                       help="Blender command")
    parser.add_argument("--blender-file", default="scene.blend",
                       help="Blender file path")
    parser.add_argument("--blender-script", default="render_script.py",
                       help="Blender script path")
    parser.add_argument("--script-save", default="scripts",
                       help="Script save directory")
    parser.add_argument("--render-save", default="renders",
                       help="Render save directory")
    
    # Image comparison arguments
    parser.add_argument("--compare-image1", default=None,
                       help="First image for comparison")
    parser.add_argument("--compare-image2", default=None,
                       help="Second image for comparison")
    
    args = parser.parse_args()
    
    # Read initial code from file if provided
    if args.init_code and os.path.exists(args.init_code):
        with open(args.init_code, 'r') as f:
            args.init_code = f.read()
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Run appropriate example
    if args.mode == "complete":
        run_complete_workflow_example(args)
    elif args.mode == "verification":
        run_verification_only_example(args)


if __name__ == "__main__":
    main() 