"""Step 1: prove Python can reach the local model through Ollama."""
import ollama

MODEL = "qwen2.5:7b"
NUM_CTX = 8192  # How many tokens the model can see at once. Set it so we know the limit.


def ask_model(question):
    """Send one question to the model and return its reply as a string."""
    messages = [{"role": "user", "content": question}]
    response = ollama.chat(model=MODEL, messages=messages, options={"num_ctx": NUM_CTX})
    return response.message["content"]
    


if __name__ == "__main__":
    print(f"Asking {MODEL}...")
    reply = ask_model("Reply with one short sentence: are you ready?")
    print("Model replied:", reply)
