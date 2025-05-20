from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector
import typing
import aiohttp
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import sqlalchemy as sa
import time
import json

Base = declarative_base()

class ChatMessage(Base):
    __tablename__ = "message"
    id = sa.Column(sa.BigInteger(), primary_key=True)
    user = sa.Column(sa.String(255))
    question = sa.Column(sa.Text())
    answer = sa.Column(sa.Text())
    created = sa.Column(sa.BigInteger())

class Memory(Base):
    __tablename__ = "memory"
    id = sa.Column(sa.BigInteger(), primary_key=True)
    user = sa.Column(sa.String(255))
    content = sa.Column(sa.Text())
    vector = sa.Column(Vector())
    created = sa.Column(sa.BigInteger())

Session = sessionmaker(Base)

class MemoryApp:
    def __init__(self, config: dict):
        self.config: dict = config["memory"]
        self.jina_api = self.config["jina"]["api"]
        if self.jina_api[-1] != "/":
            self.jina_api += "/"
        self.jina_key = self.config["jina"]["key"]
        self.jina_embedding = self.config["jina"]["models"]["embedding"]
        self.jina_reranker = self.config["jina"]["models"]["reranker"]
        user = self.config["pgvector"]["username"]
        password = self.config["pgvector"]["password"]
        host = self.config["pgvector"]["host"]
        dbname = self.config["pgvector"]["database"]
        port = self.config["pgvector"].get("port", 5432)
        self.engine = create_engine(f'postgresql://{user}:{password}@{host}:{port}/{dbname}', echo=False)
        Base.metadata.create_all(self.engine)
        self.sessionmaker = sessionmaker(self.engine)
    async def getDataVector(self, content: str) -> typing.List[int]:
        async with aiohttp.ClientSession() as session:
            req = await session.post(self.jina_api+"v1/embeddings", data=json.dumps({
                "model": self.jina_embedding,
                "input": [ content ]
            }), headers={
                "Authorization": "Bearer " + self.jina_key,
                "Content-Type": "application/json"
            })
            return (await req.json())["data"][0]["embedding"]
    async def rerankText(
            self,
            query: str,
            content: typing.List[Memory],
            top_n: int = 3,
            order: typing.Literal["origin", "match", "mismatch"] = "origin"
        ) -> typing.List[Memory]:
        if len(content) <= top_n:
            return content
        keys: typing.List[str] = [ item.content for item in content ]
        # Jina request
        async with aiohttp.ClientSession() as session:
            ret: list = (await (await session.post(self.jina_api+"v1/rerank", data=json.dumps({
                "model": self.jina_reranker,
                "query": query,
                "documents": keys,
                "top_n": top_n
            }), headers={
                "Authorization": "Bearer " + self.jina_key,
                "Content-Type": "application/json"
            })).json())["results"]
        # Order
        if order == "origin":
            ret.sort(lambda x: x["index"])
        elif order == "mismatch":
            ret.sort(lambda x: x["relevance_score"])
        else:
            ret.sort(lambda x: x["relevance_score"], reverse=True)
        # Return
        return [ content[i["index"]] for i in ret ]
    async def getMemory(self, user: str, query: str, limit: int=10, threshold: float=0.5) -> typing.List[str]:
        try:
            query: typing.List[int] = await self.getDataVector(query)
            session = self.sessionmaker()
            response = session.execute(
                sa.select(Memory)
                .where(Memory.user == user)
                .where(Memory.vector.cosine_distance(query) < (2 - threshold * 2))
                .order_by(Memory.vector.cosine_distance(query))
                .limit(limit * 2)
            )
            response = [ n.tuple()[0] for n in response.fetchall() ]
            response = await self.rerankText(query, response, top_n=limit, order='origin')
            return [ n.content for n in response ]
        except Exception:
            return []
    async def addMemory(self, user: str, content: str) -> bool:
        try:
            embedding = await self.getDataVector(content)
            ormObject = Memory(user=user, content=content, vector=embedding, created=round(time.time()))
            session = self.sessionmaker()
            session.add(ormObject)
            session.commit()
            return True
        except Exception:
            return False
    async def getChatMessages(self, user: str, limit: int=50) -> typing.List[typing.Tuple[str, str]]:
        try:
            session = self.sessionmaker()
            response = session.execute(
                sa.select(ChatMessage)
                .where(ChatMessage.user == user)
                .order_by(sa.desc(ChatMessage.created))
                .limit(limit)
            )
            response = [ n.tuple()[0] for n in response.fetchall() ]
            response.sort(lambda x: x.created)
            return [ (n.question, n.answer) for n in response ]
        except Exception:
            return []
    async def addChatMessages(self, user: str, question: str, answer: str) -> bool:
        try:
            session = self.sessionmaker()
            ormObject = ChatMessage(user=user, question=question, answer=answer, created=round(time.time()))
            session.add(ormObject)
            session.commit()
            return True
        except Exception:
            return False