from .prompt import api_library, hints

autopresent_generator_hints = {
    'refinement': hints
}

autopresent_verifier_hints = None

autopresent_system_prompt = """
You are a slide design agent. Your task is to edit code to transform an initial slide into a target slide following the target description provided. After each code edit, your code will be passed to a validator, which will provide feedback on the result. Based on this feedback, you must iteratively refine your code edits. This process will continue across multiple rounds of dialogue. In each round, you must adhere to a fixed output format.
"""

autopresent_api_library = api_library