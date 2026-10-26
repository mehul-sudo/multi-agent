"""
Regression tests for Phase 6-7-8 audit fixes.

Tests all confirmed issues that were identified and fixed:
  P8-1  Genuine multi-agent conflict detection and resolution
  P8-2  Real optimistic locking for shared context
  P8-3  Indirect delegation-cycle detection
  P6-2  Timeout propagation to LLM adapter SDK calls
  P6-3  Circuit-breaker persistence (process-level singleton)
  SEC-1 Credential IDOR prevention
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.extensions import db
from app.models.agent import Agent
from app.models.delegation_record import DelegationRecord
from app.models.encrypted_credential import EncryptedCredential
from app.models.orchestration_plan import OrchestrationPlan, PlanTask
from app.models.orchestration_session import OrchestrationSession
from app.models.organization import Organization, OrganizationMember, ORG_ROLE_ADMIN
from app.models.shared_context import CONTEXT_SCOPE_GLOBAL
from app.services.conflict_service import (
    ConflictResolutionError,
    STRATEGY_ADJUDICATOR_AGENT,
    STRATEGY_MAJORITY_VOTE,
    STRATEGY_HIGHEST_CONFIDENCE,
    detect_and_resolve_conflict,
    _extract_claims,
    _analyse_claims,
    _majority_vote_winner,
    _highest_confidence_winner,
)
from app.services.context_service import (
    ContextVersionConflictError,
    set_context_entry,
    get_context_entry,
)
from app.services.delegation_service import (
    DelegationDepthExceededError,
    DelegationLoopError,
    _get_delegation_ancestry,
    delegate_subtask,
)
from app.services.credential_service import CredentialService
from app.llm.contracts import LLMRequest, LLMMessage
from app.llm.resilience import LLMResilienceManager, CircuitBreaker
from app.services.execution_engine import _SHARED_RESILIENCE_MANAGER, LLMAgentExecutor


def _make_session(user_id):
    s = OrchestrationSession(user_id=user_id, objective="Test session")
    db.session.add(s)
    db.session.flush()
    return s


def _make_plan(session_id):
    p = OrchestrationPlan(orchestration_id=session_id, objective="Test plan")
    db.session.add(p)
    db.session.flush()
    return p


def _make_task(plan_id, depth=0, key="task1"):
    t = PlanTask(
        plan_id=plan_id,
        task_key=key,
        name=f"Task {key}",
        delegation_depth=depth,
    )
    db.session.add(t)
    db.session.flush()
    return t


class TestConflictService:

    def test_extract_claims_primitives_only(self):
        out = {"score": 0.9, "label": "positive", "meta": {"nested": True}, "count": 5}
        claims = _extract_claims(out)
        assert "score" in claims
        assert "label" in claims
        assert "count" in claims
        assert "meta" not in claims

    def test_extract_claims_non_dict_returns_empty(self):
        assert _extract_claims("not a dict") == {}
        assert _extract_claims(None) == {}
        assert _extract_claims(42) == {}

    def test_all_agents_agree_full_confidence(self):
        outputs = {
            1: {"prediction": "increase", "confidence": 0.9},
            2: {"prediction": "increase", "confidence": 0.9},
        }
        agreeing, disagreeing, confidence = _analyse_claims(outputs)
        assert "prediction" in agreeing
        assert confidence == 1.0

    def test_two_agents_disagree_zero_confidence(self):
        outputs = {
            1: {"prediction": "increase"},
            2: {"prediction": "decrease"},
        }
        agreeing, disagreeing, confidence = _analyse_claims(outputs)
        assert "prediction" in disagreeing
        assert confidence == 0.0

    def test_majority_vote_selects_majority_winner(self):
        outputs = {1: {"result": "A"}, 2: {"result": "A"}, 3: {"result": "B"}}
        agreeing, _, _ = _analyse_claims(outputs)
        winner = _majority_vote_winner(outputs, agreeing)
        assert outputs[winner]["result"] == "A"

    def test_highest_confidence_winner(self):
        outputs = {
            1: {"prediction": "X", "confidence": 0.5},
            2: {"prediction": "Y", "confidence": 0.95},
            3: {"prediction": "Z", "confidence": 0.7},
        }
        assert _highest_confidence_winner(outputs) == 2

    def test_highest_confidence_fallback_lowest_id(self):
        outputs = {5: {"result": "A"}, 3: {"result": "B"}, 7: {"result": "C"}}
        assert _highest_confidence_winner(outputs) == 3

    def test_conflict_resolution_all_agree(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"sentiment": "positive"}, 2: {"sentiment": "positive"}}
            record = detect_and_resolve_conflict(session.id, None, outputs, STRATEGY_MAJORITY_VOTE)
            assert record.id is not None
            assert record.decision_confidence == 1.0
            assert record.final_decision["sentiment"] == "positive"
            assert "sentiment" in record.evidence_references["agreeing_keys"]
            assert record.evidence_references["disagreeing_keys"] == []

    def test_conflict_resolution_two_disagree(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"prediction": "increase"}, 2: {"prediction": "decrease"}}
            record = detect_and_resolve_conflict(session.id, None, outputs, STRATEGY_ADJUDICATOR_AGENT)
            assert record.id is not None
            assert record.decision_confidence == 0.0
            assert record.evidence_references["disagreeing_keys"] == ["prediction"]

    def test_conflict_resolution_majority_vote_three_agents(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"label": "cat"}, 2: {"label": "cat"}, 3: {"label": "dog"}}
            record = detect_and_resolve_conflict(session.id, None, outputs, STRATEGY_MAJORITY_VOTE)
            assert record.final_decision["label"] == "cat"
            assert record.decision_confidence == 1.0

    def test_conflict_resolution_missing_output_raises(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            with pytest.raises(ConflictResolutionError):
                detect_and_resolve_conflict(session.id, None, {1: {"result": "yes"}, 2: None})

    def test_conflict_resolution_malformed_output_raises(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            with pytest.raises(ConflictResolutionError):
                detect_and_resolve_conflict(session.id, None, {1: "not a dict", 2: [1, 2]})

    def test_conflict_confidence_not_hardcoded(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"color": "red", "size": "large"}, 2: {"color": "red", "size": "small"}}
            record = detect_and_resolve_conflict(session.id, None, outputs)
            assert record.decision_confidence == 0.5
            assert record.decision_confidence != 0.9

    def test_conflict_evidence_references_populated(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"x": 1, "y": 10}, 2: {"x": 1, "y": 20}}
            record = detect_and_resolve_conflict(session.id, None, outputs)
            evid = record.evidence_references
            assert "winner_agent_id" in evid
            assert evid["agreeing_keys"] == ["x"]
            assert evid["disagreeing_keys"] == ["y"]

    def test_conflict_highest_confidence_strategy(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            outputs = {1: {"answer": "no", "confidence": 0.3}, 2: {"answer": "yes", "confidence": 0.95}}
            record = detect_and_resolve_conflict(session.id, None, outputs, STRATEGY_HIGHEST_CONFIDENCE)
            assert record.final_decision["answer"] == "yes"

    def test_conflict_unsupported_strategy_raises(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            with pytest.raises(ValueError, match="Unsupported"):
                detect_and_resolve_conflict(
                    session.id, None, {1: {"x": 1}, 2: {"x": 2}}, "BAD_STRATEGY"
                )


class TestOptimisticLocking:

    def test_normal_unconditional_update_backward_compatible(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            rec = set_context_entry(session.id, "key1", "v1", scope=CONTEXT_SCOPE_GLOBAL)
            assert rec.version == 1
            rec2 = set_context_entry(session.id, "key1", "v2", scope=CONTEXT_SCOPE_GLOBAL)
            assert rec2.version == 2
            assert get_context_entry(session.id, "key1", scope=CONTEXT_SCOPE_GLOBAL) == "v2"

    def test_correct_expected_version_succeeds(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            rec = set_context_entry(session.id, "key_cas", "initial", scope=CONTEXT_SCOPE_GLOBAL)
            assert rec.version == 1
            updated = set_context_entry(
                session.id, "key_cas", "updated",
                scope=CONTEXT_SCOPE_GLOBAL, expected_version=1
            )
            assert updated.version == 2
            assert get_context_entry(session.id, "key_cas") == "updated"

    def test_incorrect_expected_version_raises(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            set_context_entry(session.id, "key_stale", "v1", scope=CONTEXT_SCOPE_GLOBAL)
            set_context_entry(session.id, "key_stale", "v2", scope=CONTEXT_SCOPE_GLOBAL)
            with pytest.raises(ContextVersionConflictError) as exc_info:
                set_context_entry(
                    session.id, "key_stale", "v3_FAIL",
                    scope=CONTEXT_SCOPE_GLOBAL, expected_version=1
                )
            assert exc_info.value.expected_version == 1
            assert exc_info.value.actual_version == 2
            assert get_context_entry(session.id, "key_stale") == "v2"

    def test_version_increments_correctly(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            for expected_ver in range(1, 5):
                rec = set_context_entry(session.id, "counter_key", f"v{expected_ver}")
                assert rec.version == expected_ver

    def test_silent_overwrite_prevented(self, app, test_user):
        with app.app_context():
            session = _make_session(test_user.id)
            set_context_entry(session.id, "shared_key", "original")
            set_context_entry(session.id, "shared_key", "writer_1", expected_version=1)
            with pytest.raises(ContextVersionConflictError):
                set_context_entry(session.id, "shared_key", "writer_2", expected_version=1)
            assert get_context_entry(session.id, "shared_key") == "writer_1"


class TestDelegationCycleDetection:

    def _setup(self, user):
        a1 = Agent(user_id=user.id, name="Agent A", system_instructions="A", max_delegation_depth=5)
        a2 = Agent(user_id=user.id, name="Agent B", system_instructions="B", max_delegation_depth=5)
        a3 = Agent(user_id=user.id, name="Agent C", system_instructions="C", max_delegation_depth=5)
        db.session.add_all([a1, a2, a3])
        db.session.flush()
        sess = _make_session(user.id)
        plan = _make_plan(sess.id)
        task = _make_task(plan.id, depth=0, key="root")
        return a1, a2, a3, sess, plan, task

    def test_ancestry_empty_when_no_records(self, app, test_user):
        with app.app_context():
            assert _get_delegation_ancestry(999, 42) == {42}

    def test_ancestry_single_hop(self, app, test_user):
        with app.app_context():
            a1, a2, _, sess, _, _ = self._setup(test_user)
            db.session.add(DelegationRecord(
                orchestration_id=sess.id, parent_task_id=1, child_task_id=2,
                parent_agent_id=a1.id, child_agent_id=a2.id, delegation_depth=1,
            ))
            db.session.commit()
            ancestry = _get_delegation_ancestry(sess.id, a2.id)
            assert a1.id in ancestry and a2.id in ancestry

    def test_ancestry_two_hop(self, app, test_user):
        with app.app_context():
            a1, a2, a3, sess, _, _ = self._setup(test_user)
            db.session.add_all([
                DelegationRecord(
                    orchestration_id=sess.id, parent_task_id=1, child_task_id=2,
                    parent_agent_id=a1.id, child_agent_id=a2.id, delegation_depth=1,
                ),
                DelegationRecord(
                    orchestration_id=sess.id, parent_task_id=2, child_task_id=3,
                    parent_agent_id=a2.id, child_agent_id=a3.id, delegation_depth=2,
                ),
            ])
            db.session.commit()
            ancestry = _get_delegation_ancestry(sess.id, a3.id)
            assert all(x in ancestry for x in [a1.id, a2.id, a3.id])

    def test_direct_self_loop_rejected(self, app, test_user):
        with app.app_context():
            a1, _, _, sess, _, task = self._setup(test_user)
            with patch(
                "app.services.delegation_service.find_best_agent_for_task",
                return_value=(a1, "self", 1.0)
            ):
                with pytest.raises(DelegationLoopError):
                    delegate_subtask(sess.id, task, a1, "test", "Sub", {}, "loop test")

    def test_indirect_two_hop_cycle_rejected(self, app, test_user):
        with app.app_context():
            a1, a2, _, sess, plan, _ = self._setup(test_user)
            task_b = _make_task(plan.id, depth=1, key="task_b")
            db.session.add(DelegationRecord(
                orchestration_id=sess.id, parent_task_id=1, child_task_id=task_b.id,
                parent_agent_id=a1.id, child_agent_id=a2.id, delegation_depth=1,
            ))
            db.session.commit()
            with patch(
                "app.services.delegation_service.find_best_agent_for_task",
                return_value=(a1, "cycle", 1.0)
            ):
                with pytest.raises(DelegationLoopError):
                    delegate_subtask(sess.id, task_b, a2, "test", "Cycle", {}, "2-hop")

    def test_indirect_three_hop_cycle_rejected(self, app, test_user):
        with app.app_context():
            a1, a2, a3, sess, plan, _ = self._setup(test_user)
            task_b = _make_task(plan.id, depth=1, key="task_b3")
            task_c = _make_task(plan.id, depth=2, key="task_c3")
            db.session.add_all([
                DelegationRecord(
                    orchestration_id=sess.id, parent_task_id=1, child_task_id=task_b.id,
                    parent_agent_id=a1.id, child_agent_id=a2.id, delegation_depth=1,
                ),
                DelegationRecord(
                    orchestration_id=sess.id, parent_task_id=task_b.id, child_task_id=task_c.id,
                    parent_agent_id=a2.id, child_agent_id=a3.id, delegation_depth=2,
                ),
            ])
            db.session.commit()
            with patch(
                "app.services.delegation_service.find_best_agent_for_task",
                return_value=(a1, "3hop", 1.0)
            ):
                with pytest.raises(DelegationLoopError):
                    delegate_subtask(sess.id, task_c, a3, "test", "Cycle3", {}, "3-hop")

    def test_valid_delegation_chain_allowed(self, app, test_user):
        with app.app_context():
            a1, a2, a3, sess, plan, task_a = self._setup(test_user)
            task_b = _make_task(plan.id, depth=1, key="valid_b")
            db.session.add(DelegationRecord(
                orchestration_id=sess.id, parent_task_id=task_a.id, child_task_id=task_b.id,
                parent_agent_id=a1.id, child_agent_id=a2.id, delegation_depth=1,
            ))
            db.session.commit()
            with patch(
                "app.services.delegation_service.find_best_agent_for_task",
                return_value=(a3, "valid", 0.9)
            ):
                child, record = delegate_subtask(
                    sess.id, task_b, a2, "test", "Valid C", {}, "valid chain"
                )
            assert child.id is not None
            assert record.child_agent_id == a3.id

    def test_depth_limit_enforced(self, app, test_user):
        with app.app_context():
            a1, a2, _, sess, plan, _ = self._setup(test_user)
            a1.max_delegation_depth = 1
            db.session.flush()
            task = _make_task(plan.id, depth=1, key="depth_lim")
            with patch(
                "app.services.delegation_service.find_best_agent_for_task",
                return_value=(a2, "target", 1.0)
            ):
                with pytest.raises(DelegationDepthExceededError):
                    delegate_subtask(sess.id, task, a1, "test", "Over limit", {}, "depth test")


class TestTimeoutPropagation:

    def test_openai_adapter_passes_timeout(self):
        from app.llm.providers.openai_adapter import OpenAIProviderAdapter
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "Test"
        mock_resp.choices[0].message.tool_calls = None
        mock_resp.choices[0].finish_reason = "stop"
        mock_resp.usage.prompt_tokens = 10
        mock_resp.usage.completion_tokens = 5
        mock_resp.usage.total_tokens = 15
        mock_resp.id = "id"
        mock_resp.model = "gpt-4o"
        mock_client.chat.completions.create.return_value = mock_resp

        adapter = OpenAIProviderAdapter(client=mock_client)
        req = LLMRequest(
            provider="openai", model="gpt-4o",
            messages=[LLMMessage(role="user", content="Hi")], timeout=42.0
        )
        adapter.generate(req)
        kwargs = mock_client.chat.completions.create.call_args[1]
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 42.0

    def test_anthropic_adapter_passes_timeout(self):
        from app.llm.providers.anthropic_adapter import AnthropicProviderAdapter
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(type="text", text="Test")]
        mock_resp.stop_reason = "end_turn"
        mock_resp.usage.input_tokens = 10
        mock_resp.usage.output_tokens = 5
        mock_resp.id = "id"
        mock_resp.model = "claude-3-5-sonnet-20240620"
        mock_client.messages.create.return_value = mock_resp

        adapter = AnthropicProviderAdapter(client=mock_client)
        req = LLMRequest(
            provider="anthropic", model="claude-3-5-sonnet-20240620",
            messages=[LLMMessage(role="user", content="Hi")], timeout=15.0
        )
        adapter.generate(req)
        kwargs = mock_client.messages.create.call_args[1]
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 15.0

    def test_gemini_adapter_passes_timeout(self):
        from app.llm.providers.gemini_adapter import GeminiProviderAdapter
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = "Gemini response"
        mock_resp.usage_metadata.prompt_token_count = 10
        mock_resp.usage_metadata.candidates_token_count = 5
        mock_client.generate_content.return_value = mock_resp

        adapter = GeminiProviderAdapter(client=mock_client)
        req = LLMRequest(
            provider="gemini", model="gemini-1.5-pro",
            messages=[LLMMessage(role="user", content="Hi")], timeout=20.0
        )
        adapter.generate(req)
        kwargs = mock_client.generate_content.call_args[1]
        assert "timeout" in kwargs
        assert kwargs["timeout"] == 20.0


class TestCircuitBreakerPersistence:

    def test_shared_manager_is_module_level_singleton(self):
        from app.services.execution_engine import _SHARED_RESILIENCE_MANAGER as sm1
        from app.services import execution_engine
        assert sm1 is execution_engine._SHARED_RESILIENCE_MANAGER

    def test_two_executors_share_same_manager(self):
        mgr1 = LLMAgentExecutor().resilience_manager
        mgr2 = LLMAgentExecutor().resilience_manager
        assert mgr1 is mgr2
        assert mgr1 is _SHARED_RESILIENCE_MANAGER

    def test_injected_manager_overrides_singleton(self):
        custom = LLMResilienceManager()
        executor = LLMAgentExecutor(resilience_manager=custom)
        assert executor.resilience_manager is custom
        assert executor.resilience_manager is not _SHARED_RESILIENCE_MANAGER

    def test_failure_counts_accumulate(self):
        mgr = LLMResilienceManager()
        cb = mgr.get_circuit_breaker("test_provider_accum")
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 2

    def test_circuit_opens_after_threshold(self):
        mgr = LLMResilienceManager()
        cb = mgr.get_circuit_breaker("test_open_thresh")
        cb.failure_threshold = 3
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitBreaker.STATE_OPEN

    def test_open_circuit_blocks_requests(self):
        mgr = LLMResilienceManager()
        cb = mgr.get_circuit_breaker("test_blocking_req")
        cb.failure_threshold = 1
        cb.recovery_timeout = 9999
        cb.record_failure()
        assert cb.state == CircuitBreaker.STATE_OPEN
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_recovery(self):
        import time
        mgr = LLMResilienceManager()
        cb = mgr.get_circuit_breaker("test_halfopen_cb")
        cb.failure_threshold = 1
        cb.recovery_timeout = 0.001
        cb.record_failure()
        time.sleep(0.01)
        result = cb.allow_request()
        assert result is True
        assert cb.state == CircuitBreaker.STATE_HALF_OPEN

    def test_success_from_half_open_closes_circuit(self):
        import time
        mgr = LLMResilienceManager()
        cb = mgr.get_circuit_breaker("test_close_cb")
        cb.failure_threshold = 1
        cb.recovery_timeout = 0.001
        cb.record_failure()
        time.sleep(0.01)
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitBreaker.STATE_CLOSED
        assert cb.failure_count == 0

    def test_failure_persists_across_executor_instantiation(self):
        _SHARED_RESILIENCE_MANAGER._circuit_breakers.pop("persist_test_key", None)
        executor1 = LLMAgentExecutor()
        cb1 = executor1.resilience_manager.get_circuit_breaker("persist_test_key")
        cb1.record_failure()
        cb1.record_failure()
        executor2 = LLMAgentExecutor()
        cb2 = executor2.resilience_manager.get_circuit_breaker("persist_test_key")
        assert cb2.failure_count == 2
        _SHARED_RESILIENCE_MANAGER._circuit_breakers.pop("persist_test_key", None)


class TestCredentialIDOR:

    def _create_org(self, owner_id):
        org = Organization(
            name=f"Test Org {owner_id}",
            slug=f"test-org-{owner_id}",
            owner_user_id=owner_id,
            is_active=True,
        )
        db.session.add(org)
        db.session.flush()
        db.session.add(OrganizationMember(
            organization_id=org.id, user_id=owner_id,
            org_role=ORG_ROLE_ADMIN, is_active=True,
        ))
        db.session.flush()
        return org

    def _create_cred(self, user_id, org_id, name="Test Cred"):
        cred = EncryptedCredential(
            name=name, credential_type="api_key",
            encrypted_value="FAKE", owner_user_id=user_id,
            organization_id=org_id, is_active=True,
        )
        db.session.add(cred)
        db.session.flush()
        return cred

    def test_authorized_member_can_list(self, app, test_user):
        with app.app_context():
            org = self._create_org(test_user.id)
            self._create_cred(test_user.id, org.id)
            db.session.commit()
            creds = CredentialService.list_credentials_metadata(test_user.id, org.id)
            assert len(creds) >= 1

    def test_unauthorized_user_raises_permission_error(self, app, test_user, other_user):
        with app.app_context():
            org = self._create_org(test_user.id)
            self._create_cred(test_user.id, org.id)
            db.session.commit()
            with pytest.raises(PermissionError):
                CredentialService.list_credentials_metadata(other_user.id, org.id)

    def test_user_from_other_org_cannot_access(self, app, test_user, other_user):
        with app.app_context():
            org_a = self._create_org(test_user.id)
            self._create_cred(test_user.id, org_a.id)
            org_b = Organization(
                name=f"Org B {other_user.id}",
                slug=f"org-b-{other_user.id}",
                owner_user_id=other_user.id,
                is_active=True,
            )
            db.session.add(org_b)
            db.session.flush()
            db.session.add(OrganizationMember(
                organization_id=org_b.id, user_id=other_user.id,
                org_role=ORG_ROLE_ADMIN, is_active=True,
            ))
            db.session.commit()
            with pytest.raises(PermissionError, match="not an authorized member"):
                CredentialService.list_credentials_metadata(other_user.id, org_a.id)

    def test_no_org_id_returns_own_credentials(self, app, test_user):
        with app.app_context():
            db.session.add(EncryptedCredential(
                name="Personal Cred", credential_type="api_key",
                encrypted_value="FAKE", owner_user_id=test_user.id, is_active=True,
            ))
            db.session.commit()
            creds = CredentialService.list_credentials_metadata(test_user.id, None)
            assert any(c["name"] == "Personal Cred" for c in creds)

    def test_nonexistent_org_raises_permission_error(self, app, test_user):
        with app.app_context():
            with pytest.raises(PermissionError):
                CredentialService.list_credentials_metadata(test_user.id, 99999)

    def test_credentials_api_returns_403(self, app, client, other_auth_headers, test_user):
        with app.app_context():
            org = self._create_org(test_user.id)
            db.session.commit()
            org_id = org.id
        resp = client.get(f"/api/v1/credentials?organization_id={org_id}", headers=other_auth_headers)
        assert resp.status_code == 403
