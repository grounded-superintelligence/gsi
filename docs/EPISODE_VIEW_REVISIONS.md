# Episode view revisions

An episode keeps the same `episode_id`, `asset_id`, caption, and
`[start_ns,end_ns)` bounds when more synchronized camera views become
available. A `view_revision` describes the exact camera files and calibration
that are ready for that episode.

Four-camera output must use `view_set: "four_view"`. It is not six-camera data
until a new `six_view` revision references all six verified camera files and a
verified six-camera calibration object.

```json
{
  "view_revision": {
    "schema_version": "grounded.episode-views.v1alpha1",
    "revision_id": "viewrev_v1_<derived from exact references>",
    "view_set": "six_view",
    "status": "available",
    "required_cameras": [
      "left_front", "right_front", "left_eye", "right_eye",
      "left_side", "right_side"
    ],
    "cameras": [
      {
        "camera": "left_front",
        "status": "available",
        "lane": "hand",
        "relative_path": "left_front.mp4"
      },
      {
        "camera": "left_side",
        "status": "available",
        "lane": "side_camera",
        "relative_path": "left_side.mp4"
      }
    ],
    "calibration": {
      "lane": "side_camera",
      "relative_path": "camera_params_six_view.npz"
    }
  }
}
```

The abbreviated example omits the other four required camera entries. Each
referenced lane file must publish its URI, byte size, SHA-256, and object
version when available. The SDK rejects missing files, missing checksums,
incorrect readiness labels, and revision IDs that do not match their exact
references.

```python
client = ProcessingClient.from_manifest("episodes.json")
ready = client.is_episode_data_ready(episode_id, view_set="six_view")
revision = client.get_episode_view_revision(episode_id)
```

For legacy manifests without `view_revision`, readiness is unknown and the SDK
returns `False`; it never assumes six-view completeness from filenames alone.
