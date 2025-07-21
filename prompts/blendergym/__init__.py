from . import geometry, lighting, material, placement, blendshape

blendergym_generator_hints = {
    "geometry": geometry.generator_hints,
    "lighting": lighting.generator_hints,
    "material": material.generator_hints,
    "placement": placement.generator_hints,
    "blendshape": blendshape.generator_hints,
}

blendergym_verifier_hints = {
    "geometry": geometry.verifier_hints,
    "lighting": lighting.verifier_hints,
    "material": material.verifier_hints,
    "placement": placement.verifier_hints,
    "blendshape": blendshape.verifier_hints,
}

blendergym_system_prompt = """
You are a BlenderGym agent. Your task is to generate code to transform an initial 3D scene into a target scene following the target image provided. After each code edit, your code will be passed to a validator, which will provide feedback on the result. Based on this feedback, you must iteratively refine your code edits. This process will continue across multiple rounds of dialogue. In each round, you must adhere to a fixed output format.
"""

blendergym_generator_format = """After each code edit, your code will be passed to a validator, which will provide feedback on the result. Based on this feedback, you must iteratively refine your code edits. This process will continue across multiple rounds of dialogue. In each round, you must follow a fixed output format. Output Format (keep this format for each round):
1. Thought: Analyze the current state and provide a clear plan for the required changes.
2. Code Edition: Provide your code modifications in the following format:
   -: [lines to remove]
   +: [lines to add]
3. Full Code: Merge your code changes into the full code:
```python
[full code]
```"""

blendergym_verifier_format = """Output Structure:\n1. Thought: Analyze the current state and provide a clear plan for the required changes.\n2. Visual Difference: Describe the main differences found (between the current and target scene). Only answer the most obvious 1-2 differences at a time, don't answer too many.\n3. Code Localization: Pinpoint locations in the code that could be modified to reduce or eliminate these most obvious differences.\n4. If the current scene is already very close to the target scene, just output 'OK!'."""