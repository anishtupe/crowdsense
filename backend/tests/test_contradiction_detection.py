from app.services.contradiction_detection import detect_contradiction, any_contradictions


def test_no_contradiction_when_texts_agree():
    result = detect_contradiction("r1", "Minor flooding, situation contained", "r2", "Contained, no major damage")
    assert result.contradicts is False


def test_contradiction_on_conflicting_severity():
    result = detect_contradiction("r1", "Building collapsed, people trapped", "r2", "Situation is safe and resolved")
    assert result.contradicts is True


def test_any_contradictions_true_for_one_bad_pair():
    reports = [
        ("r1", "Fire contained, all safe"),
        ("r2", "Multiple fatalities reported, building collapsed"),
        ("r3", "Fire contained, all safe"),
    ]
    assert any_contradictions(reports) is True


def test_any_contradictions_false_when_all_agree():
    reports = [
        ("r1", "Fire contained, all safe"),
        ("r2", "Situation resolved, no injuries"),
    ]
    assert any_contradictions(reports) is False
