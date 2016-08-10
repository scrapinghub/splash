#!/bin/sh  
# Startup script for splash container . Suppress machine-id warning
# by generatin and UUID for the virtual machine

# Generate machine UUI
/bin/dbus-uuidgen > /etc/machine-id

# Run splash
python3 /app/bin/splash \
--proxy-profiles-path /etc/splash/proxy-profiles \
--js-profiles-path /etc/splash/js-profiles \
--filters-path /etc/splash/filters \
--lua-package-path /etc/splash/lua_modules/?.lua 