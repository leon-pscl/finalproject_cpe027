from langchain_community.vectorstores import FAISS
import inspect
print([m for m in dir(FAISS) if 'score' in m or 'by_vector' in m or 'load' in m or 'save' in m or 'from' in m])
print("similarity_search_with_score_by_vector:", inspect.signature(FAISS.similarity_search_with_score_by_vector))
print("from_embeddings:", inspect.signature(FAISS.from_embeddings))
print("load_local:", inspect.signature(FAISS.load_local))
print("save_local:", inspect.signature(FAISS.save_local))
