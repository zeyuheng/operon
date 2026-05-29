from app.services.election_data_service import ElectionDataService
from app.services.sports_data_service import infer_nba_team_alias, parse_espn_standings_ratings


def test_election_service_parses_matching_primary_polls() -> None:
    csv_text = (
        "candidate_name,pct,sample_size,end_date,numeric_grade\n"
        "Gavin Newsom,24,1200,05/01/26,2.5\n"
        "Kamala Harris,31,1200,05/01/26,2.5\n"
    )

    polls = ElectionDataService()._parse_primary_polls(csv_text, "Gavin Newsom")

    assert len(polls) == 1
    assert polls[0].support == 0.24
    assert polls[0].sample_size == 1200


def test_sports_service_infers_nba_team_alias() -> None:
    assert infer_nba_team_alias("Will the Oklahoma City Thunder win the NBA Finals?") == "okc"


def test_sports_service_parses_espn_team_records() -> None:
    payload = {
        "children": [
            {
                "standings": {
                    "entries": [
                        {
                            "team": {
                                "displayName": "Oklahoma City Thunder",
                                "abbreviation": "OKC",
                            },
                            "stats": [
                                {"name": "wins", "value": 64},
                                {"name": "losses", "value": 18},
                            ],
                        },
                        {
                            "team": {
                                "displayName": "Boston Celtics",
                                "abbreviation": "BOS",
                            },
                            "stats": [
                                {"name": "wins", "value": 55},
                                {"name": "losses", "value": 27},
                            ],
                        },
                    ]
                }
            }
        ]
    }

    ratings = parse_espn_standings_ratings(payload, "okc")

    assert ratings[0].team == "Oklahoma City Thunder"
    assert ratings[0].rating > ratings[1].rating
