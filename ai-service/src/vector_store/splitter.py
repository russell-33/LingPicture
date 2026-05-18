from langchain_text_splitters import RecursiveCharacterTextSplitter


def get_splitter(chunk_size: int = 512, chunk_overlap: int = 64) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "，", "、", " ", ""],
    )


def split_text(text: str, chunk_size: int = 512, chunk_overlap: int = 64) -> list[str]:
    splitter = get_splitter(chunk_size, chunk_overlap)
    return splitter.split_text(text)
