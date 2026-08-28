from dispatch.severity import compute_severity


def test_medical_outranks_stranded_at_equal_people_and_wait():
    medical = compute_severity(people_count=4, category="medical", area_risk=0.5,
                                wait_minutes=30, max_people_in_queue=4, max_wait_minutes_in_queue=30)
    stranded = compute_severity(people_count=4, category="stranded", area_risk=0.5,
                                 wait_minutes=30, max_people_in_queue=4, max_wait_minutes_in_queue=30)
    assert medical["severity"] > stranded["severity"]


def test_more_people_scores_higher_when_normalised_against_the_queue_max():
    small = compute_severity(people_count=2, category="stranded", area_risk=0.3,
                              wait_minutes=10, max_people_in_queue=10, max_wait_minutes_in_queue=10)
    large = compute_severity(people_count=10, category="stranded", area_risk=0.3,
                              wait_minutes=10, max_people_in_queue=10, max_wait_minutes_in_queue=10)
    assert large["severity"] > small["severity"]
    assert large["sev_people"] == 0.30  # at the queue max, gets the full weight


def test_components_sum_to_the_total():
    result = compute_severity(people_count=3, category="evacuation", area_risk=0.6,
                               wait_minutes=15, max_people_in_queue=5, max_wait_minutes_in_queue=40)
    total = result["sev_people"] + result["sev_category"] + result["sev_area_risk"] + result["sev_wait"]
    assert result["severity"] == total


def test_zero_queue_max_does_not_divide_by_zero():
    result = compute_severity(people_count=0, category="stranded", area_risk=0.0,
                               wait_minutes=0, max_people_in_queue=0, max_wait_minutes_in_queue=0)
    assert result["sev_people"] == 0.0
    assert result["sev_wait"] == 0.0
