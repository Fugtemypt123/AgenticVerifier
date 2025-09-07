from .autopresent import *
from .blendergym import *
from .blendergym_hard import *
from .design2code import *

prompts_dict = {
    'blendergym': {
        'hints': {
            'generator': blendergym_generator_hints,
            'verifier': blendergym_verifier_hints
        },
        'system': {
            'generator': blendergym_generator_system,
            'verifier': blendergym_verifier_system
        },
        'format':{
            'generator': blendergym_generator_format,
            'verifier': blendergym_verifier_format
        }
    },
    'autopresent': {
        'system': {
            'generator': autopresent_generator_system,
            'verifier': autopresent_verifier_system
        },
        'format':{
            'generator': autopresent_generator_format,
            'verifier': autopresent_verifier_format
        },
        'api_library': autopresent_api_library,
        'hints': autopresent_hints
    },
    'blendergym-hard': {
        'system': {
            'generator': blendergym_hard_generator_system_dict,
            'verifier': blendergym_hard_verifier_system_dict
        },
        'format':{
            'generator': blendergym_hard_generator_format_dict,
            'verifier': blendergym_hard_verifier_format_dict
        },
        'hints': blendergym_hard_hints
    },
    'design2code': {
        'system': {
            'generator': design2code_generator_system,
            'verifier': design2code_verifier_system
        },
        'format': {
            'generator': design2code_generator_format,
            'verifier': design2code_verifier_format
        },
        'hints': design2code_hints
    },
}