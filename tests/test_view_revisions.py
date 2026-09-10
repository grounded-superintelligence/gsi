from __future__ import annotations

import hashlib

import pytest

from grounded.data.processing import (
    CORE_EPISODE_CAMERAS,
    EPISODE_CONTRACT_VERSION,
    EPISODE_VIEW_REVISION_VERSION,
    SIDE_EPISODE_CAMERAS,
    EpisodeCameraReference,
    JsonEpisodeResolver,
    ProcessingClient,
    ProcessingError,
    _expected_episode_id,
    _expected_view_revision_id,
)


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _file(relative_path: str, payload: bytes, *, lane: str) -> dict:
    return {
        "relative_path": relative_path,
        "uri": f"https://downloads.example.test/{lane}/{relative_path}",
        "size_bytes": len(payload),
        "sha256": _sha(payload),
        "version_id": f"version-{relative_path}",
    }


def _six_view_contract() -> dict:
    asset_id = "ast_v1_six_view_example"
    start_ns = 10_000_000_000
    end_ns = 16_000_000_000
    episode_id = _expected_episode_id(asset_id=asset_id, start_ns=start_ns, end_ns=end_ns)
    hand_files = [_file(f"{camera}.mp4", camera.encode(), lane="hand") for camera in CORE_EPISODE_CAMERAS]
    side_files = [_file(f"{camera}.mp4", camera.encode(), lane="side_camera") for camera in SIDE_EPISODE_CAMERAS]
    calibration_file = _file("camera_params_six_view.npz", b"six camera calibration", lane="side_camera")
    timebase_file = _file("side_sync_manifest.json", b"sensor clock mapping", lane="side_camera")
    lanes = [
        {"lane": "hand", "status": "available", "files": hand_files},
        {"lane": "slam", "status": "not_processed", "files": []},
        {"lane": "depth", "status": "not_processed", "files": []},
        {
            "lane": "side_camera",
            "status": "available",
            "files": [*side_files, calibration_file, timebase_file],
            "provenance": {"run_id": "side-run", "job_id": "side-job"},
        },
    ]
    cameras = tuple(
        EpisodeCameraReference(
            camera=camera,
            status="available",
            lane="hand" if camera in CORE_EPISODE_CAMERAS else "side_camera",
            relative_path=f"{camera}.mp4",
            sha256=_sha(camera.encode()),
            size_bytes=len(camera.encode()),
            version_id=f"version-{camera}.mp4",
            frame_count=180,
            projection_model="source_original" if camera in SIDE_EPISODE_CAMERAS else "undistorted_pinhole",
            distortion_model="fisheye" if camera in SIDE_EPISODE_CAMERAS else "none",
            calibration_key=camera,
        )
        for camera in (*CORE_EPISODE_CAMERAS, *SIDE_EPISODE_CAMERAS)
    )
    revision_id = _expected_view_revision_id(
        episode_id=episode_id,
        view_set="six_view",
        cameras=cameras,
        calibration_lane="side_camera",
        calibration_relative_path="camera_params_six_view.npz",
        calibration_sha256=calibration_file["sha256"],
        calibration_version_id=calibration_file["version_id"],
        timebase_lane="side_camera",
        timebase_relative_path="side_sync_manifest.json",
        timebase_sha256=timebase_file["sha256"],
        timebase_version_id=timebase_file["version_id"],
    )
    return {
        "schema_version": EPISODE_CONTRACT_VERSION,
        "episode": {
            "episode_id": episode_id,
            "asset_id": asset_id,
            "caption": "Moves an object between two containers.",
            "interval": {
                "start_ns": start_ns,
                "end_ns": end_ns,
                "clock": "sensor_ns",
                "bounds": "[start_ns,end_ns)",
            },
            "lanes": lanes,
            "view_revision": {
                "schema_version": EPISODE_VIEW_REVISION_VERSION,
                "revision_id": revision_id,
                "view_set": "six_view",
                "status": "available",
                "required_cameras": [*CORE_EPISODE_CAMERAS, *SIDE_EPISODE_CAMERAS],
                "cameras": [
                    {
                        "camera": camera,
                        "status": "available",
                        "lane": "hand" if camera in CORE_EPISODE_CAMERAS else "side_camera",
                        "relative_path": f"{camera}.mp4",
                        "frame_count": 180,
                        "geometry": {
                            "projection_model": (
                                "source_original" if camera in SIDE_EPISODE_CAMERAS else "undistorted_pinhole"
                            ),
                            "distortion_model": "fisheye" if camera in SIDE_EPISODE_CAMERAS else "none",
                            "calibration_key": camera,
                        },
                    }
                    for camera in (*CORE_EPISODE_CAMERAS, *SIDE_EPISODE_CAMERAS)
                ],
                "calibration": {
                    "lane": "side_camera",
                    "relative_path": "camera_params_six_view.npz",
                },
                "timebase": {
                    "clock": "sensor_ns",
                    "lane": "side_camera",
                    "relative_path": "side_sync_manifest.json",
                },
                "provenance": {"side_view_receipt_id": "receipt-123"},
            },
        },
    }


def test_six_view_revision_preserves_episode_identity_and_reports_ready() -> None:
    contract = _six_view_contract()
    client = ProcessingClient(episode_resolver=JsonEpisodeResolver(contract))
    expected = contract["episode"]

    episode = client.get_episode(expected["episode_id"])
    revision = episode.view_revision

    assert episode.asset_id == expected["asset_id"]
    assert (episode.start_ns, episode.end_ns) == (
        expected["interval"]["start_ns"],
        expected["interval"]["end_ns"],
    )
    assert episode.caption == expected["caption"]
    assert revision is not None
    assert revision.view_set == "six_view"
    assert revision.available_cameras == (*CORE_EPISODE_CAMERAS, *SIDE_EPISODE_CAMERAS)
    assert revision.calibration_sha256 == _sha(b"six camera calibration")
    assert revision.timebase_sha256 == _sha(b"sensor clock mapping")
    assert revision.cameras[-1].projection_model == "source_original"
    assert revision.cameras[-1].distortion_model == "fisheye"
    assert revision.provenance == {"side_view_receipt_id": "receipt-123"}
    assert client.is_episode_data_ready(episode.episode_id, view_set="six_view")
    assert not client.is_episode_data_ready(episode.episode_id, view_set="four_view")


def test_legacy_episode_is_not_silently_counted_as_six_view_ready() -> None:
    contract = _six_view_contract()
    del contract["episode"]["view_revision"]
    client = ProcessingClient(episode_resolver=JsonEpisodeResolver(contract))
    episode_id = contract["episode"]["episode_id"]

    assert client.get_episode_view_revision(episode_id) is None
    assert not client.is_episode_data_ready(episode_id, view_set="six_view")


def test_six_view_revision_rejects_missing_side_file() -> None:
    contract = _six_view_contract()
    side_lane = next(lane for lane in contract["episode"]["lanes"] if lane["lane"] == "side_camera")
    side_lane["files"] = [file for file in side_lane["files"] if file["relative_path"] != "right_side.mp4"]

    with pytest.raises(ProcessingError, match="right_side.*references no downloadable lane file"):
        JsonEpisodeResolver(contract)


def test_six_view_revision_rejects_tampered_revision_id() -> None:
    contract = _six_view_contract()
    contract["episode"]["view_revision"]["revision_id"] = "viewrev_v1_tampered"

    with pytest.raises(ProcessingError, match="revision ID does not match exact media references"):
        JsonEpisodeResolver(contract)


def test_six_view_revision_rejects_unhashed_camera_object() -> None:
    contract = _six_view_contract()
    hand_lane = next(lane for lane in contract["episode"]["lanes"] if lane["lane"] == "hand")
    hand_lane["files"][0]["sha256"] = ""

    with pytest.raises(ProcessingError, match="left_front.*must publish SHA-256"):
        JsonEpisodeResolver(contract)


def test_six_view_revision_rejects_side_view_as_pinhole() -> None:
    contract = _six_view_contract()
    side = contract["episode"]["view_revision"]["cameras"][-1]
    side["geometry"] = {
        "projection_model": "undistorted_pinhole",
        "distortion_model": "none",
        "calibration_key": "right_side",
    }

    with pytest.raises(ProcessingError, match="right_side projection_model must be 'source_original'"):
        JsonEpisodeResolver(contract)


def test_six_view_revision_requires_exact_sensor_clock_mapping() -> None:
    contract = _six_view_contract()
    contract["episode"]["view_revision"]["timebase"]["clock"] = "fps"

    with pytest.raises(ProcessingError, match="timebase clock must be sensor_ns"):
        JsonEpisodeResolver(contract)
