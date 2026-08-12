import inspect

from grounded.data.visualize_hand import _visualize_hand_episode_to_mp4


def test_cleaning_rejected_fits_are_hidden_by_default() -> None:
    signature = inspect.signature(_visualize_hand_episode_to_mp4)

    assert signature.parameters["show_invalid"].default is False
