from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from grounded.data.visualize_hand_3d import _frame_times_ns, _nearest_pose_index, load_tum_trajectory


def test_nonzero_offset_slam_trajectory_keeps_absolute_time_and_world_origin(tmp_path: Path) -> None:
    trajectory = tmp_path / "trajectory.txt"
    trajectory.write_text(
        "\n".join(
            [
                "1234.500000000 4.0 5.0 6.0 0.0 0.0 0.0 1.0",
                "1235.000000000 4.5 5.5 6.5 0.0 0.0 0.0 1.0",
                "1236.000000000 5.0 6.0 7.0 0.0 0.0 0.0 1.0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    times_ns, positions, rotations = load_tum_trajectory(str(trajectory))

    assert times_ns.tolist() == [1_234_500_000_000, 1_235_000_000_000, 1_236_000_000_000]
    np.testing.assert_allclose(positions[0], [4.0, 5.0, 6.0])
    np.testing.assert_allclose(positions[-1], [5.0, 6.0, 7.0])
    np.testing.assert_allclose(rotations, np.repeat(np.eye(3)[None, :, :], 3, axis=0))


def test_nonzero_offset_hand_timebase_matches_absolute_slam_timestamps(tmp_path: Path) -> None:
    lane_dir = tmp_path / "hand"
    lane_dir.mkdir()
    (lane_dir / "timebase.json").write_text(
        json.dumps(
            {
                "captures": [
                    {"source_frame": 700, "t": 1_234_600_000_000},
                    {"source_frame": 701, "t": 1_234_900_000_000},
                    {"source_frame": 702, "t": 1_235_400_000_000},
                ]
            }
        ),
        encoding="utf-8",
    )
    episode = SimpleNamespace(path_manager=SimpleNamespace(lane_dir=str(lane_dir)))
    frame_times = _frame_times_ns(episode)
    slam_times = np.array([1_234_500_000_000, 1_235_000_000_000, 1_236_000_000_000])

    assert frame_times == {
        700: 1_234_600_000_000,
        701: 1_234_900_000_000,
        702: 1_235_400_000_000,
    }
    assert [_nearest_pose_index(slam_times, frame_times[index]) for index in (700, 701, 702)] == [0, 1, 1]
