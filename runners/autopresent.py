#!/usr/bin/env python3
"""
AutoPresent Runner for AgenticVerifier
Loads AutoPresent dataset and runs the dual-agent system for 2D slides generation.
"""
import os
import sys
import json
import time
import argparse
import subprocess
import asyncio
import signal
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

api_key = os.getenv("OPENAI_API_KEY")

def load_autopresent_dataset(base_path: str, task_name: str, task_id: Optional[str] = None) -> List[Dict]:
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
    
    if task_name == 'all':
        task_list = ['art_photos', 'business', 'design', 'entrepreneur', 'environment', 'food', 'marketing', 'social_media', 'technology']
    else:
        task_list = [task_name]
        
    # If task_id is not None, only run the task_id
    if task_id is not None:
        task_dirs = [(base_path / task_name / f"slides_{task_id}", task_name)]
    # Otherwise, run all tasks in the task_list
    else:
        task_dirs = []
        for task in task_list:
            current_path = base_path / task
            for task_dir in current_path.glob("slide_*"):
                task_dirs.append((task_dir, task))
    
    for task_dir, task_name in task_dirs:
        # Check for required files
        start_code_path = task_dir / "start.py"
        start_image_path = task_dir / "start.jpg"
        target_description_file = task_dir / "instruction.txt"
        
        if not start_code_path.exists():
            print(f"Warning: start.py not found in {task_dir}")
            continue
            
        if not target_description_file.exists():
            print(f"Warning: target_description.txt not found in {task_dir}")
            continue
            
        task_config = {
            "task_name": task_name,
            "task_dir": str(task_dir),
            "init_code_path": str(start_code_path),
            "init_image_path": str(start_image_path),
            "target_description_path": str(target_description_file),
        }
        tasks.append(task_config)
        print(f"Found task: {task_name}/{task_dir.name}")
    
    return tasks

def run_autopresent_task(task_config: Dict, args) -> tuple:
    """
    Run a single AutoPresent task using main.py
    
    Args:
        task_config: Task configuration dictionary
        args: Command line arguments
        
    Returns:
        Tuple of (task_name, success: bool, error_message: str)
    """
    task_name = task_config['task_name'] + "/" + task_config['task_dir'].split('/')[-1]
    print(f"\n{'='*60}")
    print(f"Running task: {task_name}")
    print(f"{'='*60}")
    
    # Prepare output directories
    output_base = Path(args.output_dir + "/" + task_name)
    output_base.mkdir(parents=True, exist_ok=True)
    
    # Build main.py command
    cmd = [
        sys.executable, "main.py",
        "--mode", "autopresent",
        "--vision-model", args.vision_model,
        "--api-key", api_key,
        "--max-rounds", str(args.max_rounds),
        "--task-name", task_config["task_name"],
        "--init-code-path", str(task_config["init_code_path"]),
        "--init-image-path", str(task_config["init_image_path"]),
        "--target-description", task_config["target_description_path"],
        # Agent server paths
        "--generator-script", args.generator_script,
        "--verifier-script", args.verifier_script,
        # Slides execution parameters (for generator)
        "--slides-server-path", args.slides_server_path,
        "--output-dir", str(output_base),
        # Tool server paths (for verifier)
        "--image-server-path", args.image_server_path,
    ]
    
    print(f"Command: {' '.join(cmd)}")
    
    try:
        # Run the command
        result = subprocess.run(cmd, check=True, capture_output=False, timeout=3600)  # 1 hour timeout
        print(f"Task completed successfully: {task_name}")
        return (task_name, True, "")
    except subprocess.CalledProcessError as e:
        error_msg = f"Task failed: {task_name}, Error: {e}"
        print(error_msg)
        return (task_name, False, str(e))
    except subprocess.TimeoutExpired:
        error_msg = f"Task timed out: {task_name}"
        print(error_msg)
        return (task_name, False, "Timeout")
    except Exception as e:
        error_msg = f"Task failed with exception: {task_name}, Error: {e}"
        print(error_msg)
        return (task_name, False, str(e))

def run_tasks_parallel(tasks: List[Dict], args, max_workers: int = 10) -> tuple:
    """
    Run tasks in parallel using ThreadPoolExecutor
    
    Args:
        tasks: List of task configurations
        args: Command line arguments
        max_workers: Maximum number of parallel workers
        
    Returns:
        Tuple of (successful_tasks: int, failed_tasks: int, failed_task_details: List)
    """
    successful_tasks = 0
    failed_tasks = 0
    failed_task_details = []
    
    print(f"\nStarting parallel execution with max {max_workers} workers...")
    print(f"Total tasks: {len(tasks)}")
    
    # Use ThreadPoolExecutor for parallel execution
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(run_autopresent_task, task_config, args): task_config 
            for task_config in tasks
        }
        
        # Process completed tasks
        for future in as_completed(future_to_task):
            task_config = future_to_task[future]
            try:
                task_name, success, error_msg = future.result()
                if success:
                    successful_tasks += 1
                    print(f"✅ {task_name} completed successfully")
                else:
                    failed_tasks += 1
                    failed_task_details.append({
                        "task_name": task_name,
                        "error": error_msg
                    })
                    print(f"❌ {task_name} failed: {error_msg}")
            except Exception as e:
                failed_tasks += 1
                task_name = task_config['task_dir'].split('/')[-1]
                failed_task_details.append({
                    "task_name": task_name,
                    "error": str(e)
                })
                print(f"❌ {task_name} failed with exception: {e}")
    
    return successful_tasks, failed_tasks, failed_task_details

def main():
    parser = argparse.ArgumentParser(description="AutoPresent Runner for AgenticVerifier")
    
    # Dataset parameters
    parser.add_argument("--dataset-path", default="data/autopresent/examples", help="Path to AutoPresent dataset root directory")
    parser.add_argument("--output-dir", default=f"output/autopresent/{time.strftime('%Y%m%d_%H%M%S')}", help="Output directory for results")
    
    # Task selection
    parser.add_argument("--task", default="all", choices=['all', 'art_photos', 'business', 'design', 'entrepreneur', 'environment', 'food', 'marketing', 'social_media', 'technology'], help="Specific task to run")
    parser.add_argument("--task-id", default=None, help="Specific task id to run (e.g., '1')")
    
    # Main.py parameters
    parser.add_argument("--max-rounds", type=int, default=10, help="Maximum number of interaction rounds")
    parser.add_argument("--vision-model", default="gpt-4o", help="OpenAI vision model to use")
    
    # Slides parameters
    parser.add_argument("--slides-server-path", default="servers/generator/slides.py", help="Path to Slides MCP server script")
    
    # Tool server paths
    parser.add_argument("--generator-script", default="agents/generator_mcp.py", help="Generator MCP script path")
    parser.add_argument("--verifier-script", default="agents/verifier_mcp.py", help="Verifier MCP script path")
    parser.add_argument("--image-server-path", default="servers/verifier/image.py", help="Path to image processing MCP server script")
    
    # Parallel execution parameters
    parser.add_argument("--max-workers", type=int, default=10, help="Maximum number of parallel workers")
    parser.add_argument("--sequential", action="store_true", help="Run tasks sequentially instead of in parallel")
    
    args = parser.parse_args()
    
    # Load dataset
    print(f"Loading AutoPresent dataset from: {args.dataset_path}")
    tasks = load_autopresent_dataset(args.dataset_path, args.task, args.task_id)
    
    if not tasks:
        print("No valid tasks found in dataset!")
        sys.exit(1)
    
    print(f"Found {len(tasks)} tasks")
    
    # Filter tasks if specific task specified
    if args.task != 'all':
        tasks = [t for t in tasks if t["task_name"] == args.task]
        print(f"Filtered to {len(tasks)} tasks for task: {args.task}")
    
    if not tasks:
        print("No tasks match the specified filters!")
        sys.exit(1)
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Save args to json
    with open(os.path.join(args.output_dir, "args.json"), "w") as f:
        json.dump(args.__dict__, f, indent=2)
    
    # Save task list for reference
    with open(os.path.join(args.output_dir, "tasks.json"), "w") as f:
        json.dump(tasks, f, indent=2)
    
    # Run tasks
    start_time = time.time()
    
    if args.sequential:
        # Sequential execution
        print("\nRunning tasks sequentially...")
        successful_tasks = 0
        failed_tasks = 0
        failed_task_details = []
        
        for i, task_config in enumerate(tasks, 1):
            print(f"\nTask {i}/{len(tasks)}")
            task_name, success, error_msg = run_autopresent_task(task_config, args)
            
            if success:
                successful_tasks += 1
            else:
                failed_tasks += 1
                failed_task_details.append({
                    "task_name": task_name,
                    "error": error_msg
                })
    else:
        # Parallel execution
        successful_tasks, failed_tasks, failed_task_details = run_tasks_parallel(
            tasks, args, max_workers=args.max_workers
        )
    
    end_time = time.time()
    execution_time = end_time - start_time
    
    # Summary
    print(f"\n{'='*60}")
    print("EXECUTION SUMMARY")
    print(f"{'='*60}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Successful: {successful_tasks}")
    print(f"Failed: {failed_tasks}")
    print(f"Execution time: {execution_time:.2f} seconds")
    print(f"Output directory: {args.output_dir}")
    
    # Save detailed results
    results = {
        "total_tasks": len(tasks),
        "successful_tasks": successful_tasks,
        "failed_tasks": failed_tasks,
        "execution_time_seconds": execution_time,
        "failed_task_details": failed_task_details,
        "execution_mode": "sequential" if args.sequential else f"parallel_{args.max_workers}_workers"
    }
    
    with open(os.path.join(args.output_dir, "execution_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    
    if successful_tasks > 0:
        print(f"\nResults saved to: {args.output_dir}")
        print("Check individual task directories for slides code and thought processes.")
    
    if failed_tasks > 0:
        print(f"\nFailed tasks details saved to: {os.path.join(args.output_dir, 'execution_results.json')}")

if __name__ == "__main__":
    main()
