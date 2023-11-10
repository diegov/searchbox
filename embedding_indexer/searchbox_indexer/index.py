import dataclasses
import os
import sys
from typing import Any, Iterable, List, Optional


import llm
from pathlib import Path
import json
from io import StringIO


from models import EMBEDDING_MODEL_NAME
from db import wait_for_pg, migrate_pg, get_pg_connection, DB_NAME


documents_path = os.environ["DOCUMENTS_PATH"]
documents_batch_size = int(os.environ.get("DOCUMENTS_BATCH_SIZE", 5))


def _sanitize_string(v: str) -> str:
    return v.replace("\x00", " ")


def make_doc(src_doc: dict[str, Any]) -> tuple[str, Optional[str], str]:
    out = StringIO()

    all_keys = set(src_doc.keys())
    skipped_keys = set()
    # Don't output raw html
    skipped_keys.add("html")

    def first_key_found(candidates: Iterable[str]) -> Optional[str]:
        return next(
            (x for x in candidates if x in all_keys and x not in skipped_keys), None
        )

    # Things we output in a specific order
    def fixed_content(*parts: Iterable[str]) -> List[Optional[Any]]:
        result = []
        for key_candidates in parts:
            v = None
            key = first_key_found(key_candidates)

            if key:
                skipped_keys.add(key)
                v = src_doc[key]
                if v:
                    out.write(_sanitize_string(str(v)))
                    out.write("\n\n")

            result.append(v)

        return result

    results = fixed_content(["name", "description"], ["content", "description"])

    title = str(results[0]) if results[0] else None

    for _, v in ((k, v) for (k, v) in src_doc.items() if k not in skipped_keys):
        if v:
            # Skip the key, it only adds noise
            # out.write(_sanitize_string(k))
            # out.write(":\n\n")
            out.write(_sanitize_string(str(v)))
            out.write("\n\n")

    out.flush()
    str_value = out.getvalue()
    out.close()

    url = src_doc.get("url", "")
    return (url, title, str_value)


@dataclasses.dataclass(frozen=True)
class IndexableDoc:
    url: str
    title: Optional[str]
    source_id: str
    content: str


def run_indexer():
    print(f"Indexing data from path: {documents_path}", file=sys.stderr)
    embedding_model = llm.get_embedding_model(EMBEDDING_MODEL_NAME)

    docs: list[IndexableDoc] = []

    conn = get_pg_connection(autocommit=True, database=DB_NAME)
    try:

        def flush_docs():
            if docs:
                vecs = embedding_model.embed_batch(x.content for x in docs)
                vec_params = (
                    (
                        docs[i].url,
                        docs[i].source_id,
                        docs[i].title,
                        docs[i].content,
                        "[" + ",".join(str(v) for v in vec) + "]",
                    )
                    for i, vec in enumerate(vecs)
                )
                query = "INSERT INTO items (url, source_id, title, content, embedding) VALUES (%s, %s, %s, %s, %s)"

                with conn.cursor() as c:
                    c.executemany(query, vec_params)

                print(f"Processed: {len(docs)} docs", file=sys.stderr)
                docs.clear()

        def doc_exists(source_id: str) -> bool:
            with conn.cursor() as c:
                c.execute("SELECT id FROM items WHERE source_id = %s", (source_id,))
                return c.fetchone() is not None

        for path in Path(documents_path).glob("*.jsonl"):
            print(f"Processing file {path}", file=sys.stderr)

            with open(path, "r") as f:
                for i, line in enumerate(f):
                    source_doc = json.loads(line)
                    if "id" in source_doc:
                        source_id = str(source_doc["id"])
                    else:
                        source_id = f"{path}/{i}"

                    if "data" in source_doc:
                        data = source_doc["data"]
                    else:
                        data = source_doc

                    url, title, content = make_doc(data)

                    if not doc_exists(source_id):
                        docs.append(
                            IndexableDoc(
                                url=url,
                                source_id=source_id,
                                title=title,
                                content=content,
                            )
                        )
                        if len(docs) >= documents_batch_size:
                            flush_docs()

        flush_docs()
    finally:
        conn.close()


wait_for_pg()
migrate_pg()

print("Postgresql ready, starting indexing", file=sys.stderr)
run_indexer()

print("Indexing complete", file=sys.stderr)
