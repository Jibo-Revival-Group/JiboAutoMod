# JiboOS V3.1 – Config locations inventory (for SSH tooling)

This workspace is a filesystem tree under `build/`. Most paths below are **absolute paths as they exist on the robot**.

If you’re using this repo as a staging image, the mapping is:

- Workspace path: `build/<ABS_PATH>`
- Robot path: `<ABS_PATH>`

Example: `build/usr/local/etc/jibo-jetstream-service.json` corresponds to `/usr/local/etc/jibo-jetstream-service.json` on-robot.

---

## Highest-level “what runs what”

### `/usr/local/etc/jibo-system-manager.json`

**Purpose:** Master orchestrator config. Defines the service startup order, executables, arguments (including which `-c /usr/local/etc/<service>.json` is used), environment variables, and some device-level settings.

**Why your tooling should care:** if you need to know **which process** consumes a config file, this is the authoritative mapping.

Notable sections:

- `SystemManager.service.services[]`
  - `name`, `executable`, `modes.<mode>.arguments` (usually includes the config file path)
  - `modes.<mode>.enabled` (turn a service on/off per mode)
- `SystemManager.skills.environment`
  - `JIBO_HUB_SHIM_HOST` (host/port target for the hub shim)
  - `JIBO_GQA_ENDPOINT` (HTTP endpoint used by the optional GQA shim)
- `credentials.path`: `/var/jibo/credentials.json` (runtime config; controls region selection in Jetstream)
- `wifi.*` (wpa_supplicant + DHCP client options)
- `time.*` (timezone/localtime paths and NTP sync)

**Apply/restart:** system-manager itself (how depends on your init/systemd on the robot). Most changes only take effect on service restart or reboot.

---

## Core robot service configs (`/usr/local/etc/*.json`)

These are the main knobs for the robot’s built-in services. Many follow this pattern:

- `WebCore.serverPort`: HTTP port for the service
- `<ServiceName>.registryPort`: service registry port (usually `8181`)
- `logging.*`: log levels / syslog routing

### `/usr/local/etc/jibo-service-registry.json`

**Purpose:** Service registry / management web endpoints.

- Ports: `8181` (`WebCore.serverPort`, `ServiceRegistry.registryPort`)

**Apply/restart:** restart `jibo-service-registry`.

### `/usr/local/etc/jibo-jetstream-service.json`

**Purpose:** Jetstream (hub client + streaming audio + wakeword/ASR pipeline glue).

Key knobs:

- `HubClient.override`: where Jetstream sends `/v1/listen` and friends.
  - `hub_hostname`, `hub_port`
  - Use this to point Jetstream to a **local or server-hosted hub shim**.
- `HubClient.listen_language`
- `HubClient.encoding_type` + `encoding-settings`: `OGG_OPUS` / `FLAC` settings
- `RecogHJ`, `HubAsr`: timing for SOS/EOS and max speech timeouts

**Apply/restart:** restart `jibo-jetstream-service`.

### `/usr/local/etc/jibo-asr-service.json`

**Purpose:** On-robot ASR service (WebSocket event stream + HTTP start/stop), logging, cloud/local STT selection.

Key knobs:

- `webCore.serverPort`: `8088`
- `AsrService.language`
- `AsrService.log_audio`, `log_text`, `log_path`, upload intervals/thresholds
- `AsrService.resident_task` / `resident_audio_channel`: default always-on hotphrase task (e.g. `audio_source_id":"alsa1"`)
- `AsrService.task_templates`: defines ASR pipelines

**Apply/restart:** restart `jibo-asr-service`.

Note: this file contains cloud credentials/keys in this build tree. Treat it as sensitive in your tooling (avoid echoing it into logs).

### `/usr/local/etc/jibo-tts-service.json`

**Purpose:** On-robot TTS voice + audio output.

Key knobs:

- `webCore.serverPort`: `8089`
- `TTSService.resourcePath`: voice resources
- `TTSService.alsaPlaybackDevice`: playback routing
- `voiceParams.*`: speed, volume, max chars, etc.

**Apply/restart:** restart `jibo-tts-service`.

### `/usr/local/etc/jibo-nlu-service.json`

**Purpose:** NLU service (local grammar/model parsing).

Key knobs:

- `webCore.serverPort`: `8787`
- `Service.nlu_data_dir`: NLU model data
- `Service.default_locale`

**Apply/restart:** restart `jibo-nlu-service`.

### `/usr/local/etc/jibo-audio-service.json`

**Purpose:** Audio routing/capture/playback device selection and audio processing thresholds.

Key knobs:

- `WebCore.serverPort`: `8383`
- `AudioService.alsaCaptureDevice`, `alsaPlaybackDevice`
- `AudioService.router*` latencies
- `AudioService.kinematic_model`: points to `/usr/local/etc/jibo-kinematic-model.json`

**Apply/restart:** restart `jibo-audio-service`.

### `/usr/local/etc/jibo-body-service.json`

**Purpose:** Low-level body control: serial devices, offsets, limits, battery thresholds, IMU calibration path.

Key knobs:

- `WebCore.serverPort`: `8282`
- `bodyBoard.*`: `/dev/ttyTHS0/1` devices, offsets, flipped flags, accel/vel limits
- `imu.driver.calibrationFile`: `/var/jibo/imu/imu-cal.json` (runtime file)
- `BodyService.kinematic_model`: points to `/usr/local/etc/jibo-kinematic-model.json`

**Apply/restart:** restart `jibo-body-service`.

### `/usr/local/etc/jibo-kinematic-model.json`

**Purpose:** Robot kinematic model (frame transforms, masses, inertias). Used by audio/body/LPS.

**Apply/restart:** restart consumers (at least `jibo-body-service`, `jibo-audio-service`, and `jibo-lps-service`).

### `/usr/local/etc/jibo-media-service.json`

**Purpose:** Media service camera configuration (CUDA/V4L2 device paths, capture params).

Key knobs:

- `WebCore.serverPort`: `7979`
- `MediaService.camera.*`: `/dev/video0`, `/dev/video1`, flips, AE/AWB tuning

**Apply/restart:** restart `jibo-media-service`.

### `/usr/local/etc/jibo-lps-service.json`

**Purpose:** LPS (Local Perception System) + internal media subsystem + visual awareness pipeline.

Key knobs:

- `WebCoreLPS.serverPort`: `8484`
- `CaptureSubsystem.camera_config_file`: `/usr/local/etc/lps/cameras.json`
- `EngineSubsystem.schemas.*`: `/usr/local/etc/lps/schemas/{normal,focused,minimal}.json`
- `EngineSubsystem.engine.state.entity_config_file`: `/usr/local/etc/lps/entityConfig.json`
- `EngineSubsystem.engine.state.geometry.*`: camera model params in `/var/jibo/lps/*.json` (runtime files)

**Apply/restart:** restart `jibo-lps-service`.

### `/usr/local/etc/lps/cameras.json`

**Purpose:** Camera device list + CUDA capture config + controls presets.

**Apply/restart:** restart `jibo-lps-service` (and anything using the same capture stack).

### `/usr/local/etc/lps/entityConfig.json`

**Purpose:** Entity tracking parameters (people/head tracking, confidence thresholds, trackers, etc.).

**Apply/restart:** restart `jibo-lps-service`.

### `/usr/local/etc/lps/schemas/normal.json`
### `/usr/local/etc/lps/schemas/focused.json`
### `/usr/local/etc/lps/schemas/minimal.json`

**Purpose:** LPS “schema” graphs: which detectors/actions run and at what cadence.

**Apply/restart:** restart `jibo-lps-service`.

### `/usr/local/etc/jibo-identity-service.json`

**Purpose:** Identity/face recognition engine + model paths.

Key knobs:

- `WebCore.serverPort`: `8489`
- `IdentityService.engine.identifier.*`: choose identifier type (deepid/eigenfaces/resnetfaceid) and model paths
- Storage path: `/var/jibo/identity/*` (runtime)

**Apply/restart:** restart `jibo-identity-service`.

### `/usr/local/etc/jibo-server-service.json`

**Purpose:** Cloud/server connection service + notifications.

- `WebCore.serverPort`: `8888`
- `NotificationSubsystem.serverURLSuffix`

**Apply/restart:** restart `jibo-server-service`.

### `/usr/local/etc/jibo-service-center-service.json`

**Purpose:** Service-center web UI/service.

- `WebCore.serverPort`: `9797`

**Apply/restart:** restart `jibo-service-center-service`.

### `/usr/local/etc/jibo-certification-service.json`

**Purpose:** Certification service.

- `WebCore.serverPort`: `9292`

**Apply/restart:** restart `jibo-certification-service`.

### `/usr/local/etc/jibo-system-monitoring-service.json`

**Purpose:** System health/storage monitoring + health log upload.

Key knobs:

- `WebCore.serverPort`: `4111`
- `SystemMonitoringService.storage.semantic`: path aliases used for reporting
- `health.upload.arguments`: uses `/var/jibo/credentials.json` (runtime)

**Apply/restart:** restart `jibo-system-monitoring-service`.

### `/usr/local/etc/jibo-test-capture-service.json`

**Purpose:** Camera capture tools service (debug/QA).

- `WebCore.serverPort`: `7979` (note: overlaps with `jibo-media-service.json` in this tree; only one should bind a given port at runtime)

**Apply/restart:** restart `jibo-test-capture-service`.

### `/usr/local/etc/jibo-test-capture.json`

**Purpose:** Test capture tool runtime behavior (recording toggles, lock counts, display/profiler options).

**Apply/restart:** whatever tool/runner loads it (not a standard service config; used by capture tooling).

### `/usr/local/etc/jibo-camera-calibrator.json`

**Purpose:** Camera calibration workflow + capture device selection. Writes calibration outputs into `/var/jibo/lps`.

**Apply/restart:** used by the calibrator tool; changes apply on next run.

### `/usr/local/etc/jibo-hub-shim.json`

**Purpose:** Robot-local hub shim config (for running the shim on the robot).

Key knobs:

- `listen.*`: bind/port/path for `/v1/listen`
- `asrService.baseUrl`: typically `http://127.0.0.1:8088` on-robot

**Apply/restart:** restart the hub-shim process (not a core Jibo service; depends on your deployment).

### `/usr/local/etc/jibo-sts.json`

**Purpose:** Placeholder config for secure-transfer (STS). In this tree it is currently empty.

**Apply/restart:** N/A (service may use defaults or other config sources).

---

## SSM / robot “mode” configuration (`/usr/local/etc/jibo-ssm/*.json`)

These files configure the Node-based SSM (service supervisor/skill launcher) and its ports per robot mode.

- `/usr/local/etc/jibo-ssm/jibo-ssm-normal.json`
- `/usr/local/etc/jibo-ssm/jibo-ssm-oobe.json`
- `/usr/local/etc/jibo-ssm/jibo-ssm-developer.json`
- `/usr/local/etc/jibo-ssm/jibo-ssm-int-developer.json`

Common knobs:

- `services.SkillsService.port` (HTTP port; typically `8779`)
- `services.DevShell.*` (developer ports: `8686/8989/9191`) (developer/int-developer)
- `services.WifiService.region` (e.g. `api`)
- `RegistryClient.host/port` (usually `127.0.0.1:8181`)
- `logging.namespaces` (fine-grained log routing)

**Apply/restart:** restart SSM / the Node process that loads these configs.

---

## Hub shim (server-hosted) config

This is for the PC/server side shim that emulates the hub `/v1/listen` endpoint.

Workspace source:

- `hub-shim/config.example.json` (template)
- `hub-shim/config.json` (local dev)
- `hub-shim/systemd/jibo-hub-shim.service` (service unit)
- `hub-shim/systemd/jibo-hub-shim.env.example` (env file template)

Server install locations (created by `hub-shim/install-server.sh`):

- `/opt/jibo-hub-shim/` (code)
- `/etc/jibo-hub-shim/config.json` (config)
- `/etc/jibo-hub-shim/jibo-hub-shim.env` (sets `JIBO_HUB_SHIM_CONFIG=/etc/jibo-hub-shim/config.json`)
- `/etc/systemd/system/jibo-hub-shim.service`

Key knobs in the shim config JSON:

- `listen.bindHost`, `listen.port`, `listen.path`
- `asrService.baseUrl`: robot ASR base URL (e.g. `http://<robot-ip>:8088` if shim runs off-robot)
- `asrService.audioSourceId`: commonly `alsa1` on-robot
- `asrService.timeoutMs`
- `gqaShim.enabled` + `gqaShim.ollama.*`: optional Ollama-backed “GQA shim” HTTP service

**Apply/restart:** `systemctl restart jibo-hub-shim` (server). For local dev: restart `node index.js ./config.json`.

---

## AI bridge (PC-side) configuration

### PC server (Python)

- `ai_bridge_server/server.py`

Config sources:

- CLI args: `--host`, `--port` (default run example uses `0.0.0.0:8020`)
- Env vars:
  - `OLLAMA_URL` (default `http://127.0.0.1:11434/api/chat`)
  - `OLLAMA_MODEL` (default `phi3.5`)
  - `WHISPER_MODEL` (default `base`) (audio endpoint only)

**Apply/restart:** restart the Python process.

### Robot-side AI bridge client config

- `/opt/jibo/Jibo/Skills/@be/be/be/ai-bridge-config.json`

Key knobs:

- `enabled`
- `mode`: `TEXT` or `AUDIO`
- `serverBaseUrl`: your PC’s bridge server URL (e.g. `http://<pc-ip>:8020`)
- ASR integration:
  - `useAsrServiceStt`, `asrServiceHost`, `asrServicePort`, `asrAudioSourceId`, `asrTimeoutMs`, `asrAutoStart`
- Behavior:
  - `wakeupChitchatPhrases[]`
  - `followupEnabled`, `followupDelayMs`
  - `aiForwardingAllowedSkills[]` gating

**Apply/restart:** restart the SkillsService / BE skill (or reboot).

Related dev-only override:

- `/opt/jibo/Jibo/Skills/@be/be/be/jibo-asr-service.local.json` (local-run ASR config variant)

---

## Skills menu / content configs (skill-layer “settings”)

These are not OS-level services, but they are **configuration surfaces** for skill UI/menu behavior.

- `/opt/jibo/Jibo/Skills/@be/menu-entries.d/*.json`
  - Defines top-level menu entries/submenus (e.g. `childrenDir` points at a skill folder containing `menuEntry.json`).
- `/opt/jibo/Jibo/Skills/*/menuEntry.json`
  - Declares skill menu metadata (title/hidden/etc.).
- `/opt/jibo/Jibo/Skills/@be/be/menu/menus/*.json`
  - Defines button menus (labels/icons/utterances + hit area polygon).

**Apply/restart:** restart SkillsService / reload the menu skill.

---

## Init scripts and env-tunable configs (`/etc/init.d/*`)

These scripts are often the real place where **ports and file paths** are chosen, via environment variables.

### `/etc/init.d/S04jibo-asr-service`

- Launches: `/usr/local/bin/jibo-asr-service -c /usr/local/etc/jibo-asr-service.json`
- PID file: `/var/run/jibo-asr-service.pid`
- Log: `/tmp/jibo-asr-service.log`

### `/etc/init.d/S02jibo-skills-logd`

Skills UDP log daemon.

Env vars:

- `JIBO_LOGD_HOST` (default `127.0.0.1`)
- `JIBO_LOGD_PORT` (default `15140`)
- `JIBO_LOGD_FILE` (default `/tmp/jibo-skills.log`)

### `/etc/init.d/S03jibo-skills-logpanel`

Skills web log panel.

Env vars:

- `JIBO_LOGPANEL_BIND` (default `0.0.0.0`)
- `JIBO_LOGPANEL_PORT` (default `15150`)
- `JIBO_LOGD_FILE` (shared logfile path)

### `/etc/init.d/S21firewall`

Firewall rules (iptables). Not JSON, but it is a major “settings surface”.

- Always allows SSH port `22`
- Also explicitly allows SkillsService panel `8779` and log panel `15150`
- Opens additional ports based on the current mode via `/usr/bin/jibo-getmode`

**Apply:** run the init script (restart) or reboot.

---

## Runtime-created or runtime-edited config files (referenced by the above)

These are not present in this build tree, but the services above reference them. Your SSH tooling will often want to read/edit these too.

- `/var/jibo/credentials.json`
  - Used for: Jetstream `region-settings` selection; system health upload credentials.
- `/var/jibo/imu/imu-cal.json`
  - Used for: BodyService IMU calibration.
- `/var/jibo/lps/CameraModelParamsL.json`
- `/var/jibo/lps/CameraModelParamsR.json`
- `/var/jibo/lps/InterCameraTransform.json`
  - Used for: LPS geometry.
- `/var/etc/timezone`, `/var/etc/localtime`
  - Used for: system timezone.

---

## Quick port index (useful for “is my edit live?” checks)

From configs in this tree:

- Service registry: `8181`
- Body: `8282`
- Audio: `8383`
- Jetstream: `8090`
- ASR: `8088`
- TTS: `8089`
- NLU: `8787`
- Identity: `8489`
- LPS: `8484` (and internal media `8486`)
- Media: `7979`
- Server service: `8888`
- System manager: `8585`
- System monitoring: `4111`
- Service center: `9797`
- Certification: `9292`
- Skills service: `8779` (SSM)
- Skills logd: UDP `15140`
- Skills log panel: `15150`
- Hub shim (this project): `9000` (server-side shim)
- AI bridge server (PC): `8020`

---

## Suggested conventions for your editor tool

- Always read/parse JSON with comment tolerance disabled (these are strict JSON files).
- Treat these keys as “high risk” and avoid accidentally printing them:
  - Anything containing `appkey`, `key`, `credential`, `password`, `token`.
- After edits:
  - Restart only the owning service (see sections above).
  - Prefer `system-manager` / SSM restart only when necessary.
