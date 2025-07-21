from autopresent import autopresent_generator_hints, autopresent_verifier_hints, autopresent_system_prompt, autopresent_api_library
from blendergym import blendergym_generator_hints, blendergym_verifier_hints, blendergym_system_prompt

prompts_dict = {
    'blendergym': {
        'generator_hints': blendergym_generator_hints,
        'verifier_hints': blendergym_verifier_hints,
        'system_prompt': blendergym_system_prompt
    },
    'autopresent': {
        'generator_hints': autopresent_generator_hints,
        'verifier_hints': autopresent_verifier_hints,
        'system_prompt': autopresent_system_prompt,
        'api_library': autopresent_api_library
    }
}