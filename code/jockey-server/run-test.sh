#!/bin/bash

## code/jockey-server/run.sh

echo """
-------------------------------------------------------
-------------------------------------------------------
--------        STARTING JOCKEY SERVER         --------
-------------------------------------------------------
-------------------------------------------------------
"""
sleep 5
	
# Start langgraph
log_info "Starting LangGraph server..."

langgraph up -c "$LANGGRAPH_JSON" -d "$COMPOSE_YAML" --recreate --verbose > >(tee -a "$LOG_FILE") 2>&1 &

