import ollama
import gradio as gr

def check_local_model():
    print("Sending a test request to Mistral:7B")
    try:
        response = ollama.chat(
            model = "mistral:7b",
            messages = [
                {
                    "role": "user",
                    "content": "Hello, are you working?"
                }
            ],
            options = {
                "temperature":0.0
            }
        )
        print("----------------Model Response:---------------------")
        print(response["message"]["content"])
        print("---------------------------------------------------")

    except Exception as e:
        print(f"The connections failed due to {e}")

if __name__ == "__main__":
    check_local_model()