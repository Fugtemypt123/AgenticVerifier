#!/usr/bin/env python3
"""
Example usage of the MCP Generator Agent with Blender and Slides executors.

This example demonstrates how to:
1. Initialize a Generator Agent session
2. Generate code iteratively
3. Execute code using Blender or Slides executors
4. Verify results and provide feedback
5. Continue the generation loop until completion

Usage:
    python examples/generator_mcp_usage.py --mode blender --init-code path/to/init.py --init-images path/to/init/images --target-images path/to/target/images
    python examples/generator_mcp_usage.py --mode slides --init-code path/to/init.py --code-save path/to/save/code
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
    
    def save_thought_process(self) -> None:
        """Save the thought process for the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.post(
            f"{self.generator_server_url}/save_thought_process",
            json={"session_id": self.session_id}
        )
        response.raise_for_status()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session."""
        if not self.session_id:
            raise ValueError("No active session. Call create_session first.")
        
        response = requests.get(
            f"{self.generator_server_url}/get_session_info",
            params={"session_id": self.session_id}
        )
        response.raise_for_status()
        return response.json()


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


class SlidesExecutorClient:
    """Client for interacting with the Slides Executor."""
    
    def __init__(self, slides_server_url: str = "http://localhost:8002"):
        self.slides_server_url = slides_server_url
    
    def execute_pptx(self, code: str, round_num: int, code_save: str) -> Dict[str, Any]:
        """Execute a PPTX generation script."""
        response = requests.post(
            f"{self.slides_server_url}/exec_pptx",
            json={
                "code": code,
                "round": round_num,
                "code_save": code_save
            }
        )
        response.raise_for_status()
        return response.json()


class VerifierClient:
    """Client for interacting with the Verifier."""
    
    def __init__(self, verifier_server_url: str = "http://localhost:8003"):
        self.verifier_server_url = verifier_server_url
    
    def verify_scene(self, code: str, render_path: str, round_num: int) -> Dict[str, Any]:
        """Verify a 3D scene."""
        response = requests.post(
            f"{self.verifier_server_url}/verify_scene",
            json={
                "code": code,
                "render_path": render_path,
                "round": round_num
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


def run_blender_generation_example(args):
    """Run the Blender generation example."""
    print("=== Blender Generation Example ===")
    
    # Initialize clients
    generator_client = MCPGeneratorClient()
    blender_client = BlenderExecutorClient()
    verifier_client = VerifierClient()
    
    # Create generation session
    print("Creating generation session...")
    session_id = generator_client.create_session(
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
    print(f"Session created: {session_id}")
    
    # Generation loop
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
            else:
                feedback = verify_result["output"]
                print(f"Verification feedback: {feedback}")
                generator_client.add_feedback(feedback)
        else:
            print(f"Execution failed: {execution_result['output']}")
            generator_client.add_feedback(f"Execution error: {execution_result['output']}")
        
        # Save thought process
        generator_client.save_thought_process()
        
        # Brief pause between rounds
        time.sleep(1)
    
    print("\n=== Generation Complete ===")
    session_info = generator_client.get_session_info()
    print(f"Final session info: {json.dumps(session_info, indent=2)}")


def run_slides_generation_example(args):
    """Run the Slides generation example."""
    print("=== Slides Generation Example ===")
    
    # Initialize clients
    generator_client = MCPGeneratorClient()
    slides_client = SlidesExecutorClient()
    
    # Create generation session
    print("Creating generation session...")
    session_id = generator_client.create_session(
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
    print(f"Session created: {session_id}")
    
    # Generation loop
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
        execution_result = slides_client.execute_pptx(
            code=code,
            round_num=round_num,
            code_save=args.code_save
        )
        
        if execution_result["status"] == "success":
            print("Code executed successfully")
            
            # Save the generated image
            if "image_base64" in execution_result:
                image_path = f"output/round_{round_num}_slide.jpg"
                save_base64_image(execution_result["image_base64"], image_path)
            
            # For slides, we might want to add some basic feedback
            feedback = "Slide generated successfully. Please review the visual result."
            generator_client.add_feedback(feedback)
        else:
            print(f"Execution failed: {execution_result['output']}")
            generator_client.add_feedback(f"Execution error: {execution_result['output']}")
        
        # Save thought process
        generator_client.save_thought_process()
        
        # Brief pause between rounds
        time.sleep(1)
    
    print("\n=== Generation Complete ===")
    session_info = generator_client.get_session_info()
    print(f"Final session info: {json.dumps(session_info, indent=2)}")


def main():
    parser = argparse.ArgumentParser(description="MCP Generator Agent Usage Example")
    parser.add_argument("--mode", choices=["blender", "slides"], required=True,
                       help="Generation mode")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--api-key", required=True,
                       help="OpenAI API key")
    parser.add_argument("--thoughtprocess-save", default="thought_process.json",
                       help="Path to save thought process")
    parser.add_argument("--max-rounds", type=int, default=10,
                       help="Maximum number of generation rounds")
    parser.add_argument("--generator-hints", default=None,
                       help="Hints for code generation")
    parser.add_argument("--init-code", required=True,
                       help="Path to initial code file")
    parser.add_argument("--init-image-path", default=None,
                       help="Path to initial images directory")
    parser.add_argument("--target-image-path", default=None,
                       help="Path to target images directory")
    parser.add_argument("--target-description", default=None,
                       help="Description of target")
    
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
    parser.add_argument("--blender-save", default=None,
                       help="Blender save path")
    
    # Slides-specific arguments
    parser.add_argument("--code-save", default="slides_code",
                       help="Code save directory for slides")
    
    args = parser.parse_args()
    
    # Read initial code from file
    with open(args.init_code, 'r') as f:
        args.init_code = f.read()
    
    # Create output directory
    os.makedirs("output", exist_ok=True)
    
    # Run appropriate example
    if args.mode == "blender":
        run_blender_generation_example(args)
    elif args.mode == "slides":
        run_slides_generation_example(args)


if __name__ == "__main__":
    main() 