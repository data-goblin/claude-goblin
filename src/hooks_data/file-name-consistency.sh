#!/bin/bash

# Debug mode flag
DEBUG=${DEBUG:-false}

if [[ "$DEBUG" == "true" ]]; then
    echo "[DEBUG] Script started" >&2
fi

# Debug logging function
debug_log() {
    if [[ "$DEBUG" == "true" ]]; then
        echo "[DEBUG] $*" >&2
    fi
}

# Check if GEMINI_API_KEY is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "Error: GEMINI_API_KEY environment variable is not set" >&2
    exit 1
fi

# Read the hook event from stdin
EVENT_JSON=$(cat)
debug_log "Received JSON: $EVENT_JSON"

# Extract tool name and command
TOOL_NAME=$(echo "$EVENT_JSON" | jq -r '.tool_name')
COMMAND=$(echo "$EVENT_JSON" | jq -r '.tool_input.command // .tool_input.file_path // ""')
debug_log "Tool name: $TOOL_NAME"
debug_log "Command/Path: $COMMAND"

# Only process Bash and Write tool calls
if [[ "$TOOL_NAME" != "Bash" && "$TOOL_NAME" != "Write" && "$TOOL_NAME" != "MultiEdit" ]]; then
    exit 0
fi

# Function to call Gemini API and get raw response
call_gemini_raw() {
    local prompt="$1"
    debug_log "Calling Gemini with prompt: $prompt"
    # Escape quotes, backslashes, and newlines in the prompt for JSON
    local escaped_prompt=$(echo "$prompt" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | awk 'BEGIN {ORS="\\n"} {print}' | sed 's/\\n$//')
    local json_payload="{
            \"contents\": [{
                \"parts\": [{\"text\": \"$escaped_prompt\"}]
            }],
            \"generationConfig\": {
                \"temperature\": 0.1,
                \"maxOutputTokens\": 1000
            }
        }"
    debug_log "Sending JSON: $json_payload"
    local start_time=$(date +%s.%N)
    local response=$(curl -s -X POST \
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    local duration_ms=$(echo "scale=0; ($end_time - $start_time) * 1000" | bc)
    debug_log "Gemini API response time: ${duration}s (${duration_ms}ms)"
    debug_log "Gemini API raw response: $response"
    
    # Extract text, remove newlines, trim whitespace
    local text=$(echo "$response" | jq -r '.candidates[0].content.parts[0].text // ""' | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    debug_log "Gemini raw response: $text"
    echo "$text"
}

# Function to call Gemini API
call_gemini() {
    local prompt="$1"
    debug_log "Calling Gemini with prompt: $prompt"
    # Escape quotes, backslashes, and newlines in the prompt for JSON
    local escaped_prompt=$(echo "$prompt" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | awk 'BEGIN {ORS="\\n"} {print}' | sed 's/\\n$//')
    local json_payload="{
            \"contents\": [{
                \"parts\": [{\"text\": \"$escaped_prompt\"}]
            }],
            \"generationConfig\": {
                \"temperature\": 0.1,
                \"maxOutputTokens\": 1000
            }
        }"
    debug_log "Sending JSON: $json_payload"
    local start_time=$(date +%s.%N)
    local response=$(curl -s -X POST \
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$GEMINI_API_KEY" \
        -H "Content-Type: application/json" \
        -d "$json_payload")
    local end_time=$(date +%s.%N)
    local duration=$(echo "$end_time - $start_time" | bc)
    local duration_ms=$(echo "scale=0; ($end_time - $start_time) * 1000" | bc)
    debug_log "Gemini API response time: ${duration}s (${duration_ms}ms)"
    debug_log "Gemini API raw response: $response"
    
    # Extract text, remove newlines, trim whitespace, and extract just snake_case, camelCase, or kebab-case
    local text=$(echo "$response" | jq -r '.candidates[0].content.parts[0].text // ""' | tr -d '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    debug_log "Gemini raw response: $text"
    # Extract snake_case, camelCase, or kebab-case from the response
    if echo "$text" | grep -q "snake_case"; then
        echo "snake_case"
    elif echo "$text" | grep -q "camelCase"; then
        echo "camelCase"
    elif echo "$text" | grep -q "kebab-case"; then
        echo "kebab-case"
    else
        echo "$text"
    fi
}

# For Write/MultiEdit tools, extract the file path
if [[ "$TOOL_NAME" == "Write" || "$TOOL_NAME" == "MultiEdit" ]]; then
    FILE_PATH=$(echo "$EVENT_JSON" | jq -r '.tool_input.file_path')
    if [[ -n "$FILE_PATH" ]]; then
        # Check if this is creating a new file
        if [[ ! -f "$FILE_PATH" ]]; then
            DIR_PATH=$(dirname "$FILE_PATH")
            FILENAME=$(basename "$FILE_PATH")
            
            # Get existing files in the directory
            if [[ -d "$DIR_PATH" ]]; then
                # Get files and filter to only those with snake_case or camelCase patterns
                ALL_FILES=$(ls -1 "$DIR_PATH" 2>/dev/null | grep -E '\.(js|ts|py|rb|go|java|cpp|c|h|hpp|rs|swift|kt|scala|php|sh|bash|zsh)$' | head -20)
                EXISTING_FILES=""
                for file in $ALL_FILES; do
                    # Check if file contains underscore (potential snake_case), has mixed case (potential camelCase), or contains hyphen (potential kebab-case)
                    if [[ "$file" =~ _ ]] || [[ "$file" =~ [a-z][A-Z] ]] || [[ "$file" =~ [A-Z][a-z] ]] || [[ "$file" =~ - ]]; then
                        EXISTING_FILES+="$file"$'\n'
                    fi
                done
                EXISTING_FILES=$(echo -n "$EXISTING_FILES")
                debug_log "DIR_PATH exists, found existing files: '$EXISTING_FILES'"
                
                if [[ -n "$EXISTING_FILES" ]]; then
                    # Ask Gemini about the naming convention
                    # Convert newlines to spaces for better prompt handling
                    FILE_LIST=$(echo "$EXISTING_FILES" | tr '\n' ' ')
                    CONVENTION_PROMPT="Which naming convention is more common in these files: $FILE_LIST? Respond with exactly one of these: snake_case, camelCase, or kebab-case. No other text, no formatting, no punctuation."
                    CONVENTION=$(call_gemini "$CONVENTION_PROMPT")
                    
                    # Check if filename needs reformatting
                    REFORMAT_PROMPT="Is $FILENAME in $CONVENTION format? Respond with exactly one word in lowercase only: yes or no. No other text, no formatting, no punctuation."
                    FOLLOWS_CONVENTION=$(call_gemini_raw "$REFORMAT_PROMPT")
                    # Convert to lowercase for comparison
                    FOLLOWS_CONVENTION=$(echo "$FOLLOWS_CONVENTION" | tr '[:upper:]' '[:lower:]')
                    
                    if [[ "$FOLLOWS_CONVENTION" == "no" ]]; then
                        # Get the reformatted filename
                        REFORMAT_PROMPT="Convert $FILENAME to $CONVENTION format. Respond with only the converted filename, no other text, no formatting, no punctuation, no quotes."
                        NEW_FILENAME=$(call_gemini_raw "$REFORMAT_PROMPT")
                    else
                        NEW_FILENAME="$FILENAME"
                    fi
                    
                    if [[ "$NEW_FILENAME" != "$FILENAME" && -n "$NEW_FILENAME" ]]; then
                        NEW_PATH="$DIR_PATH/$NEW_FILENAME"
                        echo "❌ Inconsistent file naming detected!" >&2
                        echo "✅ Directory convention is $CONVENTION" >&2
                        echo "📝 Suggested filename: $NEW_FILENAME" >&2
                        echo "Run this command instead with: $NEW_PATH" >&2
                        exit 2
                    fi
                fi
            fi
        fi
    fi
    exit 0
fi

# For Bash commands, check if it will create a file
if [[ "$TOOL_NAME" == "Bash" ]]; then
    # Ask Gemini if this command will create a file
    CREATE_FILE_PROMPT="Will this bash command create a new file or write to a file that does not exist yet? Respond with exactly one word in lowercase only: yes or no. No other text, no formatting, no punctuation.

Command: $COMMAND"
    CREATES_FILE=$(call_gemini_raw "$CREATE_FILE_PROMPT")
    debug_log "CREATES_FILE raw response: '$CREATES_FILE'"
    # Convert to lowercase for comparison
    CREATES_FILE=$(echo "$CREATES_FILE" | tr '[:upper:]' '[:lower:]')
    debug_log "CREATES_FILE after lowercase: '$CREATES_FILE'"
    
    if [[ "$CREATES_FILE" == "yes" ]]; then
        debug_log "Gemini says command creates a file"
        # Extract the file path from the command
        EXTRACT_PROMPT="Extract the path of the new file that will be created by this command. Respond with only the file path, no other text, no formatting, no quotes:

Command: $COMMAND"
        FILE_PATH=$(call_gemini_raw "$EXTRACT_PROMPT")
        debug_log "FILE_PATH extracted: '$FILE_PATH'"
        debug_log "File exists check: ! -f '$FILE_PATH' = $(! test -f "$FILE_PATH" && echo "true" || echo "false")"
        
        if [[ -n "$FILE_PATH" && ! -f "$FILE_PATH" ]]; then
            DIR_PATH=$(dirname "$FILE_PATH")
            FILENAME=$(basename "$FILE_PATH")
            
            # Get existing files in the directory
            if [[ -d "$DIR_PATH" ]]; then
                # Get files and filter to only those with snake_case or camelCase patterns
                ALL_FILES=$(ls -1 "$DIR_PATH" 2>/dev/null | grep -E '\.(js|ts|py|rb|go|java|cpp|c|h|hpp|rs|swift|kt|scala|php|sh|bash|zsh)$' | head -20)
                EXISTING_FILES=""
                for file in $ALL_FILES; do
                    # Check if file contains underscore (potential snake_case), has mixed case (potential camelCase), or contains hyphen (potential kebab-case)
                    if [[ "$file" =~ _ ]] || [[ "$file" =~ [a-z][A-Z] ]] || [[ "$file" =~ [A-Z][a-z] ]] || [[ "$file" =~ - ]]; then
                        EXISTING_FILES+="$file"$'\n'
                    fi
                done
                EXISTING_FILES=$(echo -n "$EXISTING_FILES")
                debug_log "DIR_PATH exists, found existing files: '$EXISTING_FILES'"
                
                if [[ -n "$EXISTING_FILES" ]]; then
                    # Ask Gemini about the naming convention
                    # Convert newlines to spaces for better prompt handling
                    FILE_LIST=$(echo "$EXISTING_FILES" | tr '\n' ' ')
                    CONVENTION_PROMPT="Which naming convention is more common in these files: $FILE_LIST? Respond with exactly one of these: snake_case, camelCase, or kebab-case. No other text, no formatting, no punctuation."
                    CONVENTION=$(call_gemini "$CONVENTION_PROMPT")
                    
                    # Check if filename needs reformatting
                    REFORMAT_PROMPT="Is $FILENAME in $CONVENTION format? Respond with exactly one word in lowercase only: yes or no. No other text, no formatting, no punctuation."
                    FOLLOWS_CONVENTION=$(call_gemini_raw "$REFORMAT_PROMPT")
                    # Convert to lowercase for comparison
                    FOLLOWS_CONVENTION=$(echo "$FOLLOWS_CONVENTION" | tr '[:upper:]' '[:lower:]')
                    
                    if [[ "$FOLLOWS_CONVENTION" == "no" ]]; then
                        # Get the reformatted filename
                        REFORMAT_PROMPT="Convert $FILENAME to $CONVENTION format. Respond with only the converted filename, no other text, no formatting, no punctuation, no quotes."
                        NEW_FILENAME=$(call_gemini_raw "$REFORMAT_PROMPT")
                    else
                        NEW_FILENAME="$FILENAME"
                    fi
                    
                    if [[ "$NEW_FILENAME" != "$FILENAME" && -n "$NEW_FILENAME" ]]; then
                        # Reformat the command with new filename
                        REFORMAT_COMMAND_PROMPT="Reformat this bash command to use the filename '$NEW_FILENAME' instead of '$FILENAME'. Respond with only the complete reformatted command, no other text, no formatting, no explanation:

Command: $COMMAND"
                        NEW_COMMAND=$(call_gemini_raw "$REFORMAT_COMMAND_PROMPT")
                        
                        echo "❌ Inconsistent file naming detected!" >&2
                        echo "✅ Directory convention is $CONVENTION" >&2
                        echo "📝 Suggested filename: $NEW_FILENAME" >&2
                        echo "Run this command instead: $NEW_COMMAND" >&2
                        exit 2
                    fi
                else
                    debug_log "EXISTING_FILES is empty, no files to compare"
                fi
            else
                debug_log "DIR_PATH '$DIR_PATH' does not exist"
            fi
        else
            debug_log "FILE_PATH is empty or file already exists"
        fi
    else
        debug_log "CREATES_FILE is not 'yes', it's '$CREATES_FILE'"
    fi
fi

debug_log "Exiting with code 0"
exit 0