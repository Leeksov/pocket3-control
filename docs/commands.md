# Pocket 3 — каталог команд и состояний (v0.2, из строк главного бинаря)

Два механизма:
1. **Action-хендлеры** (`dji::sdk::key::KeyHandlers`) — императивные операции: `XxxAction(KeyHandlers*, const Characteristics&, const DJIValuePtr&, const ActionCallback&)`.
2. **Topic/Pack pub-sub** (`dji::core`) — get/set/subscribe параметров и приём состояния. Суффиксы: `_req` (запрос), `_pack` (get/set пакет), `_push` (сервер→клиент событие).

Числовые cmdset/cmdid ещё **не извлечены** (нужна декомпиляция `PackProviderImpl` и конкретных Action'ов в главном бинаре).

---

## P0 — команды (Action)
| Action | Назначение | Приоритет |
|---|---|---|
| `StartRecordAction` | начать запись | P0 |
| `StopRecordAction`, `StopRecordWithCheckPrecordAction` | остановить запись | P0 |
| `FinishAutoRecAction` | завершить авто-запись | P0 |
| `ResetGimbalAction` | рецентр подвеса | P0 |
| `RotateByAngleNewAction` | поворот подвеса на угол (pan/tilt) | P0 |
| `ScreenDragGimbalAction` | управление подвесом «перетаскиванием» | P0 |
| `SubGimbalCapAction` | подписка на возможности подвеса | P0 |
| `OpticalZoomModeRatioAction` | зум | P1 |
| `ToggleCameraLiveViewAction` | вкл/выкл live view | P0 |
| `EnterPlayBackAction` / `ExitPlayBackAction` | режим воспроизведения | P2 |

Прочие Action (не для P0): аккаунт/binding (`BindAccountWithDeviceAction`…), беспроводной микрофон (`WlMicPairOprAction`, `MicCreatePasswordAction`…), NFC, super-slow-motion, ремукс медиа, screen mirroring, страховка. — по ТЗ §27 в основном игнор.

## Gimbal — req-пакеты
- `action_read_gimbal_params_req` — чтение параметров подвеса
- `set_gimbal_params_req` — установка параметров подвеса
- `action_gimbal_system_param_operate_req` — системные операции подвеса

## Camera параметры — topic/pack (get/set/subscribe)
| Topic | Содержит |
|---|---|
| `dji_topic_data_camera_expo_param` | экспозиция: ISO / shutter / EV / режим |
| `dji_topic_data_camera_photo_param`, `_photo_param_new` | параметры фото |
| `dji_topic_data_camera_video_param`, `_video_param_v2`, `_multi_video_param` | разрешение / fps / видео |
| `dji_topic_data_camera_cam_video_codec` | кодек (H.264/H.265), битрейт |
| `dji_topic_data_camera_style_filter_status` | цветовой профиль / LUT / D-Log |
| `dji_topic_data_camera_capture_status`, `camera_capture_param_push` | режим/статус съёмки |
| `dji_topic_data_camera_lapse_param`, `_motion_lapse_params` | таймлапс |
| `dji_topic_data_camera_timecode_info`, `_timecode_status` | таймкод |
| `dji_topic_data_camera_lens_state`, `_magnifier_status` | фокус / линза |
| `dji_topic_data_camera_super_slow_motion_status` | слоу-мо |
| `camera_storage_info_push`, `dji_topic_data_camera_storage_info` | SD/хранилище |
| `camera_video_filename_push` | имя текущего файла |
| `set_camera_expansion_cmd_pack`, `camera_expansion_cmd_ff_push` | расширенные команды |
| `get_camera_audio_param_req` / `set_camera_audio_param_req`, `dji_topic_data_camera_audio_status(_v2)` | аудио/микрофон |

## Capability negotiation (§18) — камера сама сообщает возможности
- `gimbal_capability_push` — возможности подвеса
- `dji_topic_data_camera_cam_photo_size_range_info` — диапазоны размеров фото
- `dji_topic_data_camera_custom_mode_params` — кастомные режимы
- `dji_topic_data_firmware_support_info` — что поддерживает прошивка
- `dji_topic_data_camera_vq_enhancement_info`, `_build_in_beauty_info`
⇒ **не хардкодить** значения — читать capability-топики.

---

## Состояния и push-события (§23 — на что подписываемся)
| Push | Событие |
|---|---|
| `camera_status_info_push` | общий статус камеры (вкл/режим) |
| `dji_topic_data_camera_capture_status` | started/stopped запись, фото |
| `dji_topic_data_camera_expo_param` | изменение ISO/shutter/EV |
| `camera_storage_info_push` | изменение хранилища |
| `dji_topic_data_camera_timecode_status` | таймкод |
| `gimbal_attitude_push` | текущий attitude (pan/tilt/roll) |
| `gimbal_state_push` | состояние подвеса |
| `gimbal_lock_status_push`, `gimbal_calibration_status_push` | блок/калибровка |
| `gimbal_handheld_stick_state_push` | состояние джойстика |
| `battery_dynamic_info_push`, `center_battery_common_info_push` | батарея |
| `general_temperature_info_set_push`, `dji_topic_data_temp_curve_info` | температура |
| `wifi_signal_quality_push` | качество Wi-Fi |
| `genera_selftest_push` | самотест |
| `gui_service_cmd_status_push`, `gui_service_cmd_pack` | экранный GUI камеры |

## GUI service (важно для полного паритета с Mimo)
`gui_service_cmd_pack`, `gui_service_cmd_param_get_pack`, `gui_service_cmd_param_set_pack`, `gui_service_cmd_file_selected_list_push` — экранный интерфейс Pocket 3 управляется теми же DUML-пакетами (мета-протокол GUI). Позволяет дёргать любые пункты меню, если знать id.

---

## Следующий шаг для получения байтов
Декомпилировать в главном `DJIMimo`:
1. `dji::crossplatform::PackProviderImpl` — точный layout DUML-кадра.
2. `StartRecordAction` / `StopRecordAction` — cmdset/cmdid/payload для REC (milestone P0).
3. `RotateByAngleNewAction`, `ResetGimbalAction` — gimbal.
4. Обработчик key `dji_topic_data_camera_expo_param` set — ISO/shutter/WB payload.
5. `DjiProtocolDecoder::DecodeCommand` — формат ответа/push.

---

## Full catalog (from strings sweep)

Полный sweep строк из `ida_targets/DJIMimo` (176 MB). Сырые списки — в `research/strings/*.txt`
(дедуп + sort). Числовых cmd_set/cmd_id в строках **нет** (это runtime-поля структур
`cmdSet/cmdId`, а не литералы) — см. `cmd_ids.txt`. Ниже — control-релевантное, сгруппировано по подсистемам.
Каждое имя ниже **дословно** присутствует в бинаре.

Счётчики: Action-хендлеров = 48, `dji::core::*` = 93, `dji_topic_data_*` = 100,
`*_push` = 123, `*_pack` = 133, `*_req` = 166, `*_rsp` = 257,
`dji::sdk::*` читаемых символов = 3000, мангленых `N3dji3sdk…E` = 8746,
capability-топиков `dji_topic_camera_capability_*` = 28.

Файлы: `actions.txt` (+ `actions_signatures.txt` — полные сигнатуры KeyHandlers),
`core_types.txt` (core + topic + push/pack/req/rsp), `topics_data.txt`,
`sdk_types.txt` (readable + мангл→демангл через `c++filt`), `capabilities.txt`,
`param_values.txt`, `cmd_ids.txt`, а также по-суффиксно `clean_{push,pack,req,rsp}.txt`.

### Recording / Capture
- Action: `StartRecordAction`, `StopRecordAction`, `StopRecordWithCheckPrecordAction`, `FinishAutoRecAction`.
- req/pack: `record_video_req`, `take_photo_req`, `delete_photo_req`, `set_camera_capture_type_req`,
  `set_photo_aspectio_req`, `get_video_recording_info_req`, `set_capture_recording_streams_req` /
  `get_capture_recording_streams_req`, `dji_camera_set_recording_mode_req`,
  `camera_record_story_configure_pack`, `set_camera_orignal_photo_config_pack` / `get_...`,
  `set_camera_photo_timelapse_req` / `get_...`.
- topic/push: `dji_topic_data_camera_capture_status`, `_capture_shooting_count`, `_capture_aspect_type`,
  `_record_time`, `camera_capture_param_push`, `camera_tau_capture_param_push`, `dji_topic_data_camera_original_video_backup`.

### Gimbal
- Action: `ResetGimbalAction`, `RotateByAngleNewAction`, `ScreenDragGimbalAction`, `SubGimbalCapAction`.
- req/pack: `set_gimbal_mode_req`, `set_gimbal_params_req`, `action_read_gimbal_params_req`,
  `action_gimbal_set_reset_req`, `set_gimbal_control_gimbal_speed_req`, `set_gimbal_roll_trimming_adjust_req`,
  `action_gimbal_system_param_operate_req`, `action_gimbal_coordinate_system_rotate_pack`,
  `action_gimbal_path_control_pack`, `gimbal_feature_control_pack`, `set_gimbal_turn_on_off_pack`,
  `set_gimbal_handheld_stick_control_enable_pack`, `action_gimbal_time_lapse_control_pack`,
  `gimbal_action_adjust_req`, `gimbal_get_ronin_params_pack` / `gimbal_set_ronin_params_pack`.
- push: `gimbal_attitude_push`, `get_gimbal_attitude_push`, `gimbal_state_push`, `gimbal_capability_push`,
  `gimbal_lock_status_push`, `gimbal_calibration_status_push`, `gimbal_system_param_push`,
  `gimbal_handheld_stick_state_push`, `gimbal_step_frequency_push`, `gimbal_timelapse_status_push`,
  `gimbal_adjust_status_push`, `gimbal_control_para_calibration_status_push`,
  `gimbal_subscribe_peripherals_status_push`.
- sdk: `GimbalAttitudeRange`, `GimbalZoomActionStateMsg`, `GimbalCmdIdsMsg`.

### Exposure (ISO / Shutter / WB / EV / Aperture / ExposureMode)
- req: `set_iso_req` / `get_iso_req`, `set_camera_shutter_speed_req` / `get_camera_shutter_speed_req`,
  `set_camera_exposure_mode_req`, `set_camera_exposure_compensation_req`,
  `set_camera_mechanical_shutter_param_req`.
- topic: `dji_topic_data_camera_expo_param`, `_cam_exposure_mode`, `_cam_shutter`, `_shutter`,
  `_cam_aperture`, `_virtual_aperture`, `_auto_aperture_range`, `_aperture_ctrl_strategy`.
- sdk-типы (диапазоны/статусы): `CameraISOMsg`, `CameraISORangeMsg`, `CameraISOAutoMaxRangeMsg`,
  `ISOAutoMaxMsg`, `CameraShutterSpeedMsg`/`RangeMsg`, `CameraShutterTypeMsg`,
  `CameraExposureModeMsg`/`RangeMsg`, `CameraExposureCompensationMsg`/`RangeMsg`,
  `CameraExposureStatusMsg`, `CameraExposureSettings`, `ExposureSensitivityModeMsg`,
  `CameraApertureMsg`, `Aperture*RangeMsg`, `CameraWhiteBalance`, `WhiteBalanceRangeMsg`.
- Полный enum-вокабуляр — `param_values.txt` (секция EXPOSURE).

### Video (resolution / fps / codec / format)
- req/pack: `set_camera_video_standard_req`, `set_camera_video_type_req`, `set_camera_video_format_req` /
  `get_video_output_format_req` / `set_video_output_format_req`, `set_camera_video_coding_standard_req`,
  `set_camera_video_quality_req`, `set_camera_video_storage_format_req`,
  `set_camera_h1_video_format_pack` / `get_...`, `camera_set_video_caption_pack` / `camera_get_...`,
  `set_camera_super_resolution_aera_pack`.
- topic: `dji_topic_data_camera_video_param`, `_video_param_v2`, `_multi_video_param`,
  `_cam_video_codec`, `_cam_video_format`, `_fov`.
- sdk-типы: `VideoResolutionFrameRateRangeMsg`, `VideoResolutionFrameRateAndFovRangeMsg`,
  `VideoResolutionFrameRateAndSpeedRatio`, `VideoFrameRateMsg`, `VideoCodecFormatMsg`,
  `VideoFileCompressionStandardMsg`/`RangeMsg`, `VideoStandardMsg`/`RangeMsg`,
  `CodecProfileParamMsg`/`RangeMsg`, `SlowMotionRatioFrameRateMsg`/`RangeMsg`,
  `H1LiveViewResolutionFrameRateMsg`, `PhotoResolutionMsg`/`RangeMsg`.
- Литеральные значения в бинаре: `4k/4K`, `2.7k`, `1080p`, `720p`, `3840x2160`, `2720x1530`,
  `4096x2160`, `1920x1080`, `h264/h265/hevc`, `24/25/30/60fps` — см. `param_values.txt` (VIDEO).

### Color / Style / D-Log / LUT
- topic: `dji_topic_data_camera_style_filter_status`, `_cam_color_mode`, `_image_effect`.
- sdk-типы: `CameraColorMsg`/`RangeMsg`, `CameraColorTemperatureRange`, `CameraStyleFilterStatusMsg`,
  `CameraStyleFilterModeRangeMsg`, `PictureStylePresetMsg`, `EIColorMsg`, `ColorRestorationEnabledMsg`,
  `SSDColorMsg`/`SSDLegacyColorMsg`.

### Focus / Zoom
- Action: `OpticalZoomModeRatioAction`.
- req/pack: `set_camera_control_zoom_req`, `set_camera_zoom_param_pack`, `set_camera_focus_area_req`,
  `set_body_focus_mode_req`.
- topic: `dji_topic_data_camera_cam_zoom`, `_lens_state`, `_lens_mode`, `_magnifier_status`,
  `_accessory_lens_type`.
- sdk-типы: `CameraFocusModeMsg`, `CameraFocusStateMsg`, `CameraActualFocusArea`, `AFStrategyMsg`/`RangeMsg`,
  `AFSensitivityMsg`, `CameraZoomStatusMsg`, `CameraContinuousOpticalZoomParam`,
  `CameraOpticalZoomSpec`, `CameraHybridZoomSpec`, `OpticalZoomRatioParam`,
  `OpticalZoomFocalLengthParam`, `DigitalZoomStrideMsg`, `ZoomPointTargetMsg`,
  `ZoomCameraRelativeFovMsg`, `MFDemarcateStateMsg`/`ResultMsg`.

### Storage
- req: `format_sdcard_req`, `set_camera_photo_storage_format_req`, `set_camera_video_storage_format_req`.
- topic/push: `dji_topic_data_camera_storage_info`, `camera_storage_info_push`,
  `dji_topic_data_camcap_photo_storage_format`, `_time_lapse_file_format`, `_pano_flat_video_format`.

### Battery / Temperature
- push: `battery_dynamic_info_push`, `get_battery_dynamic_info_push`, `center_battery_common_info_push`,
  `centerboard_smart_battery_dynamic_data_push`, `battery_box_active_push`, `fc_battery_push`,
  `general_temperature_info_set_push`, `temperature_test_info_push`.
- req: `get_battery_self_discharge_req`, `get_battery_single_voltage_req`,
  `action_battery_leds_control_req`, `general_temperature_curve_set_req`, `temperature_test_req`.
- topic: `dji_topic_data_temp_curve_info`.

### Audio / Mic
- Action (беспроводной микрофон): `WlMicPairOprAction`, `StartWlMicStorageFormatAction`,
  `MicCreatePasswordAction`, `MicChangePasswordAction`, `MicCheckPasswordAction`,
  `MicResetPasswordAction`, `MicCheckAndUnlockPasswordAction`.
- req/pack: `set_camera_audio_param_req` / `get_camera_audio_param_req`,
  `set_camera_audio_gain_req` / `get_camera_audio_gain_req`,
  `set_camera_audio_record_enable_req` / `get_...`, `dji_camera_set_audio_param_req`,
  `audio_wireless_mic_set_params_pack`, `audio_wireless_mic_set_audio_pack`,
  `audio_wireless_mic_capability_get_pack`, `audio_wireless_mic_manage_password_pack`,
  `dji_audio_product_audio_test_pack`.
- topic: `dji_topic_data_camera_audio_status`, `_audio_status_v2`, `dji_topic_data_camcap_audio_capability`.

### Capability negotiation (читать, НЕ хардкодить)
28 топиков `dji_topic_camera_capability_*`: `_iso`, `_iso_auto_max`, `_shutter`, `_shutter_max`,
`_wb`, `_aperture`, `_exposure_mode`, `_color_mode`, `_video_codec`, `_video_format`, `_fov`,
`_zoom`, `_eis`, `_denoise`, `_sharpness`, `_antiflicker`, `_mode`, `_photo_size_info`,
`_photo_storage_format`, `_photo_timer_interval`, `_slowmotion_ratio`, `_hyperlapse_ratio`,
`_timelapse_duration`, `_time_lapse_file_format`, `_time_limited_burst`, `_loop_video_duration`,
`_count_down`, `_base`. Плюс: `gimbal_capability_push`, `dji_topic_data_camera_cam_photo_size_range_info`,
`_custom_mode_params`, `_vq_enhancement_info`, `_build_in_beauty_info`, `_firmware_support_info`.
Полный список range/support-типов — `capabilities.txt`. Каждый параметр камеры имеет парный
`dji::sdk::…RangeMsg` (диапазон допустимых значений).

### GUI service (мета-протокол экранного меню)
- Action: `ExecuteGuiCmdAction`.
- pack/push: `gui_service_cmd_pack`, `gui_service_cmd_param_get_pack`, `gui_service_cmd_param_set_pack`,
  `gui_service_cmd_status_push`, `gui_service_cmd_file_selected_list_push`.

### Прочие control-Action (полный список — `actions.txt`)
`ToggleCameraLiveViewAction`, `EnterPlayBackAction`/`ExitPlayBackAction` (+`020C`, +`Audio`),
`PlayBack020CAction`, `MotionLapsePreviewAction`/`…InterruptAction`, `SaveCustomModeSettingAction`,
`ForceUpdateCacheValueAction`, `SuperSlowMotionPointOprAction`/`PullSuperSlowMotionPointAction`,
`PullHighLightAction`, `ReMuxMediaFileAction`/`CancelReMuxMediaFileAction`,
`StartIOSScreenMirroringAction`, `StopGroundWiFiAction`, `SilentTransReportAction`,
`OpenLogTransmissionPortAction`, `UpdateModelAuthInfoAction`, `UpdateCalibrationFileWithNameAction`,
`NfcWriteAppPackageNameAction`, `BLECtrlBroadCastAction`, `Bind/UnbindAccountWithDeviceAction`,
`RequestBoundDeviceListAction`, `RequestDeviceBindingInfoAction`, `QueryInsuranceInfoAction`,
`VerifyAccessLockerPwdAction`.

### Байтов по-прежнему нет
Ни один cmd_set/cmd_id-байт не встречается как литерал (проверено — `cmd_ids.txt` содержит только
runtime-имена полей `cmdSet`/`cmdId`/`PackType` и мангленые сигнатуры `SendPack`/`SendSetPackProxy`).
Для числовых значений всё ещё нужна декомпиляция `PackProviderImpl::SendPack` и конкретных
`*_req`/`*_pack` конструкторов (см. раздел «Следующий шаг»).
