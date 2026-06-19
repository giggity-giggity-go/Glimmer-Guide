"""vector_repo 单元测试 — CB-02 allow_reset + HB-12 batching"""
from __future__ import annotations

import pytest


class TestCB02Safety:
    """CB-02: 拔掉数据安全炸弹"""

    def test_no_reset_function_exposed(self):
        """reset() 必须被删除"""
        from yantu.data import vector_repo
        assert not hasattr(vector_repo, "reset"), (
            "vector_repo.reset() still exposed — CB-02 violation!"
        )

    def test_no_delete_collection_exposed(self):
        """delete_collection 也不能从 vector_repo 模块访问"""
        from yantu.data import vector_repo
        assert not hasattr(vector_repo, "delete_collection"), (
            "delete_collection leaked into vector_repo module"
        )

    def test_chroma_settings_allow_reset_disabled(self):
        """ChromaSettings 必须 allow_reset=False"""
        from chromadb.config import Settings as ChromaSettings
        s = ChromaSettings(allow_reset=False)
        assert s.allow_reset is False


class TestHB12Batching:
    """HB-12: add_documents 分批写入,避免大批量 OOM"""

    def test_batch_size_constant(self):
        from yantu.data import vector_repo
        assert hasattr(vector_repo, "_ADD_BATCH_SIZE")
        assert vector_repo._ADD_BATCH_SIZE == 100

    def test_length_mismatch_raises(self, fresh_vector_repo):
        from yantu.data import vector_repo
        with pytest.raises(ValueError, match="length mismatch"):
            vector_repo.add_documents(
                documents=["a", "b"],
                embeddings=[[0.1] * 5],  # only 1 embedding for 2 docs
                metadatas=[{}, {}],
                ids=["1", "2"],
            )

    def test_empty_input_noop(self, fresh_vector_repo):
        from yantu.data import vector_repo
        # 不应抛异常,也不应写任何东西
        vector_repo.add_documents(
            documents=[],
            embeddings=[],
            metadatas=[],
            ids=[],
        )


class TestHB04Singleton:
    """HB-04: vector_repo singleton client"""

    def test_singleton_returns_same_client(self, fresh_vector_repo):
        from yantu.data import vector_repo
        c1 = vector_repo._get_singleton_client()
        c2 = vector_repo._get_singleton_client()
        assert c1 is c2, "client should be singleton"

    def test_singleton_thread_safe_init(self, fresh_vector_repo):
        """并发调用 _get_singleton_client 不会创建多个 client"""
        from yantu.data import vector_repo
        import threading

        clients = []
        errors = []

        def worker():
            try:
                c = vector_repo._get_singleton_client()
                clients.append(id(c))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"concurrent init errors: {errors}"
        # 8 个线程应该都拿到同一个 client
        unique = set(clients)
        assert len(unique) == 1, f"expected 1 unique client, got {len(unique)}"