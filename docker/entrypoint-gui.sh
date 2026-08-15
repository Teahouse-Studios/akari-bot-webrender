#!/bin/sh
set -u

xvfb_pid=""
desktop_pid=""
x11vnc_pid=""
novnc_pid=""
app_pid=""
vnc_auth_file=""

terminate_process() {
    process_pid="$1"
    if [ -n "$process_pid" ] && kill -0 "$process_pid" 2>/dev/null; then
        kill -TERM "$process_pid" 2>/dev/null || true
    fi
}

cleanup() {
    trap - EXIT INT TERM
    terminate_process "$app_pid"
    terminate_process "$novnc_pid"
    terminate_process "$x11vnc_pid"
    terminate_process "$desktop_pid"
    terminate_process "$xvfb_pid"

    attempt=0
    while [ "$attempt" -lt 50 ]; do
        processes_running=0
        for process_pid in "$app_pid" "$novnc_pid" "$x11vnc_pid" "$desktop_pid" "$xvfb_pid"; do
            if [ -n "$process_pid" ] && kill -0 "$process_pid" 2>/dev/null; then
                processes_running=1
            fi
        done
        [ "$processes_running" -eq 0 ] && break
        attempt=$((attempt + 1))
        sleep 0.1
    done

    for process_pid in "$app_pid" "$novnc_pid" "$x11vnc_pid" "$desktop_pid" "$xvfb_pid"; do
        if [ -n "$process_pid" ] && kill -0 "$process_pid" 2>/dev/null; then
            kill -KILL "$process_pid" 2>/dev/null || true
        fi
        if [ -n "$process_pid" ]; then
            wait "$process_pid" 2>/dev/null || true
        fi
    done

    if [ -n "$vnc_auth_file" ]; then
        rm -f "$vnc_auth_file"
    fi
}

forward_signal() {
    terminate_process "$app_pid"
}

fail() {
    echo "webrender-entrypoint: $*" >&2
    exit 1
}

trap cleanup EXIT
trap forward_signal INT TERM

case "${DISPLAY:-}" in
    :[0-9]* | :[0-9]*.[0-9]*) ;;
    *) fail "DISPLAY must be a local X display such as :99" ;;
esac

case "${XVFB_SCREEN:-}" in
    [0-9]*x[0-9]*x[0-9]*) ;;
    *) fail "XVFB_SCREEN must have the form WIDTHxHEIGHTxDEPTH" ;;
esac

Xvfb "$DISPLAY" -screen 0 "$XVFB_SCREEN" -nolisten tcp -ac +extension RANDR &
xvfb_pid=$!

ready=0
attempt=0
while [ "$attempt" -lt 100 ]; do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then
        ready=1
        break
    fi
    if ! kill -0 "$xvfb_pid" 2>/dev/null; then
        fail "Xvfb exited before the display became ready"
    fi
    attempt=$((attempt + 1))
    sleep 0.1
done
[ "$ready" -eq 1 ] || fail "timed out waiting for Xvfb on $DISPLAY"

xset -display "$DISPLAY" -dpms >/dev/null 2>&1 || true
xset -display "$DISPLAY" s off >/dev/null 2>&1 || true
xset -display "$DISPLAY" s noblank >/dev/null 2>&1 || true

case "${WEBRENDER_DESKTOP:-twm}" in
    twm)
        dbus-run-session -- twm -f ./docker/twmrc &
        desktop_pid=$!
        ;;
    xfce)
        dbus-run-session -- startxfce4 &
        desktop_pid=$!
        ;;
    *) fail "WEBRENDER_DESKTOP must be 'twm' or 'xfce'" ;;
esac

if [ "${ENABLE_NOVNC:-0}" = "1" ]; then
    if [ -n "${NOVNC_PASSWORD_FILE:-}" ]; then
        [ -r "$NOVNC_PASSWORD_FILE" ] || fail "NOVNC_PASSWORD_FILE is not readable"
        vnc_password=$(cat "$NOVNC_PASSWORD_FILE")
    elif [ -n "${NOVNC_PASSWORD:-}" ]; then
        vnc_password=$NOVNC_PASSWORD
    else
        fail "ENABLE_NOVNC=1 requires NOVNC_PASSWORD or NOVNC_PASSWORD_FILE"
    fi

    [ -n "$vnc_password" ] || fail "the noVNC password must not be empty"
    vnc_auth_file=$(mktemp /tmp/webrender-vnc-passwd.XXXXXX)
    chmod 0600 "$vnc_auth_file"
    x11vnc -storepasswd "$vnc_password" "$vnc_auth_file" >/dev/null
    unset vnc_password NOVNC_PASSWORD

    x11vnc \
        -display "$DISPLAY" \
        -forever \
        -localhost \
        -noxdamage \
        -rfbauth "$vnc_auth_file" \
        -rfbport "${VNC_PORT:-5900}" \
        -shared \
        -o /tmp/x11vnc.log &
    x11vnc_pid=$!

    vnc_ready=0
    attempt=0
    while [ "$attempt" -lt 100 ]; do
        if kill -0 "$x11vnc_pid" 2>/dev/null; then
            if python -c 'import socket,sys; s=socket.socket(); s.settimeout(0.1); sys.exit(s.connect_ex(("127.0.0.1", int(sys.argv[1]))))' "${VNC_PORT:-5900}"; then
                vnc_ready=1
                break
            fi
        else
            fail "x11vnc exited before its socket became ready"
        fi
        attempt=$((attempt + 1))
        sleep 0.1
    done
    [ "$vnc_ready" -eq 1 ] || fail "timed out waiting for x11vnc"

    websockify \
        --web=/usr/share/novnc \
        "${NOVNC_LISTEN:-127.0.0.1}:${NOVNC_PORT:-6080}" \
        "127.0.0.1:${VNC_PORT:-5900}" &
    novnc_pid=$!
fi

"$@" &
app_pid=$!
wait "$app_pid"
status=$?
exit "$status"
