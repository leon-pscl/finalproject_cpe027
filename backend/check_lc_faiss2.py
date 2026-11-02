import tempfile, os
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS as LCFaiss
from langchain_core.embeddings import Embeddings
class DummyEmb(Embeddings):
    def embed_documents(self, texts): return [[0.0]*4 for _ in texts]
    def embed_query(self, text): return [0.0]*4

vectors = [[1.0,2,3,4],[5,6,7,8]]
texts = ["a","b"]
metas = [{"id":"c1"},{"id":"c2"}]
store = LCFaiss.from_embeddings(list(zip(texts,vectors)), DummyEmb(), metadatas=metas)
folder = tempfile.mkdtemp()
store.save_local(folder)
loaded = LCFaiss.load_local(folder, DummyEmb(), allow_dangerous_deserialization=True)
print("loaded type", type(loaded))
print("has index attr?", hasattr(loaded, "index"))
print("underlying type", type(loaded.index))
print("ntotal", loaded.index.ntotal)
res = loaded.similarity_search_with_score_by_vector(vectors[0], k=2)
print("results", res)
# reconstruct
print("recon", loaded.index.reconstruct_n(0, loaded.index.ntotal))
PY