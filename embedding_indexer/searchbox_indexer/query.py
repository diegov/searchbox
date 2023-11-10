import uuid
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup

import llm
from pydantic import BaseModel
from models import EMBEDDING_MODEL_NAME, SUMMARIZATION_MODEL_NAME
from db import get_pg_connection, DB_NAME

from typing import Annotated, List, Optional
from fastapi import FastAPI, Query, BackgroundTasks

app = FastAPI()


embedding_model = llm.get_embedding_model(EMBEDDING_MODEL_NAME)

summarization_model = None


def get_summarization_model() -> llm.Model:
    global summarization_model
    if summarization_model is None:
        summarization_model = llm.get_model(SUMMARIZATION_MODEL_NAME)
    return summarization_model


class QueryRequest(BaseModel):
    query: str


class QueryMatch(BaseModel):
    url: str
    source_id: str
    title: Optional[str]
    content: str


class QueryResponse(BaseModel):
    title: Optional[str] = None
    results: List[QueryMatch]


def _get_from_embedding(
    embedding: List[float],
    max_results: int,
    excluded_documents: Optional[List[str]] = None,
) -> List[QueryMatch]:
    results: List[QueryMatch] = []

    with get_pg_connection(database=DB_NAME, autocommit=True) as conn:
        with conn.cursor() as c:
            # Default is 40
            c.execute("SET hnsw.ef_search = 100;")

            query = "SELECT url, title, source_id, content FROM items "
            params = []

            if excluded_documents:
                query += "WHERE source_id NOT IN %s "
                params.append(tuple(excluded_documents))

            query += "ORDER BY embedding <-> %s::vector LIMIT %s;"
            params.append(embedding)
            params.append(max_results)

            c.execute(query, tuple(params))
            for rec in c:
                url, title, source_id, content = rec
                results.append(
                    QueryMatch(
                        url=url, title=title, source_id=source_id, content=content
                    )
                )

    return results


@app.get("/query")
def get_query(
    query: Annotated[str, Query(max_length=4096)], max_results: int = 5
) -> QueryResponse:
    embedding = embedding_model.embed(query)
    results = _get_from_embedding(embedding, max_results)
    return QueryResponse(results=results)


@app.get("/similar")
def get_similar(document_id: str, max_results: int = 5) -> QueryResponse:
    with get_pg_connection(database=DB_NAME, autocommit=True) as conn:
        with conn.cursor() as c:
            query = (
                "SELECT title, embedding, source_id FROM items WHERE source_id = %s;"
            )
            c.execute(query, (document_id,))
            r = c.fetchone()
            if r:
                (title, embedding, source_id) = r
                matches = _get_from_embedding(
                    embedding, max_results, excluded_documents=[source_id]
                )
                return QueryResponse(results=matches, title=title)
            else:
                return QueryResponse(results=[])


class RagTask(BaseModel):
    id: str
    query: str
    done: int
    total: int
    results: List[QueryMatch]

    @property
    def complete(self) -> bool:
        return self.done >= self.total


rag_results: List[RagTask] = []


def process_rag_query(id: str, query: str, raw_results: QueryResponse):
    result = RagTask(
        id=id, query=query, total=len(raw_results.results), done=0, results=[]
    )
    rag_results.append(result)

    model = get_summarization_model()

    conversation = model.conversation()
    for i, doc in enumerate(raw_results.results):
        # response = model.prompt(
        #     "I'm going to give you a document, I want you to summarize it. Be brief. Here is the document: "
        #     + doc.content[:1850]
        # )

        # response = model.prompt(
        #     "I'm going to give you a document, please answer the "
        #     "following question based on the document: \"{}\".\nHere is the document: {}".format(query, doc.content[:1800])
        # )

        if i == 0:
            response = conversation.prompt(
                "I'm going to give you a series of documents, and ask you about the contents later. "
                "Here's the first document: {}".format(doc.content[:1600])
            )
        else:
            response = conversation.prompt(
                "Here's another document: {}".format(doc.content[:1600])
            )

        result.results.append(
            QueryMatch(
                url=doc.url,
                title=doc.title,
                source_id=doc.source_id,
                content=response.text(),
            )
        )
        result.done += 1

    response = conversation.prompt(
        'Based on the context of the documents I gave you, please answer the following question: "{}"'.format(
            query
        )
    )
    result.results.append(
        QueryMatch(
            url="file://summary",
            title=query,
            source_id="summary",
            content=response.text(),
        )
    )


@app.get("/query_rag")
def get_query_rag(
    query: Annotated[str, Query(max_length=1024)],
    background_tasks: BackgroundTasks,
    max_results: int = 3,
) -> str:
    raw_results = get_query(query, max_results=max_results)
    id = str(uuid.uuid4())

    background_tasks.add_task(process_rag_query, id, query, raw_results)
    return id


def _scrape_url(url: str) -> str:
    request = Request(url)
    request.add_header(
        "User-Agent",
        "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0",
    )

    with urlopen(request) as page:
        data: str = page.read().decode("utf-8")
        dom = BeautifulSoup(data, "html.parser")
        return dom.get_text()


@app.get("/similar_by_url")
def get_similar_by_url(url: str, max_results: int = 5) -> QueryResponse:
    content = _scrape_url(url)
    embedding = embedding_model.embed(content)
    results = _get_from_embedding(embedding, max_results)
    return QueryResponse(results=results, title=f"Similar to {url}")


@app.get("/rag_tasks")
def get_rag_tasks() -> List[RagTask]:
    return rag_results
