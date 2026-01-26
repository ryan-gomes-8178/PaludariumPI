#!/bin/bash

# Available parameters
DEVICE=$1
NAME=$2
WIDTH=$3
HEIGHT=$4
ROTATION=$5
AWB=$6
DIR=$7

# Find the needed programs (prefer modern libcamera stack)
RASPIVID=$(type -p libcamera-vid)
if [ $? -ne 0 ]; then
  RASPIVID=$(type -p rpicam-vid)
  if [ $? -ne 0 ]; then
    RASPIVID=$(type -p raspivid)
  fi
fi
FFMPEG=$(type -p ffmpeg)
if [ -z "${FFMPEG}" ]; then
  echo "Error: ffmpeg not found. Please install ffmpeg to use this script." >&2
  exit 1
fi

# Defaults
if [[ "${NAME}" == "" ]]; then
  NAME="RPI Live"
fi

if [[ "${WIDTH}" == "" ]]; then
  WIDTH="1920"
fi

if [[ "${HEIGHT}" == "" ]]; then
  HEIGHT="1080"
fi

if [[ "${ROTATION}" == "" ]]; then
  ROTATION="0"
fi

if [[ "${AWB}" == "" ]]; then
  AWB="auto"
fi

if [[ "${DIR}" == "" ]]; then
  DIR="/dev/shm/test"
fi

if [[ ! -d "${DIR}" ]]; then
  mkdir -p "${DIR}"
fi

# Build rotation arguments
ROTATION_ARGS=""
if [[ "${ROTATION}" == "h" ]]; then
  ROTATION_ARGS="--hflip"
elif [[ "${ROTATION}" == "v" ]]; then
  ROTATION_ARGS="--vflip"
else
  ROTATION_ARGS="--rotation ${ROTATION}"
fi

function streamNew() {
 "${RASPIVID}" -v 0 --output - --codec h264 --bitrate 2000000 --timeout 0 --width "${WIDTH}" --height "${HEIGHT}" ${ROTATION_ARGS} --awb "${AWB}" --framerate 30 --inline | \
 "${FFMPEG}" -hide_banner -nostdin -re -i - -c:v copy -f hls -hls_time 2 -hls_list_size 3 -hls_flags delete_segments+split_by_time -hls_segment_filename "${DIR}/chunk_%03d.ts" "${DIR}/stream.m3u8"
}

function streamOld() {
 "${RASPIVID}" --output - --bitrate 2000000 --timeout 0 --width "${WIDTH}" --height "${HEIGHT}" ${ROTATION_ARGS} --awb "${AWB}" --framerate 30 --intra 30 --profile high --level 4.2 -ae 46,0xff,0x808000 -a 8 -a " ${NAME} @ %d/%m/%Y %X " -a 1024 | \
 "${FFMPEG}" -hide_banner -nostdin -re -i - -c:v copy -f hls -hls_time 2 -hls_list_size 3 -hls_flags delete_segments+split_by_time -hls_segment_filename "${DIR}/chunk_%03d.ts" "${DIR}/stream.m3u8"
}

# Start streaming
if [[ "${RASPIVID}" == *"rpicam-vid"* ]] || [[ "${RASPIVID}" == *"libcamera-vid"* ]]
then
  # New libcamera-based stack
  streamNew
else
  # Legacy raspivid path only if legacy camera stack is enabled
  if vcgencmd get_camera 2>/dev/null | grep -q 'supported=1'; then
    streamOld
  else
    echo "ERROR: Legacy camera stack not enabled; live streaming is not possible on this system." >&2
    exit 1
  fi
fi
