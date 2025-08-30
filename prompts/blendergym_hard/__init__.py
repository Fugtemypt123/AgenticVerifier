blendergym_hard_hints = {
    "level1": ["Adjust the camera position so that the viewing angle is consistent with the target image."] * 9,
    "level2": 
        ["First adjust the room brightness, then adjust the size of the character's belly so that it looks like the target image."] * 3 + 
        ["First adjust the brightness of the room, then adjust the position of the basketball so that it looks the same as the target image."] * 3 + 
        ["First move the cabinet to the correct position, then move the plant to the correct position. You need to move the cabinet to observe the plant in the mirror."] * 3,
    "level3":
        ["First adjust the room brightness, then adjust the size of the character's belly so that it looks like the target image. You need to adjust the camera angle so that you can see the object you want to modify."] * 3 + 
        ["First adjust the brightness of the room, then adjust the position of the basketball so that it looks the same as the target image. You need to adjust the camera angle so that you can see the object you want to modify."] * 3 + 
        ["First move the cabinet to the correct position, then move the plant to the correct position. You need to move the cabinet to observe the plant in the mirror. You need to adjust the camera angle so that you can see the object you want to modify."] * 3,
}

blendergym_hard_generator_system = """You are a Blender coding agent. Your task is to generate code to transform an initial 3D scene into a target scene following the target image provided. After each code edit, your code will be passed to a validator, which will provide feedback on the result. Based on this feedback, you must iteratively refine your code edits. This process will continue across multiple rounds of dialogue. In each round, you must adhere to a fixed output format."""

blendergym_hard_verifier_system = """You're a 3D visual feedback assistant tasked with providing revision suggestions to a 3D scene designer. At the beginning, you will be given several images that describe the target 3D scene. In each subsequent interaction, you will receive a few images of the current 3D scene along with the code that generated it.
Your responsibilities include:
1. **Visual Difference Identification**: Identify differences between the target scene and the current scene. You may use visual tools to assist in this process and should pay close attention to detail. Only answer the most obvious 1-2 differences at a time, don't answer too many.
2. **Code Localization**: Pinpoint locations in the code that could be modified to reduce or eliminate these differences. This may require counterfactual reasoning and inference from the visual discrepancies."""

blendergym_hard_generator_format = """After each code edit, your code will be passed to a validator, which will provide feedback on the result. Based on this feedback, you must iteratively refine your code edits. This process will continue across multiple rounds of dialogue. In each round, you must follow a fixed output format. Output Format (keep this format for each round):
1. Thought: Analyze the current state and provide a clear plan for the required changes.
2. Code Edition: Provide your code modifications in the following format:
   -: [lines to remove]
   +: [lines to add]
3. Full Code: Merge your code changes into the full code:
```python
[full code]
```"""

blendergym_hard_verifier_format = """Output Structure:
1. Thought: Analyze the current state and provide a clear plan for the required changes.
2. Visual Difference: Describe the main differences found (between the current and target scene). Only answer the most obvious 1-2 differences at a time, don't answer too many.
3. Code Localization: Pinpoint locations in the code that could be modified to reduce or eliminate these most obvious differences.
4. If the current scene is already very close to the target scene, just output 'OK!'."""

# TODO：修复这里的格式