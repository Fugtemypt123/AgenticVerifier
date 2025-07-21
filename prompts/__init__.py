from autopresent import *
from blendergym import *

prompts_dict = {
    'blendergym': {
        'generator_hints': blendergym_generator_hints,
        'verifier_hints': blendergym_verifier_hints,
        'system_prompt': blendergym_system_prompt,
        'generator_format': blendergym_generator_format,
        'verifier_format': blendergym_verifier_format
    },
    'autopresent': {
        'generator_hints': autopresent_generator_hints,
        'verifier_hints': autopresent_verifier_hints,
        'system_prompt': autopresent_system_prompt,
        'api_library': autopresent_api_library,
        'generator_format': autopresent_generator_format,
        'verifier_format': autopresent_verifier_format
    }
}