import sys
import llm

# EMBEDDING_MODEL_NAME = "jina-embeddings-v2-small-en"
# EMBEDDING_MODEL_VECTOR_SIZE = 512

EMBEDDING_MODEL_NAME = "jina-embeddings-v2-base-en"
EMBEDDING_MODEL_VECTOR_SIZE = 768


SUMMARIZATION_MODEL_NAME = "mistral-7b-instruct-v0"


if len(sys.argv) > 1 and sys.argv[1] == "init-models":
    # Force model download
    embedding_model = llm.get_embedding_model(EMBEDDING_MODEL_NAME)
    print(embedding_model.embed("init-model"))

    summarization_model = llm.get_model(SUMMARIZATION_MODEL_NAME)
    print(summarization_model.prompt(""))

    sys.exit(0)
