from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

class OllamaModel:
    def __init__(self, model_name="medgemma-4b-it:Q4_K_M", base_url="http://localhost:11434/v1"):
        """
        Initializes the OllamaModel with the specified model name and base URL.

        Parameters:
        - model_name: The name of the Ollama model to use. Default is "google/gemma-3-4b-it:latest".
        - base_url: The base URL of the Ollama server. Default is "http://localhost:11434".
        """
        self.model = model_name
        self.base_url = base_url
        self.client = ChatOpenAI(
            model=self.model,             
            base_url=self.base_url,
            api_key="loc-123",
            temperature=0.2,
            max_tokens=2048,
            top_p=0.9,
            top_k=40,            
        )
        

    def get_system_prompt(self) -> str:
        """
        Returns a default system prompt for the Ollama model.

        Returns:
        - A string containing the system prompt.
        """
        
        prompt = """
            You are a powerfull grammar und summarization specialist.
            There is a whipser transcription of a german audio file.
            Your task is to correct the grammar and summarize the content in a concise manner.
            Provide the output in well-structured german sentences.
            Keep the meaning of the original transcription intact.
            It is very important to only correct grammar and not change any words or meaning.
            Use the following format:
            
            --- Original Transcription ---
            {message}
            --- Original Transcription End ---  
            
            --- Corrected and Summarized Transcription ---
            
            Do not use more words than necessary.
            Do not add any explanations or additional information.
            Do not mention that you are an AI model.
            Do not apologize.
            Do not self-reference.
            Do not use emoticons or special characters.            
            """
       
        return prompt
    
        
    def generate_response(self, message: str) -> str:
        """
        Generates a response from the Ollama model based on the provided prompt.

        Parameters:
        - prompt: The input prompt string to send to the model.

        Returns:
        - The generated response string from the model.
        """
        
        template = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("user", "{message}")
        ])

        chain = template | self.client
        response = chain.invoke({"message": message})
        
        return response.content