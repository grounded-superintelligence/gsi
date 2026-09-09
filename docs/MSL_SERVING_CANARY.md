# MSL serving canary

This is the minimum handoff for a frozen episode delivery. It does not select
or materialize the final dataset.

## Pin the SDK

Until a signed release tag is published, install the exact tested commit:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install \
  "git+https://github.com/grounded-superintelligence/grounded.git@118208f5bec2792b0ee2b3e08230f2bc53efe41c"
```

The delivery consists of a local `grounded.episode.v1alpha1` JSON manifest,
its separately published SHA-256, and permission to read every exact object
listed in the manifest. A manifest can instead contain short-lived presigned
HTTPS URLs when AWS credentials are not appropriate.

## Enumerate and download the delivery

```python
from grounded.data.processing import ProcessingClient

client = ProcessingClient.from_manifest("msl-episodes.json", aws_profile="msl")
episodes = client.list_episodes()
print(f"{len(episodes)} episodes")

for episode in episodes:
    result = client.download_episode(
        episode.episode_id,
        target_dir="./msl-cache",
        require_sha256=True,
    )
    print(episode.episode_id, [(lane.lane, lane.status) for lane in result.lanes])
```

Downloads are deterministic and cached. Each file is checked against its
published size and SHA-256, written through a `.part` file, and atomically
renamed. Re-running the same command reuses matching files without contacting
object storage.

To make an offline copy, copy both `msl-episodes.json` and the complete
`msl-cache/` directory. Keep the same `target_dir` root when reopening it.
The manifest still supplies identity and checksums; the cache supplies the
bytes.

## Render one episode

From an SDK source checkout:

```bash
python demo.py \
  --manifest msl-episodes.json \
  --episode ep_v1_... \
  --aws-profile msl \
  --target-dir ./msl-cache \
  --cameras left_front right_front left_eye right_eye \
  --downsample 2 \
  --num-workers 4
```

This writes an overlaid MP4 and a Rerun `.rrd`. When the episode has a valid
SLAM lane, the `.rrd` places the left-front camera and Hand geometry in the
original SLAM world frame.

## Producer gate

Each episode must be materialized before it is served. A source-reference row
that only names a parent Hand archive and time interval is not directly
viewable by this SDK version.

For each episode, require:

- canonical `episode_id`, parent `asset_id`, and `[start_ns,end_ns)` in the
  shared absolute `sensor_ns` clock;
- an exact Hand lane containing its `clip_manifest.json`, `pose_frames.tar`,
  declared camera MP4s, `camera_params.npz`, and `timebase.json`;
- an exact SLAM lane containing a producer-clipped TUM `trajectory.txt` and
  clip manifest;
- original absolute SLAM timestamps and original world poses, never rebased to
  episode time zero or a new spatial origin;
- SLAM samples that cover the episode bounds and Hand timestamps that map to
  the same sensor clock;
- exact byte counts and SHA-256 checksums for every downloadable file; and
- explicit lane status for Hand, SLAM, and Depth, with no placeholder files for
  unavailable lanes.

The final MSL population, manifest, storage prefix, and permissions remain a
separate release decision. Run this gate first on one nonzero-offset episode,
then on 5 to 10 episodes before scaling the export.
