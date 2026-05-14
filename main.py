import os
import json
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
import aiofiles
import numpy as np
from sentence_transformers import SentenceTransformer
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import PyPDF2
from PIL import Image
import io
import base64
import hashlib
from pdf2image import convert_from_path

app = FastAPI(title="RAG Document Chat System")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Configuration
UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
UPLOAD_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

# Initialize sentence transformer model
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
MODEL_NAME = "qwen2.5:3b"

# Data structures
class DocumentChunk(BaseModel):
    text: str
    image_path: Optional[str] = None
    image_data: Optional[str] = None  # base64 encoded
    chunk_id: str
    source_document: str
    page_number: Optional[int] = None

class ChatRequest(BaseModel):
    message: str
    document_name: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    relevant_chunks: List[DocumentChunk]
    images: List[Dict[str, Any]]

# Vector storage
class VectorStore:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.vectors_file = data_dir / "vectors.json"
        self.chunks_file = data_dir / "chunks.json"
        self.embeddings = {}
        self.chunks = {}
        self.load_data()
    
    def load_data(self):
        try:
            if self.vectors_file.exists():
                with open(self.vectors_file, 'r') as f:
                    self.embeddings = json.load(f)
            if self.chunks_file.exists():
                with open(self.chunks_file, 'r') as f:
                    self.chunks = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error loading JSON data: {e}")
            self.embeddings = {}
            self.chunks = {}
    
    def save_data(self):
        with open(self.vectors_file, 'w') as f:
            json.dump(self.embeddings, f)
        with open(self.chunks_file, 'w') as f:
            json.dump(self.chunks, f)
    
    def add_chunk(self, chunk: DocumentChunk, embedding: List[float]):
        chunk_id = chunk.chunk_id
        self.chunks[chunk_id] = chunk.dict()
        self.embeddings[chunk_id] = embedding
        self.save_data()
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[DocumentChunk]:
        if not self.embeddings:
            return []
        
        similarities = []
        for chunk_id, embedding in self.embeddings.items():
            similarity = np.dot(query_embedding, embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(embedding)
            )
            similarities.append((similarity, chunk_id))
        
        similarities.sort(reverse=True, key=lambda x: x[0])
        
        results = []
        for similarity, chunk_id in similarities[:top_k]:
            if chunk_id in self.chunks:
                chunk_data = self.chunks[chunk_id]
                results.append(DocumentChunk(**chunk_data))
        
        return results

vector_store = VectorStore(DATA_DIR)

# Document processing
def extract_text_and_images_from_pdf(pdf_path: Path) -> List[DocumentChunk]:
    chunks = []
    image_dir = UPLOAD_DIR / "images"
    thumbnail_dir = UPLOAD_DIR / "thumbnails"
    image_dir.mkdir(exist_ok=True)
    thumbnail_dir.mkdir(exist_ok=True)

    try:
        # Extract images from PDF first (one per page)
        images = convert_from_path(pdf_path, fmt='jpeg')
        page_images = {}  # Store image paths per page (1-indexed)
        
        for idx, image in enumerate(images):
            page_num = idx + 1
            image_path = image_dir / f"{pdf_path.stem}_page_{page_num}.jpg"
            image.save(image_path, "JPEG")
            
            # Generate thumbnail
            thumbnail_path = thumbnail_dir / f"{pdf_path.stem}_page_{page_num}_thumb.jpg"
            with Image.open(image_path) as img:
                img.thumbnail((300, 300))  # Larger thumbnail for better display
                img.save(thumbnail_path, "JPEG")
            
            # Encode image as base64 for storage in chunk
            with open(image_path, "rb") as img_file:
                image_base64 = base64.b64encode(img_file.read()).decode('utf-8')
            
            page_images[page_num] = {
                "image_path": str(image_path),
                "thumbnail_path": str(thumbnail_path),
                "image_base64": image_base64
            }

        # Extract text and associate with images
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)

            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                page_number = page_num + 1

                if text.strip():
                    # Split text into chunks
                    text_chunks = split_text_into_chunks(text)

                    for i, chunk_text in enumerate(text_chunks):
                        chunk_id = f"{pdf_path.stem}_page_{page_num}_chunk_{i}"

                        # Associate image with chunk if available for this page
                        image_data = None
                        image_path = None
                        if page_number in page_images:
                            image_data = page_images[page_number]["image_base64"]
                            image_path = page_images[page_number]["image_path"]

                        chunk = DocumentChunk(
                            text=chunk_text,
                            chunk_id=chunk_id,
                            source_document=pdf_path.name,
                            page_number=page_number,
                            image_path=image_path,
                            image_data=image_data
                        )

                        chunks.append(chunk)

    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")

    return chunks

def split_text_into_chunks(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        if end >= len(text):
            chunks.append(text[start:])
            break
        
        # Try to break at a sentence boundary
        chunk_text = text[start:end]
        last_period = chunk_text.rfind('.')
        last_newline = chunk_text.rfind('\n')
        
        break_point = max(last_period, last_newline)
        
        if break_point > start + chunk_size // 2:  # Don't go back too far
            end = start + break_point + 1
            chunk_text = text[start:end]
        
        chunks.append(chunk_text.strip())
        start = end - overlap
    
    return [chunk for chunk in chunks if chunk.strip()]

# Ollama integration
def query_ollama(prompt: str) -> str:
    """Query Ollama API."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False
            },
            timeout=600
        )
        
        if response.status_code == 200:
            return response.json().get("response", "")
        else:
            return f"Error: Ollama returned status {response.status_code}"
    
    except requests.exceptions.RequestException as e:
        return f"Error connecting to Ollama: {str(e)}"

# Helper function to generate thumbnails
def generate_thumbnail(image_path: Path, thumbnail_dir: Path) -> Path:
    """Generate a thumbnail for the given image."""
    thumbnail_dir.mkdir(exist_ok=True)
    thumbnail_path = thumbnail_dir / f"{image_path.stem}_thumb.jpg"

    try:
        with Image.open(image_path) as img:
            img.thumbnail((150, 150))  # Resize to thumbnail size
            img.save(thumbnail_path, "JPEG")
    except Exception as e:
        print(f"Error generating thumbnail for {image_path}: {e}")

    return thumbnail_path

# API endpoints
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML page."""
    html_file = Path("static/index.html")
    if html_file.exists():
        return FileResponse(html_file)
    return HTMLResponse("<h1>RAG Document Chat System</h1><p>Frontend not found. Please create static/index.html</p>")

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save uploaded file
    file_path = UPLOAD_DIR / file.filename
    async with aiofiles.open(file_path, 'wb') as f:
        content = await file.read()
        await f.write(content)
    
    # Process document
    chunks = extract_text_and_images_from_pdf(file_path)
    
    # Generate embeddings and store
    for chunk in chunks:
        embedding = embedding_model.encode(chunk.text).tolist()
        vector_store.add_chunk(chunk, embedding)
    
    return {
        "message": f"Successfully processed {file.filename}",
        "chunks_processed": len(chunks),
        "document_name": file.filename
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    print('Query: ', request.message)

    """Chat with the document."""
    # Generate query embedding
    query_embedding = embedding_model.encode(request.message).tolist()
    
    # Search for relevant chunks
    relevant_chunks = vector_store.search(query_embedding, top_k=5)
    
    # Build context for LLM
    context = "\n\n".join([chunk.text for chunk in relevant_chunks])
    
    # Create prompt
    prompt = f"""Based on the following document context, please answer the user's question. 
                If the context doesn't contain enough information to answer the question, please say so.

                Context:
                {context}

                Question: {request.message}

                Please provide a helpful and consize answer:
            """
    
    # Query Ollama
    response = query_ollama(prompt)
    print(f'LLM Response: {response}')

    # Extract images from relevant chunks
    images = []
    for chunk in relevant_chunks:
        if chunk.image_data:
            images.append({
                "path": chunk.image_path,
                "caption": f"From page {chunk.page_number} of {chunk.source_document}",
                "thumbnail": f"/uploads/thumbnails/{Path(chunk.image_path).stem}_thumb.jpg",
                "image_base64": chunk.image_data
            })
    
    return ChatResponse(
        response=response,
        relevant_chunks=relevant_chunks,
        images=images
    )

@app.get("/documents")
async def list_documents():
    """List all processed documents."""
    documents = set()
    for chunk_data in vector_store.chunks.values():
        documents.add(chunk_data["source_document"])
    return {"documents": list(documents)}

@app.delete("/documents/{document_name}")
async def delete_document(document_name: str):
    """Delete a document and its chunks."""
    chunks_to_delete = []
    for chunk_id, chunk_data in vector_store.chunks.items():
        if chunk_data["source_document"] == document_name:
            chunks_to_delete.append(chunk_id)
    
    for chunk_id in chunks_to_delete:
        if chunk_id in vector_store.chunks:
            del vector_store.chunks[chunk_id]
        if chunk_id in vector_store.embeddings:
            del vector_store.embeddings[chunk_id]
    
    vector_store.save_data()
    
    # Delete uploaded file
    file_path = UPLOAD_DIR / document_name
    if file_path.exists():
        file_path.unlink()
    
    return {"message": f"Document {document_name} deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8015)
