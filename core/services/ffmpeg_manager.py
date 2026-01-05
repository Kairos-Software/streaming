import subprocess
import signal
import os

FFMPEG_BIN = "ffmpeg"

# procesos por usuario
FFMPEG_PROCESSES = {}

# IP pública o subdominio de la VPS
VPS_HOST = "kaircampanel.grupokairosarg.com"  # o la IP 85.209.92.238


def stop_program_stream(user):
    proc = FFMPEG_PROCESSES.get(user.id)

    if proc and proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=5)

    FFMPEG_PROCESSES.pop(user.id, None)


def start_program_stream(user, stream_key):
    stop_program_stream(user)

    input_rtmp = f"rtmp://{VPS_HOST}:9000/live/{stream_key}"
    output_rtmp = f"rtmp://{VPS_HOST}:9000/program/{user.username}"

    cmd = [
        FFMPEG_BIN,
        "-re",
        "-i", input_rtmp,
        "-c", "copy",
        "-f", "flv",
        output_rtmp,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    FFMPEG_PROCESSES[user.id] = proc
