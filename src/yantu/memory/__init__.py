"""v0.3.0-beta 长期记忆模块

路径 A' 架构:
- schemas.py:6 种 fact_type 的 Pydantic schema
- retriever.py:Chroma top-K 检索(注入 router system prompt)
- extractor.py:每 N 轮调 LLM 抽 facts,写 SQLite + Chroma
- langmem_bridge.py:LangMem InMemoryStore + rehydrate from SQLite
"""
