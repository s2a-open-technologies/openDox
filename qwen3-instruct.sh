#!/bin/bash

llama-server -m model/Qwen3-4B-Instruct-2507-Q8_0.gguf -c 32768 -t 2 -ctk q8_0 -ctv q8_0 -fa on -tb 4 -fit on --host 0.0.0.0 --port 9000
