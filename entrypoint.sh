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
# Give ngrok a moment to start
sleep 2
# Retrieve the public URL from ngrok API (localhost:4040)
PUBLIC_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | grep -o '"public_url":"[^"]*' | cut -d'"' -f4)
if [ -n "$PUBLIC_URL" ]; then
  echo "✅ ngrok tunnel ready: $PUBLIC_URL"
else
  echo "⚠️ ngrok tunnel not yet available – check container logs for details"
fi
# Wait for either process to exit
wait -n