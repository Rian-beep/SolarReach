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

    primary_task = Task(
        description=(
            f"Objective: {objective}.{lead_clause}\n\n"
            "1. Ground yourself in Atlas data via atlas_vector_search before "
            "delegating.\n"
            "2. Decompose into sub-tasks and delegate to the right specialist.\n"
            "3. Aggregate results into a single summary."
        ),
        expected_output=(
            "A markdown summary covering: (a) what each specialist did, "
            "(b) any artifact paths produced, (c) follow-ups."
        ),
        agent=manager,
    )

    pitch_task = Task(
        description=(
            "If the objective requires a pitch deck, generate one for the "
            "target lead using Atlas context + build_pptx. Otherwise skip."
        ),
        expected_output="Deck path or 'skipped'.",
        agent=pitch_builder,
        async_execution=True,
    )

    outreach_task = Task(
        description=(
            "Read the target lead (and any related companies/directors) from "
            "Atlas and produce a one-line outreach summary."
        ),
        expected_output="One-line outreach summary.",
        agent=outreach_editor,
        async_execution=True,
    )

    tts_task = Task(
        description=(
            "If text-to-speech is requested, render an mp3 using elevenlabs_tts. "
            "Otherwise skip."
        ),
        expected_output="MP3 path or 'skipped'.",
        agent=tts_agent,
        async_execution=True,
    )

    return Crew(
        agents=specialists,
        tasks=[primary_task, pitch_task, outreach_task, tts_task],
        process=Process.hierarchical,
        manager_llm=manager_llm(),
        verbose=False,
    )
