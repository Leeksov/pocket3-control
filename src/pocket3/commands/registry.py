"""Command & topic registry.

The numeric cmd_set / cmd_id values are NOT yet extracted — they live in the
main DJIMimo binary (PackProviderImpl + the *Action handlers). Each entry below
is a named slot; fill `cmd_set`/`cmd_id`/`payload builder` as they are recovered
by decompiling the corresponding handler.

Handler names come from docs/commands.md (verbatim C++ symbols in DJIMimo).
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable

# Known DUML command-set numbers (DJI-wide; camera/gimbal subsets TO CONFIRM):
#   0x01 common/general, 0x04 camera(FC on drones), 0x1A gimbal, ...
# Osmo Pocket 3 uses its own map — do not assume until confirmed.


@dataclass
class CommandSpec:
    name: str                       # our API name
    handler: str                    # source symbol in DJIMimo
    cmd_set: Optional[int] = None   # to fill from PackProviderImpl / handler
    cmd_id: Optional[int] = None
    build_payload: Optional[Callable[..., bytes]] = None
    note: str = ""

    @property
    def resolved(self) -> bool:
        return self.cmd_set is not None and self.cmd_id is not None


# ---------------------------------------------------------------------------
# CONFIRMED command map: every control command is dispatched as
#   dji::sdk::key::SendActionPack<dji::core::<REQ_TYPE>>(...)
# (RTTI proof in main DJIMimo binary). Full list of REQ types below — these
# ARE the on-wire message identities. cmd_set/cmd_id are the type's constants,
# still to be pulled from the dji_cmd_req fill / SendActionPack instantiation.
# ---------------------------------------------------------------------------
REQ_TYPES = {
    # recording / photo
    "record_video_req":                      "start/stop/precord recording",
    "take_photo_req":                        "shutter (photo)",
    # gimbal
    "action_gimbal_set_reset_req":           "recenter",
    "set_gimbal_control_gimbal_speed_req":   "pan/tilt by speed",
    "action_gimbal_system_param_operate_req": "gimbal system param op",
    "action_gimbal_auto_calibration":        "gimbal calibration",
    "action_gimbal_time_lapse_control_pack": "gimbal timelapse",
    "gimbal_feature_control_pack":           "gimbal feature toggle",
    "set_gimbal_turn_on_off_pack":           "gimbal on/off",
    "gimbal_send_gps_nav_data_pack":         "gps nav data",
    # camera / zoom / liveview
    "set_camera_control_zoom_req":           "zoom",
    "liveview_transmit_ctrl":                "liveview stream on/off",
    "set_live_view_camera_source_new_pack":  "liveview source select",
    "camera_playback_action_pack":           "playback",
    "format_sdcard_req":                     "format SD",
    # gui service (screen menu meta-protocol)
    "gui_service_cmd_pack":                  "gui command",
    "gui_service_cmd_param_get_pack":        "gui param get",
    "gui_service_cmd_param_set_pack":        "gui param set",
    # wifi link
    "wifi_start_req":                        "wifi on",
    "wifi_stop_req":                         "wifi off",
    "wifi_restart_req":                      "wifi restart",
    "wifi_silent_trans_report_status_pack":  "silent-trans status",
    # audio / misc
    "audio_wireless_mic_set_audio_pack":     "mic audio",
    "audio_wireless_mic_set_params_pack":    "mic params",
    "ble_nfc_read_write_pack":               "ble/nfc rw",
    "rc_ios_screen_mirroring_pack":          "screen mirroring",
    "log_export_change_state_pack":          "log export",
    "general_accesslocker_query_state_pack": "access locker",
}

# record_video_req payload (from ctor sub_10206F0D0 defaults + StartRecordAction
# field writes). Struct is little-endian; byte offsets within the req payload:
#   ctor defaults: [0..3]=01 01 02 02, [5..8]=02 00 00 03, [12..13]=0x574D('WM'),
#                  [20..23]=500, byte[6]=runtime device id
#   StartRecord overrides: [+2]=0x02, [+4]=0x03, [+7]=0x01
# NOTE: this is the record_video_req body; the DUML cmd_set/cmd_id wrap is added
# by SendActionPack and is NOT yet numerically confirmed. Do not ship as on-wire
# until cmd_set/cmd_id are pulled.
RECORD_VIDEO_REQ_DEFAULTS = bytes([0x01,0x01,0x02,0x02,0x00,0x02,0x00,0x00,0x03])

# --- P0 catalogue (verified handler names, unresolved bytes) ---
COMMANDS = {
    # recording
    "record_start":  CommandSpec("record_start",  "StartRecordAction"),
    "record_stop":   CommandSpec("record_stop",   "StopRecordAction"),
    "record_stop_precheck": CommandSpec("record_stop_precheck", "StopRecordWithCheckPrecordAction"),
    # gimbal
    "gimbal_recenter": CommandSpec("gimbal_recenter", "ResetGimbalAction"),
    "gimbal_rotate":   CommandSpec("gimbal_rotate",   "RotateByAngleNewAction",
                                   note="pan/tilt by angle; payload = angles+speed"),
    "gimbal_drag":     CommandSpec("gimbal_drag",     "ScreenDragGimbalAction"),
    # live view
    "liveview_toggle": CommandSpec("liveview_toggle", "ToggleCameraLiveViewAction"),
    # zoom / focus
    "zoom_ratio":      CommandSpec("zoom_ratio",      "OpticalZoomModeRatioAction",
                                   note="req: set_camera_control_zoom_req"),
    "focus_area":      CommandSpec("focus_area",      "set_camera_focus_area_req"),
    "focus_mode":      CommandSpec("focus_mode",      "set_body_focus_mode_req"),
    # photo
    "take_photo":      CommandSpec("take_photo",      "take_photo_req"),
    # exposure (req types confirmed by name; bytes pending)
    "set_iso":         CommandSpec("set_iso",         "set_iso_req"),
    "set_shutter":     CommandSpec("set_shutter",     "set_camera_shutter_speed_req"),
    "set_exposure_mode": CommandSpec("set_exposure_mode", "set_camera_exposure_mode_req"),
    "set_ev":          CommandSpec("set_ev",          "set_camera_exposure_compensation_req"),
    "set_white_balance": CommandSpec("set_white_balance", "set_camera_white_balance_req"),
    # video format
    "set_video_format": CommandSpec("set_video_format", "set_camera_video_format_req",
                                    note="resolution+fps in one req"),
    "set_video_codec":  CommandSpec("set_video_codec",  "set_camera_video_coding_standard_req"),
    # storage
    "format_sd":       CommandSpec("format_sd",       "format_sdcard_req"),
    # liveview source
    "liveview_source": CommandSpec("liveview_source", "set_live_view_camera_source_new_pack"),
    # gimbal extras
    "gimbal_speed":    CommandSpec("gimbal_speed",    "set_gimbal_control_gimbal_speed_req",
                                   note="continuous pan/tilt velocity"),
    "gimbal_mode":     CommandSpec("gimbal_mode",     "set_gimbal_mode_req"),
    # gui meta-protocol
    "gui_cmd":         CommandSpec("gui_cmd",         "gui_service_cmd_pack"),
    "gui_param_get":   CommandSpec("gui_param_get",   "gui_service_cmd_param_get_pack"),
    "gui_param_set":   CommandSpec("gui_param_set",   "gui_service_cmd_param_set_pack"),
    # wifi link
    "wifi_start":      CommandSpec("wifi_start",      "wifi_start_req"),
    "wifi_stop":       CommandSpec("wifi_stop",       "wifi_stop_req"),
}

# --- Parameter topics (get/set/subscribe; not Action handlers) ---
# name -> dji::core topic string (see docs/commands.md)
TOPICS = {
    "expo_param":     "dji_topic_data_camera_expo_param",     # ISO / shutter / EV / mode
    "video_param":    "dji_topic_data_camera_video_param_v2",  # resolution / fps
    "video_codec":    "dji_topic_data_camera_cam_video_codec",
    "color_style":    "dji_topic_data_camera_style_filter_status",
    "capture_status": "dji_topic_data_camera_capture_status",
    "storage_info":   "camera_storage_info_push",
    "timecode":       "dji_topic_data_camera_timecode_info",
    "gimbal_attitude": "gimbal_attitude_push",
    "gimbal_state":   "gimbal_state_push",
    "gimbal_capability": "gimbal_capability_push",
    "battery":        "battery_dynamic_info_push",
    "temperature":    "general_temperature_info_set_push",
    "wifi_quality":   "wifi_signal_quality_push",
    "camera_status":  "camera_status_info_push",
}
