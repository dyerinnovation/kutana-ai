#!/bin/bash
# Run the pipeline test on the DGX
ssh dgx "cd ~/kutana-ai && python3 examples/test-pipeline.py"
