# Prompting Patterns

This skill follows three stable patterns from official model-provider guidance:

1. Clear instructions first
- State the task, audience, and desired answer shape explicitly.
- Keep the final-output contract narrow.

2. Separate hidden organization from final answer
- Use a silent planning pass to organize facts, gaps, signal, and next step.
- Keep the final surface clean and user-facing.

3. Use structured outputs when possible
- Prefer assembling the answer into a small internal schema before writing the final markdown brief.
- Validate facts in application code when the provider supports formal structured outputs.

Provider notes:

- OpenAI guidance emphasizes clear instructions, explicit output shape, and examples when formatting matters.
- Anthropic guidance recommends structured prompts and separating internal thinking from the final answer.
- Gemini guidance recommends JSON-schema-based structured outputs when predictable final formatting is important.
