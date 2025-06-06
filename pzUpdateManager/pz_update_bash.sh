#!/bin/bash
# Simple Project Zomboid Update Monitor

# Configuration
STEAM_API_KEY="your_steam_api_key_here"
PZ_APP_ID="108600"
WORKSHOP_MODS="2169435993,2313387159"  # Comma-separated mod IDs
RCON_HOST="localhost"
RCON_PORT="27015"
RCON_PASSWORD="your_rcon_password"
SERVICE_NAME="zomboid"
CHECK_INTERVAL=300  # 5 minutes

# Files for tracking
VERSION_FILE="$HOME/.pz_versions"
RESTART_FLAG="/tmp/pz_restart_scheduled"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$HOME/pz_monitor.log"
}

check_game_update() {
    local current_build=$(curl -s "https://api.steamcmd.net/v1/info/$PZ_APP_ID" | jq -r ".data.\"$PZ_APP_ID\".depots.branches.public.buildid" 2>/dev/null)
    
    if [ -z "$current_build" ] || [ "$current_build" = "null" ]; then
        log "Failed to fetch game build info"
        return 1
    fi
    
    local stored_build=$(grep "^game:" "$VERSION_FILE" 2>/dev/null | cut -d: -f2)
    
    if [ "$current_build" != "$stored_build" ]; then
        log "Game update detected! New build: $current_build"
        sed -i "/^game:/d" "$VERSION_FILE" 2>/dev/null
        echo "game:$current_build" >> "$VERSION_FILE"
        return 0
    fi
    
    return 1
}

check_mod_updates() {
    if [ -z "$WORKSHOP_MODS" ]; then
        return 1
    fi
    
    IFS=',' read -ra MOD_ARRAY <<< "$WORKSHOP_MODS"
    
    for mod_id in "${MOD_ARRAY[@]}"; do
        mod_id=$(echo "$mod_id" | xargs)  # trim whitespace
        
        local mod_data=$(curl -s -X POST "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/" \
            -d "itemcount=1" -d "publishedfileids[0]=$mod_id")
        
        local last_updated=$(echo "$mod_data" | jq -r ".response.publishedfiledetails[0].time_updated" 2>/dev/null)
        
        if [ -z "$last_updated" ] || [ "$last_updated" = "null" ]; then
            continue
        fi
        
        local stored_time=$(grep "^mod:$mod_id:" "$VERSION_FILE" 2>/dev/null | cut -d: -f3)
        
        if [ "$last_updated" != "$stored_time" ]; then
            log "Mod update detected! Mod ID: $mod_id"
            sed -i "/^mod:$mod_id:/d" "$VERSION_FILE" 2>/dev/null
            echo "mod:$mod_id:$last_updated" >> "$VERSION_FILE"
            return 0
        fi
    done
    
    return 1
}

get_player_count() {
    local result=$(timeout 10 mcrcon -H "$RCON_HOST" -P "$RCON_PORT" -p "$RCON_PASSWORD" "players" 2>/dev/null)
    
    if echo "$result" | grep -q "Players connected"; then
        echo "$result" | sed -n 's/.*Players connected (\([0-9]*\)).*/\1/p'
    else
        echo "-1"
    fi
}

send_message() {
    local message="$1"
    timeout 10 mcrcon -H "$RCON_HOST" -P "$RCON_PORT" -p "$RCON_PASSWORD" "servermsg \"$message\"" >/dev/null 2>&1
    log "Sent message: $message"
}

restart_server() {
    log "Restarting Project Zomboid server..."
    sudo systemctl restart "$SERVICE_NAME"
    if [ $? -eq 0 ]; then
        log "Server restarted successfully"
        rm -f "$RESTART_FLAG"
    else
        log "Failed to restart server"
    fi
}

schedule_restart() {
    if [ -f "$RESTART_FLAG" ]; then
        log "Restart already scheduled, skipping..."
        return
    fi
    
    touch "$RESTART_FLAG"
    log "Scheduling restart in 30 minutes with warnings"
    
    send_message "🔄 SERVER UPDATE AVAILABLE! Server will restart in 30 minutes. Please finish your current activities."
    
    # Background process for delayed restart
    (
        sleep $((29 * 60))  # 29 minutes
        if [ -f "$RESTART_FLAG" ]; then
            send_message "⚠️ SERVER RESTART IN 1 MINUTE! Please save your progress and find a safe location!"
            sleep 60  # 1 minute
            if [ -f "$RESTART_FLAG" ]; then
                send_message "🔧 Server restarting now for updates..."
                sleep 5
                restart_server
            fi
        fi
    ) &
}

handle_update() {
    local player_count=$(get_player_count)
    
    if [ "$player_count" = "-1" ]; then
        log "Could not determine player count, skipping restart"
        return
    elif [ "$player_count" = "0" ]; then
        log "No players connected, restarting server immediately"
        restart_server
    else
        log "$player_count players connected, scheduling restart with warnings"
        schedule_restart
    fi
}

# Main monitoring loop
main() {
    log "Starting Project Zomboid update monitor..."
    
    # Create version file if it doesn't exist
    touch "$VERSION_FILE"
    
    while true; do
        game_updated=false
        mod_updated=false
        
        if check_game_update; then
            game_updated=true
        fi
        
        if check_mod_updates; then
            mod_updated=true
        fi
        
        if [ "$game_updated" = true ] || [ "$mod_updated" = true ]; then
            log "Update detected!"
            handle_update
        fi
        
        sleep "$CHECK_INTERVAL"
    done
}

# Handle script termination
trap 'log "Monitor stopped"; exit 0' SIGINT SIGTERM

# Check dependencies
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed. Run: sudo apt install jq"
    exit 1
fi

if ! command -v mcrcon &> /dev/null; then
    echo "Error: mcrcon is required but not installed. Run: sudo apt install mcrcon"
    exit 1
fi

# Run main function
main