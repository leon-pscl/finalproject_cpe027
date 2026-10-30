#!/bin/sh
# Minimal entrypoint for the nginx container – run nginx in the foreground.
exec nginx -g "daemon off;"
