import json
import os
import argparse
from pptx import Presentation


def gather_results(test_id: str, slide_name: str = 'all'):
    """
    Gather evaluation results from all slides and calculate overall metrics.
    """
    if slide_name == 'all':
        names = ['art_photos', 'business', 'design', 'entrepreneur', 'environment', 'food', 'marketing', 'social_media', 'technology']
    else:
        names = [slide_name]

    ref_eval_result = {'match': 0, 'text': 0, 'color': 0, 'position': 0}
    ref_free_eval_result = {'text': 0, 'image': 0, 'layout': 0, 'color': 0}
    fail_num = 0
    total_num = 0

    for name in names:
        slide_path = os.path.join(f"data/autopresent/examples", name, f"{name}.pptx")
        if not os.path.exists(slide_path):
            print(f"Warning: {slide_path} not found, skipping {name}")
            continue
            
        prs = Presentation(slide_path)
        pages_num = len(prs.slides)
        
        for slide_num in range(1, pages_num + 1):
            slide_dir = os.path.join(f"output/autopresent/{test_id}", name, f"slide_{slide_num}")
            
            # Find the best round (highest average score) for this slide
            best_round_score = -1
            best_round_ref_eval = None
            best_round_ref_free_eval = None
            best_round_num = None
            
            # Check rounds from 1 to 10
            for round_num in range(1, 11):
                round_dir = os.path.join(slide_dir, str(round_num))
                if not os.path.exists(round_dir):
                    continue
                    
                # Check for refined results in this round
                ref_eval_path = os.path.join(round_dir, "ref_based.txt")
                ref_free_eval_path = os.path.join(round_dir, "ref_free.json")
                
                if os.path.exists(ref_eval_path) and os.path.exists(ref_free_eval_path):
                    # Calculate score for this round
                    round_ref_eval = {'match': 0, 'text': 0, 'color': 0, 'position': 0}
                    round_ref_free_eval = {'text': 0, 'image': 0, 'layout': 0, 'color': 0}
                    
                    # Read ref-based evaluation
                    with open(ref_eval_path, 'r') as f:
                        current_ref_eval_result = f.read()
                        current_ref_eval_result = current_ref_eval_result.split('\n')
                        for result in current_ref_eval_result:
                            if 'match' in result:
                                round_ref_eval['match'] = float(result.split(': ')[1])
                            elif 'text' in result:
                                round_ref_eval['text'] = float(result.split(': ')[1])
                            elif 'color' in result:
                                round_ref_eval['color'] = float(result.split(': ')[1])
                            elif 'position' in result:
                                round_ref_eval['position'] = float(result.split(': ')[1])
                    
                    # Read ref-free evaluation
                    with open(ref_free_eval_path, 'r') as f:
                        current_ref_free_eval_result = json.load(f)
                        round_ref_free_eval['text'] = current_ref_free_eval_result['text']['score'] * 20
                        round_ref_free_eval['image'] = current_ref_free_eval_result['image']['score'] * 20
                        round_ref_free_eval['layout'] = current_ref_free_eval_result['layout']['score'] * 20
                        round_ref_free_eval['color'] = current_ref_free_eval_result['color']['score'] * 20
                    
                    # Calculate average score for this round
                    round_score = (round_ref_eval['match'] + round_ref_eval['text'] + 
                                 round_ref_eval['color'] + round_ref_eval['position'] + 
                                 round_ref_free_eval['text'] + round_ref_free_eval['image'] + 
                                 round_ref_free_eval['layout'] + round_ref_free_eval['color']) / 8
                    
                    # Update best round if this round has higher score
                    if round_score > best_round_score:
                        best_round_score = round_score
                        best_round_ref_eval = round_ref_eval.copy()
                        best_round_ref_free_eval = round_ref_free_eval.copy()
                        best_round_num = round_num
            
            # Use the best round results if found
            if best_round_num is not None:
                print(f"Using round {best_round_num} for {name} slide_{slide_num} (score: {best_round_score:.4f})")
                
                # Add to overall results
                for key in ref_eval_result:
                    ref_eval_result[key] += best_round_ref_eval[key]
                for key in ref_free_eval_result:
                    ref_free_eval_result[key] += best_round_ref_free_eval[key]
            else:
                # Check for baseline results (old format) as fallback
                # ref_eval = os.path.join(slide_dir, "baseline", "ref_eval.txt")
                # ref_free_eval = os.path.join(slide_dir, "baseline", "refree_eval.json")
                
                # if os.path.exists(ref_eval) and os.path.exists(ref_free_eval):
                #     print(f"Using baseline for {name} slide_{slide_num}")
                #     with open(ref_eval, 'r') as f:
                #         current_ref_eval_result = f.read()
                #         current_ref_eval_result = current_ref_eval_result.split('\n')
                #         for result in current_ref_eval_result:
                #             if 'match' in result:
                #                 ref_eval_result['match'] += float(result.split(': ')[1])
                #             elif 'text' in result:
                #                 ref_eval_result['text'] += float(result.split(': ')[1])
                #             elif 'color' in result:
                #                 ref_eval_result['color'] += float(result.split(': ')[1])
                #             elif 'position' in result:
                #                 ref_eval_result['position'] += float(result.split(': ')[1])
                    
                #     with open(ref_free_eval, 'r') as f:
                #         current_ref_free_eval_result = json.load(f)
                #         ref_free_eval_result['text'] += current_ref_free_eval_result['text']['score'] * 20
                #         ref_free_eval_result['image'] += current_ref_free_eval_result['image']['score'] * 20
                #         ref_free_eval_result['layout'] += current_ref_free_eval_result['layout']['score'] * 20
                #         ref_free_eval_result['color'] += current_ref_free_eval_result['color']['score'] * 20
                # else:
                fail_num += 1
                print(f"Warning: No evaluation results found for {name} slide_{slide_num}")
                    
            total_num += 1

    # Calculate averages
    if total_num > 0:
        for key in ref_eval_result.keys():
            ref_eval_result[key] = ref_eval_result[key] / total_num
        for key in ref_free_eval_result.keys():
            ref_free_eval_result[key] = ref_free_eval_result[key] / total_num

    # Print results
    print(f"Test ID: {test_id}")
    print(f"Success rate: {(total_num - fail_num) / total_num:.4f}")
    print(f"Total slides processed: {total_num}")
    print(f"Failed slides: {fail_num}")
    print(f"Ref-based evaluation results: {ref_eval_result}")
    print(f"Ref-free evaluation results: {ref_free_eval_result}")
    
    overall_score = (ref_eval_result['match'] + ref_eval_result['text'] + 
                    ref_eval_result['color'] + ref_eval_result['position'] + 
                    ref_free_eval_result['text'] + ref_free_eval_result['image'] + 
                    ref_free_eval_result['layout'] + ref_free_eval_result['color']) / 8
    print(f"Overall score: {overall_score:.4f}")
    
    return ref_eval_result, ref_free_eval_result, overall_score


def main():
    if args.slide_name == 'all':
        slides_list = ['art_photos', 'business', 'design', 'entrepreneur', 'environment', 'food', 'marketing', 'social_media', 'technology']
    else:
        slides_list = [args.slide_name]

    gather_results(args.test_id, args.slide_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('test_id', type=str, help='Test ID (e.g., 20250815_150016)')
    parser.add_argument("--slide_name", type=str, default='all', 
                       choices=['all', 'art_photos', 'business', 'design', 'entrepreneur', 'environment', 'food', 'marketing', 'social_media', 'technology'])

    args = parser.parse_args()

    main()