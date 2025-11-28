from app.predictor import predict_wait_time_and_priority


def test_predictor_returns_numbers():
    """
    Ensure that the predictor returns numeric fields for wait-time and
    priority score when given a list of symptoms.
    """
    result = predict_wait_time_and_priority(["headache"])
    assert "predicted_wait_minutes" in result
    assert "priority_score" in result
    assert isinstance(result["predicted_wait_minutes"], (int, float))
    assert isinstance(result["priority_score"], (int, float))
