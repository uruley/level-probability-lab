import pytest

from level_probability_lab.jev_companion import build_package, mock_choice, parse_response


def test_package_is_frozen_point_in_time_shape():
    p = build_package(forecast_id="f1", origin="2026-05-01T15:29Z",
                      session="2026-05-01", origin_close=100,
                      sampled_paths=[[[100, 101, 99, 100]]],
                      kronos_median=[100], kronos_range=[99, 101])
    assert p["schema_version"] == "jev_companion_input_v1"
    assert p["input_complete"] is True


def test_response_requires_three_scores_and_marks_them_unvalidated():
    out = parse_response({"scores": {"bull": .2, "neutral": .6, "bear": .2},
                          "reason": "range bound", "input_complete": True})
    assert out["probability_status"] == "unvalidated_model_scores"


def test_response_rejects_bad_scores():
    with pytest.raises(ValueError):
        parse_response({"scores": {"bull": 2, "neutral": 0, "bear": 0}})


def test_mock_transport_is_deterministic_and_network_free():
    package = build_package(forecast_id="f1", origin="2026-05-01T15:29Z",
                            session="2026-05-01", origin_close=100,
                            sampled_paths=[[[100, 101, 99, 100]]],
                            kronos_median=[100], kronos_range=[99, 101])
    assert mock_choice(package) == mock_choice(package)


def test_official_envelope_and_durable_cache(tmp_path, monkeypatch):
    import json
    import io
    from level_probability_lab.jev_companion import request_real
    calls = []
    body = {'model': 'jev-1.13.0', 'answers': {'move_5m': {
        'type': 'choice', 'choice': 'neutral', 'confidence': .4,
        'probabilities': {'bull': .2, 'neutral': .6, 'bear': .2}}}}
    def send(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(json.dumps(body).encode())
    monkeypatch.setattr('urllib.request.urlopen', send)
    with pytest.raises(ValueError, match='network disabled'):
        request_real({}, api_key='fixture', cache_dir=tmp_path)
    result = request_real({}, api_key='fixture', cache_dir=tmp_path, allow_network=True)
    assert result['model'] == 'jev-1.13.0'
    assert request_real({}, api_key='fixture', cache_dir=tmp_path) == result
    assert len(calls) == 1
    with pytest.raises(FileExistsError):
        request_real({'different': True}, api_key='fixture', cache_dir=tmp_path, allow_network=True)


@pytest.mark.parametrize('scores', [dict(bull=.2, neutral=.2, bear=.2),
    dict(bull=True, neutral=0, bear=0), dict(bull=float('nan'), neutral=.5, bear=.5)])
def test_rejects_invalid_distribution(scores):
    with pytest.raises(ValueError):
        parse_response(dict(scores=scores, input_complete=True))


def test_uncertain_request_is_not_retried(tmp_path, monkeypatch):
    from level_probability_lab.jev_companion import request_real
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr('urllib.request.urlopen', fail)
    with pytest.raises(TimeoutError):
        request_real({}, api_key='fixture', cache_dir=tmp_path, allow_network=True)
    with pytest.raises(FileExistsError):
        request_real({}, api_key='fixture', cache_dir=tmp_path, allow_network=True)


@pytest.mark.parametrize('neutral,valid', [(.56, True), (.58, True), (.50, False)])
def test_observed_rounding_retains_raw_scores(neutral, valid):
    from level_probability_lab.jev_companion import parse_typesafe
    body = {'model': 'jev-1.13.0', 'answers': {'move_5m': {
        'type': 'choice', 'choice': 'neutral', 'confidence': .35,
        'probabilities': {'bull': .1, 'neutral': neutral, 'bear': .33}}}}
    if not valid:
        with pytest.raises(ValueError, match='rounding tolerance'):
            parse_typesafe(body)
    else:
        result = parse_typesafe(body)
        assert result['raw_scores']['neutral'] == neutral
        assert sum(result['scores'].values()) == pytest.approx(1)
