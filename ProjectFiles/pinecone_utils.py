import os
from dotenv import load_dotenv
# from datasets import load_dataset  # Commented out as it's no longer used
from langchain_community.document_loaders import (
    PyMuPDFLoader,
    UnstructuredWordDocumentLoader,
    UnstructuredHTMLLoader,
    TextLoader,
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

# ----------- Loaders for each file type -----------
def load_pdf_document(path: str):
    return PyMuPDFLoader(path).load()

def load_docx_document(path: str):
    return UnstructuredWordDocumentLoader(path).load()

def load_html_document(path: str):
    return UnstructuredHTMLLoader(path).load()

def load_txt_document(path: str):
    return TextLoader(path, encoding="utf-8").load()

# ----------- Detect file type & load -----------
def load_document(path: str):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return load_pdf_document(path)
    elif ext == ".docx":
        return load_docx_document(path)
    elif ext in [".html", ".htm"]:
        return load_html_document(path)
    elif ext == ".txt":
        return load_txt_document(path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

# ----------- Create chunks -----------
def create_chunks(documents, chunk_size=500, chunk_overlap=20):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    return text_splitter.split_documents(documents)

# # ----------- Load HuggingFace Dataset (Indian IPC-Laws) -----------
# # The following function and its related calls are now commented out.
# def load_hf_dataset(dataset_name="NahOR102/Indian-IPC-Laws"):
#     dataset = load_dataset(dataset_name, split="train")
#     docs = []
#     for i, row in enumerate(dataset):
#         conversation = []
#         for msg in row["messages"]:
#             role = msg.get("role", "unknown").capitalize()
#             content = msg.get("content", "")
#             conversation.append(f"{role}: {content}")
#         content = "\n".join(conversation)
        
#         docs.append(Document(
#             page_content=content,
#             metadata={"source": dataset_name, "row": i}
#         ))
#     return docs

# ----------- MAIN PIPELINE -----------
if __name__ == "__main__":
    load_dotenv()
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    if not PINECONE_API_KEY:
        raise ValueError("❌ Pinecone API Key not found in .env file")
    
    # Initialize Pinecone
    pc = Pinecone(api_key=PINECONE_API_KEY)
    INDEX_NAME = "legal-chatbot"
    
    # Check if index exists, else create
    if INDEX_NAME not in [idx["name"] for idx in pc.list_indexes()]:
        pc.create_index(
            name=INDEX_NAME,
            metric="cosine",
            dimension=384,  # must match embedding model
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"✅ Created index: {INDEX_NAME}")
    else:
        print(f"ℹ Index '{INDEX_NAME}' already exists.")
    
    # Embedding model
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Process files from local data folder
    data_folder = "pineconedata"
    for file_name in os.listdir(data_folder):
        file_path = os.path.join(data_folder, file_name)
        try:
            docs = load_document(file_path)
            print(f"✅ Loaded {file_name}, total {len(docs)} docs")
            
            # Create chunks
            chunks = create_chunks(docs)
            print(f"📄 Split into {len(chunks)} chunks")
            
            # Insert into Pinecone via LangChain
            PineconeVectorStore.from_documents(
                documents=chunks,
                embedding=embeddings,
                index_name=INDEX_NAME
            )
            print(f"🚀 Inserted {len(chunks)} chunks from {file_name} into Pinecone")
        except Exception as e:
            print(f"❌ Could not process {file_name}: {e}")
    
    # # Process HuggingFace dataset (Indian IPC Laws) - This block is now commented out.
    # try:
    #     hf_docs = load_hf_dataset()
    #     print(f"✅ Loaded HuggingFace dataset with {len(hf_docs)} documents")
        
    #     hf_chunks = create_chunks(hf_docs)
    #     print(f"📄 Split HF dataset into {len(hf_chunks)} chunks")
        
    #     PineconeVectorStore.from_documents(
    #         documents=hf_chunks,
    #         embedding=embeddings,
    #         index_name=INDEX_NAME
    #     )
    #     print(f"🚀 Inserted HF dataset ({len(hf_chunks)} chunks) into Pinecone")
    # except Exception as e:
    #     print(f"❌ Could not process HuggingFace dataset: {e}")