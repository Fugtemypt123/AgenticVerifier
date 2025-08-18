import os
import argparse
import subprocess

def main():
    slides_dirs = os.listdir(f"../generate/examples/{args.slide_name}")
    # remove the non-directory files
    slides_dirs = [slide_dir for slide_dir in slides_dirs if '.' not in slide_dir]
    index_list = [slide_dir.split("_")[1] for slide_dir in slides_dirs]
    index_list = sorted([int(index) for index in index_list])
    for index in index_list:
        print(f"Start evaluating slide {index} ...")
        # ref-based evaluation
        # find the last execuable pptx path 
        refine_path = f"../generate/examples/{args.slide_name}/slide_{index}/refined_gpt4o" 
        files = os.listdir(refine_path) # files: 0-9
        files = sorted(files, key=lambda x: int(x), reverse=True) # sorted in descending order
        pptx_path = None
        for file in files:
            pptx_path = os.path.join(refine_path, f"{file}/refine.pptx")
            if os.path.exists(pptx_path):
                break 
        if pptx_path is None:
            print(f"No executable pptx found for slide {index}")
            continue
        else:
            print(f"Using pptx: {pptx_path}")
        eval_path = pptx_path.replace(".pptx", "_ref_eval.txt")
        if not os.path.exists(eval_path):
            command = [
                "python", "page_eval.py",
                "--reference_pptx", f"../slidesbench/examples/{args.slide_name}/{args.slide_name}.pptx",
                "--generated_pptx", pptx_path,
                "--reference_page", str(index),        
            ]
            process = subprocess.Popen(command)
            process.wait()
            print(f"Finished ref-based evaluation: {eval_path}")

        # ref-free evaluation
        jpg_path = pptx_path.replace(".pptx", ".jpg")
        eval_path = jpg_path.replace(".jpg", "_ref_free_eval.json")
        if os.path.exists(jpg_path) and not os.path.exists(eval_path):
            command = [
                "python", "reference_free_eval.py",
                "--image_path", jpg_path,
            ]
            process = subprocess.Popen(command)
            process.wait()
            print(f"Finished ref-free evaluation: {eval_path}")
        print(f"Finish evaluating slide {index} !")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slide_name", type=str, required=True)

    args = parser.parse_args()

    main()
