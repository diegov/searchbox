import os
import sys
import time
import psycopg2
from psycopg2.extensions import connection
import socket
from models import EMBEDDING_MODEL_VECTOR_SIZE


pg_pass = os.environ["POSTGRES_PASSWORD"]
pg_host = os.environ["POSTGRES_HOST"]
pg_port = 5432

DB_NAME = "embeddings"


def get_pg_connection(autocommit=False, database="postgres") -> connection:
    conn = psycopg2.connect(
        host=pg_host,
        port=pg_port,
        user="postgres",
        password=pg_pass,
        database=database,
    )
    conn.autocommit = autocommit
    return conn


max_wait = 4 * 60


def wait_for_pg():
    start = time.time()

    while time.time() - start < max_wait:
        address = pg_host
        port = pg_port

        print(
            "Attemping socket connection to %s:%d" % (address, port),
            file=sys.stderr,
        )

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            s.connect((address, port))
            break
        except Exception as e:
            print(
                "Postgresql not ready %s:%d. Exception is %s" % (address, port, e),
                file=sys.stderr,
            )
        finally:
            s.close()

        time.sleep(3)

    while time.time() - start < max_wait:
        print(
            "Attemping psycopq2 connection",
            file=sys.stderr,
        )
        c = None
        try:
            c = get_pg_connection()
            return
        except Exception as e:
            print("Postgresql not ready.  Exception is %s" % e, file=sys.stderr)
        finally:
            if c is not None:
                c.close()
        time.sleep(3)

    raise Exception("Timed out waiting for postgres")


def migrate_pg():
    conn = get_pg_connection()
    try:
        with conn.cursor() as c:
            c.execute(
                "SELECT datname FROM pg_catalog.pg_database WHERE lower(datname) = lower(%s);",
                (DB_NAME,),
            )
            data = c.fetchone()
    finally:
        conn.close()

    if not data:
        conn = get_pg_connection(autocommit=True)
        try:
            with conn.cursor() as c:
                c.execute("CREATE DATABASE " + DB_NAME + ";")
        finally:
            conn.close()

        with get_pg_connection(autocommit=True, database=DB_NAME) as conn:
            with conn.cursor() as c:
                c.execute("CREATE EXTENSION vector;")

                c.execute(
                    """CREATE TABLE items (
                      id bigserial PRIMARY KEY,
                      source_id text,
                      title text NULL,
                      url text,
                      content text,
                      embedding vector({})
                    );""".format(
                        EMBEDDING_MODEL_VECTOR_SIZE
                    )
                )

                # Defaults were 16 and 64, but they weren't working great, eg. it was very
                # hard to get the tui-rs result from  "A library to create a TUI in Rust"
                # After upgrading to this and changing the model to jina-embeddings-v2-base-en,
                # this query works fine, it's not 100% confirmed that these values are
                # the cause of the improvement, but the absence of tui-rs in the results,
                # for such an obvious query, was probably a hnsw failure not a problem
                # with the embeddings.
                hnsw_m = 32
                hnsw_ef_construction = 128

                c.execute(
                    """CREATE INDEX ON items
                    USING hnsw (embedding vector_l2_ops)
                    WITH (m = {}, ef_construction = {});
                    """.format(
                        hnsw_m, hnsw_ef_construction
                    )
                )
                c.execute("CREATE UNIQUE INDEX ON items (source_id);")
