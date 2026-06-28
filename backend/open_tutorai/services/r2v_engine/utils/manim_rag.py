"""RAG (Retrieval Augmented Generation) system for Manim documentation.

This module provides a vector store interface for retrieving relevant Manim
documentation to assist in code generation and error fixing.
"""

import os
import logging
from typing import List, Dict, Optional
try:
    from langchain_chroma import Chroma
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    RAG_AVAILABLE = True
except ImportError as e:
    RAG_AVAILABLE = False
    logging.warning(f"RAG dependencies not available: {e}. Install with: pip install langchain-chroma langchain-huggingface langchain-core")

logger = logging.getLogger(__name__)

class ManimRAG:
    """RAG system for Manim documentation retrieval."""
    
    def __init__(
        self,
        chroma_db_path: str = "manim_knowledge_base",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """Initialize the Manim RAG system.
        
        Args:
            chroma_db_path: Path to ChromaDB storage directory
            embedding_model: Name of the embedding model to use
        """
        if not RAG_AVAILABLE:
            logger.warning("RAG system not available - dependencies not installed")
            self.enabled = False
            return
            
        self.chroma_db_path = chroma_db_path
        self.embedding_model = embedding_model
        self.enabled = True
        
        try:
            # Initialize embeddings
            self.embeddings = HuggingFaceEmbeddings(
                model_name=embedding_model,
                model_kwargs={'device': 'cpu'}
            )
            
            # Load or create vector store
            self.vector_store = self._load_vector_store()
            logger.info(f"Manim RAG system initialized with {self.embedding_model}")
        except Exception as e:
            logger.error(f"Failed to initialize RAG system: {e}")
            self.enabled = False
    
    def _load_vector_store(self):
        """Load existing ChromaDB vector store."""
        if not os.path.exists(self.chroma_db_path):
            logger.warning(f"ChromaDB path does not exist: {self.chroma_db_path}")
            logger.warning("RAG system will be disabled. To enable, populate manim_knowledge_base with documentation.")
            self.enabled = False
            return None
            
        try:
            vector_store = Chroma(
                collection_name="manim_docs",
                persist_directory=self.chroma_db_path,
                embedding_function=self.embeddings
            )
            logger.info(f"Loaded ChromaDB from {self.chroma_db_path}")
            return vector_store
        except Exception as e:
            logger.error(f"Failed to load ChromaDB: {e}")
            self.enabled = False
            return None
    
    def retrieve_for_code_generation(
        self,
        scene_description: str,
        implementation_plan: str = "",
        top_k: int = 5
    ) -> str:
        """Retrieve relevant Manim documentation for code generation.
        
        Args:
            scene_description: Description of the scene to generate
            implementation_plan: Technical implementation plan
            top_k: Number of top documents to retrieve
            
        Returns:
            Formatted string with retrieved documentation
        """
        if not self.enabled or not self.vector_store:
            return ""
        
        try:
            # Combine queries for better retrieval
            query = f"{scene_description}\n{implementation_plan}"
            
            # Retrieve relevant documents
            docs = self.vector_store.similarity_search(query, k=top_k)
            
            if not docs:
                logger.info("No documents retrieved from vector store")
                return ""
            
            logger.info(f"Retrieved {len(docs)} documents from vector store for code generation")
            
            # Format retrieved documentation
            context_parts = []
            for i, doc in enumerate(docs, 1):
                context_parts.append(f"--- Documentation Reference {i} ---")
                context_parts.append(doc.page_content)
                context_parts.append("")
            
            return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error retrieving documentation: {e}")
            return ""
    
    def retrieve_for_error_fixing(
        self,
        error_message: str,
        code_snippet: str = "",
        top_k: int = 3
    ) -> str:
        """Retrieve relevant Manim documentation for fixing errors.
        
        Args:
            error_message: The error message to fix
            code_snippet: Snippet of code with the error
            top_k: Number of top documents to retrieve
            
        Returns:
            Formatted string with retrieved documentation
        """
        if not self.enabled or not self.vector_store:
            return ""
        
        try:
            # Create focused query from error context
            query_parts = []
            
            # Extract key terms from error message
            if "AttributeError" in error_message:
                query_parts.append("Manim object attributes methods")
            elif "TypeError" in error_message:
                query_parts.append("Manim function parameters types")
            elif "ImportError" in error_message or "ModuleNotFoundError" in error_message:
                query_parts.append("Manim imports modules")
            
            query_parts.append(error_message)
            if code_snippet:
                query_parts.append(code_snippet[:500])  # Limit code snippet length
            
            query = " ".join(query_parts)
            
            # Retrieve relevant documents
            docs = self.vector_store.similarity_search(query, k=top_k)
            
            if not docs:
                logger.info("No documents retrieved from vector store for error fixing")
                return ""
            
            logger.info(f"Retrieved {len(docs)} documents from vector store for error fixing")
            
            # Format retrieved documentation
            context_parts = []
            context_parts.append("=== Relevant Manim Documentation for Error Fixing ===")
            for i, doc in enumerate(docs, 1):
                context_parts.append(f"\n--- Reference {i} ---")
                context_parts.append(doc.page_content)
            
            return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error retrieving documentation for error fixing: {e}")
            return ""
    
    def retrieve_physics_specific(
        self,
        physics_concept: str,
        top_k: int = 3
    ) -> str:
        """Retrieve physics-specific Manim documentation.
        
        Args:
            physics_concept: Physics concept to visualize (e.g., "force vectors", "motion")
            top_k: Number of top documents to retrieve
            
        Returns:
            Formatted string with retrieved documentation
        """
        if not self.enabled or not self.vector_store:
            return ""
        
        try:
            # Create physics-focused query
            query = f"Manim physics visualization {physics_concept} arrows vectors motion animation"
            
            # Retrieve relevant documents
            docs = self.vector_store.similarity_search(query, k=top_k)
            
            if not docs:
                return ""
            
            # Format retrieved documentation
            context_parts = []
            context_parts.append("=== Physics Visualization Guidance ===")
            for i, doc in enumerate(docs, 1):
                context_parts.append(f"\n--- Physics Reference {i} ---")
                context_parts.append(doc.page_content)
            
            return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error retrieving physics documentation: {e}")
            return ""


# Global RAG instance (lazy initialization)
_manim_rag_instance = None

def get_manim_rag() -> Optional[ManimRAG]:
    """Get the global ManimRAG instance (singleton pattern)."""
    global _manim_rag_instance
    if _manim_rag_instance is None:
        _manim_rag_instance = ManimRAG()
    return _manim_rag_instance if _manim_rag_instance.enabled else None