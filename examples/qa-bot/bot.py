"""Sample QA Bot implementation for PromptCheck demonstration."""


def format_qa_prompt(user_query: str) -> str:
    system_instruction = (
        "You are a polite, concise technical support assistant for Acme Cloud. "
        "Answer customer queries accurately using only the provided facts."
    )
    return f"{system_instruction}\n\nUser Question: {user_query}\nAssistant:"


if __name__ == "__main__":
    test_query = "Hello, what services do you provide?"
    prompt = format_qa_prompt(test_query)
    print("Generated Prompt:\n", prompt)
