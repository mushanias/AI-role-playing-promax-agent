"""构建随应用部署的公共固定知识库。"""

import argparse

from app.retrieval.builder import KnowledgeBaseBuilder
from app.retrieval.embedding import FastEmbedTextEmbedder


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="构建 SQLite FTS5 与 FAISS 公共知识库索引"
    )
    parser.add_argument(
        "--sources",
        default="knowledge_base/sources",
        help="包含 manifest.json 的资料目录",
    )
    parser.add_argument(
        "--output",
        default="knowledge_base/indexes",
        help="索引输出目录",
    )
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    manifest = KnowledgeBaseBuilder(
        embedder=FastEmbedTextEmbedder()
    ).build(
        source_directory=arguments.sources,
        output_directory=arguments.output,
    )
    print(
        "知识库构建完成："
        f"版本={manifest.knowledge_base_version}，"
        f"文档={manifest.document_count}，"
        f"片段={manifest.chunk_count}"
    )


if __name__ == "__main__":
    main()
