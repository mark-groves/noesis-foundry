"""Context selection, freshness policy, provenance, and rendering."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from .retrieval import rank_notes, tokenize
from .vault import (
    CONTEXT_PROFILE_NAMES,
    CONTEXT_PROFILES,
    FRESHNESS_POLICIES,
    ContextHandoffGuidance,
    ContextLineageSummary,
    ContextPackage,
    ContextProfile,
    ContextSelection,
    Note,
    Vault,
    as_list,
    extract_wikilinks,
    file_content_hash,
    is_excluded,
    parse_review_date,
    searchable_note_text,
)


def build_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
) -> str:
    return compose_context(
        vault,
        scope=scope,
        purpose=purpose,
        limit=limit,
        max_chars=max_chars,
        profile=profile,
        as_of=as_of,
        freshness_policy=freshness_policy,
    ).content


def compose_context(
    vault: Vault,
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
) -> ContextPackage:
    validation_issues = vault.validate()
    if validation_issues:
        formatted = "; ".join(issue.format(vault.root) for issue in validation_issues[:3])
        remaining = len(validation_issues) - 3
        if remaining > 0:
            formatted += f"; and {remaining} more issue(s)"
        raise ValueError(f"cannot build context from invalid vault: {formatted}")
    validate_context_budget(limit=limit, max_chars=max_chars)
    cutoff = context_as_of_date(as_of)
    normalized_freshness_policy = resolve_freshness_policy(freshness_policy)
    profile_definition = resolve_context_profile(profile)
    effective_limit, effective_max_chars, applied_profile_defaults = apply_context_profile_defaults(
        profile_definition,
        limit=limit,
        max_chars=max_chars,
    )
    validate_context_budget(limit=effective_limit, max_chars=effective_max_chars)
    available = vault.current_reviewed_knowledge()
    freshness_eligible, freshness_excluded = apply_context_freshness(
        available,
        as_of=cutoff,
        policy=normalized_freshness_policy,
    )
    selected, scoped_out = select_knowledge_for_context(
        freshness_eligible,
        scope,
        as_of=cutoff,
        profile=profile_definition,
        applied_profile_defaults=applied_profile_defaults,
    )
    included, budgeted_out = apply_context_budget(
        selected,
        limit=effective_limit,
        max_chars=effective_max_chars,
    )
    excluded = sorted(
        freshness_excluded + scoped_out + budgeted_out,
        key=lambda selection: (selection.status, selection.note.title.lower()),
    )
    selection_excluded = sorted(
        scoped_out + budgeted_out,
        key=lambda selection: (selection.status, selection.note.title.lower()),
    )
    lifecycle_excluded = explain_lifecycle_exclusions(vault)
    lineage_summaries = [context_lineage_summary(vault, selection.note) for selection in included]
    handoff = context_handoff_guidance(
        vault_path=vault.root,
        scope=scope,
        purpose=purpose,
        profile=profile_definition,
        limit=effective_limit,
        max_chars=effective_max_chars,
        as_of=cutoff,
        freshness_policy=normalized_freshness_policy,
        included=included,
        excluded=excluded,
        lifecycle_excluded=lifecycle_excluded,
    )
    if is_handoff_profile(profile_definition):
        content = render_context_handoff(
            included,
            lineage_summaries,
            lifecycle_excluded,
            handoff,
            scope=scope,
            profile=profile_definition,
            limit=effective_limit,
            max_chars=effective_max_chars,
            total_candidates=len(available),
            excluded=selection_excluded,
            as_of=cutoff,
            freshness_policy=normalized_freshness_policy,
            freshness_excluded=freshness_excluded,
        )
    else:
        content = render_context(
            [selection.note for selection in included],
            scope=scope,
            purpose=purpose,
            profile=profile_definition,
            limit=effective_limit,
            max_chars=effective_max_chars,
            total_candidates=len(available),
            excluded=selection_excluded,
            as_of=cutoff,
            freshness_policy=normalized_freshness_policy,
            freshness_excluded=freshness_excluded,
        )
    return ContextPackage(
        profile=profile_definition.name if profile_definition else None,
        profile_description=profile_definition.description if profile_definition else None,
        scope=scope,
        purpose=purpose,
        as_of=cutoff.isoformat(),
        freshness_policy=normalized_freshness_policy,
        input_hashes=tuple(note_input_hash(selection.note) for selection in included),
        limit=effective_limit,
        max_chars=effective_max_chars,
        requested_limit=limit,
        requested_max_chars=max_chars,
        applied_profile_defaults=applied_profile_defaults,
        available_count=len(available),
        included=included,
        excluded=excluded,
        scoped_out=scoped_out,
        budgeted_out=budgeted_out,
        freshness_excluded=freshness_excluded,
        lifecycle_excluded=lifecycle_excluded,
        lineage_summaries=lineage_summaries,
        handoff=handoff,
        content=content,
    )


def render_context_snapshot(
    vault: Vault,
    knowledge: list[Note],
    scope: str | None = None,
    purpose: str | None = None,
    *,
    limit: int | None = None,
    max_chars: int | None = None,
    profile: str | None = None,
    as_of: str | date | None = None,
    freshness_policy: str = "balanced",
) -> str:
    """Re-render an already selected context while preserving its stored presentation contract."""
    validate_context_budget(limit=limit, max_chars=max_chars)
    cutoff = context_as_of_date(as_of)
    normalized_freshness_policy = resolve_freshness_policy(freshness_policy)
    profile_definition = resolve_context_profile(profile)
    included: list[ContextSelection] = []
    for note in knowledge:
        freshness_state, review_due_on, valid_until = note_freshness(note, as_of=cutoff)
        included.append(
            ContextSelection(
                note=note,
                status="included",
                reason="retained from the stored operational context after a lifecycle update",
                score=0,
                content_chars=len(note.body.strip()),
                freshness_state=freshness_state,
                review_due_on=review_due_on.isoformat() if review_due_on else None,
                valid_until=valid_until.isoformat() if valid_until else None,
            )
        )

    if not is_handoff_profile(profile_definition):
        return render_context(
            knowledge,
            scope=scope,
            purpose=purpose,
            profile=profile_definition,
            limit=limit,
            max_chars=max_chars,
            total_candidates=len(knowledge),
            as_of=cutoff,
            freshness_policy=normalized_freshness_policy,
        )

    lifecycle_excluded = explain_lifecycle_exclusions(vault)
    lineage_summaries = [context_lineage_summary(vault, selection.note) for selection in included]
    handoff = context_handoff_guidance(
        vault_path=vault.root,
        scope=scope,
        purpose=purpose,
        profile=profile_definition,
        limit=limit,
        max_chars=max_chars,
        as_of=cutoff,
        freshness_policy=normalized_freshness_policy,
        included=included,
        excluded=[],
        lifecycle_excluded=lifecycle_excluded,
    )
    return render_context_handoff(
        included,
        lineage_summaries,
        lifecycle_excluded,
        handoff,
        scope=scope,
        profile=profile_definition,
        limit=limit,
        max_chars=max_chars,
        total_candidates=len(knowledge),
        excluded=[],
        as_of=cutoff,
        freshness_policy=normalized_freshness_policy,
        freshness_excluded=[],
    )


def is_handoff_profile(profile: ContextProfile | None) -> bool:
    return profile is not None and profile.name in {"agent-handoff", "codex-handoff"}


def validate_context_budget(*, limit: int | None = None, max_chars: int | None = None) -> None:
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than zero")
    if max_chars is not None and max_chars < 1:
        raise ValueError("max_chars must be greater than zero")


def context_as_of_date(value: str | date | None) -> date:
    if value is None:
        return date.today()
    if isinstance(value, datetime):
        raise ValueError("as_of must be YYYY-MM-DD")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("as_of must be YYYY-MM-DD")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("as_of must be YYYY-MM-DD") from exc


def resolve_freshness_policy(value: str | None) -> str:
    normalized = str(value or "balanced").strip().lower()
    if normalized not in FRESHNESS_POLICIES:
        expected = ", ".join(sorted(FRESHNESS_POLICIES))
        raise ValueError(f"freshness_policy must be one of: {expected}")
    return normalized


def note_freshness(note: Note, *, as_of: date) -> tuple[str, date | None, date | None]:
    review_due_on = parse_review_date(note.metadata.get("next_review"))
    valid_until = parse_review_date(note.metadata.get("valid_until"))
    if valid_until is not None and as_of > valid_until:
        state = "expired"
    elif review_due_on is not None and review_due_on <= as_of:
        state = "review-due"
    elif review_due_on is None and valid_until is None:
        state = "unscheduled"
    else:
        state = "fresh"
    return state, review_due_on, valid_until


def context_freshness_eligible(state: str, *, policy: str) -> bool:
    if state == "expired":
        return False
    if policy == "strict" and state == "review-due":
        return False
    return True


def apply_context_freshness(
    knowledge: list[Note],
    *,
    as_of: date,
    policy: str,
) -> tuple[list[Note], list[ContextSelection]]:
    eligible: list[Note] = []
    excluded: list[ContextSelection] = []
    for note in knowledge:
        state, review_due_on, valid_until = note_freshness(note, as_of=as_of)
        if context_freshness_eligible(state, policy=policy):
            eligible.append(note)
            continue
        if state == "expired":
            reason = f"expired after valid_until {valid_until.isoformat()} as of {as_of.isoformat()}"
        else:
            reason = (
                f"review was due on {review_due_on.isoformat()} as of {as_of.isoformat()} "
                "and strict freshness excludes review-due knowledge"
            )
        excluded.append(
            ContextSelection(
                note=note,
                status="freshness_excluded",
                reason=reason,
                score=0,
                content_chars=len(note.body.strip()),
                freshness_state=state,
                review_due_on=review_due_on.isoformat() if review_due_on else None,
                valid_until=valid_until.isoformat() if valid_until else None,
            )
        )
    return eligible, sorted(excluded, key=lambda selection: selection.note.title.lower())


def note_input_hash(note: Note) -> str:
    return f"{note.noesis_id}={file_content_hash(note.path)}"


def resolve_context_profile(profile: str | None) -> ContextProfile | None:
    if profile is None or not profile.strip():
        return None
    key = profile.strip().lower()
    profile_definition = CONTEXT_PROFILES.get(key)
    if profile_definition is None:
        expected = ", ".join(sorted(CONTEXT_PROFILE_NAMES))
        raise ValueError(f"profile must be one of: {expected}")
    return profile_definition


def apply_context_profile_defaults(
    profile: ContextProfile | None,
    *,
    limit: int | None,
    max_chars: int | None,
) -> tuple[int | None, int | None, tuple[str, ...]]:
    if profile is None:
        return limit, max_chars, ()
    applied: list[str] = []
    effective_limit = limit
    effective_max_chars = max_chars
    if effective_limit is None and profile.default_limit is not None:
        effective_limit = profile.default_limit
        applied.append("limit")
    if effective_max_chars is None and profile.default_max_chars is not None:
        effective_max_chars = profile.default_max_chars
        applied.append("max_chars")
    return effective_limit, effective_max_chars, tuple(applied)


def select_knowledge_for_context(
    knowledge: list[Note],
    scope: str | None,
    *,
    as_of: date | None = None,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> tuple[list[ContextSelection], list[ContextSelection]]:
    scope_terms = context_scope_terms(scope)
    ranked_hits = rank_notes(knowledge, scope)
    scores = {hit.note.noesis_id: hit.score for hit in ranked_hits}
    selected: list[ContextSelection] = []
    scoped_out: list[ContextSelection] = []
    cutoff = as_of or date.today()
    for note in knowledge:
        score = scores.get(note.noesis_id, 0.0)
        freshness_state, review_due_on, valid_until = note_freshness(note, as_of=cutoff)
        selection = ContextSelection(
            note=note,
            status="included",
            reason=context_include_reason(scope, score, profile, applied_profile_defaults),
            score=score,
            content_chars=len(note.body.strip()),
            freshness_state=freshness_state,
            review_due_on=review_due_on.isoformat() if review_due_on else None,
            valid_until=valid_until.isoformat() if valid_until else None,
        )
        if scope_terms and score == 0:
            scoped_out.append(
                ContextSelection(
                    note=note,
                    status="scoped_out",
                    reason=context_scoped_out_reason(scope, profile, applied_profile_defaults),
                    score=score,
                    content_chars=selection.content_chars,
                    freshness_state=freshness_state,
                    review_due_on=selection.review_due_on,
                    valid_until=selection.valid_until,
                )
            )
        else:
            selected.append(selection)
    selected.sort(key=lambda selection: (-selection.score, selection.note.title.lower()))
    return selected, scoped_out


def apply_context_budget(
    selections: list[ContextSelection],
    *,
    limit: int | None = None,
    max_chars: int | None = None,
) -> tuple[list[ContextSelection], list[ContextSelection]]:
    included: list[ContextSelection] = []
    budgeted_out: list[ContextSelection] = []
    used_chars = 0
    for index, selection in enumerate(selections):
        if limit is not None and len(included) >= limit:
            budgeted_out.extend(
                ContextSelection(
                    note=remaining.note,
                    status="budgeted_out",
                    reason=f"excluded by limit {limit}",
                    score=remaining.score,
                    content_chars=remaining.content_chars,
                    freshness_state=remaining.freshness_state,
                    review_due_on=remaining.review_due_on,
                    valid_until=remaining.valid_until,
                )
                for remaining in selections[index:]
            )
            break
        if max_chars is not None and used_chars + selection.content_chars > max_chars:
            remaining_chars = max(max_chars - used_chars, 0)
            budgeted_out.append(
                ContextSelection(
                    note=selection.note,
                    status="budgeted_out",
                    reason=(
                        f"excluded by max_chars {max_chars}: "
                        f"{selection.content_chars} chars exceeds remaining budget {remaining_chars}"
                    ),
                    score=selection.score,
                    content_chars=selection.content_chars,
                    freshness_state=selection.freshness_state,
                    review_due_on=selection.review_due_on,
                    valid_until=selection.valid_until,
                )
            )
            continue
        included.append(selection)
        used_chars += selection.content_chars
    return included, budgeted_out


def context_scope_terms(scope: str | None) -> list[str]:
    if scope is None or not scope.strip():
        return []
    return tokenize(scope)


def context_scope_score(note: Note, scope_terms: list[str]) -> int:
    if not scope_terms:
        return 0
    searchable_terms = set(tokenize(searchable_note_text(note)))
    return sum(1 for term in scope_terms if term in searchable_terms)


def context_include_reason(
    scope: str | None,
    score: int,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    if scope is None or not scope.strip():
        reason = "included because no scope filter was requested"
    else:
        reason = f"matches scope {scope!r} with score {score}"
    reason += context_profile_reason_suffix(profile, applied_profile_defaults)
    return reason


def context_scoped_out_reason(
    scope: str | None,
    profile: ContextProfile | None = None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    reason = f"does not match scope {scope!r}"
    reason += context_profile_reason_suffix(profile, applied_profile_defaults)
    return reason


def context_profile_reason_suffix(
    profile: ContextProfile | None,
    applied_profile_defaults: tuple[str, ...] = (),
) -> str:
    if profile is None:
        return ""
    if applied_profile_defaults:
        defaults = ", ".join(applied_profile_defaults)
        return f"; profile {profile.name!r} supplied context defaults: {defaults}"
    return f"; profile {profile.name!r} selected with explicit context budgets"


def explain_lifecycle_exclusions(vault: Vault) -> list[ContextSelection]:
    selections: list[ContextSelection] = []
    for note in vault.notes:
        if not is_excluded(note):
            continue
        selections.append(
            ContextSelection(
                note=note,
                status="lifecycle_excluded",
                reason=(
                    f"{note.type} has status {note.status!r} "
                    f"and lifecycle_stage {note.lifecycle_stage!r}; "
                    f"intentionally excluded as {context_lifecycle_exclusion_kind(note)} note"
                ),
                score=0,
                content_chars=len(note.body.strip()),
            )
        )
    return sorted(selections, key=lambda selection: selection.note.title.lower())


def context_lifecycle_exclusion_kind(note: Note) -> str:
    if note.lifecycle_stage == "archive" or note.status == "archived":
        return "archived"
    if note.status == "superseded":
        return "superseded"
    if note.status == "stale":
        return "stale"
    return "excluded"


def context_lineage_summary(vault: Vault, note: Note) -> ContextLineageSummary:
    return ContextLineageSummary(
        reviewed_knowledge=note,
        sources=context_relationship_notes(vault, note, "sources", expected_type="source"),
        evidence=context_relationship_notes(vault, note, "evidence", expected_type="evidence"),
        claims=context_relationship_notes(vault, note, "claims", expected_type="claim"),
        syntheses=context_relationship_notes(vault, note, "syntheses", expected_type="synthesis"),
        reviews=context_relationship_notes(vault, note, "reviewed_by", expected_type="review"),
    )


def context_relationship_notes(
    vault: Vault,
    note: Note,
    key: str,
    *,
    expected_type: str | None = None,
) -> list[Note]:
    notes_by_id: dict[str, Note] = {}
    for item in as_list(note.metadata.get(key)):
        if not isinstance(item, str):
            continue
        for target in extract_wikilinks(item):
            target_note = vault.find_note(target)
            if target_note is None:
                continue
            if expected_type is not None and target_note.type != expected_type:
                continue
            notes_by_id[target_note.noesis_id] = target_note
    return sorted(notes_by_id.values(), key=lambda item: item.rel_path.as_posix())


def context_handoff_guidance(
    *,
    vault_path: Path,
    scope: str | None,
    purpose: str | None,
    profile: ContextProfile | None,
    limit: int | None,
    max_chars: int | None,
    as_of: date,
    freshness_policy: str,
    included: list[ContextSelection],
    excluded: list[ContextSelection],
    lifecycle_excluded: list[ContextSelection],
) -> ContextHandoffGuidance:
    vault_flag = f" --vault {shell_quote(str(vault_path))}"
    scope_flag = f" --scope {shell_quote(scope)}" if scope else ""
    purpose_flag = f" --purpose {shell_quote(purpose)}" if purpose else ""
    profile_flag = f" --profile {profile.name}" if profile is not None else ""
    limit_flag = f" --limit {limit}" if limit is not None else ""
    max_chars_flag = f" --max-chars {max_chars}" if max_chars is not None else ""
    freshness_flags = f" --as-of {as_of.isoformat()} --freshness-policy {freshness_policy}"
    task_purpose = purpose or "Continue the task using the selected current reviewed knowledge."
    assumptions = [
        "Active guidance is limited to current reviewed knowledge selected for this package.",
        (
            "Stale, superseded, and archived notes are exclusion provenance only "
            "and must not be treated as active instructions."
        ),
        "Noesis handoff output is harness-agnostic; Codex is one adapter for dogfood runs.",
        f"Freshness was evaluated as of {as_of.isoformat()} using the {freshness_policy!r} policy.",
    ]
    if scope:
        assumptions.append(
            f"The requested scope is {scope!r}; "
            "scoped-out reviewed notes need a separate handoff if they matter."
        )
    if excluded:
        assumptions.append(
            "Some current reviewed notes were omitted by scope or budget; "
            "inspect selection provenance before widening work."
        )
    if lifecycle_excluded:
        assumptions.append(
            "Lifecycle-excluded memory remains traceable for audit but is excluded from active context."
        )
    if any(selection.freshness_state == "review-due" for selection in included):
        assumptions.append(
            "Review-due knowledge is included with an explicit warning under the balanced freshness policy."
        )
    if any(selection.status == "freshness_excluded" for selection in excluded):
        assumptions.append("Expired or policy-excluded knowledge must not be treated as active guidance.")

    validation_commands = [
        "git diff --check",
        f"PYTHONPATH=src python -m noesis vault doctor {shell_quote(str(vault_path))} --json",
        (
            "PYTHONPATH=src python -m noesis context build"
            f"{vault_flag}"
            f"{scope_flag}{purpose_flag}{profile_flag}{limit_flag}{max_chars_flag}{freshness_flags} --json"
        ),
        (
            "PYTHONPATH=src python -m noesis context explain"
            f"{vault_flag}"
            f"{scope_flag}{purpose_flag}{profile_flag}{limit_flag}{max_chars_flag}{freshness_flags} --json"
        ),
        "PYTHONPATH=src python -m unittest discover -s tests -v",
    ]
    next_steps = [
        "Use the selected reviewed knowledge as the active task brief.",
        "Check the lineage summaries before changing source-backed claims or syntheses.",
        "Keep lifecycle-excluded notes out of active guidance unless they are renewed through review.",
        "Run the validation commands before handing work back.",
    ]
    if included:
        selected = ", ".join(selection.note.noesis_id for selection in included)
        next_steps.insert(1, f"Start from selected reviewed knowledge: {selected}.")
    return ContextHandoffGuidance(
        task_purpose=task_purpose,
        assumptions=assumptions,
        validation_commands=validation_commands,
        next_steps=next_steps,
    )


def shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def context_lifecycle_exclusion_counts(selections: list[ContextSelection]) -> dict[str, int]:
    summary = {"stale": 0, "superseded": 0, "archived": 0, "excluded": 0}
    for selection in selections:
        kind = context_lifecycle_exclusion_kind(selection.note)
        summary[kind] = summary.get(kind, 0) + 1
    return summary


def render_context_handoff(
    included: list[ContextSelection],
    lineage_summaries: list[ContextLineageSummary],
    lifecycle_excluded: list[ContextSelection],
    handoff: ContextHandoffGuidance,
    *,
    scope: str | None = None,
    profile: ContextProfile | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    total_candidates: int | None = None,
    excluded: list[ContextSelection] | None = None,
    as_of: date | None = None,
    freshness_policy: str = "balanced",
    freshness_excluded: list[ContextSelection] | None = None,
) -> str:
    title = "Noesis Codex Handoff Pack" if profile and profile.name == "codex-handoff" else "Noesis Agent Handoff Pack"
    lines = [f"# {title}", ""]
    if scope:
        lines.extend([f"Scope: {scope}", ""])
    lines.extend([f"Purpose: {handoff.task_purpose}", ""])
    lines.extend(
        [
            f"As of: {(as_of or date.today()).isoformat()}",
            f"Freshness policy: {freshness_policy}",
            "",
        ]
    )
    if profile is not None:
        lines.extend([f"Profile: {profile.name}", ""])
    if limit is not None or max_chars is not None:
        budget = []
        if limit is not None:
            budget.append(f"limit {limit}")
        if max_chars is not None:
            budget.append(f"max_chars {max_chars}")
        lines.extend([f"Budget: {', '.join(budget)}", ""])
    lines.extend(
        [
            "Active guidance in this pack is built from current reviewed knowledge only.",
            "Expired knowledge is excluded; review-due knowledge is visibly marked by the selected freshness policy.",
            "Stale, superseded, and archived memory is listed only as excluded provenance.",
            "The handoff contract is Markdown plus flat YAML; harness-specific launchers are adapters.",
            "",
            "## Task Purpose",
            "",
            handoff.task_purpose,
            "",
            "## Active Reviewed Knowledge",
            "",
        ]
    )
    if included:
        for selection in included:
            note = selection.note
            lines.extend(
                [
                    f"### {note.title}",
                    "",
                    f"- noesis_id: {note.noesis_id}",
                    f"- path: {note.rel_path.as_posix()}",
                    f"- confidence: {note.metadata.get('confidence', 'unknown')}",
                    f"- reviewed_at: {note.metadata.get('reviewed_at', 'unknown')}",
                    f"- selection_reason: {selection.reason}",
                    "",
                    note.body.strip(),
                    "",
                ]
            )
    else:
        lines.extend(["No current reviewed knowledge selected.", ""])

    lines.extend(["## Selection Provenance", ""])
    available_count = total_candidates if total_candidates is not None else len(included)
    lines.append(f"- Current reviewed knowledge available: {available_count}")
    lines.append(f"- Included in active handoff: {len(included)}")
    lines.append(f"- Excluded by scope or budget: {len(excluded or [])}")
    lines.append(f"- Excluded by freshness: {len(freshness_excluded or [])}")
    lines.append("")
    for selection in included:
        lines.append(format_handoff_selection(selection))
    if excluded:
        for selection in excluded:
            lines.append(format_handoff_selection(selection))
    if not included and not excluded:
        lines.append("No selection provenance available.")

    lines.extend(["", "## Freshness-Excluded Reviewed Knowledge", ""])
    if freshness_excluded:
        for selection in freshness_excluded:
            lines.append(format_handoff_selection(selection))
    else:
        lines.append("No reviewed knowledge was excluded by freshness.")

    scoped_out = [selection for selection in excluded or [] if selection.status == "scoped_out"]
    budgeted_out = [selection for selection in excluded or [] if selection.status == "budgeted_out"]
    lines.extend(["", "## Scoped-Out Reviewed Knowledge", ""])
    if scoped_out:
        for selection in scoped_out:
            lines.append(format_handoff_selection(selection))
    else:
        lines.append("No current reviewed knowledge was scoped out.")

    lines.extend(["", "## Budgeted-Out Reviewed Knowledge", ""])
    if budgeted_out:
        for selection in budgeted_out:
            lines.append(format_handoff_selection(selection))
    else:
        lines.append("No current reviewed knowledge was budgeted out.")

    lines.extend(["", "## Relevant Lineage", ""])
    if lineage_summaries:
        for summary in lineage_summaries:
            lines.append(format_handoff_lineage(summary))
    else:
        lines.append("No included reviewed knowledge lineage to summarize.")

    lines.extend(["", "## Lifecycle Exclusions", ""])
    summary = context_lifecycle_exclusion_counts(lifecycle_excluded)
    lines.append(
        "Summary: "
        f"stale={summary['stale']}, "
        f"superseded={summary['superseded']}, "
        f"archived={summary['archived']}, "
        f"other={summary['excluded']}"
    )
    lines.append("")
    if lifecycle_excluded:
        for selection in lifecycle_excluded:
            lines.append(format_handoff_selection(selection))
    else:
        lines.append("No stale, superseded, or archived reviewed memory found.")

    lines.extend(["", "## Assumptions", ""])
    lines.extend(f"- {assumption}" for assumption in handoff.assumptions)
    lines.extend(["", "## Validation Commands", ""])
    lines.extend(f"- `{command}`" for command in handoff.validation_commands)
    lines.extend(["", "## Next Steps", ""])
    lines.extend(f"- {step}" for step in handoff.next_steps)
    return "\n".join(lines).rstrip() + "\n"


def format_handoff_selection(selection: ContextSelection) -> str:
    suffix = ""
    if selection.status == "lifecycle_excluded":
        suffix = f", kind={context_lifecycle_exclusion_kind(selection.note)}"
    return (
        f"- {selection.note.noesis_id} ({selection.status}{suffix}, freshness={selection.freshness_state}, score={selection.score}, "
        f"chars={selection.content_chars}) - {selection.reason}; path: {selection.note.rel_path.as_posix()}"
    )


def format_handoff_lineage(summary: ContextLineageSummary) -> str:
    parts = [
        f"sources={format_handoff_note_ids(summary.sources)}",
        f"evidence={format_handoff_note_ids(summary.evidence)}",
        f"claims={format_handoff_note_ids(summary.claims)}",
        f"syntheses={format_handoff_note_ids(summary.syntheses)}",
        f"reviews={format_handoff_note_ids(summary.reviews)}",
    ]
    return f"- {summary.reviewed_knowledge.noesis_id}: " + "; ".join(parts)


def format_handoff_note_ids(notes: list[Note]) -> str:
    return ", ".join(note.noesis_id for note in notes) if notes else "none"


def render_context(
    knowledge: list[Note],
    scope: str | None = None,
    purpose: str | None = None,
    *,
    profile: ContextProfile | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
    total_candidates: int | None = None,
    excluded: list[ContextSelection] | None = None,
    as_of: date | None = None,
    freshness_policy: str = "balanced",
    freshness_excluded: list[ContextSelection] | None = None,
) -> str:
    title = "Noesis Operational Context"
    lines = [f"# {title}", ""]
    if scope:
        lines.extend([f"Scope: {scope}", ""])
    if purpose:
        lines.extend([f"Purpose: {purpose}", ""])
    lines.extend(
        [
            f"As of: {(as_of or date.today()).isoformat()}",
            f"Freshness policy: {freshness_policy}",
            "",
        ]
    )
    if profile is not None:
        lines.extend([f"Profile: {profile.name}", ""])
    if limit is not None or max_chars is not None:
        budget = []
        if limit is not None:
            budget.append(f"limit {limit}")
        if max_chars is not None:
            budget.append(f"max_chars {max_chars}")
        lines.extend([f"Budget: {', '.join(budget)}", ""])
    lines.extend(
        [
            "This context package is built from reviewed knowledge only.",
            "Stale, superseded, archived, and expired memory is excluded.",
            "Review-due knowledge is explicitly marked and is excluded when strict freshness is requested.",
            "",
        ]
    )

    if total_candidates is not None or excluded:
        lines.extend(["## Selection Summary", ""])
        lines.append(f"- Current reviewed knowledge available: {total_candidates if total_candidates is not None else len(knowledge)}")
        lines.append(f"- Included in active context: {len(knowledge)}")
        if excluded:
            lines.append(f"- Excluded by scope or budget: {len(excluded)}")
        lines.append(f"- Excluded by freshness: {len(freshness_excluded or [])}")
        lines.append("")

    if not knowledge:
        lines.extend(["## Reviewed Knowledge", "", "No current reviewed knowledge found.", ""])
        return "\n".join(lines)

    lines.extend(["## Reviewed Knowledge", ""])
    for note in knowledge:
        lines.extend(
            [
                f"### {note.title}",
                "",
                f"- noesis_id: {note.noesis_id}",
                f"- path: {note.rel_path.as_posix()}",
                f"- confidence: {note.metadata.get('confidence', 'unknown')}",
                f"- reviewed_at: {note.metadata.get('reviewed_at', 'unknown')}",
                f"- freshness: {note_freshness(note, as_of=as_of or date.today())[0]}",
                "",
                note.body.strip(),
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"
