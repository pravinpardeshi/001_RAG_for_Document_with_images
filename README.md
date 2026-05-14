# RAG Document Chat System with Image Support

A Retrieval-Augmented Generation (RAG) system that allows you to upload PDF documents, extract text and images, and chat with your documents using AI. The system associates images with text chunks, so relevant images are displayed when answering questions.

## Features

- **PDF Document Processing**: Upload and process PDF documents with text and image extraction
- **Image-Enhanced RAG**: Images from PDF pages are associated with text chunks and displayed when relevant
- **Semantic Search**: Uses sentence transformers for intelligent document chunk retrieval
- **AI-Powered Chat**: Query your documents using Ollama LLM (qwen2.5:3b)
- **Vector Storage**: Simple JSON-based vector store for embeddings and chunks
- **Web Interface**: Clean web UI for document management and chat
- **Document Management**: Upload, list, and delete documents

## Tech Stack

- **Backend**: FastAPI
- **Embeddings**: Sentence Transformers (all-MiniLM-L6-v2)
- **LLM**: Ollama (qwen2.5:3b)
- **PDF Processing**: PyPDF2, pdf2image
- **Image Processing**: Pillow
- **Frontend**: HTML, CSS, JavaScript

## Prerequisites

- Python 3.8+
- Ollama installed and running (with qwen2.5:3b model)
- poppler-utils (for pdf2image)

### Install Ollama

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the required model
ollama pull qwen2.5:3b

# Start Ollama server
ollama serve
```

### Install poppler-utils (Linux)

```bash
sudo apt-get install poppler-utils
```

### Install poppler (macOS)

```bash
brew install poppler
```

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd 002_RAG_for_Document_with_images
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install additional dependency for pdf2image:
```bash
pip install pdf2image
```

## Usage

1. Start the application:
```bash
python main.py
```

The server will start on `http://localhost:8015`

2. Open your browser and navigate to `http://localhost:8015`

3. Upload a PDF document using the web interface

4. Ask questions about your document in the chat interface

## API Endpoints

### `POST /upload`
Upload and process a PDF document.

**Request**: 
- Form data with file (PDF)

**Response**:
```json
{
  "message": "Successfully processed document.pdf",
  "chunks_processed": 25,
  "document_name": "document.pdf"
}
```

### `POST /chat`
Chat with the uploaded documents.

**Request Body**:
```json
{
  "message": "What is the main topic of the document?"
}
```

**Response**:
```json
{
  "response": "The main topic is...",
  "relevant_chunks": [...],
  "images": [
    {
      "path": "uploads/images/document_page_1.jpg",
      "caption": "From page 1 of document.pdf",
      "thumbnail": "/uploads/thumbnails/document_page_1_thumb.jpg",
      "image_base64": "..."
    }
  ]
}
```

### `GET /documents`
List all processed documents.

**Response**:
```json
{
  "documents": ["document1.pdf", "document2.pdf"]
}
```

### `DELETE /documents/{document_name}`
Delete a document and its chunks.

**Response**:
```json
{
  "message": "Document document.pdf deleted successfully"
}
```

## Configuration

You can modify the following settings in `main.py`:

- `OLLAMA_BASE_URL`: Ollama server URL (default: `http://localhost:11434`)
- `MODEL_NAME`: Ollama model name (default: `qwen2.5:3b`)
- `chunk_size`: Text chunk size (default: 500)
- `overlap`: Text chunk overlap (default: 100)

## Project Structure

```
.
├── main.py              # FastAPI application
├── requirements.txt     # Python dependencies
├── static/              # Frontend files
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── favicon.svg
├── uploads/             # Uploaded PDFs and extracted images
│   ├── images/
│   └── thumbnails/
├── data/                # Vector store data
│   ├── vectors.json
│   └── chunks.json
└── README.md
```

## How It Works

1. **Document Upload**: When a PDF is uploaded, it's saved to the `uploads/` directory
2. **Image Extraction**: pdf2image extracts each page as an image
3. **Text Extraction**: PyPDF2 extracts text from each page
4. **Chunking**: Text is split into overlapping chunks (500 characters with 100 overlap)
5. **Image Association**: Each text chunk is associated with the image from its page
6. **Embedding Generation**: Sentence transformers generate embeddings for each chunk
7. **Storage**: Chunks and embeddings are stored in JSON files
8. **Query Processing**: 
   - User question is embedded
   - Similar chunks are retrieved using cosine similarity
   - Relevant chunks and their images are sent to the LLM
   - LLM generates a response based on the context

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
