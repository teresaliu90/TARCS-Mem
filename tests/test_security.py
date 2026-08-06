from datetime import date

import pytest

from tarcsmem.models import MemoryRecord, SourceType
from tarcsmem.security import SecurityGate, SecurityViolation, scan_sensitive_text
from tarcsmem.service import TARCSMemoryService


def fake_openai_key() -> str:
    return "sk" + "-" + ("a" * 26)


def record(fact: str, record_id: str = "security-case") -> MemoryRecord:
    return MemoryRecord(
        id=record_id,
        fact=fact,
        source_type=SourceType.OFFICIAL_POLICY,
        source_ref="SECURITY-TEST#1",
        authority=0.9,
        conflict_key=record_id,
        evidence=["SECURITY-TEST#1"],
        valid_from=date(2026, 1, 1),
    )


def test_detector_returns_categories_without_secret_values():
    text = f"联系人 a.person@example.com，token={fake_openai_key()}"
    findings = scan_sensitive_text(text)
    assert {item.category for item in findings} == {"email", "openai_api_key"}
    assert all(not hasattr(item, "value") for item in findings)


def test_default_gate_redacts_pii():
    decision = SecurityGate().evaluate("请联系 13812345678 或 alice@example.com")
    assert decision.allowed is True
    assert decision.redacted is True
    assert "13812345678" not in decision.text
    assert "alice@example.com" not in decision.text
    assert decision.counts == {"cn_mobile": 1, "email": 1}


@pytest.mark.parametrize(
    "text,category",
    [
        ("密钥 " + fake_openai_key(), "openai_api_key"),
        ("token " + "ghp" + "_" + ("A" * 24), "github_token"),
        ("AWS " + "AKIA" + ("A" * 16), "aws_access_key"),
        ("password=correct-horse-battery-staple", "assigned_secret"),
        ("-----" + "BEGIN " + "PRIVATE KEY" + "-----", "private_key"),
    ],
)
def test_default_gate_blocks_credentials(text, category):
    decision = SecurityGate().evaluate(text)
    assert decision.allowed is False
    assert decision.text == ""
    assert decision.counts[category] == 1


def test_modes_are_explicit():
    text = "员工邮箱 alice@example.com"
    assert SecurityGate("reject").evaluate(text).allowed is False
    assert SecurityGate("audit").evaluate(text).text == text
    assert SecurityGate("off").evaluate(text).counts == {}
    with pytest.raises(ValueError, match="security mode"):
        SecurityGate("unknown")


def test_blocked_secret_never_reaches_memory_or_audit(tmp_path):
    service = TARCSMemoryService(tmp_path / "blocked.db")
    secret = fake_openai_key()
    with pytest.raises(SecurityViolation):
        service.ingest(record(f"生产密钥 {secret}"))
    assert service.store.count() == 0
    serialized = str(service.audit_trail("security-case"))
    assert secret not in serialized
    assert "openai_api_key" in serialized
    service.close()


def test_service_persists_only_redacted_pii(tmp_path):
    service = TARCSMemoryService(tmp_path / "redacted.db")
    email = "alice@example.com"
    saved = service.ingest(record(f"制度联系人 {email}"))
    assert email not in saved.fact
    assert saved.metadata["security"]["redacted"] is True
    assert email not in (tmp_path / "redacted.db").read_bytes().decode("utf-8", errors="ignore")
    service.close()


def test_review_note_is_scanned_before_status_change():
    service = TARCSMemoryService()
    pending = service.ingest(
        MemoryRecord(
            fact="待审核会议结论",
            source_type=SourceType.MEETING_NOTE,
            source_ref="MEETING#1",
            authority=0.7,
            conflict_key="review-security",
            evidence=["MEETING#1"],
        )
    )
    with pytest.raises(SecurityViolation):
        service.review(
            pending.id,
            "approve",
            "security-owner",
            f"使用 {fake_openai_key()} 调试",
        )
    assert service.store.get(pending.id).status.value == "pending"
    service.close()
