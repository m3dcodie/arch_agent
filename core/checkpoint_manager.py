"""
CheckpointManager — time travel, replay, and fault-recovery for ADAG runs.

LangGraph saves a StateSnapshot (checkpoint) at every super-step boundary:

    step -1  → empty state, START queued
    step  0  → after intake
    step  1  → after policy_analyst
    step  2  → after auditor
    step  3  → after remediation   (only when violations found)

These checkpoints are stored in SQLite (./data/adag.db) and are keyed by the
``thread_id`` returned on every AuditResult.

Quick-start
-----------
    from core.checkpoint_manager import CheckpointManager
    from core.graph import create_graph

    graph  = create_graph()
    cm     = CheckpointManager(graph)

    # Inspect a completed run
    history = cm.history("a3f1-...")
    cm.print_history("a3f1-...")

    # Re-run from before the auditor node (step 1 = after policy_analyst)
    cm.replay_from_step("a3f1-...", step=1)

    # Resume a run that crashed after intake (step 0)
    cm.resume("a3f1-...")
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.graph import ADAGGraph

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Wraps an ADAGGraph to expose LangGraph's checkpoint API in a simple,
    ADAG-specific interface.

    All methods take a ``thread_id`` string — the value stored on
    ``AuditResult.thread_id`` after every ``runner.scan()`` call.

    Args:
        graph: An initialised ADAGGraph instance (from ``create_graph()``).
    """

    def __init__(self, graph: "ADAGGraph"):
        self._graph = graph

    # ------------------------------------------------------------------
    # Read-only inspection
    # ------------------------------------------------------------------

    def history(self, thread_id: str) -> list[dict]:
        """
        Return all checkpoints for a run, newest first.

        Each entry is a plain dict with:
            step           – super-step index (-1 is the input checkpoint)
            next           – tuple of node names still to execute  (empty = done)
            checkpoint_id  – LangGraph's checkpoint UUID (for replay_from_checkpoint)
            created_at     – ISO 8601 timestamp
            node_that_ran  – name of the last node that wrote this checkpoint
            status         – AuditStatus value at this point, or None
            violations     – number of violations at this point
            resources      – number of parsed resources at this point

        Args:
            thread_id: The thread_id from AuditResult.

        Returns:
            List of checkpoint dicts, newest first.
        """
        config = {"configurable": {"thread_id": thread_id}}
        result = []
        for snapshot in self._graph.graph.get_state_history(config):
            # Which node produced this checkpoint?
            writes = snapshot.metadata.get("writes") or {}
            node_that_ran = next(iter(writes), None)

            result.append({
                "step": snapshot.metadata.get("step"),
                "next": snapshot.next,
                "checkpoint_id": snapshot.config["configurable"].get("checkpoint_id"),
                "created_at": snapshot.created_at,
                "node_that_ran": node_that_ran,
                "status": (
                    snapshot.values.get("status").value
                    if snapshot.values.get("status") is not None
                    else None
                ),
                "violations": len(snapshot.values.get("violations") or []),
                "resources": len(snapshot.values.get("parsed_resources") or []),
            })
        return result

    def current_state(self, thread_id: str) -> dict:
        """
        Return the latest (most recent) state snapshot values for a run.

        Useful for inspecting a completed or crashed run without re-running it.

        Args:
            thread_id: The thread_id from AuditResult.

        Returns:
            The raw state dict (same shape as AgentState).
        """
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self._graph.graph.get_state(config)
        return dict(snapshot.values)

    def print_history(self, thread_id: str) -> None:
        """
        Pretty-print the checkpoint history to stdout.  Useful during
        debugging sessions — similar to the timeline view in LangSmith Studio.

        Args:
            thread_id: The thread_id from AuditResult.
        """
        rows = self.history(thread_id)
        print(f"\n{'='*60}")
        print(f"  Checkpoint history for thread: {thread_id}")
        print(f"{'='*60}")
        if not rows:
            print("  (no checkpoints found — thread_id may be wrong)")
            return
        for row in reversed(rows):          # show oldest → newest
            step      = row["step"]
            node      = row["node_that_ran"] or "__start__"
            next_     = ", ".join(row["next"]) if row["next"] else "END"
            status    = row["status"] or "—"
            viol      = row["violations"]
            ckpt_id   = (row["checkpoint_id"] or "")[:12]
            created   = (row["created_at"] or "")[:19]
            print(
                f"  step {step:>3} │ {node:<20} │ next={next_:<20} │ "
                f"status={status:<10} │ violations={viol} │ {created} │ ckpt={ckpt_id}"
            )
        print(f"{'='*60}\n")

    # ------------------------------------------------------------------
    # Replay and resume
    # ------------------------------------------------------------------

    def resume(self, thread_id: str) -> dict:
        """
        Resume a run that crashed or was interrupted before reaching END.

        LangGraph re-executes only the nodes that had not yet completed.
        Nodes whose writes were already saved (pending writes) are skipped.

        If the run already reached END, the existing final state is returned
        without any LLM calls being made.

        Args:
            thread_id: The thread_id from the crashed AuditResult.

        Returns:
            Final state dict (same shape as graph.invoke() return value).
        """
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self._graph.graph.get_state(config)

        if not snapshot.next:
            logger.info(
                "thread=%s already complete — returning saved final state", thread_id
            )
            raw = dict(snapshot.values)
            raw["_thread_id"] = thread_id
            return raw

        logger.info(
            "Resuming thread=%s from step=%s, next=%s",
            thread_id,
            snapshot.metadata.get("step"),
            snapshot.next,
        )
        # Passing None as state means "use the checkpoint's persisted state"
        raw = self._graph.graph.invoke(None, config)
        raw["_thread_id"] = thread_id
        return raw

    def replay_from_step(self, thread_id: str, step: int) -> dict:
        """
        Replay a run starting from a specific super-step.

        Nodes that ran BEFORE ``step`` are not re-executed — their state is
        loaded from SQLite.  Nodes at ``step`` and after re-execute, including
        all LLM calls.  The result is saved as a new fork in the same thread.

        Example: replay from step=1 (after policy_analyst) to re-run the
        auditor with different policies without re-parsing the Terraform.

        Args:
            thread_id: The thread_id from AuditResult.
            step:      The super-step to restart from (inclusive).
                       Use history() to see available steps.

        Returns:
            Final state dict after the replayed execution.

        Raises:
            ValueError: If no checkpoint exists at the requested step.
        """
        config = {"configurable": {"thread_id": thread_id}}
        all_snapshots = list(self._graph.graph.get_state_history(config))

        target = next(
            (s for s in all_snapshots if s.metadata.get("step") == step),
            None,
        )
        if target is None:
            available = [s.metadata.get("step") for s in all_snapshots]
            raise ValueError(
                f"No checkpoint at step={step} for thread={thread_id}. "
                f"Available steps: {sorted(available)}"
            )

        logger.info(
            "Replaying thread=%s from step=%s (checkpoint=%s)",
            thread_id,
            step,
            target.config["configurable"].get("checkpoint_id", "")[:12],
        )
        raw = self._graph.graph.invoke(None, target.config)
        raw["_thread_id"] = thread_id
        return raw

    def replay_from_checkpoint(self, thread_id: str, checkpoint_id: str) -> dict:
        """
        Replay from an exact checkpoint ID (more precise than step number).

        Use this when two checkpoints share the same step (e.g., after
        update_state() creates a fork) and you need to target a specific one.

        Args:
            thread_id:     The thread_id from AuditResult.
            checkpoint_id: The checkpoint_id from history().

        Returns:
            Final state dict after the replayed execution.
        """
        config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        logger.info(
            "Replaying thread=%s from checkpoint=%s", thread_id, checkpoint_id[:12]
        )
        raw = self._graph.graph.invoke(None, config)
        raw["_thread_id"] = thread_id
        return raw

    def inject_and_replay(
        self,
        thread_id: str,
        step: int,
        state_patch: dict[str, Any],
        as_node: str | None = None,
    ) -> dict:
        """
        Patch state at a given step and replay from there.

        This is LangGraph's ``update_state()`` + replay combo — the equivalent
        of editing a step in AWS Step Functions and re-running.  A new fork
        checkpoint is written; the original checkpoints are not modified.

        Example: re-run the auditor with corrected policies injected:

            cm.inject_and_replay(
                thread_id="a3f1-...",
                step=1,                          # after policy_analyst
                state_patch={"retrieved_policies": [fixed_policy]},
                as_node="policy_analyst",        # treat the patch as if policy_analyst wrote it
            )

        Args:
            thread_id:   The thread_id from AuditResult.
            step:        The super-step to patch (use history() to find it).
            state_patch: Dict of state keys to override.
            as_node:     Treat the update as coming from this node name.
                         Controls which node runs next.

        Returns:
            Final state dict after the forked execution.

        Raises:
            ValueError: If no checkpoint exists at the requested step.
        """
        config = {"configurable": {"thread_id": thread_id}}
        all_snapshots = list(self._graph.graph.get_state_history(config))

        target = next(
            (s for s in all_snapshots if s.metadata.get("step") == step),
            None,
        )
        if target is None:
            available = [s.metadata.get("step") for s in all_snapshots]
            raise ValueError(
                f"No checkpoint at step={step} for thread={thread_id}. "
                f"Available steps: {sorted(available)}"
            )

        # update_state writes a new "fork" checkpoint and returns its config
        fork_config = self._graph.graph.update_state(
            target.config,
            state_patch,
            as_node=as_node,
        )
        logger.info(
            "Injected state patch at step=%s for thread=%s, replaying fork",
            step,
            thread_id,
        )
        raw = self._graph.graph.invoke(None, fork_config)
        raw["_thread_id"] = thread_id
        return raw
