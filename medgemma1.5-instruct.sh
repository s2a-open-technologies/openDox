#!/bin/bash

llama-server -m model/medgemma-1.5-4b-it-Q8_0.gguf \
             -c 32768 \
             -t 2 \
             -ctk q8_0 \
             -ctv q8_0 \
             -fa on \
             -tb 4 \
             -fit on \
             --host 0.0.0.0 \
             --chat-template-kwargs '{"enable_thinking": false}' \
             --reasoning-budget 0
