#!/bin/sh
# entrypoint for the nginx+ngrok container
# Starts nginx in the background, configures ngrok, and opens a tunnel.

# Start nginx in background
nginx -g "daemon off;" &
NGROK_TOKEN=${NGROK_AUTHTOKEN:-}
if [ -n "$NGROK_TOKEN" ]; then
  ngrok config add-authtoken "$NGROK_TOKEN"
fi
# Tunnel HTTP port 80 (where nginx serves) and log to stdout
ngrok http 80 --log=stdout &
# Wait for either process to exit
wait -n