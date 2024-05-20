__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

import os
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_chroma import Chroma
from langchain_community.chat_message_histories import ChatMessageHistory, RedisChatMessageHistory
from langchain_community.document_loaders import TextLoader
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from django.conf import settings
from langchain.schema.output_parser import StrOutputParser

import json
import pickle

os.environ["OPENAI_API_KEY"] = settings.OPENAI_API_KEY
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
os.environ["PINECONE_API_KEY"] = settings.PINECONE_API_KEY
os.environ["PINECONE_INDEX_NAME"] = "podcasts"

def __initialise_chain(transcript_file, namespace):
    llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0) 

    loader = TextLoader(transcript_file)
    docs = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    print(f"Length of splits: {len(splits)}")
    embeddings = OpenAIEmbeddings()
    vectorstore = PineconeVectorStore(index_name="podcasts", embedding=embeddings)
    vectorstore.add_documents(splits, namespace=namespace)
    retriever = vectorstore.as_retriever(search_kwargs={"namespace": namespace, 'k': 10})
    output_parser = StrOutputParser()

    ### Contextualize question ###
    contextualize_q_system_prompt = """
        As the initial step in the PodQuest system, your task is to prepare the user's latest question by making it clear and self-contained. This involves utilizing the chat history to provide contextually relevant and accurate reformulations. Here’s how you should handle the user's latest question:

        1. **Contextual Understanding:** Carefully review the chat history to understand the context of the ongoing conversation. Use this context to fully comprehend the user's latest question.

        2. **Reformulate for Clarity:** If the latest user question references previous parts of the conversation and is not standalone, reformulate it to make it clear and self-contained. Ensure that the reformulated question maintains the original intent and meaning.

        3. **Direct Response:** Provide only the reformulated question as the output. Do not include any context summary or additional information.

        4. **No Redundancy:** If the user's latest question is already clear and self-contained, return it as is without any modifications.

        5. **Example:**
        - **Chat History:** 
            - User: "Can you tell me about the new AI technique mentioned?"
            - PodQuest: "Sure! The podcast mentions a new AI technique called X, which involves [detailed explanation]."
            - User: "How is it applied in real-world scenarios?"
        - **Reformulated Question:** "How is the new AI technique called X, mentioned earlier, applied in real-world scenarios?"

        By following these guidelines, you will ensure that each user question is clear, self-contained, and contextually relevant, enabling accurate and helpful responses in subsequent steps of the PodQuest system.
        """
    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )


    ### Answer question ###
    qa_system_prompt = """
        You are PodQuest, an expert chatbot designed to assist users with questions about podcast content. You use a Retrieval-Augmented Generation (RAG) model to provide accurate and detailed responses based on the context retrieved from the podcasts. Here’s how you should behave:

        1. Expert and Friendly: Always maintain a friendly and professional demeanor. You are an expert on the podcast content and should provide detailed and informative answers.

        2. Contextual Responses: Answer each user's question directly using the context provided. Avoid giving irrelevant information. Ensure that your answers are concise (r detailed if user asked for) and relevant to the context retrieved from the podcast.

        3. Engaging Conversation: Strive to keep the conversation engaging. Provide additional relevant information when appropriate and encourage users to ask more questions if they need further clarification.

        4. Handling Irrelevant Questions:
        - If a user asks an irrelevant question or a question outside the scope of the podcast, politely let them know that you can only answer questions related to the podcast content.
        - Suggest they ask questions specific to the podcast to get the most accurate information.

        5. No Context Available:
        - If the context does not contain the information needed to answer a question, let the user know that the specific detail is not available in the current podcast.
        - Offer to help with another question.
        
        By following these guidelines, you will ensure users have a helpful and engaging experience while interacting with you. Always aim to provide the most accurate and contextually relevant information available. Good luck, PodQuest!
        Here is the context retrieved from the podcast:
    {context}"""
    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    
    beautify_system_prompt = """
    Your task is to format the response generated by PodQuest into a clean, readable HTML format. This involves converting lists, points, and other elements into their appropriate HTML tags to enhance readability. Ensure the response is presented in a user-friendly and visually appealing manner.
    Make sure to not change the content of the response, only the formatting. Follow this rule very strictly!!!
    Example:
    - Response: "The new AI technique involves several steps: data preprocessing, model training, and evaluation. Each step has specific requirements."
    - Formatted Response: "<p>The new AI technique involves several steps:</p><ul><li>Data preprocessing</li><li>Model training</li><li>Evaluation</li></ul><p>Each step has specific requirements.</p>"
    """
    beautify_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", beautify_system_prompt),
            ("human", "{answer}"),
        ]
    )

    full_chain = rag_chain | (beautify_prompt | llm) | {"formatted_answer": output_parser}

    def get_message_history(session_id: str) -> RedisChatMessageHistory:
        return RedisChatMessageHistory(session_id, url=settings.REDIS_URL)

    conversational_rag_chain = RunnableWithMessageHistory(
        full_chain,
        get_message_history,
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="formatted_answer",
    )

    return conversational_rag_chain