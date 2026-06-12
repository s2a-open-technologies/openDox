#!/bin/bash

llama-server --models-dir model/ -c 32768 -t 2 -ctk q8_0 -ctv q8_0 -fa on -tb 4 -fit on --host 0.0.0.0

