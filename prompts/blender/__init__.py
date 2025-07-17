from . import geometry, lighting, material, placement, shape

blender_generator_hints = {
    "geometry": geometry.generator_hints,
    "lighting": lighting.generator_hints,
    "material": material.generator_hints,
    "placement": placement.generator_hints,
    "shape": shape.generator_hints,
}

blender_verifier_hints = {
    "geometry": geometry.verifier_hints,
    "lighting": lighting.verifier_hints,
    "material": material.verifier_hints,
    "placement": placement.verifier_hints,
    "shape": shape.verifier_hints,
}