import re

with open('codebase/app/services/extractor/grounding_checker.py', 'r') as f:
    text = f.read()

import ast
# We'll just replace everything between "is_grounded = score >= self.threshold" and "# Find best evidence snippet"
start_idx = text.find('        is_grounded = score >= self.threshold')
end_idx = text.find('        # Find best evidence snippet')

replacement = """        is_grounded = score >= self.threshold

        # W02 Minimal Contradiction Check (Target-Aware)
        step_lower = step.lower()
        step_is_disable = "turn off" in step_lower or "disable" in step_lower
        step_is_enable = "turn on" in step_lower or "enable" in step_lower

        if step_is_disable or step_is_enable:
            polarity_words = {"turn", "off", "on", "enable", "disable", "turned", "disabled", "enabled"}
            target_tokens = set(step_tokens) - polarity_words

            if target_tokens:
                sentences = re.split(r"[.\\n]+", siis_text)
                for s in sentences:
                    s_lower = s.lower()
                    s_tokens = set(tokenize_content_words(s))

                    # Only consider sentences discussing the same target
                    if target_tokens.intersection(s_tokens):
                        s_is_enable = "turn on" in s_lower or "enable" in s_lower or "turned on" in s_lower
                        s_is_disable = "turn off" in s_lower or "disable" in s_lower or "turned off" in s_lower

                        if step_is_disable and s_is_enable and not s_is_disable:
                            is_grounded = False
                        if step_is_enable and s_is_disable and not s_is_enable:
                            is_grounded = False

"""

text = text[:start_idx] + replacement + text[end_idx:]

with open('codebase/app/services/extractor/grounding_checker.py', 'w') as f:
    f.write(text)
