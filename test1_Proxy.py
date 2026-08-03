import os
from dotenv import load_dotenv
from openai import OpenAI

# 1. Load the environment variables from your .env file
load_dotenv()

# 2. Retrieve the variables
API_KEY = os.getenv("PROXY_API_KEY")
BASE_URL = os.getenv("PROXY_BASE_URL")
MODEL_NAME = os.getenv("PROXY_MODEL_NAME")

# 3. Check if the API key was loaded successfully
if not API_KEY:
    raise ValueError("API Key not found. Please check your .env file.")

# 4. Initialize the client using the custom proxy URL
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

def ask_ai(question):
    print(f"You asked: {question}")
    print("Waiting for response...\n")
    
    try:
        # Make the API request
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": question}
            ]
        )
        
        # Extract the text answer from the response
        answer = response.choices[0].message.content
        print(f"AI Answer:\n{answer}")
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # --- Put your request right here ---
    my_question = "What is the time and how are you today?"
    
    ask_ai(my_question)