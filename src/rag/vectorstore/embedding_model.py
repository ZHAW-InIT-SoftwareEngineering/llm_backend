from langchain_huggingface import HuggingFaceEmbeddings


MODEL_NAME: str = "Qwen/Qwen3-Embedding-8B"


def get_embedding_model(model_name: str = MODEL_NAME) -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=model_name,
        encode_kwargs={"normalize_embeddings": True},
    )


def main() -> None:
    embedding_model = get_embedding_model()
    print(f"Loaded embedding model: {embedding_model.model_name}")


if __name__ == "__main__":
    main()
