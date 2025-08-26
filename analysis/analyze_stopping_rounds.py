#!/usr/bin/env python3
"""
Script to analyze intermediate_scores.json and count instances by task type and stopping round.
"""

import json
import os
from collections import defaultdict
from typing import Dict, List, Any

def analyze_stopping_rounds(json_file_path: str) -> Dict[str, Dict[int, int]]:
    """
    Analyze the intermediate_scores.json file to count instances by task type and stopping round.
    
    Args:
        json_file_path: Path to the intermediate_scores.json file
        
    Returns:
        Dictionary mapping task_type -> {round_number -> count}
    """
    
    # Load the JSON data
    with open(json_file_path, 'r') as f:
        data = json.load(f)
    
    # Dictionary to store results: task_type -> {round -> count}
    stopping_rounds = defaultdict(lambda: defaultdict(int))
    
    # Iterate through each task type
    for task_type, task_data in data.items():
        if 'instance_details' not in task_data:
            continue
            
        instance_details = task_data['instance_details']
        
        # Iterate through each instance
        for instance_name, instance_data in instance_details.items():
            if not isinstance(instance_data, dict):
                continue
                
            # Find the highest round number for this instance
            max_round = 0
            finded = False
            for round_str in instance_data.keys():
                try:
                    round_num = int(round_str)
                    max_round = max(max_round, round_num)
                    finded = True
                except (ValueError, TypeError):
                    continue
            
            # Count this instance as stopping at the highest round
            if max_round > 0 and finded == True:
                stopping_rounds[task_type][max_round] += 1
    
    return dict(stopping_rounds)

def print_analysis_results(results: Dict[str, Dict[int, int]]):
    """
    Print the analysis results in a formatted way.
    
    Args:
        results: Results from analyze_stopping_rounds
    """
    
    print("=" * 80)
    print("ANALYSIS OF STOPPING ROUNDS BY TASK TYPE")
    print("=" * 80)
    
    for task_type, round_counts in results.items():
        print(f"\nTask Type: {task_type}")
        print("-" * 50)
        
        # Get all round numbers and sort them
        all_rounds = sorted(round_counts.keys())
        
        if not all_rounds:
            print("  No instances found")
            continue
            
        # Print header
        print("Round | Count | Percentage")
        print("------|-------|-----------")
        
        # Calculate total instances for this task type
        total_instances = sum(round_counts.values())
        
        # Print each round's data
        for round_num in all_rounds:
            count = round_counts[round_num]
            percentage = (count / total_instances) * 100
            print(f"  {round_num:2d}  |  {count:3d}  |  {percentage:6.1f}%")
        
        print(f"Total instances: {total_instances}")

def save_results_to_json(results: Dict[str, Dict[int, int]], output_file: str):
    """
    Save the analysis results to a JSON file.
    
    Args:
        results: Results from analyze_stopping_rounds
        output_file: Path to save the results
    """
    
    # Convert defaultdict to regular dict for JSON serialization
    serializable_results = {}
    for task_type, round_counts in results.items():
        serializable_results[task_type] = dict(round_counts)
    
    with open(output_file, 'w') as f:
        json.dump(serializable_results, f, indent=2)
    
    print(f"\nResults saved to: {output_file}")

def main():
    """Main function to run the analysis."""
    
    # Path to the intermediate_scores.json file
    json_file_path = "output/blendergym/gpt-4o/_evaluation/intermediate_scores.json"
    
    # Check if file exists
    if not os.path.exists(json_file_path):
        print(f"Error: File not found: {json_file_path}")
        return
    
    print(f"Analyzing file: {json_file_path}")
    
    # Run the analysis
    results = analyze_stopping_rounds(json_file_path)
    
    # Print results
    print_analysis_results(results)
    
    # Save results to JSON
    output_file = "stopping_rounds_analysis.json"
    save_results_to_json(results, output_file)
    
    # Print summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    
    for task_type, round_counts in results.items():
        total_instances = sum(round_counts.values())
        if total_instances == 0:
            continue
            
        # Calculate average stopping round
        total_rounds = sum(round_num * count for round_num, count in round_counts.items())
        avg_stopping_round = total_rounds / total_instances
        
        # Find most common stopping round
        most_common_round = max(round_counts.items(), key=lambda x: x[1])[0]
        most_common_count = round_counts[most_common_round]
        
        print(f"\n{task_type}:")
        print(f"  Total instances: {total_instances}")
        print(f"  Average stopping round: {avg_stopping_round:.2f}")
        print(f"  Most common stopping round: {most_common_round} ({most_common_count} instances)")

if __name__ == "__main__":
    main()
