"""
Script to check FAISS index and determine which embedding model was used
"""
import os
import pickle

def check_index(index_path="index"):
    print(f"🔍 Checking index at: {index_path}")
    
    # Check if directory exists
    if not os.path.exists(index_path):
        print(f"❌ Directory not found: {index_path}")
        return
    
    # List files
    files = os.listdir(index_path)
    print(f"📂 Files in directory: {files}")
    
    # Check for metadata file
    metadata_file = os.path.join(index_path, "embedding_model.txt")
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            model_type = f.read().strip()
            print(f"📝 Embedding model from metadata: {model_type}")
    else:
        print("⚠️  No embedding_model.txt found")
    
    # Try to read index.pkl to get more info
    pkl_file = os.path.join(index_path, "index.pkl")
    if os.path.exists(pkl_file):
        try:
            with open(pkl_file, 'rb') as f:
                data = pickle.load(f)
                print(f"📊 Index PKL contents:")
                if hasattr(data, '__dict__'):
                    for key, value in data.__dict__.items():
                        print(f"  - {key}: {type(value)}")
        except Exception as e:
            print(f"⚠️  Could not read index.pkl: {e}")
    
    # Try to load FAISS index to get dimension
    try:
        import faiss
        faiss_file = os.path.join(index_path, "index.faiss")
        if os.path.exists(faiss_file):
            index = faiss.read_index(faiss_file)
            print(f"📐 Index dimensions: {index.d}")
            print(f"📊 Number of vectors: {index.ntotal}")
            
            # Common embedding dimensions:
            if index.d == 384:
                print("💡 Likely created with: sentence-transformers/all-MiniLM-L6-v2 (HuggingFace)")
            elif index.d == 768:
                print("💡 Likely created with: Gemini embedding-001 or BERT-based models")
            elif index.d == 1536:
                print("💡 Likely created with: OpenAI text-embedding-ada-002")
            else:
                print(f"💡 Unknown embedding model (dimension: {index.d})")
    except Exception as e:
        print(f"⚠️  Could not read FAISS index: {e}")

if __name__ == "__main__":
    check_index()