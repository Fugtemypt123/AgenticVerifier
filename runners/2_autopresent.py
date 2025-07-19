#!/usr/bin/env python3
"""
AutoPresent Runner for AgenticVerifier
Loads AutoPresent dataset and runs the dual-agent system for 2D slide generation.
"""
import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

def load_autopresent_dataset(base_path: str) -> List[Dict]:
    """
    Load AutoPresent dataset structure.
    
    Args:
        base_path: Path to AutoPresent dataset root
        
    Returns:
        List of task configurations
    """
    tasks = []
    base_path = Path(base_path)
    
    if not base_path.exists():
        print(f"Error: AutoPresent dataset path does not exist: {base_path}")
        return tasks
    
    # Traverse AutoPresent dataset structure
    # Expected structure: base_path/task_name/start.py, description.txt
    for task_dir in base_path.iterdir():
        if not task_dir.is_dir():
            continue
            
        task_name = task_dir.name
        
        # Check for required files
        start_file = task_dir / "start.py"
        description_file = task_dir / "description.txt"
        
        if not start_file.exists():
            print(f"Warning: start.py not found in {task_dir}")
            continue
            
        if not description_file.exists():
            print(f"Warning: description.txt not found in {task_dir}")
            continue
            
        # Read target description
        try:
            with open(description_file, 'r', encoding='utf-8') as f:
                target_description = f.read().strip()
        except Exception as e:
            print(f"Warning: Could not read description from {description_file}: {e}")
            continue
            
        if not target_description:
            print(f"Warning: Empty description in {description_file}")
            continue
            
        task_config = {
            "task_name": task_name,
            "init_code_path": str(start_file),
            "target_description": target_description,
            "description_file": str(description_file)
        }
        
        tasks.append(task_config)
        print(f"Found task: {task_name}")
        print(f"  Description: {target_description[:100]}...")
    
    return tasks

def run_autopresent_task(task_config: Dict, args) -> bool:
    """
    Run a single AutoPresent task using main.py
    
    Args:
        task_config: Task configuration dictionary
        args: Command line arguments
        
    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*60}")
    print(f"Running task: {task_config['task_name']}")
    print(f"{'='*60}")
    
    # Prepare output directories
    output_base = Path(args.output_dir) / task_config['task_name']
    code_save = output_base / "slides_code"
    thoughtprocess_save = output_base / "generator_thought.json"
    verifier_thoughtprocess_save = output_base / "verifier_thought.json"
    
    # Create directories
    code_save.mkdir(parents=True, exist_ok=True)
    
    # Build main.py command
    cmd = [
        sys.executable, "main.py",
        "--mode", "2d",
        "--init-code", task_config["init_code_path"],
        "--target-description", task_config["target_description"],
        "--max-rounds", str(args.max_rounds),
        "--code-save", str(code_save),
        "--thoughtprocess-save", str(thoughtprocess_save),
        "--verifier-thoughtprocess-save", str(verifier_thoughtprocess_save),
        "--vision-model", args.vision_model
    ]
    
    # Add optional parameters
    if args.generator_hints:
        cmd.extend(["--generator-hints", args.generator_hints])
    if args.verifier_hints:
        cmd.extend(["--verifier-hints", args.verifier_hints])
    if args.slides_url:
        cmd.extend(["--slides-url", args.slides_url])
    
    # Add tool server paths
    if args.image_server_path:
        cmd.extend(["--image-server-path", args.image_server_path])
    if args.scene_server_path:
        cmd.extend(["--scene-server-path", args.scene_server_path])
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Run the command
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"Task completed successfully: {task_config['task_name']}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Task failed: {task_config['task_name']}")
        print(f"Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="AutoPresent Runner for AgenticVerifier")
    
    # Dataset parameters
    parser.add_argument("--dataset-path", required=True, 
                       help="Path to AutoPresent dataset root directory")
    parser.add_argument("--output-dir", default="output/autopresent",
                       help="Output directory for results")
    
    # Task selection
    parser.add_argument("--task-name", 
                       help="Specific task name to run")
    
    # Main.py parameters
    parser.add_argument("--max-rounds", type=int, default=10,
                       help="Maximum number of interaction rounds")
    parser.add_argument("--vision-model", default="gpt-4o",
                       help="OpenAI vision model to use")
    parser.add_argument("--generator-hints", 
                       help="Hints for generator agent")
    parser.add_argument("--verifier-hints", 
                       help="Hints for verifier agent")
    
    # Slides parameters
    parser.add_argument("--slides-url", default="http://localhost:8002",
                       help="Slides executor server URL")
    
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
    
    # Dataset filtering
    parser.add_argument("--description-filter", 
                       help="Filter tasks by description content (substring match)")
    parser.add_argument("--max-tasks", type=int,
                       help="Maximum number of tasks to run")
    
    args = parser.parse_args()
    
    # Load dataset
    print(f"Loading AutoPresent dataset from: {args.dataset_path}")
    tasks = load_autopresent_dataset(args.dataset_path)
    
    if not tasks:
        print("No valid tasks found in dataset!")
        sys.exit(1)
    
    print(f"Found {len(tasks)} tasks")
    
    # Filter tasks if specific task specified
    if args.task_name:
        tasks = [t for t in tasks if t["task_name"] == args.task_name]
        print(f"Filtered to {len(tasks)} tasks for task_name: {args.task_name}")
    
    # Filter by description content
    if args.description_filter:
        original_count = len(tasks)
        tasks = [t for t in tasks if args.description_filter.lower() in t["target_description"].lower()]
        print(f"Filtered to {len(tasks)} tasks matching description filter: '{args.description_filter}'")
    
    # Limit number of tasks
    if args.max_tasks and len(tasks) > args.max_tasks:
        print(f"Limiting to {args.max_tasks} tasks (from {len(tasks)})")
        tasks = tasks[:args.max_tasks]
    
    if not tasks:
        print("No tasks match the specified filters!")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save task list for reference
    with open(os.path.join(args.output_dir, "tasks.json"), "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)
    
    # Save descriptions for easy review
    with open(os.path.join(args.output_dir, "descriptions.txt"), "w", encoding='utf-8') as f:
        for task in tasks:
            f.write(f"Task: {task['task_name']}\n")
            f.write(f"Description: {task['target_description']}\n")
            f.write("-" * 80 + "\n\n")
    
    # Run tasks
    successful_tasks = 0
    failed_tasks = 0
    
    for i, task_config in enumerate(tasks, 1):
        print(f"\nTask {i}/{len(tasks)}")
        
        if args.dry_run:
            print(f"Would run: {task_config['task_name']}")
            print(f"  Description: {task_config['target_description'][:100]}...")
            continue
        
        success = run_autopresent_task(task_config, args)
        
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
        print("Check individual task directories for generated slides and thought processes.")
        print("Review descriptions.txt for all task descriptions.")

if __name__ == "__main__":
    main()
