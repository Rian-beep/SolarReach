"""CrewAI hierarchical crew definition.

Process.hierarchical means the Manager (Opus 4.7) decides which specialist to
invoke for each task. async_execution=True on the specialist tasks lets them
run concurrently when the manager fans out.
"""
from __future__ import annotations

from crewai import Crew, Process, Task

from .agents import (
    make_google_engineer,
    make_manager,
    make_outreach_editor,
    make_pitch_deck_builder,
    make_tts_agent,
    manager_llm,
)


def build_crew(objective: str, target_lead_id: str | None = None) -> Crew:
    """Build a hierarchical crew for the given objective.

    The manager owns delegation. Specialists are passed as `agents`; we declare
    one umbrella Task that names the objective and lets the manager fan out.
    Specialist tasks (pitch / outreach / tts) are marked async so they can
    run concurrently when the manager dispatches them.
    """
    manager = make_manager()
    google_engineer = make_google_engineer()
    pitch_builder = make_pitch_deck_builder()
    outreach_editor = make_outreach_editor()
    tts_agent = make_tts_agent()

    specialists = [google_engineer, pitch_builder, outreach_editor, tts_agent]

    lead_clause = (
        f" Target lead id: {target_lead_id}." if target_lead_id else ""
    )

    # In hierarchical mode the manager owns delegation. Specialist async
    # fan-out happens inside the manager's reasoning loop (it picks the right
    # coworker for each sub-step) — CrewAI rejects multiple consecutive async
    # tasks at the top level, so we declare context-gathering tasks (sync) and
    # one terminal async aggregation step.

    ground_task = Task(
        description=(
            "Ground the swarm in Atlas data. Run atlas_vector_search and/or "
            "atlas_query for any leads/companies relevant to the objective. "
            "Return the raw context for downstream specialists."
        ),
        expected_output="Markdown summary of the grounding context (5-15 bullets).",
        agent=outreach_editor,
    )

    plan_task = Task(
        description=(
            f"Objective: {objective}.{lead_clause}\n\n"
            "Using the grounding context, decompose the objective into "
            "specialist sub-steps. For each sub-step name the specialist "
            "(GoogleEngineer / PitchDeckBuilder / OutreachEditor / "
            "ElevenLabsTTSAgent) and the expected artifact."
        ),
        expected_output="Numbered plan with one specialist per step.",
        agent=manager,
        context=[ground_task],
    )

    execute_task = Task(
        description=(
            "Execute the plan. Delegate each sub-step to the named specialist "
            "and aggregate their outputs. Pitch generation, outreach edits, "
            "and TTS all run via specialist tool calls — every paid call is "
            "audit-logged automatically."
        ),
        expected_output=(
            "Markdown summary covering (a) specialist actions, (b) artifact "
            "paths produced, (c) follow-ups."
        ),
        agent=manager,
        context=[plan_task],
        async_execution=True,
    )

    return Crew(
        agents=specialists,
        tasks=[ground_task, plan_task, execute_task],
        process=Process.hierarchical,
        manager_llm=manager_llm(),
        verbose=False,
    )
