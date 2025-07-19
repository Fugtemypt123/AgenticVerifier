#!/usr/bin/env python3
"""
BlenderGym Runner for AgenticVerifier
Loads BlenderGym dataset and runs the dual-agent system for 3D scene generation.
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

def load_blendergym_dataset(base_path: str) -> List[Dict]:
    """
    Load BlenderGym dataset structure.
    
    Args:
        base_path: Path to BlenderGym dataset root
        
    Returns:
        List of task configurations
    """
    tasks = []
    base_path = Path(base_path)
    
    if not base_path.exists():
        print(f"Error: BlenderGym dataset path does not exist: {base_path}")
        return tasks
    
    # Traverse BlenderGym dataset structure
    # Expected structure: base_path/task_name/blendshape*/start.py, goal/renders/
    for task_dir in base_path.iterdir():
        if not task_dir.is_dir():
            continue
            
        task_name = task_dir.name
        
        # Look for blendshape directories
        for blendshape_dir in task_dir.glob("blendshape*"):
            if not blendshape_dir.is_dir():
                continue
                
            # Check for required files
            start_file = blendshape_dir / "start.py"
            goal_renders_dir = blendshape_dir / "renders" / "goal"
            
            if not start_file.exists():
                print(f"Warning: start.py not found in {blendshape_dir}")
                continue
                
            if not goal_renders_dir.exists():
                print(f"Warning: goal renders directory not found: {goal_renders_dir}")
                continue
                
            # Check for render files
            render_files = list(goal_renders_dir.glob("*.png"))
            if not render_files:
                print(f"Warning: No render files found in {goal_renders_dir}")
                continue
                
            task_config = {
                "task_name": task_name,
                "blendshape_name": blendshape_dir.name,
                "init_code_path": str(start_file),
                "target_image_path": str(goal_renders_dir),
                "render_files": [str(f) for f in render_files],
                "blender_file": str(blendshape_dir / "blender_file.blend") if (blendshape_dir / "blender_file.blend").exists() else None
            }
            
            tasks.append(task_config)
            print(f"Found task: {task_name}/{blendshape_dir.name}")
    
    return tasks

def run_blendergym_task(task_config: Dict, args) -> bool:
    """
    Run a single BlenderGym task using main.py
    
    Args:
        task_config: Task configuration dictionary
        args: Command line arguments
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Running task: {task_config['task_name']}/{task_config['blendshape_name']}")
    print(f"{'='*60}")
    
    # Prepare output directories
    output_base = Path(args.output_dir) / task_config['task_name'] / task_config['blendshape_name']
    render_save = output_base / "renders"
    thoughtprocess_save = output_base / "generator_thought.json"
    verifier_thoughtprocess_save = output_base / "verifier_thought.json"
    
    # Create directories
    render_save.mkdir(parents=True, exist_ok=True)
    
    # Build main.py command
    cmd = [
        sys.executable, "main.py",
        "--mode", "3d",
        "--init-code", task_config["init_code_path"],
        "--target-image-path", task_config["target_image_path"],
        "--max-rounds", str(args.max_rounds),
        "--render-save", str(render_save),
        "--thoughtprocess-save", str(thoughtprocess_save),
        "--verifier-thoughtprocess-save", str(verifier_thoughtprocess_save),
        "--vision-model", args.vision_model
    ]
    
    # Add optional parameters
    if args.generator_hints:
        cmd.extend(["--generator-hints", args.generator_hints])
    if args.verifier_hints:
        cmd.extend(["--verifier-hints", args.verifier_hints])
    if task_config.get("blender_file"):
        cmd.extend(["--blender-file", task_config["blender_file"]])
    if args.blender_command:
        cmd.extend(["--blender-command", args.blender_command])
    if args.blender_script:
        cmd.extend(["--blender-script", args.blender_script])
    if args.script_save:
        cmd.extend(["--script-save", args.script_save])
    if args.blender_save:
        cmd.extend(["--blender-save", args.blender_save])
    if args.blender_url:
        cmd.extend(["--blender-url", args.blender_url])
    
    # Add tool server paths
    if args.image_server_path:
        cmd.extend(["--image-server-path", args.image_server_path])
    if args.scene_server_path:
        cmd.extend(["--scene-server-path", args.scene_server_path])
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Run the command
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"Task completed successfully: {task_config['task_name']}/{task_config['blendshape_name']}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Task failed: {task_config['task_name']}/{task_config['blendshape_name']}")
        print(f"Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="BlenderGym Runner for AgenticVerifier")
    
    # Dataset parameters
    parser.add_argument("--dataset-path", required=True, 
                       help="Path to BlenderGym dataset root directory")
    parser.add_argument("--output-dir", default="output/blendergym",
                       help="Output directory for results")
    
    # Task selection
    parser.add_argument("--task-name", 
                       help="Specific task name to run (e.g., 'blendshape1')")
    parser.add_argument("--blendshape-name", 
                       help="Specific blendshape name to run (e.g., 'blendshape1')")
    
    # Main.py parameters
    parser.add_argument("--max-rounds", type=int, default=10,
                       help="Maximum number of interaction rounds")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--generator-hints", 
                       help="Hints for generator agent")
    parser.add_argument("--verifier-hints", 
                       help="Hints for verifier agent")
    
    # Blender parameters
    parser.add_argument("--blender-command", default="blender",
                       help="Blender command path")
    parser.add_argument("--blender-file", 
                       help="Blender template file")
    parser.add_argument("--blender-script", default="data/blendergym/pipeline_render_script.py",
                       help="Blender execution script")
    parser.add_argument("--script-save", default="scripts",
                       help="Directory to save generated scripts")
    parser.add_argument("--blender-save", 
                       help="Blender save path")
    parser.add_argument("--blender-url", default="http://localhost:8001",
                       help="Blender executor server URL")
    
    # Tool server paths
    parser.add_argument("--image-server-path", default="servers/verifier/image.py",
                       help="Path to image processing MCP server script")
    parser.add_argument("--scene-server-path", default="servers/verifier/scene.py",
                       help="Path to scene investigation MCP server script")
    
    # Execution control
    parser.add_argument("--dry-run", action="store_true",
                       help="Show what would be run without executing")
    parser.add_argument("--continue-on-error", action="store_true",
                       help="Continue to next task if current task fails")
    
    args = parser.parse_args()
    
    # Load dataset
    print(f"Loading BlenderGym dataset from: {args.dataset_path}")
    tasks = load_blendergym_dataset(args.dataset_path)
    
    if not tasks:
        print("No valid tasks found in dataset!")
        sys.exit(1)
    
    print(f"Found {len(tasks)} tasks")
    
    # Filter tasks if specific task/blendshape specified
    if args.task_name:
        tasks = [t for t in tasks if t["task_name"] == args.task_name]
        print(f"Filtered to {len(tasks)} tasks for task_name: {args.task_name}")
    
    if args.blendshape_name:
        tasks = [t for t in tasks if t["blendshape_name"] == args.blendshape_name]
        print(f"Filtered to {len(tasks)} tasks for blendshape_name: {args.blendshape_name}")
    
    if not tasks:
        print("No tasks match the specified filters!")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save task list for reference
    with open(os.path.join(args.output_dir, "tasks.json"), "w") as f:
        json.dump(tasks, f, indent=2)
    
    # Run tasks
    successful_tasks = 0
    failed_tasks = 0
    
    for i, task_config in enumerate(tasks, 1):
        print(f"\nTask {i}/{len(tasks)}")
        
        if args.dry_run:
            print(f"Would run: {task_config['task_name']}/{task_config['blendshape_name']}")
            continue
        
        success = run_blendergym_task(task_config, args)
        
        if success:
            successful_tasks += 1
        else:
            failed_tasks += 1
            if not args.continue_on_error:
                print("Stopping due to task failure (use --continue-on-error to continue)")
                break
    
    # Summary
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Successful: {successful_tasks}")
    print(f"Failed: {failed_tasks}")
    print(f"Output directory: {args.output_dir}")
    
    if successful_tasks > 0:
        print(f"\nResults saved to: {args.output_dir}")
        print("Check individual task directories for renders and thought processes.")

if __name__ == "__main__":
    main()
