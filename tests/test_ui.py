"""Exercise creator-facing workflows through the actual Streamlit app."""

from pathlib import Path

import pytest

from creative_doe import Experiment

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py"


def widget(items, label):
    return next(item for item in items if item.label == label)


def start():
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    return app


def navigate(app, page):
    widget(app.radio, "Navigation").set_value(page).run()
    assert not app.exception


def test_starter_plan_and_record_without_json():
    app = start()
    widget(app.button, "Use the music starter  ↗").click().run()
    assert not app.exception
    assert len(app.session_state.experiment.factors) == 3
    navigate(app, "Next posts")
    widget(app.button, "Build my next batch  ↗").click().run()
    assert not app.exception
    assert len(app.session_state.batch_preview) == 3
    widget(app.button, "Record this post").click().run()
    assert not app.exception
    expected = app.session_state.record_prefill["configuration"]
    widget(app.number_input, "Reached 3 seconds").set_value(320)
    widget(app.number_input, "Eligible starts").set_value(1000)
    widget(app.button, "Save result").click().run()
    assert not app.exception
    assert len(app.session_state.experiment.observations) == 1
    assert app.session_state.experiment.observations[0].configuration == expected
    assert "batch_preview" not in app.session_state
    navigate(app, "Insights")
    assert not app.exception


def test_add_choice_dialog_and_pause():
    app = start()
    navigate(app, "Creative choices")
    widget(app.button, "＋ Add a choice").click().run()
    widget(app.text_input, "Choice name").set_value("Opening hook")
    widget(app.text_area, "Options · one per line").set_value("Question\nStatement")
    widget(app.button, "Add choice").click().run()
    assert not app.exception
    assert app.session_state.experiment.factors["opening_hook"].levels == ["Question", "Statement"]
    widget(app.button, "Manage choice").click().run()
    widget(app.selectbox, "Next step").set_value("Pause this choice")
    widget(app.text_input, "Why make this change?").set_value("Focus on other creative questions")
    widget(app.button, "Update choice").click().run()
    assert not app.exception
    assert app.session_state.experiment.factors["opening_hook"].status.value == "RETIRED"


def test_empty_states_and_invalid_outcome_do_not_invent_data():
    app = start()
    for page in ["Insights", "Next posts", "Results"]:
        navigate(app, page)
    widget(app.button, "Save result").click().run()
    assert not app.exception
    assert app.error
    assert len(app.session_state.experiment.observations) == 0


def test_sample_is_explicitly_simulated_and_all_pages_render():
    app = start()
    widget(app.button, "Explore a sample experiment").click().run()
    assert not app.exception
    assert app.session_state.is_demo
    assert len(app.session_state.experiment.observations) == 80
    for page in ["Creative choices", "Next posts", "Results", "Insights", "Overview"]:
        navigate(app, page)


def test_context_forms_follow_batch_size_and_recorded_counts_validate():
    app = start()
    e = Experiment()
    e.add_factor("lyrics", [False, True])
    e.add_context("song", levels=["A", "B"])
    app.session_state.experiment = e
    navigate(app, "Next posts")
    widget(app.number_input, "How many posts?").set_value(2).run()
    assert len([s for s in app.selectbox if s.label == "Song"]) == 2
    widget(app.button, "Build my next batch  ↗").click().run()
    assert not app.exception
    assert len(app.session_state.batch_preview) == 2


def test_numeric_metric_and_nondefault_factor_schema():
    app = start()
    e = Experiment()
    e.add_factor("duration", [10, 20], dtype="numeric")
    old = e.schema_version
    e.add_factor("face", [False, True], dtype="boolean")
    app.session_state.experiment = e
    navigate(app, "Results")
    widget(app.selectbox, "Creative setup used for this post").set_value(old).run()
    assert not any(s.label == "Face" for s in app.selectbox)
    widget(app.number_input, "Reached 3 seconds").set_value(1)
    widget(app.number_input, "Eligible starts").set_value(10)
    widget(app.button, "Save result").click().run()
    assert not app.exception
    assert "face" not in app.session_state.experiment.observations[0].configuration
