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