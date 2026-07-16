#!/usr/bin/env bash

restart_after_model_change() {
  if [ "${SKIP_COMPOSE_AFTER_MODEL_CHANGE:-false}" = "true" ]; then
    return
  fi
  compose_up
}

model_list() {
  load_env
  run_model_cli list
}

ask_yes_no() {
  local prompt="$1"
  local answer
  read -r -p "${prompt} [y/N]: " answer
  case "$answer" in
    y|Y) return 0 ;;
    *) return 1 ;;
  esac
}

read_required() {
  local prompt="$1"
  local value
  read -r -p "$prompt" value
  if [ -z "$value" ]; then
    echo "Value cannot be empty." >&2
    return 1
  fi
  printf '%s' "$value"
}

choose_llm_vendor() {
  LLM_BRAND=""
  LLM_BASE_URL=""
  LLM_DEFAULT_MODEL=""
  echo
  echo "Choose $(t llm_label) brand:"
  echo "1) DeepSeek"
  echo "2) Qwen / Alibaba Cloud Model Studio"
  echo "3) Doubao / Volcengine Ark"
  echo "4) Kimi / Moonshot"
  echo "5) OpenAI"
  echo "6) Other / custom OpenAI-compatible"
  read -r -p "Select [1]: " choice
  choice="${choice:-1}"
  case "$choice" in
    1) LLM_BRAND="deepseek"; LLM_BASE_URL="https://api.deepseek.com"; LLM_DEFAULT_MODEL="deepseek-v4-flash" ;;
    2) LLM_BRAND="qwen"; LLM_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"; LLM_DEFAULT_MODEL="qwen-flash" ;;
    3) LLM_BRAND="doubao"; LLM_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"; LLM_DEFAULT_MODEL="doubao-1-5-pro-32k-250115" ;;
    4) LLM_BRAND="kimi"; LLM_BASE_URL="https://api.moonshot.cn/v1"; LLM_DEFAULT_MODEL="moonshot-v1-8k" ;;
    5) LLM_BRAND="openai"; LLM_BASE_URL="https://api.openai.com/v1"; LLM_DEFAULT_MODEL="gpt-4o-mini" ;;
    6)
      LLM_BRAND="$(read_required "Brand name: ")" || return 1
      LLM_BASE_URL="$(read_required "AI 调用网站 / OpenAI-compatible base URL: ")" || return 1
      LLM_DEFAULT_MODEL=""
      ;;
    *) echo "Unknown brand." >&2; return 1 ;;
  esac
}

add_llm_model() {
  local remark api_key model model_id
  choose_llm_vendor || return 1
  read -r -p "备注名称 [${LLM_BRAND}-${LLM_DEFAULT_MODEL:-model}]: " remark
  remark="${remark:-${LLM_BRAND}-${LLM_DEFAULT_MODEL:-model}}"
  api_key="$(read_required "API key: ")" || return 1
  read -r -p "模型名 / Model name [${LLM_DEFAULT_MODEL}]: " model
  model="${model:-$LLM_DEFAULT_MODEL}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return 1; }
  ensure_runtime_config
  model_id="$(run_model_cli add-llm \
    --brand "$LLM_BRAND" \
    --name "$remark" \
    --remark "$remark" \
    --base-url "$LLM_BASE_URL" \
    --api-key "$api_key" \
    --model "$model" \
    --activate)"
  set_env_value LLM_PROVIDER "auto"
  set_env_value LLM_DEFAULT_VENDOR "$LLM_BRAND"
  set_env_value MODEL_CONFIG_PATH "${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  restart_after_model_change
  echo "Added and activated $(t llm_label): ${model_id} ${LLM_BRAND}/${model}"
}

choose_asr_vendor() {
  ASR_BRAND=""
  ASR_PROVIDER_KIND=""
  ASR_BASE_URL=""
  ASR_BASE_HTTP_API_URL=""
  ASR_DEFAULT_MODEL=""
  echo
  echo "Choose $(t asr_label) source:"
  echo "1) Qwen3-ASR-Flash / DashScope（默认，短录音准确率优先）"
  echo "2) OpenAI-compatible multimodal ASR（把录音交给多模态大模型）"
  echo "3) Other / custom multimodal ASR"
  read -r -p "Select [1]: " choice
  choice="${choice:-1}"
  case "$choice" in
    1)
      ASR_BRAND="qwen"
      ASR_PROVIDER_KIND="qwen_dashscope"
      ASR_BASE_HTTP_API_URL="https://dashscope.aliyuncs.com/api/v1"
      ASR_DEFAULT_MODEL="qwen3-asr-flash"
      ;;
    2)
      ASR_BRAND="openai-compatible"
      ASR_PROVIDER_KIND="openai_multimodal"
      ASR_BASE_URL="$(read_required "AI 调用网站 / base URL: ")" || return 1
      ASR_DEFAULT_MODEL=""
      ;;
    3)
      ASR_BRAND="$(read_required "Brand name: ")" || return 1
      ASR_PROVIDER_KIND="openai_multimodal"
      ASR_BASE_URL="$(read_required "AI 调用网站 / base URL: ")" || return 1
      ASR_DEFAULT_MODEL=""
      ;;
    *) echo "Unknown ASR source." >&2; return 1 ;;
  esac
}

add_asr_model() {
  local remark api_key model language model_id
  choose_asr_vendor || return 1
  read -r -p "备注名称 [${ASR_BRAND}-${ASR_DEFAULT_MODEL:-asr}]: " remark
  remark="${remark:-${ASR_BRAND}-${ASR_DEFAULT_MODEL:-asr}}"
  api_key="$(read_required "API key: ")" || return 1
  read -r -p "模型名 / Model name [${ASR_DEFAULT_MODEL}]: " model
  model="${model:-$ASR_DEFAULT_MODEL}"
  [ -n "$model" ] || { echo "Model name cannot be empty." >&2; return 1; }
  read -r -p "Language hint [zh]: " language
  language="${language:-zh}"
  ensure_runtime_config
  model_id="$(run_model_cli add-asr \
    --brand "$ASR_BRAND" \
    --provider "$ASR_PROVIDER_KIND" \
    --name "$remark" \
    --remark "$remark" \
    --base-url "$ASR_BASE_URL" \
    --base-http-api-url "$ASR_BASE_HTTP_API_URL" \
    --api-key "$api_key" \
    --model "$model" \
    --language "$language" \
    --enable-itn \
    --activate)"
  set_env_value ASR_PROVIDER "auto"
  set_env_value ASR_PRIMARY "configured_asr"
  set_env_value ASR_FALLBACK "vosk"
  set_env_value ASR_STRATEGY "${ASR_STRATEGY:-cloud_first}"
  set_env_value ASR_DEFAULT_VENDOR "$ASR_BRAND"
  set_env_value MODEL_CONFIG_PATH "${MODEL_CONFIG_PATH:-runtime/config/models.json}"
  restart_after_model_change
  echo "Added and activated $(t asr_label): ${model_id} ${ASR_BRAND}/${model}"
}

configure_models_interactive() {
  local mode count index purpose default_kind
  load_language
  echo
  echo "Model configuration is stored in runtime/config/models.json."
  echo "Secrets in that file are under runtime/ and are not committed to git."
  echo "0) Skip for now"
  echo "1) Add one model"
  echo "2) Add multiple models"
  read -r -p "Select [1]: " mode
  mode="${mode:-1}"
  case "$mode" in
    0) return ;;
    1) count=1 ;;
    2)
      read -r -p "How many models do you want to add? " count
      case "$count" in ''|*[!0-9]*) echo "Count must be a number." >&2; return 1 ;; esac
      ;;
    *) echo "Unknown option." >&2; return 1 ;;
  esac
  index=1
  while [ "$index" -le "$count" ]; do
    echo
    echo "Model ${index}/${count}:"
    echo "1) $(t llm_label)"
    echo "2) $(t asr_label)"
    read -r -p "Purpose [1]: " purpose
    purpose="${purpose:-1}"
    case "$purpose" in
      1) add_llm_model ;;
      2) add_asr_model ;;
      *) echo "Unknown purpose." >&2; return 1 ;;
    esac
    index=$((index + 1))
  done

  if [ "$count" -gt 1 ]; then
    echo
    echo "Multiple models are configured. The active model marked with * is the default used by the cloud service."
    model_list || true
    read -r -p "Switch default model now? [y/N]: " default_kind
    case "$default_kind" in
      y|Y) deployed_model_menu ;;
    esac
  fi
}

first_run_model_wizard() {
  load_language
  echo
  menu_title "$(t first_run_wizard)"
  echo "$(t first_run_intro)"
  echo

  if ask_yes_no "$(t wizard_configure_asr)"; then
    add_asr_model || return 1
  else
    echo "$(t wizard_skip_asr)"
  fi

  echo
  if ask_yes_no "$(t wizard_configure_llm)"; then
    add_llm_model || return 1
  else
    echo "$(t wizard_skip_llm)"
  fi

  echo
  if ask_yes_no "$(t wizard_configure_strategy)"; then
    asr_strategy_menu
  fi

  echo
  echo "$(t wizard_status)"
  print_health_summary || true
  model_list || true
  echo
  echo "$(t wizard_done)"
  press_enter "$(t back): "
}

switch_model_by_id() {
  local kind="$1"
  local model_id
  model_list || true
  read -r -p "Model ID: " model_id
  [ -n "$model_id" ] || return
  run_model_cli switch "$kind" "$model_id"
  if [ "$kind" = "llm" ]; then
    set_env_value LLM_PROVIDER "auto"
  else
    set_env_value ASR_PROVIDER "auto"
    set_env_value ASR_PRIMARY "configured_asr"
  fi
  restart_after_model_change
}

delete_model_by_id() {
  local kind="$1"
  local model_id
  model_list || true
  read -r -p "Model ID to delete: " model_id
  [ -n "$model_id" ] || return
  confirm_phrase "DELETE" "Type DELETE to delete ${model_id}: " || { echo "Cancelled."; return; }
  run_model_cli delete "$kind" "$model_id"
  restart_after_model_change
}

deployed_model_menu() {
  local kind action
  while true; do
    echo
    model_list || true
    echo
    echo "1) $(t select_llm_model)"
    echo "2) $(t select_asr_model)"
    echo "0) $(t back)"
    read -r -p "$(t select): " kind
    case "$kind" in
      1) kind="llm" ;;
      2) kind="asr" ;;
      0) return ;;
      *) warn "$(t unknown_option)"; continue ;;
    esac
    echo "1) $(t switch_default_model)"
    echo "2) $(t delete_model)"
    echo "0) $(t back)"
    read -r -p "$(t select): " action
    case "$action" in
      1) switch_model_by_id "$kind" ;;
      2) delete_model_by_id "$kind" ;;
      0) ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

asr_strategy_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t asr_strategy)"
    echo "$(t current): ASR_PROVIDER=${ASR_PROVIDER:-auto}, ASR_STRATEGY=${ASR_STRATEGY:-cloud_first}"
    echo "1) $(t asr_strategy_cloud_first)"
    echo "2) $(t asr_strategy_local_first)"
    echo "3) $(t asr_strategy_llm_audio)"
    echo "4) $(t asr_strategy_offline)"
    echo "5) $(t manual_provider)"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1)
        set_env_value ASR_PROVIDER "auto"
        set_env_value ASR_STRATEGY "cloud_first"
        set_env_value ASR_PRIMARY "configured_asr"
        set_env_value ASR_FALLBACK "vosk"
        restart_after_model_change
        ;;
      2)
        set_env_value ASR_PROVIDER "auto"
        set_env_value ASR_STRATEGY "local_first"
        set_env_value ASR_PRIMARY "vosk"
        set_env_value ASR_FALLBACK "configured_asr"
        restart_after_model_change
        ;;
      3)
        set_env_value ASR_PROVIDER "auto"
        set_env_value ASR_STRATEGY "llm_audio"
        set_env_value ASR_PRIMARY "configured_asr"
        set_env_value ASR_FALLBACK "qwen_dashscope"
        restart_after_model_change
        ;;
      4)
        set_env_value ASR_PROVIDER "local"
        set_env_value ASR_STRATEGY "offline"
        restart_after_model_change
        ;;
      5)
        read -r -p "ASR_PROVIDER value: " provider
        [ -n "$provider" ] && set_env_value ASR_PROVIDER "$provider"
        restart_after_model_change
        ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

llm_model_menu() {
  while true; do
    echo
    menu_title "$(t llm_label)"
    echo "1) $(t deployed_models)"
    echo "2) $(t add_model)"
    echo "3) $(t switch_default_model)"
    echo "4) $(t delete_model)"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) model_list ;;
      2) add_llm_model ;;
      3) switch_model_by_id llm ;;
      4) delete_model_by_id llm ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

asr_model_menu() {
  while true; do
    echo
    menu_title "$(t asr_label)"
    echo "1) $(t deployed_models)"
    echo "2) $(t add_model)"
    echo "3) $(t switch_default_model)"
    echo "4) $(t delete_model)"
    echo "5) $(t asr_strategy)"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) model_list ;;
      2) add_asr_model ;;
      3) switch_model_by_id asr ;;
      4) delete_model_by_id asr ;;
      5) asr_strategy_menu ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

tts_menu() {
  local voice provider
  while true; do
    load_env
    echo
    menu_title "TTS"
    echo "TTS_PROVIDER=${TTS_PROVIDER:-edge}"
    echo "EDGE_TTS_VOICE=${EDGE_TTS_VOICE:-zh-CN-XiaoxiaoNeural}"
    echo "1) $(t set_tts_provider)"
    echo "2) $(t set_edge_voice)"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1)
        read -r -p "TTS_PROVIDER [edge/tone]: " provider
        [ -n "$provider" ] && set_env_value TTS_PROVIDER "$provider"
        restart_after_model_change
        ;;
      2)
        read -r -p "EDGE_TTS_VOICE: " voice
        [ -n "$voice" ] && set_env_value EDGE_TTS_VOICE "$voice"
        restart_after_model_change
        ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}

models_voice_menu() {
  while true; do
    load_env
    echo
    menu_title "$(t models_voice)"
    echo "$(t current_llm): ${LLM_PROVIDER:-auto}"
    echo "$(t current_asr): ${ASR_PROVIDER:-auto} / ${ASR_STRATEGY:-cloud_first}"
    echo "1) $(t first_run_wizard)"
    echo "2) $(t model_status)"
    echo "3) $(t llm_label)"
    echo "4) $(t asr_label)"
    echo "5) $(t deployed_models)"
    echo "6) $(t asr_strategy_default)"
    echo "7) $(t tts_settings)"
    echo "8) $(t view_model_config)"
    echo "0) $(t back)"
    read -r -p "$(t select): " choice
    case "$choice" in
      1) first_run_model_wizard ;;
      2) print_health_summary; model_list || true ;;
      3) llm_model_menu ;;
      4) asr_model_menu ;;
      5) deployed_model_menu ;;
      6) asr_strategy_menu ;;
      7) tts_menu ;;
      8) model_list ;;
      0) return ;;
      *) warn "$(t unknown_option)" ;;
    esac
  done
}
