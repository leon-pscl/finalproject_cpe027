import tempfile
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS as LCFaiss
class DummyEmb(Embeddings):
    def embed_documents(self, texts): return [[0.0]*4 for _ in texts]
    def embed_query(self, text): return [0.0]*4
folder = tempfile.mkdtemp()
try:
    store = LCFaiss.from_embeddings([], DummyEmb())
    print("empty from embeddings ok")
    store.save_local(folder)
    loaded = LCFaiss.load_local(folder, DummyEmb(), allow_dangerous_deserialization=True)
    print("loaded empty ok", loaded.index.ntotal)
except Exception as e:
    print("ERROR:", type(e).__name__, str(e)[:300])
PY