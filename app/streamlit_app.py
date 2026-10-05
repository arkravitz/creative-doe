"""A local creative-experiment workspace. Run: streamlit run app/streamlit_app.py."""

import html
import json
import re
from pathlib import Path

import streamlit as st

from creative_doe import Experiment, Metric, Status
from creative_doe.design.matrix import Encoder
from creative_doe.scheduler import Constraints

ROOT = Path(__file__).resolve().parents[1]
PAGES = ["Overview", "Creative choices", "Next posts", "Results", "Insights"]
STATUS_LABELS = {
    "PROPOSED": "Idea",
    "SCREENING": "Exploring",
    "ACTIVE": "Active",
    "RETIRED": "Paused",
}
METRIC_NAMES = {"hold_rate": "3-second hold rate", "views": "Views", "shares": "Share rate"}

st.set_page_config(
    page_title="Creative DOE · Your creative workspace", page_icon="✳", layout="wide"
)
st.html(f"<style>{(ROOT / 'app/style.css').read_text()}</style>")


def esc(value):
    return html.escape(str(value))


def pretty(value):
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    if value is None:
        return "Not recorded"
    return str(value).replace("_", " ").capitalize()


def title(key):
    return METRIC_NAMES.get(key, pretty(key))


def factor_name(key):
    factor = e.factors[key]
    return pretty(key) if factor.name == key else factor.name


def slug(value):
    value = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not value or not value[0].isalpha():
        raise ValueError("Start the name with a letter.")
    return value


def section(name, detail=""):
    st.html(f'<div class="section-label"><h2>{esc(name)}</h2><span>{esc(detail)}</span></div>')


def empty(name, detail, icon="↗"):
    st.html(
        f'<div class="empty"><div class="empty-icon">{icon}</div><h3>{esc(name)}</h3><p>{esc(detail)}</p></div>'
    )


def chip(text):
    return f'<span class="chip">{esc(text)}</span>'


def pill(text, color=""):
    return f'<span class="pill {color}">{esc(text)}</span>'


def go(page):
    st.session_state.next_page = page
    st.rerun()


def changed(message):
    st.session_state.pop("active_dialog", None)
    st.session_state.pop("batch_preview", None)
    st.session_state.flash = message
    st.rerun()


def replace_experiment(experiment, demo=False):
    # Clear old form values so settings cannot bleed into a newly loaded experiment.
    for key in list(st.session_state):
        del st.session_state[key]
    st.session_state.experiment = experiment
    st.session_state.is_demo = demo
    st.rerun()


def level_input(label, levels, key, default=None, allow_unknown=False):
    options = list(levels) + ([None] if allow_unknown else [])
    index = options.index(default) if default in options else 0
    return st.selectbox(label, options, index=index, format_func=pretty, key=key)


def context_inputs(prefix, source=None):
    values = {}
    source = source or {}
    for key, ctx in e.contexts.items():
        if ctx.kind == "categorical":
            values[key] = level_input(title(key), ctx.levels, f"{prefix}_{key}", source.get(key))
        else:
            values[key] = st.number_input(
                title(key), value=float(source.get(key, ctx.center)), key=f"{prefix}_{key}"
            )
    return values


def error(err):
    st.error(str(err))


def close_dialog():
    st.session_state.pop("active_dialog", None)


def open_dialog(name, argument=None):
    st.session_state.active_dialog = (name, argument)
    st.rerun()


@st.dialog("Start a new experiment", on_dismiss=close_dialog)
def new_experiment():
    st.caption(
        "Give this creative question a home. Your current experiment will be replaced; save a copy first if you need it."
    )
    with st.form("new_experiment"):
        name = st.text_input("Experiment name", placeholder="Finding the hook for my next release")
        metric_name = st.text_input("What will you measure?", "3-second hold rate")
        kind = st.selectbox(
            "How is it measured?", ["A rate (successes / total)", "A count", "A number"]
        )
        starter = st.checkbox("Start with music-video choices", value=True)
        if st.form_submit_button("Create experiment", type="primary", use_container_width=True):
            try:
                if not name.strip():
                    raise ValueError("Give your experiment a name.")
                key = "hold_rate" if metric_name == "3-second hold rate" else slug(metric_name)
                obj = Experiment(
                    name.strip(),
                    Metric(
                        key,
                        {
                            "A rate (successes / total)": "proportion",
                            "A count": "count",
                            "A number": "continuous",
                        }[kind],
                    ),
                    seed=42,
                )
                if starter:
                    add_starter(obj)
                replace_experiment(obj)
            except ValueError as err:
                error(err)


def add_starter(obj):
    obj.add_factor("lyrics", [False, True], name="Lyrics on screen", dtype="boolean")
    obj.add_factor("hook", ["question", "statement"], name="Opening hook")
    obj.add_factor("song_section", ["chorus", "verse"], name="Song section")


@st.dialog("Add a creative choice", on_dismiss=close_dialog)
def add_factor_dialog():
    e = st.session_state.experiment
    st.caption("Choose one thing you can vary between posts. Keep the options practical to make.")
    kind = st.selectbox("Choice type", ["Options", "Yes / no", "Numbers"], key="add_choice_type")
    with st.form("add_choice"):
        name = st.text_input("Choice name", placeholder="Opening hook")
        raw = (
            st.text_area("Options · one per line", placeholder="Question\nStatement\nLyrics first")
            if kind != "Yes / no"
            else None
        )
        if kind == "Yes / no":
            st.caption("Options: Yes and No")
        with st.expander("Research settings"):
            sesoi = st.number_input(
                "Smallest effect worth caring about",
                min_value=0.0,
                value=0.0,
                help="On the modeled outcome scale. Leave at zero if unsure.",
            )
            proposed = st.checkbox("Save as an idea for later")
        if st.form_submit_button("Add choice", type="primary", use_container_width=True):
            try:
                levels = (
                    [False, True] if kind == "Yes / no" else parse_levels(raw, kind == "Numbers")
                )
                e.add_factor(
                    slug(name),
                    levels,
                    name=name.strip(),
                    dtype={"Options": "categorical", "Yes / no": "boolean", "Numbers": "numeric"}[
                        kind
                    ],
                    sesoi=sesoi or None,
                    status=Status.PROPOSED if proposed else Status.SCREENING,
                )
                changed("Creative choice added. Earlier posts stay unchanged.")
            except ValueError as err:
                error(err)


def parse_levels(raw, numeric=False):
    levels = [part.strip() for part in raw.splitlines() if part.strip()]
    return [float(v) for v in levels] if numeric else levels


@st.dialog("Manage creative choice", on_dismiss=close_dialog)
def manage_factor(key):
    e = st.session_state.experiment
    f = e.factors[key]
    st.subheader(factor_name(key))
    st.caption(f"Introduced at post {f.introduced_run} · {STATUS_LABELS[f.status.value]}")
    actions = {
        Status.PROPOSED: ["Start exploring"],
        Status.SCREENING: ["Mark active", "Pause this choice"],
        Status.ACTIVE: ["Pause this choice", "Return to exploring"],
        Status.RETIRED: ["Explore again"],
    }
    with st.form(f"manage_{key}"):
        action = st.selectbox("Next step", actions[f.status])
        fixed = level_input("Keep this option when paused", f.levels, f"fixed_{key}", f.fixed_value)
        reason = st.text_input(
            "Why make this change?",
            placeholder="A new hypothesis, or a practical production decision",
        )
        if st.form_submit_button("Update choice", type="primary"):
            try:
                target = {
                    "Start exploring": Status.SCREENING,
                    "Mark active": Status.ACTIVE,
                    "Pause this choice": Status.RETIRED,
                    "Return to exploring": Status.SCREENING,
                    "Explore again": Status.SCREENING,
                }[action]
                e.set_status(
                    key,
                    target,
                    rationale=reason,
                    fixed_value=fixed if target == Status.RETIRED else None,
                )
                changed("Choice updated. Its historical results are preserved.")
            except ValueError as err:
                error(err)
    if f.dtype != "boolean":
        with st.expander("Edit available options"), st.form(f"levels_{key}"):
            raw = st.text_area("Options · one per line", "\n".join(map(str, f.levels)))
            reason = st.text_input("Reason for changing options")
            if st.form_submit_button("Save options"):
                try:
                    e.update_levels(key, parse_levels(raw, f.dtype == "numeric"), rationale=reason)
                    changed("Options updated. Removed options remain in history.")
                except ValueError as err:
                    error(err)
    with st.expander("Change history"):
        for event in reversed(f.events):
            st.caption(f"Post {event['run']} · {event.get('rationale', 'Introduced')}")


@st.dialog("Add context", on_dismiss=close_dialog)
def add_context_dialog():
    e = st.session_state.experiment
    st.caption(
        "Record something you observe but don't experimentally change, like the song or posting slot."
    )
    kind = st.selectbox("Context type", ["Categories", "Number"])
    with st.form("add_context"):
        name = st.text_input("Context name", placeholder="Song")
        raw = (
            st.text_area("Categories · one per line", placeholder="First single\nSecond single")
            if kind == "Categories"
            else ""
        )
        center, scale = 0.0, 1.0
        if kind == "Number":
            center = st.number_input("Typical value", value=0.0)
            scale = st.number_input("Typical variation", min_value=0.001, value=1.0)
        if st.form_submit_button("Add context", type="primary"):
            try:
                e.add_context(
                    slug(name),
                    kind="categorical" if kind == "Categories" else "numeric",
                    levels=parse_levels(raw) if raw else None,
                    center=center,
                    scale=scale,
                )
                changed(
                    "Context added. Earlier posts without this context are excluded from adjusted analyses."
                )
            except ValueError as err:
                error(err)


@st.dialog("Workspace settings", width="large", on_dismiss=close_dialog)
def workspace_settings():
    e = st.session_state.experiment
    st.subheader("Keep a copy of your work")
    st.caption(
        "Your workspace lives in this browser session. Download it before closing or starting over."
    )
    st.download_button(
        "Download experiment",
        json.dumps(e.to_dict(), indent=2),
        "experiment.json",
        "application/json",
        use_container_width=True,
    )
    upload = st.file_uploader("Restore an experiment", type="json")
    if st.button("Restore saved experiment", disabled=upload is None):
        try:
            replace_experiment(Experiment.from_dict(json.load(upload)))
        except (ValueError, TypeError, KeyError) as err:
            error(err)
    with st.expander("Model & research settings"), st.form("model_settings"):
        half = st.number_input(
            "Temporal half-life in posts",
            min_value=0.0,
            value=float(e.model.half_life or 0),
            help="Zero uses all history equally. Discounting is a working approximation, not a fitted drift model.",
        )
        seed = st.number_input("Random seed", min_value=0, value=int(e.seed))
        if st.form_submit_button("Save settings"):
            e.model.half_life = half or None
            e.seed = int(seed)
            changed("Research settings saved.")
    with st.expander("Track another outcome"), st.form("add_metric"):
        name = st.text_input("Outcome name", placeholder="Shares")
        kind = st.selectbox(
            "Outcome type",
            ["proportion", "count", "continuous"],
            format_func=lambda k: {
                "proportion": "Rate",
                "count": "Count",
                "continuous": "Number",
            }[k],
        )
        if st.form_submit_button("Add outcome"):
            try:
                e.add_metric(slug(name), kind)
                changed("Outcome added. Your primary outcome is unchanged.")
            except ValueError as err:
                error(err)


def model_notices(fit):
    if fit.diagnostics["rank"] < fit.diagnostics["columns"]:
        st.html(
            '<div class="notice">Some effects cannot yet be separated. Treat the estimates below as provisional; more crossed observations may help.</div>'
        )
    with st.expander("How to read this analysis · assumptions & diagnostics"):
        for warning in fit.diagnostics["warnings"]:
            st.write(warning)
        st.caption(
            "Intervals are 95% marginal model-based credible intervals. A narrow prior-driven interval is not evidence that an effect is identified."
        )
        st.json(fit.diagnostics)


def effect_name(record):
    encoder = Encoder(e)
    term = next((term for term in encoder.terms if term.name == record["term"]), None)
    if term is None:
        return pretty(record["term"])
    return " × ".join(
        f"{factor_name(key)} · {pretty(value)} vs {pretty(encoder.domains[key][0])}"
        for key, value in term.parts
    )


def effect_chart(records):
    if not records:
        empty(
            "Nothing to estimate yet",
            "Add creative choices and record some posts to start learning.",
        )
        return
    bound = max(max(abs(r["low"]), abs(r["high"])) for r in records) or 1
    bound *= 1.1
    for r in records:
        lo, hi, mu = [50 + 50 * r[k] / bound for k in ("low", "high", "mean")]
        cls = "identified" if r["identified"] else ""
        status = (
            "Needs separation"
            if not r["identified"]
            else "Promising direction"
            if r["low"] > 0
            else "Negative direction"
            if r["high"] < 0
            else "Still uncertain"
        )
        st.html(
            f'<div class="effect-row"><div class="effect-head"><span class="effect-name">{esc(effect_name(r))}</span>{pill(status, "green" if cls else "orange")}</div><div class="interval" role="img" aria-label="{esc(effect_name(r))}: mean {r["mean"]:.2f}, 95% interval {r["low"]:.2f} to {r["high"]:.2f}"><div class="interval-line {cls}" style="left:{lo}%;width:{hi - lo}%"></div><div class="interval-dot {cls}" style="left:{mu}%"></div></div><div class="insight-caption">{r["mean"]:+.2f} · interval {r["low"]:+.2f} to {r["high"]:+.2f}</div></div>'
        )
    st.html(
        f'<div class="interval-axis"><span>−{bound:.1f}</span><span>0 · no difference</span><span>+{bound:.1f}</span></div>'
    )


def observed_value(obs, metric):
    result = obs.outcomes.get(metric)
    if result is None:
        return "—"
    return (
        f"{result['numerator'] / result['denominator']:.1%}"
        if e.metrics[metric].kind == "proportion"
        else f"{result['value']:,.2f}"
    )


def overview():
    st.title("Make room for better ideas.")
    st.html(
        '<div class="page-intro">A little structure. More creative freedom. Learn what makes your content connect.</div>'
    )
    st.html(
        '<div class="hero"><div class="hero-copy"><div class="eyebrow">YOUR CREATIVE ADVANTAGE</div><h2>Don’t just make more.<br>Learn what moves people.</h2><p>Turn your next few posts into a thoughtful experiment, one creative choice at a time.</p></div><div class="hero-art" aria-hidden="true"><div class="specimen back"><small>THE NEXT RELEASE</small><strong>find your<br>own rhythm.</strong><div class="wave"></div></div><div class="specimen front"><small>ONE SMALL CHANGE</small><strong>what if<br>we tried<br>this?</strong></div><div class="art-tag">a little curiosity goes a long way ↗</div></div></div>'
    )
    active = sum(f.status in {Status.SCREENING, Status.ACTIVE} for f in e.factors.values())
    records = e.effects() if e.observations else []
    promising = sum(r["identified"] and (r["low"] > 0 or r["high"] < 0) for r in records)
    for col, label, value, note in zip(
        st.columns(3),
        ["POSTS RECORDED", "CHOICES IN PLAY", "DIRECTIONS TO EXPLORE"],
        [len(e.observations), active, promising],
        [
            "Each post adds to the picture",
            "Small changes, useful questions",
            "Exploratory, not confirmed effects",
        ],
    ):
        with col:
            st.html(
                f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{value:02d}</div><div class="stat-note">{note}</div></div>'
            )
    left, right = st.columns([1.5, 1], gap="large")
    with left:
        section("Your next move", "KEEP THE MOMENTUM")
        with st.container(border=True):
            if not e.factors:
                st.html(
                    f'{pill("START HERE", "orange")}<div class="card-title">What are you curious about?</div><div class="card-meta">Start with a few choices you can actually change.<br>Our music starter includes lyrics, opening hook, and song section.</div><div class="chips">{chip("Lyrics on screen")}{chip("Opening hook")}{chip("Song section")}</div>'
                )
                st.write("")
                if st.button("Use the music starter  ↗", type="primary", use_container_width=True):
                    add_starter(e)
                    changed("Your first three choices are ready. Plan a few posts next.")
                if st.button("Start with my own choices", use_container_width=True):
                    go("Creative choices")
            else:
                st.html(
                    f'{pill("READY WHEN YOU ARE", "green")}<div class="card-title">Give your next posts a purpose.</div><div class="card-meta">You have {active} creative choices to explore. Build a small batch that helps distinguish their effects.</div>'
                )
                st.write("")
                if st.button("Plan next posts  ↗", type="primary", use_container_width=True):
                    go("Next posts")
                if st.button("I have results to record", use_container_width=True):
                    go("Results")
        section("Recent activity", f"{len(e.observations)} POSTS")
        if not e.observations:
            with st.container(border=True):
                empty(
                    "The first post is the beginning",
                    "Once you record results, your latest posts will appear here.",
                    "◷",
                )
        else:
            for obs in list(e.observations)[-4:][::-1]:
                choices = " · ".join(
                    f"{pretty(k)}: {pretty(v)}" for k, v in list(obs.configuration.items())[:2]
                )
                st.html(
                    f'<div class="event-row"><span class="event-number">#{obs.run:02}</span><span class="event-description">{esc(choices)}</span><span class="event-value">{observed_value(obs, e.primary_metric)}</span></div>'
                )
            st.caption(title(e.primary_metric))
    with right:
        section("What you’re learning")
        with st.container(border=True):
            if not records:
                empty(
                    "Curiosity first. Evidence follows.",
                    "Your effect estimates will appear here after you record posts. You’ll see uncertainty alongside every estimate.",
                    "✳",
                )
            else:
                for r in records[:3]:
                    label = (
                        "Needs more separation"
                        if not r["identified"]
                        else "Worth a closer look"
                        if r["low"] > 0 or r["high"] < 0
                        else "Still an open question"
                    )
                    st.html(
                        f'<div class="insight-row"><div class="insight-name">{esc(effect_name(r))}</div>{pill(label, "purple")}<div class="insight-caption">{r["n_posts"]} usable posts · interval {r["low"]:+.2f} to {r["high"]:+.2f}</div></div>'
                    )
                if st.button("See all insights →", use_container_width=True):
                    go("Insights")
        st.html(
            '<div class="soft-note">GOOD EXPERIMENTS LEAVE ROOM FOR DOUBT<br>A promising result is a reason to investigate, not a reason to stop asking questions.</div>'
        )
        if not e.observations:
            st.divider()
            st.caption("Want to see how it works with results?")
            if st.button("Explore a sample experiment", use_container_width=True):
                path = ROOT / "examples/music_creator/output/experiment.json"
                if path.exists():
                    replace_experiment(Experiment.load(path), demo=True)
                else:
                    st.info("Run the music_creator demo to create the sample experiment.")


def choices_page():
    heading, action = st.columns([3, 1])
    with heading:
        st.title("Small choices. Big questions.")
        st.html(
            '<div class="page-intro">Define what you can change. Keep the creative possibilities open.</div>'
        )
    with action:
        if st.button("＋ Add a choice", type="primary", use_container_width=True):
            open_dialog("add_factor")
    if not e.factors:
        with st.container(border=True):
            empty(
                "Start with one clear question",
                "Does showing the lyrics help? Does a question make a stronger opening? Add a choice to find out.",
                "✳",
            )
    for offset in range(0, len(e.factors), 3):
        for col, (key, f) in zip(st.columns(3), list(e.factors.items())[offset : offset + 3]):
            with col, st.container(border=True):
                status = STATUS_LABELS[f.status.value]
                st.html(
                    f'<div class="card-top"><span class="card-index">CHOICE {list(e.factors).index(key) + 1:02}</span>{pill(status, "green" if f.status == Status.ACTIVE else "purple" if f.status == Status.SCREENING else "")}</div><div class="card-title">{esc(factor_name(key))}</div><div class="card-meta">{len(f.levels)} options · introduced at post {f.introduced_run}</div><div class="chips">{"".join(chip(pretty(v)) for v in f.levels)}</div>'
                )
                if f.status == Status.RETIRED:
                    st.caption(f"Held at {pretty(f.fixed_value)}. History is preserved.")
                st.write("")
                if st.button("Manage choice", key=f"manage_{key}", use_container_width=True):
                    open_dialog("manage_factor", key)
    section("The context around your posts", "OBSERVE, DON’T MANIPULATE")
    st.caption(
        "Songs, platforms, and posting slots can change the baseline. Record them separately from creative choices."
    )
    for key, ctx in e.contexts.items():
        with st.container(border=True):
            st.html(
                f'<div class="card-title">{esc(title(key))}</div><div class="chips">{"".join(chip(pretty(v)) for v in ctx.levels) if ctx.kind == "categorical" else chip("Numeric context")}</div>'
            )
    if st.button("＋ Add context"):
        open_dialog("add_context")
    st.html(
        '<div class="soft-note">Add, pause, or revisit choices whenever your question changes. Old posts always keep their original settings. New choices never get invented values in history.</div>'
    )


def next_posts_page():
    st.title("Make the next few count.")
    st.html(
        '<div class="page-intro">A small, intentional batch. Enough variety to learn something useful.</div>'
    )
    if not any(f.status in {Status.ACTIVE, Status.SCREENING} for f in e.factors.values()):
        empty(
            "Give your posts something to explore",
            "Add a creative choice or reactivate a paused one first.",
        )
        if st.button("Go to creative choices", type="primary"):
            go("Creative choices")
        return
    with st.container(border=True):
        a, b = st.columns([1, 2], gap="large")
        with a:
            n = st.number_input(
                "How many posts?", min_value=1, max_value=12, value=3, key="batch_size"
            )
        with b:
            mode = st.select_slider(
                "What matters most right now?",
                ["Explore", "Mostly learn", "Balance", "Mostly perform", "Perform"],
                value="Explore",
            )
        st.caption(
            "Explore favors designs that help separate effects. Perform favors predicted outcomes, with less assurance of useful comparisons."
        )
        contexts = []
        if e.contexts:
            section("Where these posts will happen")
            for i in range(int(n)):
                with st.expander(f"Post {e.next_run + i} · planned context", expanded=i == 0):
                    contexts.append(context_inputs(f"planned_{i}"))
        else:
            contexts = [{} for _ in range(int(n))]
        with st.expander("Fine-tune the plan"):
            balance = st.multiselect(
                "Keep these choices balanced across the batch",
                [k for k, f in e.factors.items() if f.status in {Status.SCREENING, Status.ACTIVE}],
                format_func=factor_name,
            )
            cooldown = st.number_input("Avoid repeating the last N posts", min_value=0, value=0)
            unique = st.checkbox("Use different configurations within this batch", value=True)
            limit_changes = st.checkbox("Limit changes from a baseline")
            baseline, max_changes = None, None
            if limit_changes:
                max_changes = st.number_input(
                    "Maximum changed choices", min_value=0, max_value=len(e.factors), value=1
                )
                baseline = {
                    k: f.fixed_value
                    if f.status == Status.RETIRED
                    else level_input(factor_name(k), f.levels, f"baseline_{k}")
                    for k, f in e.factors.items()
                    if f.status != Status.PROPOSED
                }
            st.caption(
                "Combination rules apply to this batch. Each required pattern must appear at least once."
            )
            rules_key = f"rules_{e.schema_version}"
            if rules_key not in st.session_state:
                st.session_state[rules_key] = {"forbidden": [], "required": []}
            rules = st.session_state[rules_key]
            with st.container(border=True):
                rule_type = st.selectbox(
                    "Rule type", ["Avoid this combination", "Include this combination"]
                )
                pattern = {}
                for k, f in e.factors.items():
                    if f.status in {Status.SCREENING, Status.ACTIVE}:
                        index = st.selectbox(
                            factor_name(k),
                            list(range(-1, len(f.levels))),
                            format_func=lambda j, levels=f.levels: (
                                "Any option" if j == -1 else pretty(levels[j])
                            ),
                            key=f"rule_{k}_{e.schema_version}",
                        )
                        if index >= 0:
                            pattern[k] = f.levels[index]
                if st.button("Add rule"):
                    if pattern:
                        bucket = "forbidden" if rule_type.startswith("Avoid") else "required"
                        if pattern not in rules[bucket]:
                            rules[bucket].append(pattern)
                    else:
                        st.warning("Choose at least one option for the rule.")
            for bucket, patterns in rules.items():
                for i, pattern in enumerate(patterns):
                    st.caption(
                        ("Avoid: " if bucket == "forbidden" else "Include: ")
                        + ", ".join(f"{factor_name(k)} = {pretty(v)}" for k, v in pattern.items())
                    )
            if (rules["forbidden"] or rules["required"]) and st.button("Clear combination rules"):
                st.session_state[rules_key] = {"forbidden": [], "required": []}
                st.rerun()
        if st.button("Build my next batch  ↗", type="primary", use_container_width=True):
            try:
                st.session_state.batch_preview = e.recommend_next(
                    int(n),
                    exploration={
                        "Explore": 1.0,
                        "Mostly learn": 0.9,
                        "Balance": 0.5,
                        "Mostly perform": 0.1,
                        "Perform": 0.0,
                    }[mode],
                    contexts=contexts,
                    constraints=Constraints(
                        balance=balance,
                        forbidden=rules["forbidden"],
                        required=rules["required"],
                        cooldown=int(cooldown),
                        unique_batch=unique,
                        baseline=baseline,
                        max_changes=int(max_changes) if max_changes is not None else None,
                    ),
                )
            except ValueError as err:
                st.session_state.pop("batch_preview", None)
                error(err)
    batch = st.session_state.get("batch_preview")
    if not batch:
        st.html(
            '<div class="soft-note">Recommendations are a preview, not a posting queue. Make the posts in order, then record results before generating a new batch.</div>'
        )
        return
    if batch[0]["schema_version"] != e.schema_version or batch[0]["run"] != e.next_run:
        st.info("Your experiment changed. Build a fresh batch with the latest results.")
        return
    section("Your creative brief", f"{len(batch)} POSTS TO TRY")
    for offset in range(0, len(batch), 3):
        for col, rec in zip(st.columns(3), batch[offset : offset + 3]):
            with col, st.container(border=True):
                st.html(
                    f'<div class="card-top"><span class="post-number">{rec["run"]:02}</span>{pill("NEXT EXPERIMENT", "green")}</div>'
                )
                for k, v in rec["configuration"].items():
                    st.html(
                        f'<div class="setting-row"><span>{esc(factor_name(k))}</span><strong>{esc(pretty(v))}</strong></div>'
                    )
                if rec["context"]:
                    st.caption(
                        " · ".join(f"{title(k)}: {pretty(v)}" for k, v in rec["context"].items())
                    )
                st.html(
                    '<div class="insight-caption" style="margin-top:15px">WHY THIS POST<br>Adds contrast information about the choices you’re exploring.</div>'
                )
                with st.expander("See the reasoning"):
                    for reason in rec["reasons"]:
                        st.write(reason)
                    p = rec["prediction"]
                    st.caption(
                        f"Predicted outcome on modeled scale: {p['mean_transformed']:.2f}; predictive interval {p['predictive_low']:.2f} to {p['predictive_high']:.2f}. This is not a percentage-point lift."
                    )
                if st.button(
                    "Record this post", key=f"record_rec_{rec['run']}", use_container_width=True
                ):
                    st.session_state.record_prefill = rec
                    go("Results")
    st.download_button(
        "Download creative brief", brief_text(batch), "creative-brief.md", "text/markdown"
    )
    with st.expander("Design cautions"):
        for warning in batch[0]["warnings"]:
            st.write(warning)


def brief_text(batch):
    lines = [f"# {e.name} — creative brief", "", "Preview only. Record posts in publication order."]
    for rec in batch:
        lines.extend(["", f"## Post {rec['run']} (schema {rec['schema_version']})"])
        lines += [f"- {factor_name(k)}: {pretty(v)}" for k, v in rec["configuration"].items()]
        lines += [f"- Context / {title(k)}: {pretty(v)}" for k, v in rec["context"].items()]
        lines.extend(["", *rec["reasons"]])
    lines.extend(["", "## Design cautions", *batch[0]["warnings"]])
    return "\n".join(lines)


def results_page():
    st.title("Every post adds a little clarity.")
    st.html(
        '<div class="page-intro">Record what you actually made and how it performed. Let the evidence build.</div>'
    )
    prefill = st.session_state.get("record_prefill", {})
    default_version = prefill.get("schema_version", e.schema_version)
    with st.expander("Recording an older post?"):
        version = st.selectbox(
            "Creative setup used for this post",
            range(len(e.schemas)),
            index=default_version,
            format_func=lambda i: f"Setup {i} · available from post {e.schemas[i]['at_run']}",
        )
        unknown = st.checkbox("Allow unrecorded choice values")
        st.caption(
            "Enter results in publication order. This selects the original creative setup; it does not insert a post into earlier history."
        )
    schema = e.schemas[version]
    additional_metrics = (
        st.multiselect(
            "Additional outcomes to record",
            [key for key in e.metrics if key != e.primary_metric],
            format_func=title,
        )
        if len(e.metrics) > 1
        else []
    )
    left, right = st.columns([1.6, 1], gap="large")
    with left, st.form("record_result"):
        st.subheader(f"Record post {e.next_run:02}")
        configuration = {}
        for k, f in schema["factors"].items():
            if f["status"] == "PROPOSED":
                continue
            if f["status"] == "RETIRED":
                configuration[k] = f["fixed_value"]
                st.caption(f"{factor_name(k)} · held at {pretty(f['fixed_value'])}")
            else:
                configuration[k] = level_input(
                    factor_name(k),
                    f["levels"],
                    f"result_{e.next_run}_{version}_{k}",
                    prefill.get("configuration", {}).get(k),
                    allow_unknown=unknown,
                )
        ctx = {}
        for k, c in schema["contexts"].items():
            default = prefill.get("context", {}).get(k)
            ctx[k] = (
                level_input(title(k), c["levels"], f"observed_{e.next_run}_{version}_{k}", default)
                if c["kind"] == "categorical"
                else st.number_input(
                    title(k),
                    value=float(default if default is not None else c["center"]),
                    key=f"observed_{e.next_run}_{version}_{k}",
                )
            )
        st.divider()
        outcomes = {}
        for key, metric in e.metrics.items():
            include = key == e.primary_metric or key in additional_metrics
            if not include:
                continue
            st.markdown(f"**{title(key)}**")
            if metric.kind == "proportion":
                a, b = st.columns(2)
                with a:
                    numerator = st.number_input(
                        "Reached 3 seconds" if key == "hold_rate" else "Successes",
                        min_value=0,
                        value=None,
                        placeholder="e.g. 320",
                        key=f"num_{e.next_run}_{key}",
                    )
                with b:
                    denominator = st.number_input(
                        "Eligible starts" if key == "hold_rate" else "Total opportunities",
                        min_value=1,
                        value=None,
                        placeholder="e.g. 1000",
                        key=f"den_{e.next_run}_{key}",
                    )
                outcomes[key] = {"numerator": numerator, "denominator": denominator}
            else:
                val = st.number_input(
                    "Observed value",
                    min_value=0 if metric.kind == "count" else None,
                    value=None,
                    step=1 if metric.kind == "count" else 0.1,
                    placeholder="Enter measured outcome",
                    key=f"value_{e.next_run}_{key}",
                )
                outcomes[key] = {"value": val}
        if st.form_submit_button("Save result", type="primary", use_container_width=True):
            try:
                e.observe(
                    configuration,
                    context=ctx,
                    outcomes=outcomes,
                    schema_version=version,
                    allow_unknown=unknown,
                )
                st.session_state.pop("record_prefill", None)
                changed("Result saved. Your next recommendations will use this evidence.")
            except (ValueError, TypeError) as err:
                error(err)
    with right:
        with st.container(border=True):
            st.html(
                f'{pill("A CONSISTENT MEASURE", "purple")}<div class="card-title">Compare posts at the same age.</div><div class="card-meta">Choose a measurement window, such as 48 hours after publishing, and use it every time. A week-old post and a new post aren’t a fair comparison.</div>'
            )
        st.html(
            '<div class="soft-note">Record actual settings, even if you changed the recommendation. Counts stay intact; the model treats each post as an observation, not each viewer as an experiment.</div>'
        )
        with st.expander("Import or export results"):
            st.download_button(
                "Download results CSV",
                e.export_csv(),
                "observations.csv",
                "text/csv",
                use_container_width=True,
            )
            upload = st.file_uploader("Import results CSV", type="csv")
            st.caption(
                "Use the exported format with this experiment’s setup IDs. Imports append rows; importing twice creates duplicates."
            )
            if st.button("Import CSV", disabled=upload is None):
                try:
                    count = e.import_csv(upload.getvalue().decode())
                    changed(f"Imported {count} results.")
                except (ValueError, TypeError, KeyError) as err:
                    error(err)
    section("Your observation log", title(e.primary_metric))
    if e.observations:
        rows = [
            {
                "Post": o.run,
                "Outcome": observed_value(o, e.primary_metric),
                "Creative choices": " · ".join(
                    f"{pretty(k)}: {pretty(v)}" for k, v in o.configuration.items()
                ),
                "Context": " · ".join(f"{title(k)}: {pretty(v)}" for k, v in o.context.items()),
                "Setup": o.schema_version,
            }
            for o in reversed(e.observations)
        ]
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        empty(
            "No results yet",
            "Your recorded posts will appear here, with the choices that made them.",
            "◷",
        )


def insights_page():
    st.title("A clearer picture. Not a final answer.")
    st.html(
        '<div class="page-intro">See which creative directions deserve another look, and where the evidence is still thin.</div>'
    )
    if not e.observations:
        with st.container(border=True):
            empty(
                "Let’s give your curiosity some evidence",
                "Record your first results to see estimated effects and their uncertainty.",
                "✳",
            )
        if st.button("Record a result", type="primary"):
            go("Results")
        return
    _a, b = st.columns([2, 1])
    with b:
        metric = st.selectbox("Outcome to explore", list(e.metrics), format_func=title)
    with st.expander("Choose which factors to analyze"):
        selected = st.multiselect(
            "Include these choices",
            list(e.factors),
            default=[k for k, f in e.factors.items() if f.status != Status.PROPOSED],
            format_func=factor_name,
        )
        st.caption(
            "A model using only older choices can retain more history. Changing the included factors changes the question being estimated. All recorded context variables remain in the model."
        )
    fit = e.fit(factor_ids=selected, metric=metric)
    records = e.effects(factor_ids=selected, metric=metric)
    model_notices(fit)
    left, right = st.columns([1.7, 1], gap="large")
    with left, st.container(border=True):
        section("The direction of each effect", f"{fit.n_used} USABLE POSTS")
        st.caption("Dot = estimate · line = 95% interval · center = no difference")
        effect_chart(records)
        scale = {
            "proportion": "smoothed log odds",
            "count": "log(1 + count)",
            "continuous": "the original outcome units",
        }[e.metrics[metric].kind]
        st.html(
            f'<div class="soft-note">Shown in {scale}. Contrasts compare an option with its historical reference. Positive values indicate a higher modeled outcome; they are not automatically causal.</div>'
        )
    with right:
        with st.container(border=True):
            st.html(
                f'{pill("THE EVIDENCE SO FAR", "purple")}<div class="stat-value">{fit.n_used} <span style="font-size:1rem;color:#9a9686">/ {len(e.observations)} posts</span></div><div class="card-meta">Posts with known settings for this analysis. Older posts are preserved even when they can’t answer a newer question.</div>'
            )
            st.caption(f"Weighted post count: {fit.weighted_posts:.1f}")
        section("Worth your attention")
        for r in records:
            if "review for retirement" in r["interpretation"]:
                st.info(
                    f"{effect_name(r)}: within your smallest meaningful effect range. Review every contrast and interaction before pausing the choice."
                )
            elif r["identified"] and (r["low"] > 0 or r["high"] < 0):
                st.html(
                    f'<div class="insight-row"><div class="insight-name">{esc(effect_name(r))}</div><div class="insight-caption">A direction worth testing again with fresh posts. This is exploratory evidence.</div></div>'
                )
        if not any(r["identified"] and (r["low"] > 0 or r["high"] < 0) for r in records):
            st.caption(
                "No clear direction yet. That is useful to know: keep the next batch varied."
            )
    with st.expander("Explore how choices work together"):
        pairs = e.interaction_candidates()
        st.caption(
            "Pairwise interactions are exploratory. Both parent choices need identified evidence, and the expanded model must pass data and rank checks. This can miss interactions with weak main effects."
        )
        if pairs:
            with st.form("enable_interaction"):
                pair = st.selectbox(
                    "Pair to investigate",
                    pairs,
                    format_func=lambda p: " × ".join(factor_name(k) for k in p),
                )
                rationale = st.text_input("What is your interaction hypothesis?")
                if st.form_submit_button("Investigate this interaction"):
                    try:
                        e.enable_interaction(*pair, rationale=rationale)
                        changed(
                            "Exploratory interaction enabled. Intervals do not account for selection."
                        )
                    except ValueError as err:
                        error(err)
        else:
            st.write("No eligible pairs yet. Keep learning about individual choices first.")
    with st.expander("Full effect table"):
        st.dataframe(records, hide_index=True, use_container_width=True)


if "experiment" not in st.session_state:
    st.session_state.experiment = Experiment("My creative experiment", seed=42)
if "next_page" in st.session_state:
    st.session_state.page = st.session_state.pop("next_page")
e = st.session_state.experiment

with st.sidebar:
    st.html(
        '<div class="brand"><span class="brand-mark">✳</span>creative doe<span style="color:#a6a191;font-size:.7rem;font-weight:400">/</span></div>'
    )
    st.html(
        f'<div class="workspace-name"><div class="workspace-label">YOUR WORKSPACE</div>{esc(e.name)}</div>'
    )
    page = st.radio("Navigation", PAGES, key="page", label_visibility="collapsed")
    st.divider()
    if st.button("＋ New experiment", use_container_width=True):
        open_dialog("new_experiment")
    if st.button("Workspace settings", use_container_width=True):
        open_dialog("settings")
    st.download_button(
        "↓ Save a copy",
        json.dumps(e.to_dict(), indent=2),
        "experiment.json",
        "application/json",
        use_container_width=True,
    )
    st.html(
        '<div class="local-note">A little science for your creative practice.<br><br>Saved in this session.<br>Download a copy to keep your work.</div>'
    )

st.html(
    f'<div class="topline"><span class="breadcrumb">Your workspace &nbsp; / &nbsp; {esc(page)}{pill("SIMULATED EXAMPLE", "demo") if st.session_state.get("is_demo") else ""}</span><span class="local-dot">Local workspace · just for you</span></div>'
)
with st.container(key="mobile_navigation"):
    destination = st.selectbox("Go to", PAGES, index=PAGES.index(page), key=f"mobile_{page}")
    if destination != page:
        go(destination)
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"))
if st.session_state.get("is_demo"):
    st.caption(
        "You’re exploring synthetic results from the music example. These are not real creator outcomes."
    )
{
    "Overview": overview,
    "Creative choices": choices_page,
    "Next posts": next_posts_page,
    "Results": results_page,
    "Insights": insights_page,
}[page]()
st.html(
    '<div class="footer"><span>CREATIVE DOE &nbsp; / &nbsp; CONTINUOUS EXPERIMENTATION</span><span>Made for questions worth asking.</span></div>'
)

if "active_dialog" in st.session_state:
    dialog_name, argument = st.session_state.active_dialog
    if dialog_name == "manage_factor":
        manage_factor(argument)
    else:
        {
            "add_factor": add_factor_dialog,
            "add_context": add_context_dialog,
            "new_experiment": new_experiment,
            "settings": workspace_settings,
        }[dialog_name]()
