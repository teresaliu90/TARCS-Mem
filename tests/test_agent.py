from datetime import date

from tarcsmem.adapters import HashEmbedding
from tarcsmem.agent import LocalAgentConfig, TARCSChatAgent
from tarcsmem.models import AccessContext, MemoryRecord, SourceType
from tarcsmem.public_data import PublicDocument


class FakeVectorStore:
    def __init__(self):
        self.entries = []

    def upsert(self, entries):
        self.entries.extend(entries)

    def search(self, vector, limit=12, tenant_id=None):
        entries = self.entries
        if tenant_id is not None:
            entries = [entry for entry in entries if entry[2].get("tenant_id") == tenant_id]
        return [{"payload": {"record_id": record_id}} for record_id, _, _ in entries[:limit]]


class AdversarialVectorStore(FakeVectorStore):
    """Records source filtering but deliberately returns a foreign candidate too."""

    def __init__(self):
        super().__init__()
        self.search_calls = []

    def search(self, vector, limit=12, tenant_id=None):
        self.search_calls.append({"limit": limit, "tenant_id": tenant_id})
        return [{"payload": {"record_id": record_id}} for record_id, _, _ in self.entries[:limit]]


class FakeReranker:
    def rerank(self, query, passages):
        return [1.0] * len(passages)


class FakeLLM:
    def chat(self, messages, temperature=0.1):
        return "基于受治理证据的本地模型回答。[SOURCE: POLICY-SALES-2026-07#1]"


class FakeCloudLLM:
    provider_name = "test-cloud"
    is_cloud = True

    def __init__(self):
        self.calls = 0

    def chat(self, messages, temperature=0.1):
        self.calls += 1
        return "云端回答。[SOURCE: CONFIDENTIAL-POLICY#1]"


class FakeUncitedLLM:
    def chat(self, messages, temperature=0.1):
        return "没有来源标记的回答。"


class FakeInventedCitationLLM:
    def chat(self, messages, temperature=0.1):
        return "带有虚构来源的回答。[SOURCE: INVENTED#1]"


def test_local_agent_keeps_tarcs_governance_before_llm(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "agent.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeLLM(),
    )
    agent.vectors = FakeVectorStore()
    agent.seed_demo()
    result = agent.chat("2026年8月华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "answered"
    assert result["citations"] == ["POLICY-SALES-2026-07#1"]
    assert "受治理证据" in result["answer"]
    trail = agent.memory.get_answer_audit_trail(str(result["answer_id"]), AccessContext())
    assert trail is not None
    assert trail.outcome == "answered"
    assert trail.verification["citation_membership"] == "passed"
    agent.close()


def test_local_agent_forwards_bounded_conversation_but_keeps_evidence_governed(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "context.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeLLM(),
    )
    agent.vectors = FakeVectorStore()
    agent.seed_demo()
    result = agent.chat(
        "那现在是多少？",
        date(2026, 8, 15),
        conversation=[{"role": "user", "content": "华南区折扣上限是多少？"}],
    )
    assert result["outcome"] == "answered"
    assert result["context_messages"] == 1
    assert "华南区折扣上限" in result["retrieval_query"]
    agent.close()


def test_public_dataset_ingest_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tarcsmem.agent.load_fiqa_documents",
        lambda limit: [
            PublicDocument(document_id="test-1", title="", text="financial retrieval test")
        ],
    )
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "dedupe.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeLLM(),
    )
    agent.vectors = FakeVectorStore()
    assert len(agent.ingest_fiqa_sample(1)) == 1
    assert agent.ingest_fiqa_sample(1) == []
    assert agent.memory.store.count() == 1
    agent.close()


def test_message_text_normalizes_gradio_content_payloads():
    assert TARCSChatAgent._message_text({"text": "上一轮问题"}) == "上一轮问题"


def test_system_prompt_explains_governed_open_ended_validity():
    evidence = MemoryRecord(
        fact="华南区销售折扣上限为5%。",
        source_type=SourceType.OFFICIAL_POLICY,
        source_ref="POLICY#1",
        authority=1.0,
        conflict_key="sales-discount",
        valid_from=date(2026, 7, 1),
        evidence=["POLICY#1"],
    )
    prompt = TARCSChatAgent._system_prompt("2026年8月折扣上限？", [evidence])
    assert "[VALID_TO: open-ended]" in prompt
    assert "already passed" in prompt
    assert "do not demand" in prompt


def test_cloud_egress_blocks_confidential_evidence_before_generation(tmp_path):
    cloud = FakeCloudLLM()
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "egress.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=cloud,
    )
    agent.vectors = FakeVectorStore()
    agent.ingest_record(
        MemoryRecord(
            id="confidential-policy",
            fact="机密审批上限为100万元。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="CONFIDENTIAL-POLICY#1",
            authority=1.0,
            conflict_key="approval-limit",
            evidence=["CONFIDENTIAL-POLICY#1"],
            classification="confidential",
        )
    )
    result = agent.chat("机密审批上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "abstained"
    assert result["generation_metrics"]["status"] == "blocked_by_cloud_egress_policy"
    assert cloud.calls == 0
    events = agent.memory.audit_trail(str(result["answer_id"]))
    assert any(event["event_type"] == "cloud_egress" for event in events)
    assert events[-1]["detail"]["outcome"] == "abstained"
    trail = agent.memory.get_answer_audit_trail(str(result["answer_id"]), AccessContext())
    assert trail is not None
    assert trail.outcome == "abstained"
    assert trail.verification["cloud_egress"] == "blocked"
    assert "tarcsmem_cloud_egress_total" in agent.memory.observability.metrics.prometheus_text()
    agent.close()


def test_cloud_egress_can_be_explicitly_allowed_by_deployment_policy(tmp_path, monkeypatch):
    monkeypatch.setenv("TARCSMEM_CLOUD_ALLOWED_CLASSIFICATIONS", "public,internal,confidential")
    cloud = FakeCloudLLM()
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "allowed.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=cloud,
    )
    agent.vectors = FakeVectorStore()
    agent.ingest_record(
        MemoryRecord(
            id="explicitly-allowed",
            fact="机密审批上限为100万元。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="CONFIDENTIAL-POLICY#1",
            authority=1.0,
            conflict_key="approval-limit",
            evidence=["CONFIDENTIAL-POLICY#1"],
            classification="confidential",
        )
    )
    result = agent.chat("机密审批上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "answered"
    assert cloud.calls == 1
    agent.close()


def test_uncited_generation_is_blocked_after_governed_retrieval(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "uncited.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeUncitedLLM(),
    )
    agent.vectors = FakeVectorStore()
    agent.seed_demo()
    result = agent.chat("2026年8月华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "abstained"
    assert result["citations"] == []
    assert result["generation_metrics"]["citation_verification"] == "missing"
    events = agent.memory.audit_trail(str(result["answer_id"]))
    assert any(event["event_type"] == "generation_verified" for event in events)
    assert events[-1]["detail"]["outcome"] == "abstained"
    trail = agent.memory.get_answer_audit_trail(str(result["answer_id"]), AccessContext())
    assert trail is not None
    assert trail.verification["citation_membership"] == "missing"
    assert (
        "tarcsmem_generation_verification_total"
        in agent.memory.observability.metrics.prometheus_text()
    )
    agent.close()


def test_invented_generation_citation_is_blocked(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "invented.db"), qdrant_url="http://qdrant-test.invalid"
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeInventedCitationLLM(),
    )
    agent.vectors = FakeVectorStore()
    agent.seed_demo()
    result = agent.chat("2026年8月华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "abstained"
    assert result["generation_metrics"]["citation_verification"] == "unsupported"
    agent.close()


def test_vector_candidate_oversampling_filters_acl_decoys_before_governance(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "oversampling.db"),
            qdrant_url="http://qdrant-test.invalid",
            retrieval_limit=3,
            candidate_pool_multiplier=5,
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeLLM(),
    )
    agent.vectors = FakeVectorStore()
    for index in range(14):
        agent.ingest_record(
            MemoryRecord(
                id=f"restricted-{index}",
                fact=f"华南区销售折扣内部草案{index}",
                source_type=SourceType.OFFICIAL_POLICY,
                source_ref=f"RESTRICTED#{index}",
                authority=1.0,
                conflict_key=f"restricted-{index}",
                evidence=[f"RESTRICTED#{index}"],
                classification="restricted",
                allowed_roles=["admin"],
            )
        )
    agent.ingest_record(
        MemoryRecord(
            id="eligible-policy",
            fact="华南区销售折扣上限为5%。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="POLICY-SALES-2026-07#1",
            authority=1.0,
            conflict_key="sales-limit",
            evidence=["POLICY-SALES-2026-07#1"],
        )
    )
    candidates = agent._candidate_records(
        "华南区销售折扣上限是多少？", date(2026, 8, 15), AccessContext()
    )
    assert [record.id for record in candidates] == ["eligible-policy"]
    result = agent.chat("华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "answered"
    assert result["citations"] == ["POLICY-SALES-2026-07#1"]
    agent.close()


def test_vector_candidates_are_tenant_filtered_at_source_and_rechecked_after_load(tmp_path):
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "tenant-vector.db"),
            qdrant_url="http://qdrant-test.invalid",
            retrieval_limit=2,
            candidate_pool_multiplier=4,
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
        llm=FakeLLM(),
    )
    vectors = AdversarialVectorStore()
    agent.vectors = vectors
    agent.ingest_record(
        MemoryRecord(
            id="foreign-vector-hit",
            fact="华南区销售折扣上限为99%。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="FOREIGN#1",
            authority=1.0,
            conflict_key="foreign-limit",
            evidence=["FOREIGN#1"],
            tenant_id="beta",
        )
    )
    agent.ingest_record(
        MemoryRecord(
            id="allowed-vector-hit",
            fact="华南区销售折扣上限为5%。",
            source_type=SourceType.OFFICIAL_POLICY,
            source_ref="ALPHA#1",
            authority=1.0,
            conflict_key="alpha-limit",
            evidence=["ALPHA#1"],
            tenant_id="alpha",
        )
    )

    candidates = agent._candidate_records(
        "华南区销售折扣上限是多少？",
        date(2026, 8, 6),
        AccessContext.from_values("alpha", []),
    )

    assert vectors.search_calls == [{"limit": 8, "tenant_id": "alpha"}]
    assert [record.id for record in candidates] == ["allowed-vector-hit"]
    agent.close()


def test_zero_config_generation_path_needs_no_llm_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("TARCSMEM_LLM_PROVIDER", raising=False)
    agent = TARCSChatAgent(
        LocalAgentConfig(
            db_path=str(tmp_path / "zero-config.db"),
            qdrant_url="http://qdrant-test.invalid",
        ),
        embedding=HashEmbedding(),
        reranker=FakeReranker(),
    )
    agent.vectors = FakeVectorStore()
    agent.seed_demo()
    result = agent.chat("2026年8月华南区销售折扣上限是多少？", date(2026, 8, 15))
    assert result["outcome"] == "answered"
    assert result["generation_metrics"]["provider"] == "extractive-demo"
    assert result["generation_metrics"]["citation_verification"] == "passed"
    assert result["citations"] == ["POLICY-SALES-2026-07#1"]
    agent.close()
